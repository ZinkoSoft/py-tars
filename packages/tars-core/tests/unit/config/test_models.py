"""Tests for configuration Pydantic models and validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tars.config.models import (
    STTWorkerConfig,
    TTSWorkerConfig,
    RouterConfig,
    LLMWorkerConfig,
    MemoryWorkerConfig,
    WakeActivationConfig,
)


class TestSTTWorkerConfig:
    """Tests for STTWorkerConfig validation."""

    def test_valid_config(self):
        """Test creating a valid STT worker config."""
        config = STTWorkerConfig(
            whisper_model="base.en",
            stt_backend="whisper",
            vad_threshold=0.5,
        )
        assert config.whisper_model == "base.en"
        assert config.stt_backend == "whisper"
        assert config.vad_threshold == 0.5

    def test_invalid_whisper_model(self):
        """Test that invalid whisper model is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            STTWorkerConfig(whisper_model="invalid-model")
        
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert "whisper_model" in str(errors[0]["loc"])

    def test_vad_threshold_out_of_range(self):
        """Test that VAD threshold out of range is rejected."""
        # Test upper bound
        with pytest.raises(ValidationError) as exc_info:
            STTWorkerConfig(vad_threshold=1.5)
        assert "vad_threshold" in str(exc_info.value.errors()[0]["loc"])

        # Test lower bound
        with pytest.raises(ValidationError) as exc_info:
            STTWorkerConfig(vad_threshold=-0.1)
        assert "vad_threshold" in str(exc_info.value.errors()[0]["loc"])

    def test_vad_speech_pad_ms_validation(self):
        """Test VAD speech padding validation."""
        # Valid range
        config = STTWorkerConfig(vad_speech_pad_ms=500)
        assert config.vad_speech_pad_ms == 500

        # Out of range
        with pytest.raises(ValidationError):
            STTWorkerConfig(vad_speech_pad_ms=2000)  # > 1000 max

    def test_ws_url_validation(self):
        """Test WebSocket URL validation."""
        # Valid WebSocket URL
        config = STTWorkerConfig(
            stt_backend="ws",
            ws_url="ws://localhost:8765",
        )
        assert config.ws_url == "ws://localhost:8765"

        # Valid secure WebSocket URL
        config = STTWorkerConfig(
            stt_backend="ws",
            ws_url="wss://example.com:443/stt",
        )
        assert config.ws_url == "wss://example.com:443/stt"

        # Invalid URL (not WebSocket)
        with pytest.raises(ValidationError) as exc_info:
            STTWorkerConfig(
                stt_backend="ws",
                ws_url="http://localhost:8765",
            )
        assert "ws_url" in str(exc_info.value.errors()[0]["loc"])

    def test_channels_validation(self):
        """Test audio channels validation."""
        # Valid: mono
        config = STTWorkerConfig(channels=1)
        assert config.channels == 1

        # Valid: stereo
        config = STTWorkerConfig(channels=2)
        assert config.channels == 2

        # Invalid: > 2
        with pytest.raises(ValidationError):
            STTWorkerConfig(channels=3)

        # Invalid: < 1
        with pytest.raises(ValidationError):
            STTWorkerConfig(channels=0)


class TestTTSWorkerConfig:
    """Tests for TTSWorkerConfig validation."""

    def test_valid_config(self):
        """Test creating a valid TTS worker config."""
        config = TTSWorkerConfig(
            piper_voice="en_US-lessac-medium",
            tts_streaming=True,
            volume_percent=100,
        )
        assert config.piper_voice == "en_US-lessac-medium"
        assert config.tts_streaming is True
        assert config.volume_percent == 100

    def test_volume_percent_validation(self):
        """Test volume percentage validation."""
        # Valid range
        config = TTSWorkerConfig(volume_percent=150)
        assert config.volume_percent == 150

        # Out of range high
        with pytest.raises(ValidationError) as exc_info:
            TTSWorkerConfig(volume_percent=250)
        assert "volume_percent" in str(exc_info.value.errors()[0]["loc"])

        # Out of range low
        with pytest.raises(ValidationError) as exc_info:
            TTSWorkerConfig(volume_percent=-10)
        assert "volume_percent" in str(exc_info.value.errors()[0]["loc"])

    def test_aggregate_timeout_validation(self):
        """Test TTS aggregate timeout validation."""
        # Valid range
        config = TTSWorkerConfig(tts_aggregate_timeout_sec=2.0)
        assert config.tts_aggregate_timeout_sec == 2.0

        # Out of range (too low)
        with pytest.raises(ValidationError):
            TTSWorkerConfig(tts_aggregate_timeout_sec=0.05)  # < 0.1 min

        # Out of range (too high)
        with pytest.raises(ValidationError):
            TTSWorkerConfig(tts_aggregate_timeout_sec=15.0)  # > 10.0 max

    def test_piper_voice_validation(self):
        """Test Piper voice name validation."""
        # Valid
        config = TTSWorkerConfig(piper_voice="en_US-lessac-medium")
        assert config.piper_voice == "en_US-lessac-medium"

        # Empty string should fail
        with pytest.raises(ValidationError):
            TTSWorkerConfig(piper_voice="")


