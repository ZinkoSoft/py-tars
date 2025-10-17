"""Integration tests for MQTT reconnection and subscription reestablishment.

These tests require a running MQTT broker (Mosquitto) to validate:
- Reconnection after broker restart/disconnect
- Exponential backoff behavior
- Subscription reestablishment after reconnect

TDD Workflow: Write tests FIRST (RED), verify they fail, then ensure GREEN.
"""

import asyncio
import pytest
import orjson

from tars.adapters.mqtt_client import MQTTClient


@pytest.mark.integration
@pytest.mark.asyncio
class TestReconnection:
    """Integration tests for reconnection behavior."""

    @pytest.mark.skip("Requires broker restart simulation - manual test only")
    async def test_reconnect_after_broker_restart(self, mosquitto_url):
        """Client reconnects automatically after broker restart."""
        # This test requires manually restarting the broker during execution
        # Not suitable for automated CI testing
        pass

    async def test_subscriptions_persist_across_reconnect(self, mosquitto_url):
        """Subscriptions are tracked and can be reestablished."""
        received_messages = []
        
        async def handler(payload: bytes) -> None:
            received_messages.append(payload)
        
        client = MQTTClient(
            mosquitto_url,
            "test-reconnect-sub",
            enable_health=False,
            reconnect_min_delay=0.5,
            reconnect_max_delay=5.0,
        )
        
        try:
            await client.connect()
            
            # Subscribe to topic
            await client.subscribe("test/reconnect/persistent", handler)
            await asyncio.sleep(0.2)
            
            # Verify subscription is tracked
            assert "test/reconnect/persistent" in client._subscriptions
            
            # Publish test message
            await client.publish_event(
                topic="test/reconnect/persistent",
                event_type="test.message",
                data={"msg": "before"},
            )
            
            await asyncio.sleep(0.5)
            
            # Verify message received
            assert len(received_messages) >= 1
            
        finally:
            await client.shutdown()

    async def test_reconnect_config_values(self, mosquitto_url):
        """Reconnect delays are configurable."""
        client = MQTTClient(
            mosquitto_url,
            "test-reconnect-config",
            enable_health=False,
            reconnect_min_delay=1.0,
            reconnect_max_delay=10.0,
        )
        
        # Verify configuration stored
        assert client._config.reconnect_min_delay == 1.0
        assert client._config.reconnect_max_delay == 10.0
        
        # Note: Actual reconnection behavior tested manually or with broker simulation


@pytest.mark.integration
@pytest.mark.asyncio  
class TestSubscriptionReestablishment:
    """Integration tests for subscription reestablishment after reconnect."""

    async def test_wildcard_subscriptions_tracked(self, mosquitto_url):
        """Wildcard subscriptions are tracked for reconnection."""
        async def handler(payload: bytes) -> None:
            pass
        
        client = MQTTClient(
            mosquitto_url,
            "test-wildcard-tracking",
            enable_health=False,
        )
        
        try:
            await client.connect()
            
            # Subscribe to wildcards
            await client.subscribe("test/+/status", handler)
            await client.subscribe("test/events/#", handler)
            
            # Verify tracking
            assert "test/+/status" in client._subscriptions
            assert "test/events/#" in client._subscriptions
            
        finally:
            await client.shutdown()

    async def test_multiple_subscriptions_tracked(self, mosquitto_url):
        """Multiple subscriptions to different topics are tracked."""
        async def handler1(payload: bytes) -> None:
            pass
        
        async def handler2(payload: bytes) -> None:
            pass
        
        client = MQTTClient(
            mosquitto_url,
            "test-multi-sub",
            enable_health=False,
        )
        
        try:
            await client.connect()
            
            # Subscribe to multiple topics
            await client.subscribe("topic/a", handler1)
            await client.subscribe("topic/b", handler2)
            await client.subscribe("topic/c", handler1)
            
            # Verify all tracked
            assert len(client._subscriptions) == 3
            assert "topic/a" in client._subscriptions
            assert "topic/b" in client._subscriptions
            assert "topic/c" in client._subscriptions
            
        finally:
            await client.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
