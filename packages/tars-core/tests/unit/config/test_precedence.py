"""Unit tests for configuration precedence resolution."""

import os

import pytest

from tars.config.models import STTWorkerConfig
from tars.config.precedence import ConfigResolver
from tars.config.types import ConfigSource


class TestConfigResolver:
    """Test configuration precedence resolution."""

    def test_defaults_when_no_overrides(self) -> None:
        """Test that defaults are used when no env or db config."""
        resolver = ConfigResolver()
        config = resolver.resolve_config(STTWorkerConfig, db_config=None)

        assert config.whisper_model == "base.en"  # Default
        assert config.stt_backend == "whisper"  # Default
        assert config.vad_threshold == 0.5  # Default

    def test_database_overrides_defaults(self) -> None:
        """Test that database values override defaults."""
        resolver = ConfigResolver()
        db_config = {"whisper_model": "small.en", "vad_threshold": 0.7}

        config = resolver.resolve_config(STTWorkerConfig, db_config=db_config)

        assert config.whisper_model == "small.en"  # From DB
        assert config.vad_threshold == 0.7  # From DB
        assert config.stt_backend == "whisper"  # Default (not in DB)

    def test_env_overrides_database_and_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that environment variables override database and defaults."""
        monkeypatch.setenv("WHISPER_MODEL", "medium.en")
        monkeypatch.setenv("VAD_THRESHOLD", "0.6")

        resolver = ConfigResolver()
        db_config = {"whisper_model": "small.en", "vad_threshold": 0.7}

        config = resolver.resolve_config(STTWorkerConfig, db_config=db_config)

        assert config.whisper_model == "medium.en"  # From ENV (highest precedence)
        assert config.vad_threshold == 0.6  # From ENV
        assert config.stt_backend == "whisper"  # Default

    def test_env_prefix_support(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that environment variable prefix works."""
        monkeypatch.setenv("TARS_WHISPER_MODEL", "large.en")

        resolver = ConfigResolver(env_prefix="TARS_")
        config = resolver.resolve_config(STTWorkerConfig)

        assert config.whisper_model == "large.en"

    def test_config_source_tracking(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that config source is correctly identified."""
        monkeypatch.setenv("WHISPER_MODEL", "tiny.en")

        resolver = ConfigResolver()
        db_config = {"vad_threshold": 0.8}

        assert resolver.get_config_source("whisper_model", db_config) == ConfigSource.ENV
        assert resolver.get_config_source("vad_threshold", db_config) == ConfigSource.DATABASE
        assert resolver.get_config_source("stt_backend", db_config) == ConfigSource.DEFAULT

    def test_resolve_with_metadata(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test resolution with source metadata."""
        monkeypatch.setenv("WHISPER_MODEL", "base.en")

        resolver = ConfigResolver()
        db_config = {"vad_threshold": 0.9}

        config, source_map = resolver.resolve_with_metadata(STTWorkerConfig, db_config)

        assert config.whisper_model == "base.en"
        assert source_map["whisper_model"] == ConfigSource.ENV
        assert source_map["vad_threshold"] == ConfigSource.DATABASE
        assert source_map["stt_backend"] == ConfigSource.DEFAULT

    def test_parse_boolean_env_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test boolean parsing from environment."""
        resolver = ConfigResolver()

        test_cases = [
            ("true", True),
            ("True", True),
            ("1", True),
            ("yes", True),
            ("on", True),
            ("false", False),
            ("False", False),
            ("0", False),
            ("no", False),
            ("off", False),
        ]

        for env_value, expected in test_cases:
            monkeypatch.setenv("STREAMING_PARTIALS", env_value)
            config = resolver.resolve_config(STTWorkerConfig)
            assert config.streaming_partials == expected, f"Failed for {env_value}"

    def test_parse_numeric_env_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test numeric parsing from environment."""
        monkeypatch.setenv("VAD_THRESHOLD", "0.75")
        monkeypatch.setenv("SAMPLE_RATE", "48000")

        resolver = ConfigResolver()
        config = resolver.resolve_config(STTWorkerConfig)

        assert config.vad_threshold == 0.75  # Float
        assert config.sample_rate == 48000  # Int

    def test_validation_constraints_enforced(self) -> None:
        """Test that Pydantic validation constraints are enforced."""
        resolver = ConfigResolver()

        # vad_threshold must be between 0.0 and 1.0
        with pytest.raises(Exception):  # Pydantic ValidationError
            resolver.resolve_config(STTWorkerConfig, db_config={"vad_threshold": 1.5})

        # channels must be >= 1
        with pytest.raises(Exception):
            resolver.resolve_config(STTWorkerConfig, db_config={"channels": 0})
