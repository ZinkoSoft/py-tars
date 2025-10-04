"""Tests for MQTT client."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_bridge.mqtt_client import MCPBridgeMQTTClient


def test_mqtt_client_initialization_default():
    """Test MQTT client initialization with default values."""
    with patch.dict("os.environ", {}, clear=True):
        client = MCPBridgeMQTTClient()
        
        assert client.host == "127.0.0.1"
        assert client.port == 1883
        assert client.user is None
        assert client.password is None


def test_mqtt_client_initialization_from_env():
    """Test MQTT client initialization from environment variables."""
    env = {
        "MQTT_HOST": "mqtt.example.com",
        "MQTT_PORT": "8883",
        "MQTT_USER": "testuser",
        "MQTT_PASS": "testpass"
    }
    
    with patch.dict("os.environ", env, clear=True):
        client = MCPBridgeMQTTClient()
        
        assert client.host == "mqtt.example.com"
        assert client.port == 8883
        assert client.user == "testuser"
        assert client.password == "testpass"


@pytest.mark.asyncio
async def test_publish_tool_registry():
    """Test publishing tool registry."""
    mock_client = AsyncMock()
    tools = [
        {
            "type": "function",
            "function": {
                "name": "mcp__server__tool1",
                "description": "Test tool",
                "parameters": {"type": "object"}
            }
        }
    ]
    
    await MCPBridgeMQTTClient.publish_tool_registry(mock_client, tools)
    
    # Verify publish was called
    mock_client.publish.assert_called_once()
    call_args = mock_client.publish.call_args
    
    # Check topic
    assert call_args[0][0] == "llm/tools/registry"
    
    # Check QoS and retain
    assert call_args[1]["qos"] == 1
    assert call_args[1]["retain"] is True
    
    # Check payload contains tools
    import orjson
    payload = orjson.loads(call_args[0][1])
    assert "tools" in payload
    assert len(payload["tools"]) == 1


@pytest.mark.asyncio
async def test_publish_tool_registry_empty():
    """Test publishing empty tool registry."""
    mock_client = AsyncMock()
    tools = []
    
    await MCPBridgeMQTTClient.publish_tool_registry(mock_client, tools)
    
    mock_client.publish.assert_called_once()
    
    import orjson
    payload = orjson.loads(mock_client.publish.call_args[0][1])
    assert payload["tools"] == []


@pytest.mark.asyncio
async def test_publish_health_ready():
    """Test publishing health ready status."""
    mock_client = AsyncMock()
    
    await MCPBridgeMQTTClient.publish_health(mock_client, event="ready", ok=True)
    
    mock_client.publish.assert_called_once()
    call_args = mock_client.publish.call_args
    
    # Check topic
    assert call_args[0][0] == "system/health/mcp-bridge"
    
    # Check retain
    assert call_args[1]["retain"] is True
    
    # Check payload uses HealthPing model
    from tars.contracts.v1.health import HealthPing
    health = HealthPing.model_validate_json(call_args[0][1])
    assert health.ok is True
    assert health.event == "ready"
    assert health.message_id is not None
    assert health.timestamp > 0


@pytest.mark.asyncio
async def test_publish_health_heartbeat():
    """Test publishing health heartbeat."""
    mock_client = AsyncMock()
    
    await MCPBridgeMQTTClient.publish_health(mock_client, event="heartbeat")
    
    mock_client.publish.assert_called_once()
    
    from tars.contracts.v1.health import HealthPing
    health = HealthPing.model_validate_json(mock_client.publish.call_args[0][1])
    assert health.ok is True
    assert health.event == "heartbeat"


@pytest.mark.asyncio
async def test_publish_health_error():
    """Test publishing health error status."""
    mock_client = AsyncMock()
    
    await MCPBridgeMQTTClient.publish_health(mock_client, event="error", ok=False, err="Test error")
    
    mock_client.publish.assert_called_once()
    
    from tars.contracts.v1.health import HealthPing
    health = HealthPing.model_validate_json(mock_client.publish.call_args[0][1])
    assert health.ok is False
    assert health.event == "error"
    assert health.err == "Test error"


@pytest.mark.asyncio
async def test_subscribe_llm_health():
    """Test subscribing to LLM worker health."""
    mock_client = AsyncMock()
    
    await MCPBridgeMQTTClient.subscribe_llm_health(mock_client)
    
    mock_client.subscribe.assert_called_once_with("system/health/llm")


def test_is_llm_ready_event_ready():
    """Test detecting LLM ready event."""
    from tars.contracts.v1.health import HealthPing
    
    health = HealthPing(ok=True, event="ready")
    payload = health.model_dump_json().encode()
    
    assert MCPBridgeMQTTClient.is_llm_ready_event(payload) is True


def test_is_llm_ready_event_restart():
    """Test detecting LLM restart event."""
    from tars.contracts.v1.health import HealthPing
    
    health = HealthPing(ok=True, event="restart")
    payload = health.model_dump_json().encode()
    
    assert MCPBridgeMQTTClient.is_llm_ready_event(payload) is True


def test_is_llm_ready_event_heartbeat():
    """Test that heartbeat events are not treated as ready."""
    from tars.contracts.v1.health import HealthPing
    
    health = HealthPing(ok=True, event="heartbeat")
    payload = health.model_dump_json().encode()
    
    assert MCPBridgeMQTTClient.is_llm_ready_event(payload) is False


def test_is_llm_ready_event_not_ok():
    """Test that events with ok=False are not treated as ready."""
    from tars.contracts.v1.health import HealthPing
    
    health = HealthPing(ok=False, event="ready", err="Error")
    payload = health.model_dump_json().encode()
    
    assert MCPBridgeMQTTClient.is_llm_ready_event(payload) is False


def test_is_llm_ready_event_invalid_json():
    """Test handling invalid JSON payload."""
    payload = b"invalid json"
    
    assert MCPBridgeMQTTClient.is_llm_ready_event(payload) is False


@pytest.mark.asyncio
async def test_subscribe_llm_health():
    """Test subscribing to LLM health topic."""
    mock_client = AsyncMock()
    
    await MCPBridgeMQTTClient.subscribe_llm_health(mock_client)
    
    mock_client.subscribe.assert_called_once_with("system/health/llm")


def test_is_llm_ready_event_ready():
    """Test detecting LLM ready event."""
    import orjson
    payload = orjson.dumps({"ok": True, "event": "ready"})
    
    assert MCPBridgeMQTTClient.is_llm_ready_event(payload) is True


def test_is_llm_ready_event_restart():
    """Test detecting LLM restart event."""
    import orjson
    payload = orjson.dumps({"ok": True, "event": "restart"})
    
    assert MCPBridgeMQTTClient.is_llm_ready_event(payload) is True


def test_is_llm_ready_event_startup():
    """Test detecting LLM startup event."""
    import orjson
    payload = orjson.dumps({"ok": True, "event": "startup"})
    
    assert MCPBridgeMQTTClient.is_llm_ready_event(payload) is True


def test_is_llm_ready_event_initialized():
    """Test detecting LLM initialized event."""
    import orjson
    payload = orjson.dumps({"ok": True, "event": "initialized"})
    
    assert MCPBridgeMQTTClient.is_llm_ready_event(payload) is True


def test_is_llm_ready_event_heartbeat():
    """Test that heartbeat is not a ready event."""
    import orjson
    payload = orjson.dumps({"ok": True, "event": "heartbeat"})
    
    assert MCPBridgeMQTTClient.is_llm_ready_event(payload) is False


def test_is_llm_ready_event_ok_false():
    """Test that ok=False is not a ready event."""
    import orjson
    payload = orjson.dumps({"ok": False, "event": "ready"})
    
    assert MCPBridgeMQTTClient.is_llm_ready_event(payload) is False


def test_is_llm_ready_event_invalid_json():
    """Test handling invalid JSON."""
    payload = b"invalid json"
    
    assert MCPBridgeMQTTClient.is_llm_ready_event(payload) is False


def test_is_llm_ready_event_missing_fields():
    """Test handling missing fields."""
    import orjson
    payload = orjson.dumps({})
    
    assert MCPBridgeMQTTClient.is_llm_ready_event(payload) is False
