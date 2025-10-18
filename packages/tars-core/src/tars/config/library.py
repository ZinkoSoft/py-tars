"""Public configuration library API for TARS services.

This module provides the main ConfigLibrary class that services use to:
- Load configuration at startup
- Subscribe to runtime configuration updates via MQTT
- Automatically fall back to LKG cache on database failure
- Verify MQTT message signatures
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, TypeVar

import orjson
from asyncio_mqtt import Client as MQTTClient
from pydantic import BaseModel

from tars.config.cache import LKGCacheManager
from tars.config.crypto import verify_signature_async
from tars.config.database import ConfigDatabase
from tars.config.mqtt_models import ConfigUpdatePayload
from tars.config.precedence import ConfigResolver
from tars.config.types import ConfigSource

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)

# Type alias for config update callback
ConfigUpdateCallback = Callable[[BaseModel], None]


class ConfigLibrary:
    """Main configuration library for TARS services.

    Example:
        >>> from tars.config.library import ConfigLibrary
        >>> from tars.config.models import STTWorkerConfig
        >>>
        >>> config_lib = ConfigLibrary(service_name="stt-worker")
        >>> await config_lib.initialize()
        >>>
        >>> # Load configuration
        >>> config = await config_lib.get_config(STTWorkerConfig)
        >>> print(config.whisper_model)
        >>>
        >>> # Subscribe to updates
        >>> async def on_update(new_config: STTWorkerConfig):
        ...     print(f"Config updated: {new_config}")
        >>>
        >>> await config_lib.subscribe_updates(on_update, STTWorkerConfig)
    """

    def __init__(
        self,
        service_name: str,
        db_path: str | Path | None = None,
        cache_path: str | Path | None = None,
        mqtt_url: str | None = None,
        signature_public_key: str | None = None,
        hmac_key_base64: str | None = None,
    ):
        """Initialize configuration library.

        Args:
            service_name: Name of the service using this library
            db_path: Path to config database (default: from CONFIG_DB_PATH env)
            cache_path: Path to LKG cache (default: from CONFIG_LKG_CACHE_PATH env)
            mqtt_url: MQTT broker URL (default: from MQTT_URL env)
            signature_public_key: Ed25519 public key for signature verification
            hmac_key_base64: HMAC key for cache verification
        """
        import os

        self.service_name = service_name
        self.db_path = Path(db_path or os.getenv("CONFIG_DB_PATH", "/data/config/config.db"))
        self.cache_path = Path(
            cache_path or os.getenv("CONFIG_LKG_CACHE_PATH", "/data/config/config.lkg.json")
        )
        self.mqtt_url = mqtt_url or os.getenv("MQTT_URL", "mqtt://localhost:1883")
        self.signature_public_key = signature_public_key or os.getenv(
            "CONFIG_SIGNATURE_PUBLIC_KEY", ""
        )
        self.hmac_key_base64 = hmac_key_base64 or os.getenv("LKG_HMAC_KEY_BASE64", "")

        self._db: ConfigDatabase | None = None
        self._cache_manager: LKGCacheManager | None = None
        self._resolver = ConfigResolver()
        self._mqtt_client: MQTTClient | None = None
        self._update_callbacks: dict[type[BaseModel], ConfigUpdateCallback] = {}
        self._read_only_mode = False
        self._mqtt_task: asyncio.Task[None] | None = None

    async def initialize(self) -> None:
        """Initialize database and cache connections.

        This must be called before using get_config or subscribe_updates.
        """
        # Initialize database
        try:
            self._db = ConfigDatabase(self.db_path)
            await self._db.connect()
            await self._db.initialize_schema()
            self._read_only_mode = False
            logger.info(f"[{self.service_name}] Connected to config database")
        except Exception as e:
            logger.warning(
                f"[{self.service_name}] Database unavailable, entering read-only fallback mode: {e}"
            )
            self._read_only_mode = True

        # Initialize cache manager
        if self.hmac_key_base64:
            self._cache_manager = LKGCacheManager(self.cache_path, self.hmac_key_base64)
            cache_valid = await self._cache_manager.verify_lkg_signature()
            logger.info(
                f"[{self.service_name}] LKG cache {'valid' if cache_valid else 'invalid or missing'}"
            )
        else:
            logger.warning(f"[{self.service_name}] No HMAC key provided, LKG cache disabled")

    async def get_config(self, config_model: type[T]) -> T:
        """Get configuration with automatic fallback.

        Resolution order:
        1. Try database (if available)
        2. Fall back to LKG cache (if database unavailable)
        3. Use defaults from Pydantic model

        Args:
            config_model: Pydantic model class for configuration

        Returns:
            Resolved configuration instance

        Raises:
            RuntimeError: If library not initialized
            ValueError: If configuration cannot be loaded from any source
        """
        if self._db is None and self._cache_manager is None:
            raise RuntimeError("ConfigLibrary not initialized. Call initialize() first.")

        db_config: dict[str, Any] | None = None

        # Try database first
        if not self._read_only_mode and self._db:
            try:
                service_config = await self._db.get_service_config(self.service_name)
                if service_config:
                    db_config = service_config.config
                    logger.debug(
                        f"[{self.service_name}] Loaded config from database (version {service_config.version})"
                    )
            except Exception as e:
                logger.warning(f"[{self.service_name}] Database read failed: {e}")
                self._read_only_mode = True

        # Fall back to LKG cache if needed
        if self._read_only_mode and self._cache_manager:
            cached_config = await self._cache_manager.get_cached_config(self.service_name)
            if cached_config:
                db_config = cached_config
                logger.info(f"[{self.service_name}] Using LKG cache (read-only fallback mode)")

        # Resolve configuration with precedence
        config = self._resolver.resolve_config(config_model, db_config)
        return config

    async def subscribe_updates(
        self,
        callback: ConfigUpdateCallback,
        config_model: type[T],
    ) -> None:
        """Subscribe to runtime configuration updates via MQTT.

        Args:
            callback: Function to call when configuration updates
            config_model: Pydantic model class for configuration

        Note:
            Updates are only received if MQTT is configured and signature verification
            passes. Invalid signatures are logged and ignored.
        """
        if not self.signature_public_key:
            logger.warning(
                f"[{self.service_name}] No signature public key, MQTT updates disabled"
            )
            return

        # Store callback for this config type
        self._update_callbacks[config_model] = callback

        # Start MQTT subscription task if not already running
        if self._mqtt_task is None:
            self._mqtt_task = asyncio.create_task(self._mqtt_subscription_loop())

    async def _mqtt_subscription_loop(self) -> None:
        """Persistent MQTT subscription for configuration updates."""
        topic = f"system/config/{self.service_name}"

        while True:
            try:
                # Connect to MQTT broker
                async with MQTTClient(self.mqtt_url) as client:
                    await client.subscribe(topic, qos=1)
                    logger.info(f"[{self.service_name}] Subscribed to {topic}")

                    # Process messages
                    async with client.messages() as messages:
                        async for msg in messages:
                            if msg.topic.matches(topic):
                                await self._handle_config_update(msg.payload)

            except Exception as e:
                logger.error(f"[{self.service_name}] MQTT subscription error: {e}")
                await asyncio.sleep(5)  # Retry after 5 seconds

    async def _handle_config_update(self, payload: bytes) -> None:
        """Handle incoming configuration update message.

        Args:
            payload: MQTT message payload
        """
        try:
            # Parse payload
            data = orjson.loads(payload)
            update = ConfigUpdatePayload.model_validate(data)

            # Verify signature
            if not await self._verify_config_signature(update):
                logger.error(
                    f"[{self.service_name}] Invalid signature on config update, ignoring"
                )
                return

            # Verify checksum
            config_json = orjson.dumps(update.config, option=orjson.OPT_SORT_KEYS)
            actual_checksum = hashlib.sha256(config_json).hexdigest()
            if actual_checksum != update.checksum:
                logger.error(f"[{self.service_name}] Checksum mismatch, ignoring update")
                return

            # Call registered callbacks
            for config_model, callback in self._update_callbacks.items():
                try:
                    # Resolve new configuration
                    new_config = self._resolver.resolve_config(config_model, update.config)
                    # Call callback
                    if asyncio.iscoroutinefunction(callback):
                        await callback(new_config)
                    else:
                        callback(new_config)
                    logger.info(
                        f"[{self.service_name}] Config updated to version {update.version}"
                    )
                except Exception as e:
                    logger.error(f"[{self.service_name}] Config update callback failed: {e}")

        except Exception as e:
            logger.error(f"[{self.service_name}] Failed to process config update: {e}")

    async def _verify_config_signature(self, update: ConfigUpdatePayload) -> bool:
        """Verify Ed25519 signature on configuration update.

        Args:
            update: Configuration update payload

        Returns:
            True if signature is valid
        """
        if not self.signature_public_key:
            return False

        # Construct signed message (version|service|config|checksum|epoch|issued_at)
        message_parts = [
            str(update.version),
            update.service,
            orjson.dumps(update.config, option=orjson.OPT_SORT_KEYS).decode(),
            update.checksum,
            update.config_epoch,
            update.issued_at.isoformat(),
        ]
        message = "|".join(message_parts).encode()

        # Verify signature
        return await verify_signature_async(
            message, update.signature, self.signature_public_key
        )

    async def close(self) -> None:
        """Close database and MQTT connections."""
        if self._mqtt_task:
            self._mqtt_task.cancel()
            try:
                await self._mqtt_task
            except asyncio.CancelledError:
                pass

        if self._db:
            await self._db.close()

        logger.info(f"[{self.service_name}] ConfigLibrary closed")

    @property
    def is_read_only(self) -> bool:
        """Check if library is in read-only fallback mode."""
        return self._read_only_mode

    @property
    def database_available(self) -> bool:
        """Check if database is available."""
        return not self._read_only_mode and self._db is not None
