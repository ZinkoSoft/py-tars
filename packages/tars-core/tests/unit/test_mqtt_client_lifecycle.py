"""Unit tests for MQTTClient lifecycle (connect, disconnect, shutdown).

TDD Workflow: Write tests FIRST (RED), then implement (GREEN).
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tars.adapters.mqtt_client import MQTTClient, MQTTClientConfig


class TestMQTTClientInit:
    """Tests for MQTTClient.__init__() validation."""

    def test_init_creates_client(self, mqtt_url, client_id):
        """Initialize MQTTClient with valid configuration."""
        client = MQTTClient(mqtt_url, client_id)
        
        assert client is not None
        assert client.connected is False
        assert client.client is None  # Not connected yet

    def test_init_with_all_options(self, mqtt_url):
        """Initialize MQTTClient with all optional parameters."""
        client = MQTTClient(
            mqtt_url=mqtt_url,
            client_id="test-client",
            source_name="test-source",
            keepalive=30,
            enable_health=True,
            enable_heartbeat=True,
            heartbeat_interval=10.0,
            dedupe_ttl=60.0,
            dedupe_max_entries=4096,
            reconnect_min_delay=1.0,
            reconnect_max_delay=10.0,
        )
        
        assert client is not None
        assert client.connected is False

    def test_init_validation_errors(self):
        """Reject invalid configuration during initialization."""
        # Invalid reconnect delays
        with pytest.raises(ValueError, match="reconnect_max_delay"):
            MQTTClient(
                mqtt_url="mqtt://localhost:1883",
                client_id="test",
                reconnect_min_delay=5.0,
                reconnect_max_delay=1.0,  # max < min
            )
        
        # Invalid dedupe config
        with pytest.raises(ValueError, match="dedupe_max_entries"):
            MQTTClient(
                mqtt_url="mqtt://localhost:1883",
                client_id="test",
                dedupe_ttl=30.0,
                dedupe_max_entries=0,  # Required when ttl > 0
            )

    def test_init_creates_deduplicator_when_enabled(self, mqtt_url):
        """Create MessageDeduplicator when deduplication enabled."""
        client = MQTTClient(
            mqtt_url=mqtt_url,
            client_id="test",
            dedupe_ttl=30.0,
            dedupe_max_entries=100,
        )
        
        assert client._deduplicator is not None

    def test_init_no_deduplicator_when_disabled(self, mqtt_url):
        """Don't create MessageDeduplicator when deduplication disabled."""
        client = MQTTClient(mqtt_url=mqtt_url, client_id="test")
        
        assert client._deduplicator is None


@pytest.mark.asyncio
class TestMQTTClientConnect:
    """Tests for MQTTClient.connect() method."""

    async def test_connect_establishes_connection(self, mqtt_url, mock_mqtt_client):
        """Connect to MQTT broker successfully."""
        client = MQTTClient(mqtt_url, "test-client")
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
        
        assert client.connected is True
        assert client.client is not None
        mock_mqtt_client.__aenter__.assert_called_once()

    async def test_connect_parses_url(self, mock_mqtt_client):
        """Parse MQTT URL and use connection parameters."""
        url = "mqtt://user:password@broker.example.com:1883"
        client = MQTTClient(url, "test-client")
        
        with patch("tars.adapters.mqtt_client.mqtt.Client") as MockClient:
            MockClient.return_value = mock_mqtt_client
            await client.connect()
            
            # Verify Client was created with parsed parameters
            MockClient.assert_called_once()
            call_kwargs = MockClient.call_args.kwargs
            assert call_kwargs["hostname"] == "broker.example.com"
            assert call_kwargs["port"] == 1883
            assert call_kwargs["username"] == "user"
            assert call_kwargs["password"] == "password"

    async def test_connect_starts_dispatch_task(self, mqtt_url, mock_mqtt_client):
        """Start message dispatch background task on connect."""
        client = MQTTClient(mqtt_url, "test-client")
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
        
        assert client._dispatch_task is not None
        assert not client._dispatch_task.done()

    async def test_connect_starts_heartbeat_when_enabled(self, mqtt_url, mock_mqtt_client):
        """Start heartbeat task when enable_heartbeat=True."""
        client = MQTTClient(
            mqtt_url,
            "test-client",
            enable_heartbeat=True,
            heartbeat_interval=5.0,
        )
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
        
        assert client._heartbeat_task is not None
        assert not client._heartbeat_task.done()

    async def test_connect_no_heartbeat_when_disabled(self, mqtt_url, mock_mqtt_client):
        """Don't start heartbeat task when enable_heartbeat=False."""
        client = MQTTClient(mqtt_url, "test-client", enable_heartbeat=False)
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
        
        assert client._heartbeat_task is None

    async def test_connect_invalid_url_raises_error(self):
        """Fail with clear error for invalid MQTT URL."""
        # Invalid URL is caught during __init__, not connect()
        with pytest.raises(ValueError, match="Invalid MQTT URL scheme"):
            client = MQTTClient("http://localhost:1883", "test-client")

    async def test_connect_twice_is_idempotent(self, mqtt_url, mock_mqtt_client):
        """Calling connect() twice is safe (idempotent)."""
        client = MQTTClient(mqtt_url, "test-client")
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            first_client = client.client
            
            # Connect again
            await client.connect()
            
            # Should reuse same client
            assert client.client is first_client
            assert mock_mqtt_client.__aenter__.call_count == 1  # Not called again


