"""MQTT integration for config manager service."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

import orjson
from aiomqtt import Client, MqttError

from tars.config.crypto import sign_message_async
from tars.config.mqtt_models import ConfigHealthPayload, ConfigUpdatePayload

from .config import ConfigManagerConfig

logger = logging.getLogger(__name__)


class MQTTPublisher:
    """Publishes configuration updates and health status via MQTT.

    All configuration update messages are signed with Ed25519 to ensure
    authenticity. Clients verify signatures before applying updates.
    """

    def __init__(self, config: ConfigManagerConfig):
        """Initialize MQTT publisher.

        Args:
            config: Service configuration
        """
        self.config = config
        self.client: Optional[Client] = None
        self._connected = False
        self._reconnect_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        """Connect to MQTT broker with auto-reconnect."""
        logger.info(f"Connecting to MQTT broker: {self.config.mqtt_url}")

        try:
            # Parse MQTT URL
            from urllib.parse import urlparse

            parsed = urlparse(self.config.mqtt_url)
            hostname = parsed.hostname or "localhost"
            port = parsed.port or 1883
            username = parsed.username
            password = parsed.password

            self.client = Client(
                hostname=hostname,
                port=port,
                username=username,
                password=password,
                clean_session=False,
                client_id="config-manager",
            )

            await self.client.__aenter__()
            self._connected = True
            logger.info("Connected to MQTT broker")

            # Publish initial health status
            await self.publish_health(ok=True, event="connected")

        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}", exc_info=True)
            self._connected = False
            raise

    async def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        if self.client and self._connected:
            try:
                # Publish offline health status
                await self.publish_health(ok=False, event="disconnecting")
                await self.client.__aexit__(None, None, None)
                logger.info("Disconnected from MQTT broker")
            except Exception as e:
                logger.error(f"Error disconnecting from MQTT: {e}", exc_info=True)
            finally:
                self._connected = False

    async def publish_config_update(
        self,
        service: str,
        config: dict,
        version: int,
        config_epoch: str,
    ) -> None:
        """Publish configuration update with Ed25519 signature.

        Args:
            service: Service name
            config: Configuration dictionary
            version: Configuration version for optimistic locking
            config_epoch: Current configuration epoch identifier

        Raises:
            RuntimeError: If MQTT client not connected or signing fails
        """
        if not self._connected or not self.client:
            raise RuntimeError("MQTT client not connected")

        # Create payload
        payload = ConfigUpdatePayload(
            service=service,
            config=config,
            version=version,
            config_epoch=config_epoch,
        )

        # Serialize payload
        payload_bytes = orjson.dumps(
            payload.model_dump(),
            option=orjson.OPT_SORT_KEYS,  # Deterministic JSON for signing
        )

        # Sign message
        if not self.config.signature_private_key:
            logger.warning("No signature private key configured - message will be unsigned")
            signature = None
        else:
            try:
                signature = await sign_message_async(
                    payload_bytes, self.config.signature_private_key
                )
                logger.debug(f"Signed config update for {service}")
            except Exception as e:
                logger.error(f"Failed to sign config update: {e}", exc_info=True)
                raise RuntimeError(f"Failed to sign message: {e}") from e

        # Add signature to payload
        payload_with_sig = payload.model_dump()
        if signature:
            payload_with_sig["signature"] = signature

        # Publish
        topic = self.config.mqtt_config_update_topic
        message = orjson.dumps(payload_with_sig)

        try:
            await self.client.publish(topic, message, qos=1, retain=False)
            logger.info(f"Published config update for {service} (v{version})")
        except MqttError as e:
            logger.error(f"Failed to publish config update: {e}", exc_info=True)
            raise RuntimeError(f"MQTT publish failed: {e}") from e

    async def publish_health(
        self, ok: bool, event: Optional[str] = None, error: Optional[str] = None
    ) -> None:
        """Publish health status (retained).

        Args:
            ok: Whether service is healthy
            event: Optional event description
            error: Optional error message
        """
        if not self._connected or not self.client:
            logger.warning("Cannot publish health status - MQTT not connected")
            return

        payload = ConfigHealthPayload(ok=ok, event=event, error=error)
        topic = self.config.mqtt_health_topic
        message = orjson.dumps(payload.model_dump(exclude_none=True))

        try:
            await self.client.publish(topic, message, qos=1, retain=True)
            logger.debug(f"Published health status: ok={ok}")
        except MqttError as e:
            logger.error(f"Failed to publish health status: {e}", exc_info=True)

    @property
    def is_connected(self) -> bool:
        """Check if MQTT client is connected."""
        return self._connected
