"""Shared pytest fixtures for tars-core tests."""

import asyncio
from typing import AsyncIterator, Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_mqtt_client():
    """Mock asyncio_mqtt.Client for unit testing.
    
    Returns a MagicMock configured with async methods for MQTT operations.
    Use this to test code that depends on MQTT without a real broker.
    
    Example:
        async def test_publish(mock_mqtt_client):
            client = MQTTClient("mqtt://localhost", "test")
            client._client = mock_mqtt_client
            await client.publish_event("topic", "event.type", {"data": "value"})
            mock_mqtt_client.publish.assert_called_once()
    """
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.subscribe = AsyncMock()
    client.unsubscribe = AsyncMock()
    client.publish = AsyncMock()
    client.messages = MagicMock()
    return client


@pytest.fixture
def mock_mqtt_messages():
    """Mock message stream from asyncio_mqtt.Client.messages().
    
    Returns an async iterator that yields mock MQTT messages.
    Configure the messages list to control what messages are yielded.
    
    Example:
        async def test_subscription(mock_mqtt_messages):
            messages = [
                MagicMock(topic="test/topic", payload=b'{"event": "test"}'),
            ]
            mock_mqtt_messages.messages = messages
            
            async with mock_mqtt_messages as stream:
                async for msg in stream:
                    assert msg.topic == "test/topic"
    """
    messages_context = MagicMock()
    messages_context.messages = []
    
    async def async_iter(self):
        for msg in self.messages:
            yield msg
    
    messages_context.__aiter__ = lambda self: async_iter(messages_context)
    messages_context.__aenter__ = AsyncMock(return_value=messages_context)
    messages_context.__aexit__ = AsyncMock(return_value=None)
    
    return messages_context


@pytest.fixture
def mock_envelope_factory():
    """Factory for creating mock Envelope instances.
    
    Returns a callable that creates Envelope-like objects with valid structure.
    
    Example:
        def test_envelope_handling(mock_envelope_factory):
            envelope = mock_envelope_factory(
                event_type="test.event",
                data={"key": "value"},
            )
            assert envelope.type == "test.event"
    """
    from tars.contracts.envelope import Envelope
    
    def factory(event_type: str, data: dict, **kwargs):
        return Envelope.new(
            event_type=event_type,
            data=data,
            source=kwargs.get("source", "test-source"),
            correlate=kwargs.get("correlate"),
        )
    
    return factory


@pytest.fixture
def mqtt_url() -> str:
    """Default MQTT URL for testing."""
    return "mqtt://test:test@localhost:1883"


@pytest.fixture
def client_id() -> str:
    """Default MQTT client ID for testing."""
    return "test-client"


@pytest.fixture(autouse=True)
def reset_env(monkeypatch):
    """Reset environment variables before each test.
    
    This fixture automatically runs before each test to ensure clean environment.
    Tests can override specific env vars using monkeypatch.setenv().
    """
    # Clear MQTT-related env vars
    mqtt_env_vars = [
        "MQTT_URL",
        "MQTT_CLIENT_ID",
        "MQTT_SOURCE_NAME",
        "MQTT_KEEPALIVE",
        "MQTT_ENABLE_HEALTH",
        "MQTT_ENABLE_HEARTBEAT",
        "MQTT_HEARTBEAT_INTERVAL",
        "MQTT_DEDUPE_TTL",
        "MQTT_DEDUPE_MAX_ENTRIES",
        "MQTT_RECONNECT_MIN_DELAY",
        "MQTT_RECONNECT_MAX_DELAY",
    ]
    for var in mqtt_env_vars:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case.
    
    This fixture is required for pytest-asyncio to work correctly with
    async test functions and fixtures.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Integration test fixtures (require real MQTT broker)

@pytest.fixture(scope="session")
def mosquitto_url() -> str:
    """MQTT broker URL for integration tests.
    
    Override with environment variable INTEGRATION_MQTT_URL if needed.
    Defaults to localhost:1883 (assumes Mosquitto running in Docker).
    """
    import os
    return os.getenv("INTEGRATION_MQTT_URL", "mqtt://localhost:1883")


@pytest.fixture
async def integration_mqtt_client(mosquitto_url: str) -> AsyncIterator:
    """Create a real MQTT client for integration tests.
    
    This fixture connects to a real Mosquitto broker for end-to-end testing.
    Use pytest.mark.integration to mark tests using this fixture.
    
    Example:
        @pytest.mark.integration
        async def test_real_publish(integration_mqtt_client):
            client = integration_mqtt_client
            await client.publish_event("test/topic", "test.event", {"data": "value"})
    """
    from tars.adapters.mqtt_client import MQTTClient
    
    client = MQTTClient(
        mqtt_url=mosquitto_url,
        client_id=f"test-integration-{asyncio.current_task().get_name()}",
    )
    await client.connect()
    
    yield client
    
    await client.shutdown()


# Markers for test organization

def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as unit test (no external dependencies)"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires MQTT broker)"
    )
    config.addinivalue_line(
        "markers", "contract: mark test as contract test (validates MQTT message schemas)"
    )