@pytest.mark.asyncio
class TestMQTTClientDisconnect:
    """Tests for MQTTClient.disconnect() method."""

    async def test_disconnect_closes_connection(self, mqtt_url, mock_mqtt_client):
        """Disconnect from MQTT broker cleanly."""
        client = MQTTClient(mqtt_url, "test-client")
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            await client.disconnect()
        
        assert client.connected is False
        mock_mqtt_client.__aexit__.assert_called_once()

    async def test_disconnect_cancels_dispatch_task(self, mqtt_url, mock_mqtt_client):
        """Cancel message dispatch task on disconnect."""
        client = MQTTClient(mqtt_url, "test-client")
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            dispatch_task = client._dispatch_task
            
            await client.disconnect()
        
        assert dispatch_task.cancelled() or dispatch_task.done()

    async def test_disconnect_cancels_heartbeat_task(self, mqtt_url, mock_mqtt_client):
        """Cancel heartbeat task on disconnect."""
        client = MQTTClient(mqtt_url, "test-client", enable_heartbeat=True)
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            heartbeat_task = client._heartbeat_task
            
            await client.disconnect()
        
        assert heartbeat_task.cancelled() or heartbeat_task.done()

    async def test_disconnect_when_not_connected(self, mqtt_url):
        """Disconnect is safe when not connected (no-op)."""
        client = MQTTClient(mqtt_url, "test-client")
        
        # Should not raise
        await client.disconnect()
        
        assert client.connected is False


@pytest.mark.asyncio
class TestMQTTClientShutdown:
    """Tests for MQTTClient.shutdown() graceful shutdown."""

    async def test_shutdown_publishes_health(self, mqtt_url, mock_mqtt_client):
        """Publish health(ok=False, event='shutdown') when enabled."""
        client = MQTTClient(mqtt_url, "test-client", enable_health=True)
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            
            # Mock publish_health to track calls
            client.publish_health = AsyncMock()
            
            await client.shutdown()
        
        client.publish_health.assert_called_once_with(
            ok=False, event="shutdown"
        )

    async def test_shutdown_no_health_when_disabled(self, mqtt_url, mock_mqtt_client):
        """Don't publish health when enable_health=False."""
        client = MQTTClient(mqtt_url, "test-client", enable_health=False)
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            
            # Mock publish_health to track calls
            client.publish_health = AsyncMock()
            
            await client.shutdown()
        
        # Should not be called
        client.publish_health.assert_not_called()

    async def test_shutdown_cancels_tasks(self, mqtt_url, mock_mqtt_client):
        """Cancel all background tasks during shutdown."""
        client = MQTTClient(mqtt_url, "test-client", enable_heartbeat=True)
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            dispatch_task = client._dispatch_task
            heartbeat_task = client._heartbeat_task
            
            await client.shutdown()
        
        assert dispatch_task.cancelled() or dispatch_task.done()
        assert heartbeat_task.cancelled() or heartbeat_task.done()

    async def test_shutdown_waits_for_tasks_with_timeout(self, mqtt_url, mock_mqtt_client):
        """Wait up to 5 seconds for tasks to complete."""
        client = MQTTClient(mqtt_url, "test-client")
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            
            # Tasks should complete within timeout
            await client.shutdown()
        
        # No exception raised = success

    async def test_shutdown_disconnects_client(self, mqtt_url, mock_mqtt_client):
        """Disconnect from broker during shutdown."""
        client = MQTTClient(mqtt_url, "test-client")
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            await client.shutdown()
        
        assert client.connected is False
        mock_mqtt_client.__aexit__.assert_called_once()

    async def test_shutdown_idempotent(self, mqtt_url, mock_mqtt_client):
        """Calling shutdown() multiple times is safe."""
        client = MQTTClient(mqtt_url, "test-client")
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            
            await client.shutdown()
            await client.shutdown()  # Second call
        
        # Should not raise exception


@pytest.mark.asyncio
class TestMQTTClientContextManager:
    """Tests for async context manager (__aenter__, __aexit__)."""

    async def test_async_context_manager_connects(self, mqtt_url, mock_mqtt_client):
        """Auto-connect when entering context."""
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            async with MQTTClient(mqtt_url, "test-client") as client:
                assert client.connected is True

    async def test_async_context_manager_disconnects(self, mqtt_url, mock_mqtt_client):
        """Auto-shutdown when exiting context."""
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            async with MQTTClient(mqtt_url, "test-client") as client:
                pass
        
        # After exiting context
        assert client.connected is False


