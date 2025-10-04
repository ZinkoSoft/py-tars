"""MQTT client wrapper for MCP Bridge."""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import orjson
import asyncio_mqtt
from pydantic import ValidationError

from tars.contracts.v1.health import HealthPing  # type: ignore[import]

if TYPE_CHECKING:
    from asyncio_mqtt import Client as Mqtt

logger = logging.getLogger("mcp-bridge.mqtt")

# MQTT Topics
TOPIC_TOOL_REGISTRY = "llm/tools/registry"
TOPIC_HEALTH_MCP_BRIDGE = "system/health/mcp-bridge"
TOPIC_HEALTH_LLM = "system/health/llm"


class MCPBridgeMQTTClient:
    """MQTT client for publishing tool registry and health status."""
    
    def __init__(self):
        """Initialize MQTT client with configuration from environment."""
        self.host = os.getenv("MQTT_HOST", "127.0.0.1")
        self.port = int(os.getenv("MQTT_PORT", "1883"))
        self.user = os.getenv("MQTT_USER")
        self.password = os.getenv("MQTT_PASS")
        
    async def connect(self):
        """Create and return connected MQTT client context manager."""
        return asyncio_mqtt.Client(
            hostname=self.host,
            port=self.port,
            username=self.user,
            password=self.password
        )
    
    @staticmethod
    async def publish_tool_registry(client: Mqtt, tools: list[dict]) -> None:
        """Publish tool registry to MQTT.
        
        Args:
            client: Connected MQTT client
            tools: List of tool function definitions
        """
        registry_payload = orjson.dumps({"tools": tools})
        logger.info(
            "Publishing %d tools to registry (payload size: %d bytes, retained=True)",
            len(tools),
            len(registry_payload)
        )
        
        await client.publish(
            TOPIC_TOOL_REGISTRY,
            registry_payload,
            qos=1,
            retain=True
        )
        
        logger.info("✅ Published %d tools to %s (retained)", len(tools), TOPIC_TOOL_REGISTRY)
    
    @staticmethod
    async def publish_health(
        client: Mqtt,
        event: str = "ready",
        ok: bool = True,
        err: str | None = None
    ) -> None:
        """Publish health status to MQTT using HealthPing model.
        
        Args:
            client: Connected MQTT client
            event: Event type (ready, heartbeat, error, etc.)
            ok: Health status boolean
            err: Optional error message
        """
        health = HealthPing(ok=ok, event=event, err=err)
        payload = health.model_dump_json().encode()
        
        await client.publish(
            TOPIC_HEALTH_MCP_BRIDGE,
            payload,
            retain=True
        )
        
        if ok:
            logger.debug("Health published: %s", event)
        else:
            logger.warning("Health error published: %s (err=%s)", event, err)
    
    @staticmethod
    async def subscribe_llm_health(client: Mqtt) -> None:
        """Subscribe to LLM worker health status.
        
        Args:
            client: Connected MQTT client
        """
        await client.subscribe(TOPIC_HEALTH_LLM)
        logger.info("📡 Subscribed to %s", TOPIC_HEALTH_LLM)
    
    @staticmethod
    def is_llm_ready_event(payload: bytes) -> bool:
        """Check if payload indicates LLM worker is ready.
        
        Args:
            payload: MQTT message payload
            
        Returns:
            True if LLM worker sent a ready/restart event
        """
        try:
            health = HealthPing.model_validate_json(payload)
            
            # Look for ready or restart events with ok=True
            if health.ok and health.event in ("ready", "restart", "startup", "initialized"):
                logger.info("🔄 LLM worker ready event detected: %s", health.event)
                return True
            return False
        except (ValidationError, Exception) as e:
            logger.debug("Failed to parse LLM health payload: %s", e)
            return False
