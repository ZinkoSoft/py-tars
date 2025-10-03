"""MQTT client for memory worker - handles all message broker communication."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import asyncio_mqtt as mqtt

from tars.contracts.envelope import Envelope


logger = logging.getLogger("memory-worker.mqtt")


def parse_mqtt_url(url: str) -> tuple[str, int, str | None, str | None]:
    """Parse MQTT URL into connection parameters.
    
    Args:
        url: MQTT URL in format mqtt://user:pass@host:port
        
    Returns:
        Tuple of (host, port, username, password)
    """
    parsed = urlparse(url)
    return (
        parsed.hostname or "127.0.0.1",
        parsed.port or 1883,
        parsed.username,
        parsed.password,
    )


class MemoryMQTTClient:
    """MQTT client wrapper for memory worker.
    
    Handles connection management, topic subscriptions, and message publishing
    with proper envelope wrapping and correlation IDs.
    """

    def __init__(
        self,
        mqtt_url: str,
        *,
        client_id: str = "tars-memory",
        source_name: str = "memory-worker",
    ):
        """Initialize MQTT client.
        
        Args:
            mqtt_url: MQTT broker URL (mqtt://user:pass@host:port)
            client_id: MQTT client identifier
            source_name: Source identifier for envelope metadata
        """
        self.mqtt_url = mqtt_url
        self.client_id = client_id
        self.source_name = source_name
        self._client: mqtt.Client | None = None

    async def connect(self) -> mqtt.Client:
        """Connect to MQTT broker and return client instance.
        
        Returns:
            Connected MQTT client
            
        Raises:
            Exception: If connection fails
        """
        host, port, user, password = parse_mqtt_url(self.mqtt_url)
        logger.info("Connecting to MQTT %s:%s as %s", host, port, self.client_id)
        
        self._client = mqtt.Client(
            hostname=host,
            port=port,
            username=user,
            password=password,
            client_id=self.client_id,
        )
        
        logger.info("Connected to MQTT %s:%s", host, port)
        return self._client

    async def subscribe(self, client: mqtt.Client, topics: list[str]) -> None:
        """Subscribe to multiple topics.
        
        Args:
            client: Connected MQTT client
            topics: List of topic strings to subscribe to
        """
        for topic in topics:
            await client.subscribe(topic)
            logger.info("Subscribed to %s", topic)

    async def publish_event(
        self,
        client: mqtt.Client,
        *,
        event_type: str,
        topic: str,
        payload: Any,
        correlate: str | None = None,
        qos: int = 0,
        retain: bool = False,
    ) -> None:
        """Publish event wrapped in Envelope to MQTT topic.
        
        Args:
            client: Connected MQTT client
            event_type: Event type identifier for registry
            topic: MQTT topic to publish to
            payload: Pydantic model or dict payload (will be serialized)
            correlate: Optional correlation ID for request-response patterns
            qos: MQTT QoS level (0, 1, or 2)
            retain: Whether to retain message on broker
        """
        envelope = Envelope.new(
            event_type=event_type,
            data=payload,
            correlate=correlate,
            source=self.source_name,
        )
        
        message = envelope.model_dump_json().encode()
        await client.publish(topic, message, qos=qos, retain=retain)
        
        logger.debug(
            "Published event type=%s topic=%s qos=%d retain=%s correlate=%s",
            event_type,
            topic,
            qos,
            retain,
            correlate,
        )