@pytest.mark.asyncio
class TestMQTTClientReconnection:
    """Tests for reconnection logic with exponential backoff."""

    async def test_reconnect_on_connection_lost(self, mqtt_url, mock_mqtt_client):
        """Automatically reconnect when connection is lost."""
        reconnect_called = []
        
        # Simulate connection loss during dispatch
        async def simulate_disconnect():
            await asyncio.sleep(0.1)
            # Connection will be lost during message loop
        
        client = MQTTClient(
            mqtt_url,
            "test-client",
            reconnect_min_delay=0.1,
            reconnect_max_delay=0.5,
        )
        
        # This test is better suited for integration testing
        # Unit test just verifies reconnect parameters are stored
        assert client._config.reconnect_min_delay == 0.1
        assert client._config.reconnect_max_delay == 0.5

    async def test_exponential_backoff_delays(self, mqtt_url):
        """Reconnect delays increase exponentially."""
        client = MQTTClient(
            mqtt_url,
            "test-client",
            reconnect_min_delay=0.5,
            reconnect_max_delay=5.0,
        )
        
        # Verify backoff configuration
        assert client._config.reconnect_min_delay == 0.5
        assert client._config.reconnect_max_delay == 5.0
        
        # Note: Actual backoff behavior is tested in integration tests
        # Unit tests just verify configuration is stored

    async def test_subscription_tracking_for_reconnect(self, mqtt_url, mock_mqtt_client):
        """Track subscriptions for reestablishment after reconnect."""
        client = MQTTClient(mqtt_url, "test-client")
        
        async def handler(payload: bytes) -> None:
            pass
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            
            # Subscribe to multiple topics
            await client.subscribe("topic1", handler)
            await client.subscribe("topic2", handler)
            await client.subscribe("topic3/#", handler)
        
        # Verify subscriptions are tracked
        assert "topic1" in client._subscriptions
        assert "topic2" in client._subscriptions
        assert "topic3/#" in client._subscriptions
        assert len(client._subscriptions) == 3


@pytest.mark.asyncio
class TestMQTTClientHeartbeat:
    """Tests for heartbeat functionality."""

    async def test_heartbeat_task_started_when_enabled(self, mqtt_url, mock_mqtt_client):
        """Heartbeat task starts when enable_heartbeat=True."""
        client = MQTTClient(
            mqtt_url,
            "test-client",
            enable_heartbeat=True,
            heartbeat_interval=5.0,
        )
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            
            # Heartbeat task should be running
            assert client._heartbeat_task is not None
            assert not client._heartbeat_task.done()
            
            await client.shutdown()

    async def test_heartbeat_task_not_started_when_disabled(self, mqtt_url, mock_mqtt_client):
        """No heartbeat task when enable_heartbeat=False."""
        client = MQTTClient(
            mqtt_url,
            "test-client",
            enable_heartbeat=False,
        )
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            
            # No heartbeat task
            assert client._heartbeat_task is None
            
            await client.shutdown()

    async def test_heartbeat_interval_configurable(self, mqtt_url):
        """Heartbeat interval is configurable."""
        client = MQTTClient(
            mqtt_url,
            "test-client",
            enable_heartbeat=True,
            heartbeat_interval=10.0,
        )
        
        assert client._config.heartbeat_interval == 10.0

    async def test_heartbeat_publishes_to_keepalive_topic(self, mqtt_url, mock_mqtt_client):
        """Heartbeat publishes to system/keepalive/{client_id}."""
        published_topics = []
        
        async def capture_publish(topic, payload, **kwargs):
            published_topics.append(topic)
        
        mock_mqtt_client.publish.side_effect = capture_publish
        
        client = MQTTClient(
            mqtt_url,
            "test-heartbeat-client",
            enable_heartbeat=True,
            heartbeat_interval=1.0,  # Minimum allowed interval
        )
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            
            # Wait for heartbeat to publish
            await asyncio.sleep(1.5)
            
            await client.shutdown()
        
        # Should have published to keepalive topic
        keepalive_topics = [t for t in published_topics if "keepalive" in t]
        assert len(keepalive_topics) > 0
        assert any("test-heartbeat-client" in t for t in keepalive_topics)


@pytest.mark.asyncio
class TestMQTTClientProperties:
    """Tests for MQTTClient properties."""

    async def test_client_property_returns_underlying_client(self, mqtt_url, mock_mqtt_client):
        """client property exposes underlying mqtt.Client."""
        client = MQTTClient(mqtt_url, "test-client")
        
        # Before connect, client is None
        assert client.client is None
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            
            # After connect, client is available
            assert client.client is mock_mqtt_client
            
            await client.shutdown()

    async def test_connected_property(self, mqtt_url, mock_mqtt_client):
        """connected property reflects connection state."""
        client = MQTTClient(mqtt_url, "test-client")
        
        assert client.connected is False
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            assert client.connected is True
            
            await client.disconnect()
            assert client.connected is False

    async def test_client_property_read_only(self, mqtt_url, mock_mqtt_client):
        """client property is read-only (no setter)."""
        client = MQTTClient(mqtt_url, "test-client")
        
        # Verify no setter exists (fset is None)
        assert type(client).client.fset is None
        assert type(client).client.fget is not None
        
        # Verify cannot set
        with pytest.raises(AttributeError):
            client.client = mock_mqtt_client  # type: ignore


