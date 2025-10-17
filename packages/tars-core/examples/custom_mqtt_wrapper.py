"""Extension examples demonstrating composition patterns for MQTTClient.

This module shows three approaches to extending MQTTClient for service-specific needs:

1. **Composition Wrapper**: Wrap MQTTClient with additional domain logic
2. **Message Batching**: Aggregate messages before publishing to reduce overhead
3. **Direct Client Access**: Use .client property for advanced asyncio-mqtt features

All patterns avoid modifying the core mqtt_client.py, enabling clean separation
of concerns and independent testing.

Usage:
    # Run this example (requires Mosquitto at mqtt://localhost:1883)
    python -m examples.custom_mqtt_wrapper
"""

import asyncio
import time
from typing import Any, Callable, Optional
from collections import defaultdict

import orjson

from tars.adapters.mqtt_client import MQTTClient


# === Pattern 1: Composition Wrapper for Domain Logic ===


class DomainMQTTClient:
    """Wraps MQTTClient with domain-specific convenience methods.
    
    This pattern is useful when a service needs domain-specific
    publishing methods (e.g., publish_stt_final, publish_llm_response)
    without polluting the core MQTTClient with every service's vocabulary.
    
    Example:
        client = DomainMQTTClient("mqtt://localhost:1883", "stt-worker")
        await client.connect()
        
        # Domain-specific method instead of generic publish_event()
        await client.publish_stt_final(text="hello world", confidence=0.95)
    """
    
    def __init__(self, mqtt_url: str, client_id: str, **kwargs):
        """Initialize domain client wrapping MQTTClient.
        
        Args:
            mqtt_url: MQTT broker URL
            client_id: Unique client identifier
            **kwargs: Additional MQTTClient config (enable_health, etc.)
        """
        self._client = MQTTClient(mqtt_url, client_id, **kwargs)
    
    async def connect(self) -> None:
        """Connect to broker (delegates to wrapped client)."""
        await self._client.connect()
    
    async def shutdown(self) -> None:
        """Shutdown gracefully (delegates to wrapped client)."""
        await self._client.shutdown()
    
    # Domain-specific publishing methods
    
    async def publish_stt_final(
        self,
        text: str,
        confidence: float,
        lang: str = "en",
    ) -> None:
        """Publish STT final transcription result.
        
        Encapsulates the event_type and topic conventions for STT service.
        
        Args:
            text: Transcribed text
            confidence: Recognition confidence (0.0-1.0)
            lang: Language code
        """
        await self._client.publish_event(
            topic="stt/final",
            event_type="stt.final",
            data={
                "text": text,
                "confidence": confidence,
                "lang": lang,
                "is_final": True,
            },
            qos=1,
        )
    
    async def publish_llm_response(
        self,
        request_id: str,
        reply: str,
        model: str,
        tokens: Optional[int] = None,
    ) -> None:
        """Publish LLM response.
        
        Args:
            request_id: Correlation ID from request
            reply: Generated text response
            model: Model identifier
            tokens: Token count (optional)
        """
        data = {
            "reply": reply,
            "model": model,
        }
        if tokens is not None:
            data["tokens"] = tokens
        
        await self._client.publish_event(
            topic="llm/response",
            event_type="llm.response",
            data=data,
            correlation_id=request_id,
            qos=1,
        )


# === Pattern 2: Message Batching Extension ===


class BatchingMQTTClient:
    """Extends MQTTClient with message batching to reduce publishing overhead.
    
    Accumulates messages in a buffer and flushes them in batches, useful for
    high-frequency events (e.g., audio stream chunks, sensor readings).
    
    Example:
        client = BatchingMQTTClient(
            "mqtt://localhost:1883",
            "sensor-service",
            batch_size=10,
            batch_interval=1.0,
        )
        await client.connect()
        
        # Messages are buffered until batch_size or batch_interval
        for i in range(100):
            await client.publish_batched("sensor/readings", {"value": i})
    """
    
    def __init__(
        self,
        mqtt_url: str,
        client_id: str,
        batch_size: int = 10,
        batch_interval: float = 1.0,
        **kwargs,
    ):
        """Initialize batching client.
        
        Args:
            mqtt_url: MQTT broker URL
            client_id: Unique client identifier
            batch_size: Max messages per batch before auto-flush
            batch_interval: Max seconds before auto-flush
            **kwargs: Additional MQTTClient config
        """
        self._client = MQTTClient(mqtt_url, client_id, **kwargs)
        self._batch_size = batch_size
        self._batch_interval = batch_interval
        
        # Batching state
        self._batches: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._last_flush: dict[str, float] = {}
        self._flush_task: Optional[asyncio.Task] = None
    
    async def connect(self) -> None:
        """Connect and start batch flush task."""
        await self._client.connect()
        self._flush_task = asyncio.create_task(self._flush_loop())
    
    async def shutdown(self) -> None:
        """Flush pending batches and shutdown."""
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        
        # Flush remaining batches
        await self._flush_all()
        await self._client.shutdown()
    
    async def publish_batched(self, topic: str, data: dict[str, Any]) -> None:
        """Add message to batch for topic.
        
        Args:
            topic: MQTT topic
            data: Message payload
        """
        self._batches[topic].append(data)
        
        # Auto-flush if batch size reached
        if len(self._batches[topic]) >= self._batch_size:
            await self._flush_topic(topic)
    
    async def _flush_loop(self) -> None:
        """Background task to flush batches at configured interval."""
        try:
            while True:
                await asyncio.sleep(self._batch_interval)
                await self._flush_all()
        except asyncio.CancelledError:
            pass
    
    async def _flush_all(self) -> None:
        """Flush all topic batches."""
        for topic in list(self._batches.keys()):
            await self._flush_topic(topic)
    
    async def _flush_topic(self, topic: str) -> None:
        """Flush batch for specific topic.
        
        Args:
            topic: Topic to flush
        """
        if not self._batches[topic]:
            return
        
        batch = self._batches[topic]
        self._batches[topic] = []
        
        # Publish batch as single event
        await self._client.publish_event(
            topic=f"{topic}/batch",
            event_type=f"{topic.replace('/', '.')}.batch",
            data={
                "items": batch,
                "count": len(batch),
            },
        )
        
        self._last_flush[topic] = time.time()


