"""MQTT client wrapper for LLM worker with subscription management and publishing."""

from __future__ import annotations

import logging
from typing import Any, Optional, AsyncIterator
from urllib.parse import urlparse

import asyncio_mqtt as mqtt
import orjson as json

from tars.contracts.envelope import Envelope  # type: ignore[import]

logger = logging.getLogger("llm-worker.mqtt")


def parse_mqtt_url(url: str) -> tuple[str, int, Optional[str], Optional[str]]:
    """Parse MQTT URL into connection components."""
    u = urlparse(url)
    return (u.hostname or "127.0.0.1", u.port or 1883, u.username, u.password)


class MQTTClient:
    """Wrapper for MQTT client with LLM-specific functionality."""

    def __init__(self, mqtt_url: str, client_id: str = "tars-llm", source_name: str = "llm-worker"):
        self.mqtt_url = mqtt_url
        self.client_id = client_id
        self.source_name = source_name
        self._client: Optional[mqtt.Client] = None

    async def connect(self) -> mqtt.Client:
        """Connect to MQTT broker and return client."""
        host, port, user, pwd = parse_mqtt_url(self.mqtt_url)
        logger.info("Connecting to MQTT %s:%s", host, port)
        self._client = mqtt.Client(
            hostname=host, port=port, username=user, password=pwd, client_id=self.client_id
        )
        return self._client

    async def publish_health(
        self, client: mqtt.Client, topic: str, ok: bool = True, event: str = "ready"
    ) -> None:
        """Publish health status to MQTT."""
        payload = json.dumps({"ok": ok, "event": event})
        await client.publish(topic, payload, retain=True)
        logger.debug("Published health: ok=%s event=%s", ok, event)

    async def publish_event(
        self,
        client: mqtt.Client,
        *,
        event_type: str,
        topic: str,
        payload: Any,
        correlate: Optional[str] = None,
        qos: int = 1,
        retain: bool = False,
    ) -> None:
        """Publish an event wrapped in Envelope to MQTT."""
        envelope = Envelope.new(
            event_type=event_type, data=payload, correlate=correlate, source=self.source_name
        )
        await client.publish(topic, envelope.model_dump_json().encode(), qos=qos, retain=retain)
        logger.debug("Published event: type=%s topic=%s", event_type, topic)

    async def subscribe_all(
        self,
        client: mqtt.Client,
        *,
        llm_request_topic: str,
        character_current_topic: str,
        character_result_topic: str,
        character_get_topic: str,
        rag_enabled: bool = False,
        memory_results_topic: Optional[str] = None,
        tool_calling_enabled: bool = False,
        tools_registry_topic: Optional[str] = None,
        tools_result_topic: Optional[str] = None,
    ) -> None:
        """Subscribe to all required MQTT topics for LLM worker."""
        # Core subscriptions
        await client.subscribe(llm_request_topic)
        await client.subscribe(character_current_topic)
        await client.subscribe(character_result_topic)

        logger.info(
            "Subscribed to %s, %s and %s",
            llm_request_topic,
            character_current_topic,
            character_result_topic,
        )

        # Optional RAG subscription
        if rag_enabled and memory_results_topic:
            await client.subscribe(memory_results_topic, qos=1)
            logger.info("Subscribed to %s for RAG queries (QoS 1)", memory_results_topic)

        # Optional tool calling subscriptions
        if tool_calling_enabled:
            if tools_registry_topic:
                await client.subscribe(tools_registry_topic)
                logger.info("Subscribed to tool registry: %s", tools_registry_topic)
            if tools_result_topic:
                await client.subscribe(tools_result_topic)
                logger.info("Subscribed to tool results: %s", tools_result_topic)

        # Request initial character state
        try:
            await client.publish(character_get_topic, json.dumps({"section": None}))
            logger.info("Requested character/get on startup")
        except Exception:
            logger.debug("character/get publish failed (may be offline)")

    async def publish_tool_call(
        self, client: mqtt.Client, call_id: str, tool_name: str, arguments: dict
    ) -> None:
        """Publish tool call request to mcp-bridge.

        Args:
            client: MQTT client
            call_id: Unique call ID for correlation
            tool_name: Tool name (format: mcp__server-name__tool-name)
            arguments: Tool arguments dict
        """
        payload = {"call_id": call_id, "tool_name": tool_name, "arguments": arguments}
        from .config import TOPIC_TOOL_CALL_REQUEST

        await client.publish(TOPIC_TOOL_CALL_REQUEST, json.dumps(payload), qos=1, retain=False)
        logger.info(
            "Published tool call to %s: %s (call_id=%s)",
            TOPIC_TOOL_CALL_REQUEST,
            tool_name,
            call_id,
        )

    async def message_stream(self, client: mqtt.Client) -> AsyncIterator:
        """Get async iterator for MQTT messages."""
        async with client.messages() as messages:
            async for message in messages:
                yield message
