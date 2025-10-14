"""Shared pytest fixtures for TTS worker tests."""

import pytest


@pytest.fixture
def mock_mqtt_client():
    """Mock MQTT client for testing."""
    # Placeholder for shared MQTT mocking if needed
    pass


@pytest.fixture
def sample_tts_text():
    """Sample text for TTS testing."""
    return "Hello, this is a test message."


@pytest.fixture
def sample_utt_id():
    """Sample utterance ID for testing."""
    return "test-utt-001"
