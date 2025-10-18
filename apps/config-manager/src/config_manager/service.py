"""Config Manager Service - Core business logic."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from tars.config.cache import LKGCacheManager
from tars.config.database import ConfigDatabase

from .config import ConfigManagerConfig
from .mqtt import MQTTPublisher

logger = logging.getLogger(__name__)


class ConfigManagerService:
    """Core service for centralized configuration management.

    Responsibilities:
    - Initialize and maintain configuration database
    - Manage last-known-good cache
    - Provide configuration CRUD operations
    - Publish configuration updates via MQTT
    - Monitor health and report status
    """

    def __init__(self, config: ConfigManagerConfig):
        """Initialize config manager service.

        Args:
            config: Service configuration
        """
        self.config = config
        self.database: Optional[ConfigDatabase] = None
        self.cache_manager: Optional[LKGCacheManager] = None
        self.mqtt_publisher: Optional[MQTTPublisher] = None
        self._healthy = False
        self._shutdown_event = asyncio.Event()

    async def initialize(self) -> None:
        """Initialize database and cache manager.

        Raises:
            RuntimeError: If initialization fails
        """
        logger.info("Initializing config manager service")

        try:
            # Initialize database
            logger.info(f"Opening database: {self.config.db_path}")
            self.database = ConfigDatabase(str(self.config.db_path))
            await self.database.connect()
            await self.database.initialize_schema()

            # Initialize cache manager
            logger.info(f"Initializing LKG cache: {self.config.lkg_cache_path}")
            self.cache_manager = LKGCacheManager(
                cache_path=str(self.config.lkg_cache_path),
                hmac_key_base64=self.config.hmac_key_base64,
            )

            # Sync cache with database
            logger.info("Syncing LKG cache with database")
            # Get all services from database
            services = await self.database.list_services()
            service_configs = {}
            config_epoch = None
            
            for service_name in services:
                config_data = await self.database.get_service_config(service_name)
                if config_data:
                    service_configs[service_name] = config_data.config
                    # Get epoch from first service (all have same epoch)
                    if config_epoch is None:
                        config_epoch = config_data.config_epoch
            
            # If no services exist yet, create initial epoch
            if config_epoch is None:
                config_epoch = await self.database.create_epoch()
                logger.info(f"Created initial config epoch: {config_epoch}")
            
            # Update cache (even if empty, to create the cache file)
            await self.cache_manager.atomic_update_from_db(
                service_configs, config_epoch
            )
            if service_configs:
                logger.info(f"LKG cache synced with {len(service_configs)} services")
            else:
                logger.info("LKG cache initialized with empty configuration")

            # Initialize MQTT publisher
            logger.info("Connecting to MQTT broker")
            self.mqtt_publisher = MQTTPublisher(self.config)
            await self.mqtt_publisher.connect()

            self._healthy = True
            logger.info("Config manager service initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize config manager: {e}", exc_info=True)
            self._healthy = False
            raise RuntimeError(f"Config manager initialization failed: {e}") from e

    async def health_check(self) -> dict[str, any]:
        """Perform health check.

        Returns:
            Health status dictionary with ok, database_available, cache_available
        """
        db_available = False
        cache_available = False

        if self.database:
            try:
                # Simple database query to verify connectivity
                await self.database.list_services()
                db_available = True
            except Exception as e:
                logger.warning(f"Database health check failed: {e}")

        if self.cache_manager:
            try:
                # Verify cache file is readable
                cache_available = self.config.lkg_cache_path.exists()
            except Exception as e:
                logger.warning(f"Cache health check failed: {e}")

        self._healthy = db_available and cache_available

        return {
            "ok": self._healthy,
            "database_available": db_available,
            "cache_available": cache_available,
            "db_path": str(self.config.db_path),
            "cache_path": str(self.config.lkg_cache_path),
        }

    async def shutdown(self) -> None:
        """Gracefully shutdown the service."""
        logger.info("Shutting down config manager service")
        self._shutdown_event.set()

        # Disconnect MQTT
        if self.mqtt_publisher:
            try:
                await self.mqtt_publisher.disconnect()
                logger.info("MQTT disconnected")
            except Exception as e:
                logger.error(f"Error disconnecting MQTT: {e}", exc_info=True)

        # Close database connection
        if self.database:
            try:
                await self.database.close()
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database: {e}", exc_info=True)

        self._healthy = False
        logger.info("Config manager service shutdown complete")

    @property
    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self._healthy

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()