class TestRouterConfig:
    """Tests for RouterConfig validation."""

    def test_valid_config(self):
        """Test creating a valid router config."""
        config = RouterConfig(
            router_llm_tts_stream=True,
            router_stream_min_chars=30,
            router_stream_max_chars=200,
        )
        assert config.router_llm_tts_stream is True
        assert config.router_stream_min_chars == 30
        assert config.router_stream_max_chars == 200

    def test_stream_char_limits_validation(self):
        """Test stream character limits validation."""
        # Min chars validation
        with pytest.raises(ValidationError) as exc_info:
            RouterConfig(router_stream_min_chars=0)
        assert "router_stream_min_chars" in str(exc_info.value.errors()[0]["loc"])

        with pytest.raises(ValidationError):
            RouterConfig(router_stream_min_chars=600)  # > 500 max

        # Max chars validation
        with pytest.raises(ValidationError):
            RouterConfig(router_stream_max_chars=0)

        with pytest.raises(ValidationError):
            RouterConfig(router_stream_max_chars=1500)  # > 1000 max

    def test_boundary_regex_validation(self):
        """Test boundary regex pattern validation."""
        # Valid regex
        config = RouterConfig(router_stream_boundary_regex=r"[.!?]+\s")
        assert config.router_stream_boundary_regex == r"[.!?]+\s"

        # Invalid regex
        with pytest.raises(ValidationError) as exc_info:
            RouterConfig(router_stream_boundary_regex="[invalid(regex")
        assert "boundary regex" in str(exc_info.value.errors()[0]["msg"]).lower()


