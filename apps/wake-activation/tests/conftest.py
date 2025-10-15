"""
Shared pytest fixtures for wake-activation tests.
"""

import asyncio

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def mock_mqtt_client():
    """Mock MQTT client for testing."""
    from unittest.mock import AsyncMock

    client = AsyncMock()
    client.publish = AsyncMock()
    client.subscribe = AsyncMock()
    return client


@pytest.fixture
def sample_audio_data():
    """Provide sample audio data for testing."""
    import numpy as np

    # Generate 1 second of silence at 16kHz
    sample_rate = 16000
    duration = 1.0
    samples = int(sample_rate * duration)
    audio = np.zeros(samples, dtype=np.float32)

    return audio, sample_rate


@pytest.fixture
def wake_word_config():
    """Provide default wake word configuration."""
    return {
        "model_path": "models/openwakeword/test_model.tflite",
        "threshold": 0.5,
        "trigger_level": 3,
        "chunk_size": 1280,
        "sample_rate": 16000,
    }
