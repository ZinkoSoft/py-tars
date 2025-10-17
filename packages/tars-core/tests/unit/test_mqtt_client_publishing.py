"""Unit tests for MQTTClient publishing methods.

TDD Workflow: Write tests FIRST (RED), then implement (GREEN).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel

from tars.adapters.mqtt_client import MQTTClient
from tars.contracts.v1.health import HealthPing
from tars.contracts.envelope import Envelope


class TestPublishEvent:
    """Tests for MQTTClient.publish_event() method."""

    @pytest.mark.asyncio
    async def test_publish_event_wraps_envelope(self, mqtt_url, mock_mqtt_client):
        """Wrap data in Envelope before publishing."""
        client = MQTTClient(mqtt_url, "test-client", source_name="test-source")
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            
            await client.publish_event(
                topic="test/topic",
                event_type="test.event",
                data={"key": "value"},
            )
        
        # Verify publish was called
        mock_mqtt_client.publish.assert_called_once()
        
        # Verify payload is Envelope
        call_args = mock_mqtt_client.publish.call_args
        payload = call_args[0][1]  # Second positional arg
        
        envelope = Envelope.model_validate_json(payload)
        assert envelope.type == "test.event"
        assert envelope.source == "test-source"
        assert envelope.data == {"key": "value"}

    @pytest.mark.asyncio
    async def test_publish_event_uses_orjson(self, mqtt_url, mock_mqtt_client):
        """Use orjson for JSON serialization."""
        client = MQTTClient(mqtt_url, "test-client")
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            
            # Patch orjson to verify it's used
            with patch("tars.adapters.mqtt_client.orjson.dumps") as mock_dumps:
                mock_dumps.return_value = b'{"test": "data"}'
                
                await client.publish_event(
                    topic="test/topic",
                    event_type="test.event",
                    data={"key": "value"},
                )
                
                mock_dumps.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_event_with_correlation_id(self, mqtt_url, mock_mqtt_client):
        """Include correlation ID in Envelope."""
        client = MQTTClient(mqtt_url, "test-client")
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            
            await client.publish_event(
                topic="test/topic",
                event_type="test.event",
                data={"msg": "hello"},
                correlation_id="request-123",
            )
        
        call_args = mock_mqtt_client.publish.call_args
        payload = call_args[0][1]
        envelope = Envelope.model_validate_json(payload)
        
        # Correlation ID is set as the envelope ID
        assert envelope.id == "request-123"

    @pytest.mark.asyncio
    async def test_publish_event_with_pydantic_model(self, mqtt_url, mock_mqtt_client):
        """Serialize Pydantic models as data."""
        
        class TestData(BaseModel):
            text: str
            value: int
        
        client = MQTTClient(mqtt_url, "test-client")
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            
            data_model = TestData(text="hello", value=42)
            await client.publish_event(
                topic="test/topic",
                event_type="test.event",
                data=data_model,
            )
        
        call_args = mock_mqtt_client.publish.call_args
        payload = call_args[0][1]
        envelope = Envelope.model_validate_json(payload)
        
        assert envelope.data["text"] == "hello"
        assert envelope.data["value"] == 42

    @pytest.mark.asyncio
    async def test_publish_event_with_qos_retain(self, mqtt_url, mock_mqtt_client):
        """Pass QoS and retain flags to broker."""
        client = MQTTClient(mqtt_url, "test-client")
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            
            await client.publish_event(
                topic="test/topic",
                event_type="test.event",
                data={"key": "value"},
                qos=1,
                retain=True,
            )
        
        call_args = mock_mqtt_client.publish.call_args
        assert call_args.kwargs["qos"] == 1
        assert call_args.kwargs["retain"] is True

    @pytest.mark.asyncio
    async def test_publish_event_defaults_qos_0_no_retain(self, mqtt_url, mock_mqtt_client):
        """Default to QoS 0 and retain=False."""
        client = MQTTClient(mqtt_url, "test-client")
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            
            await client.publish_event(
                topic="test/topic",
                event_type="test.event",
                data={"key": "value"},
            )
        
        call_args = mock_mqtt_client.publish.call_args
        # QoS 0 and retain False should be defaults
        assert call_args.kwargs.get("qos", 0) == 0
        assert call_args.kwargs.get("retain", False) is False

    @pytest.mark.asyncio
    async def test_publish_event_not_connected_raises(self, mqtt_url):
        """Raise RuntimeError if not connected."""
        client = MQTTClient(mqtt_url, "test-client")
        
        # Don't connect
        with pytest.raises(RuntimeError, match="not connected"):
            await client.publish_event(
                topic="test/topic",
                event_type="test.event",
                data={"key": "value"},
            )


class TestPublishHealth:
    """Tests for MQTTClient.publish_health() method."""

    @pytest.mark.asyncio
    async def test_publish_health_qos_1_retain_true(self, mqtt_url, mock_mqtt_client):
        """Always use QoS 1 and retain=True for health."""
        client = MQTTClient(mqtt_url, "test-client", enable_health=True)
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            
            await client.publish_health(ok=True, event="ready")
        
        call_args = mock_mqtt_client.publish.call_args
        assert call_args.kwargs["qos"] == 1
        assert call_args.kwargs["retain"] is True

    @pytest.mark.asyncio
    async def test_publish_health_topic_format(self, mqtt_url, mock_mqtt_client):
        """Publish to system/health/{client_id} topic."""
        client = MQTTClient(mqtt_url, "test-client-123", enable_health=True)
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            
            await client.publish_health(ok=True, event="ready")
        
        call_args = mock_mqtt_client.publish.call_args
        topic = call_args[0][0]  # First positional arg
        
        assert topic == "system/health/test-client-123"

    @pytest.mark.asyncio
    async def test_publish_health_wraps_in_envelope(self, mqtt_url, mock_mqtt_client):
        """Wrap HealthPing in Envelope with event_type='health.status'."""
        client = MQTTClient(mqtt_url, "test-client", enable_health=True)
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            
            await client.publish_health(ok=False, err="Connection lost")
        
        call_args = mock_mqtt_client.publish.call_args
        payload = call_args[0][1]
        envelope = Envelope.model_validate_json(payload)
        
        assert envelope.type == "health.status"
        assert envelope.data["ok"] is False
        assert envelope.data["err"] == "Connection lost"

    @pytest.mark.asyncio
    async def test_publish_health_disabled_is_noop(self, mqtt_url, mock_mqtt_client):
        """No-op when enable_health=False."""
        client = MQTTClient(mqtt_url, "test-client", enable_health=False)
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            
            await client.publish_health(ok=True, event="ready")
        
        # Should not call publish
        mock_mqtt_client.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_health_with_event(self, mqtt_url, mock_mqtt_client):
        """Publish health with event name."""
        client = MQTTClient(mqtt_url, "test-client", enable_health=True)
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            
            await client.publish_health(ok=True, event="reconnected")
        
        call_args = mock_mqtt_client.publish.call_args
        payload = call_args[0][1]
        envelope = Envelope.model_validate_json(payload)
        
        assert envelope.data["ok"] is True
        assert envelope.data["event"] == "reconnected"

    @pytest.mark.asyncio
    async def test_publish_health_with_error(self, mqtt_url, mock_mqtt_client):
        """Publish health with error message."""
        client = MQTTClient(mqtt_url, "test-client", enable_health=True)
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            
            await client.publish_health(ok=False, err="Broker unreachable")
        
        call_args = mock_mqtt_client.publish.call_args
        payload = call_args[0][1]
        envelope = Envelope.model_validate_json(payload)
        
        assert envelope.data["ok"] is False
        assert envelope.data["err"] == "Broker unreachable"
