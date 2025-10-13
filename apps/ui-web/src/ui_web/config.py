"""Configuration management for TARS Web UI."""

import os
from dataclasses import dataclass
from urllib.parse import urlparse


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
            partial_topic=os.getenv("UI_PARTIAL_TOPIC", "stt/partial"),
            final_topic=os.getenv("UI_FINAL_TOPIC", "stt/final"),
            fft_topic=os.getenv("UI_AUDIO_TOPIC", "stt/audio_fft"),
            tts_topic=os.getenv("UI_TTS_TOPIC", "tts/status"),
            tts_say_topic=os.getenv("UI_TTS_SAY_TOPIC", "tts/say"),
            llm_stream_topic=os.getenv("UI_LLM_STREAM_TOPIC", "llm/stream"),
            llm_response_topic=os.getenv("UI_LLM_RESPONSE_TOPIC", "llm/response"),
            memory_query_topic=os.getenv("UI_MEMORY_QUERY", "memory/query"),
            memory_results_topic=os.getenv("UI_MEMORY_RESULTS", "memory/results"),
            health_topic=os.getenv("UI_HEALTH_TOPIC", "system/health/#"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
