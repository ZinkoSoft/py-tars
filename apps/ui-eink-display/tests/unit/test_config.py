"""Unit tests for config.py."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from ui_eink_display.config import DisplayConfig


class TestDisplayConfig:
    """Test suite for DisplayConfig."""

    def test_from_env_with_minimal_config(self, monkeypatch):
        """Test loading config with only required variables."""
        monkeypatch.setenv("MQTT_HOST", "test-broker")
        monkeypatch.setenv("MOCK_DISPLAY", "1")  # Skip font path validation

        config = DisplayConfig.from_env()

        assert config.mqtt_host == "test-broker"
        assert config.mqtt_port == 1883
        assert config.mqtt_client_id == "ui-eink-display"
        assert config.display_timeout_sec == 45
        assert config.mock_display is True
        assert config.log_level == "INFO"

    def test_from_env_with_all_config(self, monkeypatch):
        """Test loading config with all variables set."""
        monkeypatch.setenv("MQTT_HOST", "192.168.1.100")
        monkeypatch.setenv("MQTT_PORT", "1884")
        monkeypatch.setenv("MQTT_CLIENT_ID", "custom-display")
        monkeypatch.setenv("DISPLAY_TIMEOUT_SEC", "60")
        monkeypatch.setenv("MOCK_DISPLAY", "1")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("PYTHONPATH", "/custom/path")
        monkeypatch.setenv("FONT_PATH", "/custom/fonts")
        monkeypatch.setenv("HEALTH_CHECK_INTERVAL_SEC", "20")

        config = DisplayConfig.from_env()

        assert config.mqtt_host == "192.168.1.100"
        assert config.mqtt_port == 1884
        assert config.mqtt_client_id == "custom-display"
        assert config.display_timeout_sec == 60
        assert config.mock_display is True
        assert config.log_level == "DEBUG"
        assert config.pythonpath == "/custom/path"
        assert config.font_path == Path("/custom/fonts")
        assert config.health_check_interval_sec == 20

    def test_from_env_missing_mqtt_host(self, monkeypatch):
        """Test that missing MQTT_HOST raises error."""
        monkeypatch.delenv("MQTT_HOST", raising=False)

        with pytest.raises(ValueError, match="MQTT_HOST environment variable is required"):
            DisplayConfig.from_env()

    def test_validate_log_level_valid(self):
        """Test log level validation with valid values."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config = DisplayConfig(
                mqtt_host="test",
                log_level=level,
                mock_display=True,
            )
            assert config.log_level == level

    def test_validate_log_level_case_insensitive(self):
        """Test log level validation is case-insensitive."""
        config = DisplayConfig(
            mqtt_host="test",
            log_level="debug",
            mock_display=True,
        )
        assert config.log_level == "DEBUG"

    def test_validate_log_level_invalid(self):
        """Test log level validation with invalid value."""
        with pytest.raises(ValidationError, match="Invalid log level"):
            DisplayConfig(
                mqtt_host="test",
                log_level="INVALID",
                mock_display=True,
            )

    def test_mqtt_port_validation(self):
        """Test MQTT port validation."""
        # Valid port
        config = DisplayConfig(
            mqtt_host="test",
            mqtt_port=8883,
            mock_display=True,
        )
        assert config.mqtt_port == 8883

        # Invalid port (too low)
        with pytest.raises(ValidationError):
            DisplayConfig(
                mqtt_host="test",
                mqtt_port=0,
                mock_display=True,
            )

        # Invalid port (too high)
        with pytest.raises(ValidationError):
            DisplayConfig(
                mqtt_host="test",
                mqtt_port=65536,
                mock_display=True,
            )

    def test_display_timeout_validation(self):
        """Test display timeout validation."""
        # Valid timeout
        config = DisplayConfig(
            mqtt_host="test",
            display_timeout_sec=120,
            mock_display=True,
        )
        assert config.display_timeout_sec == 120

        # Too short
        with pytest.raises(ValidationError):
            DisplayConfig(
                mqtt_host="test",
                display_timeout_sec=4,
                mock_display=True,
            )

        # Too long
        with pytest.raises(ValidationError):
            DisplayConfig(
                mqtt_host="test",
                display_timeout_sec=301,
                mock_display=True,
            )

    def test_setup_pythonpath(self, monkeypatch):
        """Test PYTHONPATH setup."""
        import sys

        config = DisplayConfig(
            mqtt_host="test",
            pythonpath="/test/path1:/test/path2",
            mock_display=True,
        )

        # Clear sys.path for test
        original_path = sys.path.copy()
        sys.path = []

        try:
            config.setup_pythonpath()

            assert "/test/path1" in sys.path
            assert "/test/path2" in sys.path
        finally:
            sys.path = original_path

    def test_setup_pythonpath_no_duplicates(self, monkeypatch):
        """Test PYTHONPATH setup doesn't add duplicates."""
        import sys

        config = DisplayConfig(
            mqtt_host="test",
            pythonpath="/test/path",
            mock_display=True,
        )

        # Add path first
        sys.path.insert(0, "/test/path")
        original_length = len(sys.path)

        config.setup_pythonpath()

        # Should not add duplicate
        assert len(sys.path) == original_length
        assert sys.path.count("/test/path") == 1

    def test_setup_pythonpath_none(self):
        """Test PYTHONPATH setup with None."""
        import sys

        config = DisplayConfig(
            mqtt_host="test",
            pythonpath=None,
            mock_display=True,
        )

        original_path = sys.path.copy()
        config.setup_pythonpath()

        # Should not modify sys.path
        assert sys.path == original_path
