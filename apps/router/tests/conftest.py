"""Shared pytest fixtures for router tests."""

from __future__ import annotations

import asyncio
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_mqtt_client() -> MagicMock:
    """Mock MQTT client for testing."""
    client = MagicMock()
    client.publish = AsyncMock()
    client.subscribe = AsyncMock()
    client.unsubscribe = AsyncMock()
    return client


@pytest.fixture
def mock_publisher() -> AsyncMock:
    """Mock MQTT publisher for testing."""
    publisher = AsyncMock()
    publisher.publish = AsyncMock()
    return publisher


@pytest.fixture
def mock_subscriber() -> AsyncMock:
    """Mock MQTT subscriber for testing."""
    subscriber = AsyncMock()
    subscriber.subscribe = AsyncMock()
    return subscriber


@pytest.fixture
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
