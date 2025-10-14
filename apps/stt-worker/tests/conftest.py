"""Shared pytest fixtures for stt-worker tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_mqtt_client():
    """Mock MQTT client for testing."""
    client = AsyncMock()
    client.publish = AsyncMock()
    client.subscribe = AsyncMock()
    client.unsubscribe = AsyncMock()
    return client


@pytest.fixture
def mock_transcriber():
    """Mock transcriber for testing."""
    transcriber = MagicMock()
    transcriber.transcribe = MagicMock(return_value=("test transcription", 0.95, {}))
    transcriber.transcribe_async = AsyncMock(return_value=("test transcription", 0.95, {}))
    return transcriber


@pytest.fixture
def sample_audio_data():
    """Sample audio data for testing."""
    # 16kHz mono audio, 1 second
    import numpy as np

    sample_rate = 16000
    duration = 1.0
    samples = int(sample_rate * duration)
    audio = np.zeros(samples, dtype=np.float32)
    return audio.tobytes(), sample_rate