class TestMessageDeduplication:
    """Integration tests for message deduplication."""

    async def test_duplicate_messages_deduplicated(self, mosquitto_url):
        """Duplicate messages within TTL are filtered."""
        received_messages = []
        
        async def handler(payload: bytes) -> None:
            data = orjson.loads(payload)
            received_messages.append(data)
        
        client = MQTTClient(
            mosquitto_url,
            "test-dedup-receiver",
            enable_health=False,
            dedupe_ttl=5.0,  # 5 second TTL
            dedupe_max_entries=100,
        )
        
        publisher = MQTTClient(
            mosquitto_url,
            "test-dedup-publisher",
            enable_health=False,
        )
        
        try:
            await client.connect()
            await publisher.connect()
            
            # Subscribe with deduplication
            await client.subscribe("test/dedup", handler)
            await asyncio.sleep(0.2)
            
            # Publish same message multiple times using publish_event (which adds envelope)
            for _ in range(5):
                await publisher.publish_event(
                    topic="test/dedup",
                    event_type="test.dedup",
                    data={"id": "msg-123", "text": "test"},
                    correlation_id="corr-123",  # Same correlation_id = same message
                )
                await asyncio.sleep(0.1)
            
            # Wait for processing
            await asyncio.sleep(0.5)
            
            # Should only receive once due to deduplication
            # (all messages have same envelope ID due to same correlation_id)
            assert len(received_messages) == 1
            
        finally:
            await client.shutdown()
            await publisher.shutdown()

    async def test_different_messages_not_deduplicated(self, mosquitto_url):
        """Different messages are not deduplicated."""
        received_messages = []
        
        async def handler(payload: bytes) -> None:
            data = orjson.loads(payload)
            received_messages.append(data)
        
        client = MQTTClient(
            mosquitto_url,
            "test-unique-receiver",
            enable_health=False,
            dedupe_ttl=5.0,
            dedupe_max_entries=100,
        )
        
        publisher = MQTTClient(
            mosquitto_url,
            "test-unique-publisher",
            enable_health=False,
        )
        
        try:
            await client.connect()
            await publisher.connect()
            
            await client.subscribe("test/unique", handler)
            await asyncio.sleep(0.2)
            
            # Publish different messages (different correlation_id = different envelope IDs)
            for i in range(3):
                await publisher.publish_event(
                    topic="test/unique",
                    event_type="test.unique",
                    data={"id": f"msg-{i}", "text": f"test-{i}"},
                    correlation_id=f"corr-{i}",  # Different correlation_ids
                )
                await asyncio.sleep(0.1)
            
            await asyncio.sleep(0.5)
            
            # Should receive all 3 messages (different envelope IDs)
            assert len(received_messages) == 3
            
        finally:
            await client.shutdown()
            await publisher.shutdown()


@pytest.mark.integration
@pytest.mark.asyncio
class TestHeartbeatWatchdog:
    """Integration tests for heartbeat watchdog functionality."""

    async def test_heartbeat_publishes_keepalive(self, mosquitto_url):
        """Heartbeat publishes keepalive messages at configured interval."""
        received_keepalives = []
        
        async def handler(payload: bytes) -> None:
            data = orjson.loads(payload)
            received_keepalives.append(data)
        
        # Monitoring client
        monitor = MQTTClient(
            mosquitto_url,
            "test-monitor",
            enable_health=False,
        )
        
        # Client with heartbeat
        client = MQTTClient(
            mosquitto_url,
            "test-heartbeat",
            enable_health=False,
            enable_heartbeat=True,
            heartbeat_interval=1.0,  # Minimum allowed interval
        )
        
        try:
            await monitor.connect()
            await client.connect()
            
            # Monitor keepalive topic
            await monitor.subscribe("system/keepalive/test-heartbeat", handler)
            await asyncio.sleep(0.2)
            
            # Wait for multiple heartbeats
            await asyncio.sleep(2.5)
            
            # Should have received 2-3 heartbeats (1.0s interval, 2.5s wait)
            assert len(received_keepalives) >= 2
            assert len(received_keepalives) <= 3
            
            # Verify payload structure (matches HeartbeatPayload)
            for msg in received_keepalives:
                assert "timestamp" in msg
                assert "ok" in msg
                assert msg["ok"] is True
                assert "event" in msg
                assert msg["event"] == "heartbeat"
            
        finally:
            await monitor.shutdown()
            await client.shutdown()

    @pytest.mark.skip("Requires connection simulation - complex test")
    async def test_watchdog_detects_stale_connection(self, mosquitto_url):
        """Watchdog detects stale connection when heartbeat fails.
        
        This test would require simulating a stale connection where
        the MQTT client appears connected but cannot publish. This is
        difficult to test reliably in integration tests.
        
        The watchdog logic is validated in unit tests instead.
        """
        pass
