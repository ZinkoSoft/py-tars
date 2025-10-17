"""Configuration management for TARS Web UI."""

import os
from dataclasses import dataclass
from urllib.parse import urlparse

from tars.contracts.v1 import (  # type: ignore[import]
    TOPIC_LLM_RESPONSE,
    TOPIC_LLM_STREAM,
    TOPIC_MEMORY_QUERY,
    TOPIC_MEMORY_RESULTS,
    TOPIC_STT_AUDIO_FFT,
    TOPIC_STT_FINAL,
    TOPIC_STT_PARTIAL,
    TOPIC_TTS_SAY,
    TOPIC_TTS_STATUS,
)


@dataclass
class Config:
    """Configuration for TARS Web UI."""

    # MQTT Configuration
    mqtt_url: str
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None

    # STT Topics
    partial_topic: str
    final_topic: str
    fft_topic: str

    # TTS Topics
    tts_topic: str
    tts_say_topic: str

    # LLM Topics
    llm_stream_topic: str
    llm_response_topic: str

    # Memory Topics
    memory_query_topic: str
    memory_results_topic: str

    # Health Topics
    health_topic: str

    # Server Configuration
    port: int
    log_level: str

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        mqtt_url = os.getenv("MQTT_URL", "mqtt://tars:pass@127.0.0.1:1883")
        u = urlparse(mqtt_url)

        return cls(
            mqtt_url=mqtt_url,
            mqtt_host=u.hostname or "127.0.0.1",
            mqtt_port=u.port or 1883,
            mqtt_username=u.username,
            mqtt_password=u.password,
            partial_topic=os.getenv("UI_PARTIAL_TOPIC", TOPIC_STT_PARTIAL),
            final_topic=os.getenv("UI_FINAL_TOPIC", TOPIC_STT_FINAL),
            fft_topic=os.getenv("UI_AUDIO_TOPIC", TOPIC_STT_AUDIO_FFT),
            tts_topic=os.getenv("UI_TTS_TOPIC", TOPIC_TTS_STATUS),
            tts_say_topic=os.getenv("UI_TTS_SAY_TOPIC", TOPIC_TTS_SAY),
            llm_stream_topic=os.getenv("UI_LLM_STREAM_TOPIC", TOPIC_LLM_STREAM),
            llm_response_topic=os.getenv("UI_LLM_RESPONSE_TOPIC", TOPIC_LLM_RESPONSE),
            memory_query_topic=os.getenv("UI_MEMORY_QUERY", TOPIC_MEMORY_QUERY),
            memory_results_topic=os.getenv("UI_MEMORY_RESULTS", TOPIC_MEMORY_RESULTS),
            health_topic=os.getenv("UI_HEALTH_TOPIC", "system/health/#"),
            port=int(os.getenv("PORT", "8080")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
