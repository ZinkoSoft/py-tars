"""Shared pytest fixtures for UI tests."""

import pytest


@pytest.fixture
def mock_pygame():
    """Mock pygame to avoid display requirements in tests."""
    # TODO: Add pygame mocking when tests are implemented
    pass


@pytest.fixture
def mock_mqtt_client():
    """Mock MQTT client for testing."""
    # TODO: Add MQTT client mock
    pass


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "mqtt": {
            "url": "mqtt://test:test@localhost:1883",
        },
        "ui": {
            "width": 480,
            "height": 800,
            "fps": 30,
            "num_bars": 64,
            "font": "Arial",
            "fullscreen": False,
        },
        "layout": {
            "file": "layout.json",
            "rotation": 0,
        },
        "topics": {
            "audio": "stt/audio_fft",
            "partial": "stt/partial",
            "final": "stt/final",
            "tts": "tts/status",
            "llm_response": "llm/response",
        },
        "fft_ws": {
            "enabled": True,
            "url": "ws://0.0.0.0:8765/fft",
            "retry_seconds": 5.0,
        },
    }
