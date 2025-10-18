"""Shared pytest fixtures for ui-web tests."""

import pytest


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    from ui_web.config import Config

    return Config(
        mqtt_url="mqtt://test:test@localhost:1883",
        mqtt_host="localhost",
        mqtt_port=1883,
        mqtt_username="test",
        mqtt_password="test",
        partial_topic="stt/partial",
        final_topic="stt/final",
        fft_topic="stt/audio_fft",
        tts_topic="tts/status",
        tts_say_topic="tts/say",
        llm_stream_topic="llm/stream",
        llm_response_topic="llm/response",
        memory_query_topic="memory/query",
        memory_results_topic="memory/results",
        health_topic="system/health/#",
        log_level="INFO",
    )