class TestLLMWorkerConfig:
    """Tests for LLMWorkerConfig validation."""

    def test_valid_config(self):
        """Test creating a valid LLM worker config."""
        config = LLMWorkerConfig(
            llm_provider="openai",
            openai_api_key="sk-1234567890abcdef",
            openai_model="gpt-4o-mini",
        )
        assert config.llm_provider == "openai"
        assert config.openai_api_key == "sk-1234567890abcdef"

    def test_invalid_provider(self):
        """Test that invalid provider is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            LLMWorkerConfig(llm_provider="invalid-provider")
        assert "llm_provider" in str(exc_info.value.errors()[0]["loc"])

    def test_api_key_validation(self):
        """Test API key validation."""
        # Valid OpenAI key format
        config = LLMWorkerConfig(openai_api_key="sk-proj-1234567890")
        assert config.openai_api_key.startswith("sk-")

        # Too short
        with pytest.raises(ValidationError):
            LLMWorkerConfig(openai_api_key="short")

    def test_timeout_validation(self):
        """Test LLM timeout validation."""
        # Valid range
        config = LLMWorkerConfig(llm_timeout_sec=30.0)
        assert config.llm_timeout_sec == 30.0

        # Out of range (too low)
        with pytest.raises(ValidationError):
            LLMWorkerConfig(llm_timeout_sec=0.5)  # < 1.0 min

        # Out of range (too high)
        with pytest.raises(ValidationError):
            LLMWorkerConfig(llm_timeout_sec=200.0)  # > 120.0 max


class TestMemoryWorkerConfig:
    """Tests for MemoryWorkerConfig validation."""

    def test_valid_config(self):
        """Test creating a valid memory worker config."""
        config = MemoryWorkerConfig(
            memory_dir="/data/memory",
            character_name="TARS",
            rag_strategy="hybrid",
            memory_top_k=5,
        )
        assert config.memory_dir == "/data/memory"
        assert config.character_name == "TARS"
        assert config.rag_strategy == "hybrid"

    def test_memory_file_pattern_validation(self):
        """Test memory file name pattern validation."""
        # Valid filename
        config = MemoryWorkerConfig(memory_file="memory.pickle.gz")
        assert config.memory_file == "memory.pickle.gz"

        # Invalid characters
        with pytest.raises(ValidationError) as exc_info:
            MemoryWorkerConfig(memory_file="../../../etc/passwd")
        assert "memory_file" in str(exc_info.value.errors()[0]["loc"])

    def test_character_name_validation(self):
        """Test character name validation."""
        # Valid
        config = MemoryWorkerConfig(character_name="TARS")
        assert config.character_name == "TARS"

        # Too short
        with pytest.raises(ValidationError):
            MemoryWorkerConfig(character_name="")

    def test_top_k_validation(self):
        """Test memory top_k validation."""
        # Valid range
        config = MemoryWorkerConfig(memory_top_k=10)
        assert config.memory_top_k == 10

        # Out of range
        with pytest.raises(ValidationError):
            MemoryWorkerConfig(memory_top_k=0)  # < 1 min

        with pytest.raises(ValidationError):
            MemoryWorkerConfig(memory_top_k=25)  # > 20 max

    def test_rag_strategy_validation(self):
        """Test RAG strategy validation."""
        # Valid values
        for strategy in ["hybrid", "semantic", "keyword"]:
            config = MemoryWorkerConfig(rag_strategy=strategy)
            assert config.rag_strategy == strategy

        # Invalid value
        with pytest.raises(ValidationError):
            MemoryWorkerConfig(rag_strategy="invalid")

    def test_path_absolute_validation(self):
        """Test that directory paths must be absolute."""
        # Relative paths should fail
        with pytest.raises(ValidationError) as exc_info:
            MemoryWorkerConfig(memory_dir="relative/path")
        assert "must be an absolute path" in str(exc_info.value.errors()[0]["msg"])

        with pytest.raises(ValidationError):
            MemoryWorkerConfig(character_dir="./characters")


class TestWakeActivationConfig:
    """Tests for WakeActivationConfig validation."""

    def test_valid_config(self):
        """Test creating a valid wake activation config."""
        config = WakeActivationConfig(
            wake_model_path="/models/openwakeword/hey_tars.tflite",
            wake_detection_threshold=0.35,
            wake_vad_threshold=0.3,
        )
        assert config.wake_model_path == "/models/openwakeword/hey_tars.tflite"
        assert config.wake_detection_threshold == 0.35

    def test_threshold_validation(self):
        """Test detection threshold validation (0.0-1.0)."""
        # Valid range
        config = WakeActivationConfig(wake_detection_threshold=0.5)
        assert config.wake_detection_threshold == 0.5

        # Out of range
        with pytest.raises(ValidationError):
            WakeActivationConfig(wake_detection_threshold=1.5)

        with pytest.raises(ValidationError):
            WakeActivationConfig(wake_detection_threshold=-0.1)

    def test_retrigger_time_validation(self):
        """Test min retrigger time validation."""
        # Valid range
        config = WakeActivationConfig(wake_min_retrigger_sec=0.8)
        assert config.wake_min_retrigger_sec == 0.8

        # Out of range
        with pytest.raises(ValidationError):
            WakeActivationConfig(wake_min_retrigger_sec=0.05)  # < 0.1

        with pytest.raises(ValidationError):
            WakeActivationConfig(wake_min_retrigger_sec=10.0)  # > 5.0

    def test_energy_boost_validation(self):
        """Test energy boost factor validation."""
        # Valid range
        config = WakeActivationConfig(wake_energy_boost_factor=1.5)
        assert config.wake_energy_boost_factor == 1.5

        # Out of range
        with pytest.raises(ValidationError):
            WakeActivationConfig(wake_energy_boost_factor=0.1)  # < 0.5

        with pytest.raises(ValidationError):
            WakeActivationConfig(wake_energy_boost_factor=5.0)  # > 3.0

    def test_model_path_absolute_validation(self):
        """Test that model path must be absolute."""
        # Relative path should fail
        with pytest.raises(ValidationError) as exc_info:
            WakeActivationConfig(wake_model_path="models/wake.tflite")
        assert "must be an absolute path" in str(exc_info.value.errors()[0]["msg"])


class TestModelRoundTrip:
    """Tests for model serialization round-trip."""

    def test_stt_config_round_trip(self):
        """Test STT config serialization/deserialization."""
        original = STTWorkerConfig(
            whisper_model="base.en",
            stt_backend="whisper",
            vad_threshold=0.5,
        )
        
        # Serialize to dict
        data = original.model_dump()
        
        # Deserialize back
        restored = STTWorkerConfig(**data)
        
        assert restored.whisper_model == original.whisper_model
        assert restored.vad_threshold == original.vad_threshold

    def test_all_configs_round_trip(self):
        """Test all config models can round-trip."""
        configs = [
            STTWorkerConfig(),
            TTSWorkerConfig(),
            RouterConfig(),
            LLMWorkerConfig(),
            MemoryWorkerConfig(),
            WakeActivationConfig(),
        ]
        
        for config in configs:
            data = config.model_dump()
            restored = config.__class__(**data)
            assert restored == config
