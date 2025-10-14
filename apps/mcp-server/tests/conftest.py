"""Shared test fixtures for tars-mcp-server."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_mqtt_client():
    """Mock MQTT client for testing tool functions."""
    client = AsyncMock()
    client.publish = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    return client


@pytest.fixture
def mock_mqtt_context(mock_mqtt_client):
    """Patch asyncio_mqtt.Client to return mock client."""
    with patch("tars_mcp_server.server.mqtt.Client", return_value=mock_mqtt_client):
        yield mock_mqtt_client


@pytest.fixture
def valid_traits():
    """Set of valid personality trait names."""
    return {
        "honesty",
        "humor",
        "empathy",
        "curiosity",
        "confidence",
        "formality",
        "sarcasm",
        "adaptability",
        "discipline",
        "imagination",
        "emotional_stability",
        "pragmatism",
        "optimism",
        "resourcefulness",
        "cheerfulness",
        "engagement",
        "respectfulness",
        "verbosity",
    }


@pytest.fixture
def sample_trait_update():
    """Sample trait update payload."""
    return {
        "trait": "humor",
        "value": 75,
    }


@pytest.fixture
def sample_envelope():
    """Sample MQTT envelope structure."""
    return {
        "event_type": "character.update",
        "data": {
            "trait": "humor",
            "value": 75,
        },
    }
