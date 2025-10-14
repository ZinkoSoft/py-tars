"""Shared pytest fixtures for llm-worker tests."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_mqtt_client():
    """Mock MQTT client for testing."""
    client = MagicMock()
    client.publish = AsyncMock()
    client.subscribe = AsyncMock()
    client.unsubscribe = AsyncMock()
    return client


@pytest.fixture
def mock_mcp_client():
    """Mock MCP client for testing."""
    client = AsyncMock()
    client.list_tools = AsyncMock(return_value=[])
    client.call_tool = AsyncMock(return_value={})
    return client


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_llm_request():
    """Sample LLM request payload for testing."""
    return {
        "id": "test-request-123",
        "text": "Hello, how are you?",
        "stream": False,
        "use_rag": False,
    }


@pytest.fixture
def sample_llm_response():
    """Sample LLM response payload for testing."""
    return {
        "id": "test-request-123",
        "reply": "I'm doing well, thank you!",
        "provider": "openai",
        "model": "gpt-4",
    }


@pytest.fixture
def sample_character():
    """Sample character data for testing."""
    return {
        "name": "TARS",
        "description": "A helpful AI assistant",
        "system_prompt": "You are TARS, a helpful AI assistant.",
    }
