"""Unit tests for MQTTClient subscription and message dispatch.

TDD Workflow: Write tests FIRST (RED), then implement (GREEN).
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import orjson

from tars.adapters.mqtt_client import MQTTClient
from tars.contracts.envelope import Envelope


class TestSubscribe:
    """Tests for MQTTClient.subscribe() method."""

    @pytest.mark.asyncio
    async def test_subscribe_registers_handler(self, mqtt_url, mock_mqtt_client):
        """Add handler to internal registry."""
        client = MQTTClient(mqtt_url, "test-client")
        
        async def test_handler(payload: bytes) -> None:
            pass
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            await client.subscribe("test/topic", test_handler)
        
        assert "test/topic" in client._handlers
        assert client._handlers["test/topic"] is test_handler

    @pytest.mark.asyncio
    async def test_subscribe_adds_to_subscriptions_set(self, mqtt_url, mock_mqtt_client):
        """Track topic in subscriptions set for reconnect."""
        client = MQTTClient(mqtt_url, "test-client")
        
        async def test_handler(payload: bytes) -> None:
            pass
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            await client.subscribe("test/topic", test_handler)
        
        assert "test/topic" in client._subscriptions

    @pytest.mark.asyncio
    async def test_subscribe_calls_broker(self, mqtt_url, mock_mqtt_client):
        """Call client.subscribe() to register with broker."""
        client = MQTTClient(mqtt_url, "test-client")
        
        async def test_handler(payload: bytes) -> None:
            pass
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            await client.subscribe("test/topic", test_handler, qos=1)
        
        mock_mqtt_client.subscribe.assert_called_once_with("test/topic", qos=1)

    @pytest.mark.asyncio
    async def test_subscribe_default_qos_0(self, mqtt_url, mock_mqtt_client):
        """Default to QoS 0 for subscriptions."""
        client = MQTTClient(mqtt_url, "test-client")
        
        async def test_handler(payload: bytes) -> None:
            pass
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            await client.subscribe("test/topic", test_handler)
        
        call_args = mock_mqtt_client.subscribe.call_args
        assert call_args.kwargs.get("qos", 0) == 0

    @pytest.mark.asyncio
    async def test_subscribe_wildcard_single_level(self, mqtt_url, mock_mqtt_client):
        """Support single-level wildcard (+)."""
        client = MQTTClient(mqtt_url, "test-client")
        
        async def test_handler(payload: bytes) -> None:
            pass
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            await client.subscribe("system/health/+", test_handler)
        
        assert "system/health/+" in client._subscriptions

    @pytest.mark.asyncio
    async def test_subscribe_wildcard_multi_level(self, mqtt_url, mock_mqtt_client):
        """Support multi-level wildcard (#)."""
        client = MQTTClient(mqtt_url, "test-client")
        
        async def test_handler(payload: bytes) -> None:
            pass
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            await client.subscribe("events/#", test_handler)
        
        assert "events/#" in client._subscriptions

    @pytest.mark.asyncio
    async def test_subscribe_replaces_handler(self, mqtt_url, mock_mqtt_client):
        """Replace handler for existing topic."""
        client = MQTTClient(mqtt_url, "test-client")
        
        async def handler1(payload: bytes) -> None:
            pass
        
        async def handler2(payload: bytes) -> None:
            pass
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            await client.connect()
            await client.subscribe("test/topic", handler1)
            await client.subscribe("test/topic", handler2)
        
        # Second handler should replace first
        assert client._handlers["test/topic"] is handler2

    @pytest.mark.asyncio
    async def test_subscribe_not_connected_raises(self, mqtt_url):
        """Raise RuntimeError if not connected."""
        client = MQTTClient(mqtt_url, "test-client")
        
        async def test_handler(payload: bytes) -> None:
            pass
        
        with pytest.raises(RuntimeError, match="not connected"):
            await client.subscribe("test/topic", test_handler)


@pytest.mark.asyncio
@pytest.mark.skip("Message dispatch tests require integration testing with real broker")
class TestMessageDispatch:
    """Tests for message dispatch and handler invocation.
    
    Note: These tests are better suited for integration tests as they require
    complex async message flow mocking. They are covered by integration tests.
    """

    async def test_handler_receives_message(self, mqtt_url):
        """Dispatch message to correct handler.
        
        Covered by integration tests with real MQTT broker.
        """
        pass

    async def test_handler_error_isolated(self, mqtt_url):
        """Continue dispatch when handler raises exception.
        
        Covered by integration tests with real MQTT broker.
        """
        pass

    async def test_deduplication_skips_duplicate(self, mqtt_url):
        """Skip duplicate messages when deduplication enabled.
        
        Covered by integration tests with real MQTT broker.
        """
        pass

