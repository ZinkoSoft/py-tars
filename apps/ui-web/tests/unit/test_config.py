"""Unit tests for ui-web configuration."""

import os
from ui_web.config import Config


def test_config_from_env_defaults():
    """Test that Config.from_env() returns defaults when environment is not set."""
    # Clear any existing env vars
    for key in list(os.environ.keys()):
        if key.startswith("MQTT_URL") or key.startswith("UI_"):
            del os.environ[key]

    config = Config.from_env()

    assert config.mqtt_host == "127.0.0.1"
    assert config.mqtt_port == 1883
    assert config.partial_topic == "stt/partial"
    assert config.final_topic == "stt/final"
    assert config.log_level == "INFO"


def test_config_from_env_custom():
    """Test that Config.from_env() respects environment variables."""
    os.environ["MQTT_URL"] = "mqtt://user:pass@testhost:1234"
    os.environ["UI_PARTIAL_TOPIC"] = "custom/partial"
    os.environ["LOG_LEVEL"] = "DEBUG"

    config = Config.from_env()

    assert config.mqtt_host == "testhost"
    assert config.mqtt_port == 1234
    assert config.mqtt_username == "user"
    assert config.mqtt_password == "pass"
    assert config.partial_topic == "custom/partial"
    assert config.log_level == "DEBUG"

    # Cleanup
    del os.environ["MQTT_URL"]
    del os.environ["UI_PARTIAL_TOPIC"]
    del os.environ["LOG_LEVEL"]