# === Pattern 3: Direct Client Access for Advanced Features ===


class AdvancedMQTTClient:
    """Uses .client property to access advanced asyncio-mqtt features.
    
    The MQTTClient.client property exposes the underlying asyncio_mqtt.Client,
    allowing direct access to advanced features not wrapped by MQTTClient:
    - Manual message iteration
    - Custom subscription filtering
    - Low-level MQTT callbacks
    
    Example:
        client = AdvancedMQTTClient("mqtt://localhost:1883", "advanced-service")
        await client.connect()
        await client.subscribe_with_filter("sensors/#", lambda msg: "temperature" in msg.topic)
    """
    
    def __init__(self, mqtt_url: str, client_id: str, **kwargs):
        self._client = MQTTClient(mqtt_url, client_id, **kwargs)
    
    async def connect(self) -> None:
        await self._client.connect()
    
    async def shutdown(self) -> None:
        await self._client.shutdown()
    
    async def subscribe_with_filter(
        self,
        topic: str,
        filter_fn: Callable[[Any], bool],
        handler: Callable[[bytes], None],
    ) -> None:
        """Subscribe with custom message filtering.
        
        Uses direct client access to filter messages before dispatching.
        
        Args:
            topic: Topic pattern to subscribe
            filter_fn: Predicate to test messages (receives message object)
            handler: Handler for filtered messages (receives payload bytes)
        """
        # Access underlying asyncio-mqtt client
        underlying_client = self._client.client
        if not underlying_client:
            raise RuntimeError("Not connected")
        
        await underlying_client.subscribe(topic)
        
        # Manual message iteration with filtering
        async def filtered_dispatch():
            async with underlying_client.messages() as messages:
                async for msg in messages:
                    if filter_fn(msg):
                        await handler(msg.payload)
        
        # Start background task for this subscription
        asyncio.create_task(filtered_dispatch())
    
    def get_connection_stats(self) -> dict[str, Any]:
        """Get low-level connection statistics.
        
        Example of accessing underlying paho-mqtt client for diagnostics.
        
        Returns:
            Dict with connection statistics
        """
        underlying_client = self._client.client
        if not underlying_client:
            return {"connected": False}
        
        # Access underlying paho-mqtt client (asyncio-mqtt wraps it)
        # Note: This is an example; actual implementation depends on
        # asyncio-mqtt's internal structure and may not be stable.
        return {
            "connected": self._client.connected,
            "client_id": self._client._config.client_id,
            # Add more stats as needed from underlying client
        }


# === Example Usage ===


async def main():
    """Demonstrate all three extension patterns."""
    
    mqtt_url = "mqtt://localhost:1883"
    
    # Pattern 1: Domain-specific wrapper
    print("\n=== Pattern 1: Domain Wrapper ===")
    domain_client = DomainMQTTClient(
        mqtt_url,
        "example-domain",
        enable_health=False,
    )
    
    await domain_client.connect()
    await domain_client.publish_stt_final(
        text="hello world",
        confidence=0.95,
    )
    print("Published STT final via domain method")
    await domain_client.shutdown()
    
    # Pattern 2: Message batching
    print("\n=== Pattern 2: Message Batching ===")
    batching_client = BatchingMQTTClient(
        mqtt_url,
        "example-batching",
        batch_size=5,
        batch_interval=2.0,
        enable_health=False,
    )
    
    await batching_client.connect()
    for i in range(12):
        await batching_client.publish_batched("test/batch", {"value": i})
        print(f"Queued message {i}")
    print("Waiting for final batch flush...")
    await asyncio.sleep(2.5)
    await batching_client.shutdown()
    
    # Pattern 3: Direct client access
    print("\n=== Pattern 3: Direct Client Access ===")
    advanced_client = AdvancedMQTTClient(
        mqtt_url,
        "example-advanced",
        enable_health=False,
    )
    
    await advanced_client.connect()
    stats = advanced_client.get_connection_stats()
    print(f"Connection stats: {stats}")
    await advanced_client.shutdown()
    
    print("\n=== All examples complete ===")


if __name__ == "__main__":
    asyncio.run(main())
