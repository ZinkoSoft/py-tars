"""Pytest configuration and fixtures for tars-mcp-character tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import os


@pytest.fixture
def mock_mqtt_client():
    """Mock MQTT client for testing."""
    client = MagicMock()
    client.publish = AsyncMock()
    client.subscribe = AsyncMock()
    return client


@pytest.fixture(autouse=True)
def mock_mqtt_context(mock_mqtt_client):
    """Auto-patch asyncio_mqtt.Client to return mock client in context manager.
    
    This fixture automatically applies to all tests, mocking the async context manager
    pattern used in server.py:
        async with mqtt.Client(MQTT_URL) as client:
            await client.publish(...)
    """
    with patch("asyncio_mqtt.Client") as mock_mqtt_class:
        # Mock the context manager protocol
        mock_mqtt_class.return_value.__aenter__ = AsyncMock(return_value=mock_mqtt_client)
        mock_mqtt_class.return_value.__aexit__ = AsyncMock(return_value=None)
        yield mock_mqtt_client


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    env_vars = {
        "MQTT_URL": "mqtt://test:test@localhost:1883",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        yield env_vars


@pytest.fixture
def sample_character_traits():
    """Sample character trait data for testing."""
    return {
        "humor": 90,
        "formality": 10,
        "loyalty": 100,
        "honesty": 95,
        "sarcasm": 85,
        "curiosity": 80,
        "creativity": 75,
        "patience": 70,
    }
