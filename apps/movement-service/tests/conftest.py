"""Shared test fixtures for movement-service tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_test_movement_request() -> dict:
    """Sample TestMovementRequest payload for testing."""
    return {
        "command": "wave",
        "speed": 0.8,
        "params": {},
        "request_id": "test-123",
    }


@pytest.fixture
def sample_emergency_stop() -> dict:
    """Sample EmergencyStopCommand payload for testing."""
    return {
        "reason": "test stop",
    }


@pytest.fixture
def sample_movement_status() -> dict:
    """Sample MovementStatusUpdate payload for testing."""
    return {
        "event": "command_started",
        "command": "wave",
        "request_id": "test-123",
    }


@pytest.fixture
def mqtt_url() -> str:
    """Test MQTT broker URL."""
    return "mqtt://test:test@localhost:1883"


@pytest.fixture
def movement_settings_dict() -> dict:
    """Sample movement settings as dict."""
    return {
        "mqtt_url": "mqtt://test:test@localhost:1883",
        "test_topic": "movement/test",
        "health_topic": "system/health/movement",
        "publish_qos": 1,
    }
