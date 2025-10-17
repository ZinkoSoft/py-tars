"""Integration tests for MQTTClient with real Mosquitto broker.

These tests require a running MQTT broker (Mosquitto) to validate:
- Message dispatch to handlers
- Error isolation in handlers
- Deduplication behavior
- Wildcard subscription matching

TDD Workflow: Write tests FIRST (RED), verify they fail, then ensure GREEN.
"""

import asyncio
import pytest
import orjson

from tars.adapters.mqtt_client import MQTTClient
from tars.contracts.envelope import Envelope


@pytest.mark.integration
@pytest.mark.asyncio
class TestEndToEndPublishSubscribe:
    """End-to-end tests with real MQTT broker."""

    async def test_handler_receives_message(self, mosquitto_url):
        """Message published to topic is dispatched to subscribed handler."""
        received_payloads = []
        
        async def test_handler(payload: bytes) -> None:
            received_payloads.append(payload)
        
        # Create two clients: publisher and subscriber
        publisher = MQTTClient(
            mosquitto_url,
            "test-publisher",
            enable_health=False,
        )
        subscriber = MQTTClient(
            mosquitto_url,
            "test-subscriber",
            enable_health=False,
        )
        
        try:
            await publisher.connect()
            await subscriber.connect()
            
            # Subscribe before publishing
            await subscriber.subscribe("test/integration/basic", test_handler)
            
            # Allow subscription to register
            await asyncio.sleep(0.2)
            
            # Publish test event
            await publisher.publish_event(
                topic="test/integration/basic",
                event_type="test.message",
                data={"msg": "hello integration"},
            )
            
            # Allow message to dispatch
            await asyncio.sleep(0.5)
            
            # Verify handler received message
            assert len(received_payloads) == 1
            
            # Verify payload is valid Envelope
            envelope_data = orjson.loads(received_payloads[0])
            assert envelope_data["type"] == "test.message"
            assert envelope_data["data"]["msg"] == "hello integration"
            
        finally:
            await publisher.shutdown()
            await subscriber.shutdown()

    async def test_handler_error_isolated(self, mosquitto_url):
        """Handler exception doesn't crash dispatch loop."""
        call_count = [0]
        
        async def failing_handler(payload: bytes) -> None:
            call_count[0] += 1
            raise ValueError("Intentional test error")
        
        publisher = MQTTClient(
            mosquitto_url,
            "test-publisher-errors",
            enable_health=False,
        )
        subscriber = MQTTClient(
            mosquitto_url,
            "test-subscriber-errors",
            enable_health=False,
        )
        
        try:
            await publisher.connect()
            await subscriber.connect()
            
            await subscriber.subscribe("test/integration/errors", failing_handler)
            await asyncio.sleep(0.2)
            
            # Publish two messages
            await publisher.publish_event(
                topic="test/integration/errors",
                event_type="test.error1",
                data={"msg": 1},
            )
            await publisher.publish_event(
                topic="test/integration/errors",
                event_type="test.error2",
                data={"msg": 2},
            )
            
            # Allow messages to dispatch
            await asyncio.sleep(0.5)
            
            # Both messages processed despite handler errors
            assert call_count[0] == 2
            
        finally:
            await publisher.shutdown()
            await subscriber.shutdown()

    async def test_deduplication_skips_duplicate(self, mosquitto_url):
        """Duplicate messages are filtered when deduplication enabled."""
        received_count = [0]
        
        async def counting_handler(payload: bytes) -> None:
            received_count[0] += 1
        
        publisher = MQTTClient(
            mosquitto_url,
            "test-publisher-dedupe",
            enable_health=False,
        )
        subscriber = MQTTClient(
            mosquitto_url,
            "test-subscriber-dedupe",
            enable_health=False,
            dedupe_ttl=30.0,  # Enable deduplication
            dedupe_max_entries=100,
        )
        
        try:
            await publisher.connect()
            await subscriber.connect()
            
            await subscriber.subscribe("test/integration/dedupe", counting_handler)
            await asyncio.sleep(0.2)
            
            # Publish same message twice (same correlation_id)
            correlation_id = "dedupe-test-123"
            
            await publisher.publish_event(
                topic="test/integration/dedupe",
                event_type="test.dedupe",
                data={"msg": "duplicate me"},
                correlation_id=correlation_id,
            )
            await publisher.publish_event(
                topic="test/integration/dedupe",
                event_type="test.dedupe",
                data={"msg": "duplicate me"},
                correlation_id=correlation_id,
            )
            
            # Allow messages to dispatch
            await asyncio.sleep(0.5)
            
            # Only first message processed (second deduplicated)
            assert received_count[0] == 1
            
        finally:
            await publisher.shutdown()
            await subscriber.shutdown()

    async def test_wildcard_single_level_subscription(self, mosquitto_url):
        """Single-level wildcard (+) matches one topic level."""
        received_topics = []
        
        async def wildcard_handler(payload: bytes) -> None:
            envelope_data = orjson.loads(payload)
            received_topics.append(envelope_data["data"]["source"])
        
        publisher = MQTTClient(
            mosquitto_url,
            "test-publisher-wildcard",
            enable_health=False,
        )
        subscriber = MQTTClient(
            mosquitto_url,
            "test-subscriber-wildcard",
            enable_health=False,
        )
        
        try:
            await publisher.connect()
            await subscriber.connect()
            
            # Subscribe to wildcard pattern
            await subscriber.subscribe("test/integration/+/status", wildcard_handler)
            await asyncio.sleep(0.2)
            
            # Publish to matching topics
            await publisher.publish_event(
                topic="test/integration/service1/status",
                event_type="test.wildcard",
                data={"source": "service1"},
            )
            await publisher.publish_event(
                topic="test/integration/service2/status",
                event_type="test.wildcard",
                data={"source": "service2"},
            )
            
            # Publish to non-matching topic (too many levels)
            await publisher.publish_event(
                topic="test/integration/service3/extra/status",
                event_type="test.wildcard",
                data={"source": "service3-nomatch"},
            )
            
            await asyncio.sleep(0.5)
            
            # Only two matching messages received
            assert len(received_topics) == 2
            assert "service1" in received_topics
            assert "service2" in received_topics
            assert "service3-nomatch" not in received_topics
            
        finally:
            await publisher.shutdown()
            await subscriber.shutdown()

    async def test_wildcard_multi_level_subscription(self, mosquitto_url):
        """Multi-level wildcard (#) matches multiple topic levels."""
        received_count = [0]
        
        async def multi_handler(payload: bytes) -> None:
            received_count[0] += 1
        
        publisher = MQTTClient(
            mosquitto_url,
            "test-publisher-multi",
            enable_health=False,
        )
        subscriber = MQTTClient(
            mosquitto_url,
            "test-subscriber-multi",
            enable_health=False,
        )
        
        try:
            await publisher.connect()
            await subscriber.connect()
            
            # Subscribe to multi-level wildcard
            await subscriber.subscribe("test/integration/events/#", multi_handler)
            await asyncio.sleep(0.2)
            
            # Publish to various matching depths
            await publisher.publish_event(
                topic="test/integration/events/a",
                event_type="test.multi",
                data={},
            )
            await publisher.publish_event(
                topic="test/integration/events/a/b",
                event_type="test.multi",
                data={},
            )
            await publisher.publish_event(
                topic="test/integration/events/a/b/c",
                event_type="test.multi",
                data={},
            )
            
            # Publish to non-matching topic
            await publisher.publish_event(
                topic="test/integration/other/a",
                event_type="test.multi",
                data={},
            )
            
            await asyncio.sleep(0.5)
            
            # Only three matching messages received
            assert received_count[0] == 3
            
        finally:
            await publisher.shutdown()
            await subscriber.shutdown()

    async def test_multiple_handlers_same_topic(self, mosquitto_url):
        """Multiple handlers can subscribe to same topic (last wins)."""
        handler1_count = [0]
        handler2_count = [0]
        
        async def handler1(payload: bytes) -> None:
            handler1_count[0] += 1
        
        async def handler2(payload: bytes) -> None:
            handler2_count[0] += 1
        
        publisher = MQTTClient(
            mosquitto_url,
            "test-publisher-multi-handler",
            enable_health=False,
        )
        subscriber = MQTTClient(
            mosquitto_url,
            "test-subscriber-multi-handler",
            enable_health=False,
        )
        
        try:
            await publisher.connect()
            await subscriber.connect()
            
            # Subscribe with handler1, then replace with handler2
            await subscriber.subscribe("test/integration/replace", handler1)
            await subscriber.subscribe("test/integration/replace", handler2)
            await asyncio.sleep(0.2)
            
            # Publish message
            await publisher.publish_event(
                topic="test/integration/replace",
                event_type="test.replace",
                data={},
            )
            
            await asyncio.sleep(0.5)
            
            # Only handler2 should receive (handler1 was replaced)
            assert handler1_count[0] == 0
            assert handler2_count[0] == 1
            
        finally:
            await publisher.shutdown()
            await subscriber.shutdown()
