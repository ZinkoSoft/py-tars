"""MQTT integration for config manager service."""

from __future__ import annotations

import logging
from typing import Optional

import orjson

from tars.adapters.mqtt_client import MQTTClient
from tars.config.crypto import sign_message_async
from tars.config.mqtt_models import ConfigHealthPayload, ConfigUpdatePayload

from .config import ConfigManagerConfig

logger = logging.getLogger(__name__)


class MQTTPublisher:
    """Publishes configuration updates and health status via MQTT.

    All configuration update messages are signed with Ed25519 to ensure
    authenticity. Clients verify signatures before applying updates.
    
    Uses the centralized tars-core MQTTClient for connection management.
    """

    def __init__(self, config: ConfigManagerConfig):
        """Initialize MQTT publisher.

        Args:
            config: Service configuration
        """
        self.config = config
        self.client: Optional[MQTTClient] = None

    async def connect(self) -> None:
        """Connect to MQTT broker with health monitoring."""
        logger.info(f"Connecting to MQTT broker: {self.config.mqtt_url}")

        try:
            # Create MQTTClient with health and heartbeat enabled
            self.client = MQTTClient(
                mqtt_url=self.config.mqtt_url,
                client_id="config-manager",
                enable_health=True,
                enable_heartbeat=True,
                heartbeat_interval=10.0,
            )

            await self.client.connect()
            logger.info("Connected to MQTT broker")

        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}", exc_info=True)
            raise

    async def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        if self.client:
            try:
                await self.client.shutdown()
                logger.info("Disconnected from MQTT broker")
            except Exception as e:
                logger.error(f"Error disconnecting from MQTT: {e}", exc_info=True)
            finally:
                self.client = None

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
        if not self.client or not self.client.connected:
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

        # Publish using raw MQTT client (not envelope-wrapped)
        topic = self.config.mqtt_config_update_topic
        message = orjson.dumps(payload_with_sig)

        try:
            # Access underlying asyncio-mqtt client for raw publish
            assert self.client.client is not None
            await self.client.client.publish(topic, message, qos=1, retain=False)
            logger.info(f"Published config update for {service} (v{version})")
        except Exception as e:
            logger.error(f"Failed to publish config update: {e}", exc_info=True)
            raise RuntimeError(f"MQTT publish failed: {e}") from e

    async def publish_health(
        self, ok: bool, event: Optional[str] = None, error: Optional[str] = None
    ) -> None:
        """Publish health status using MQTTClient's built-in health publishing.

        Args:
            ok: Whether service is healthy
            event: Optional event description
            error: Optional error message
        """
        if not self.client or not self.client.connected:
            logger.warning("Cannot publish health status - MQTT not connected")
            return

        try:
            # Use MQTTClient's publish_health method
            await self.client.publish_health(ok=ok, event=event, err=error)
            logger.debug(f"Published health status: ok={ok}")
        except Exception as e:
            logger.error(f"Failed to publish health status: {e}", exc_info=True)

    @property
    def is_connected(self) -> bool:
        """Check if MQTT client is connected."""
        return self.client is not None and self.client.connected
