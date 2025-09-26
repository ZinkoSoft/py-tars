from __future__ import annotations

import math
from pathlib import Path

import pytest

from wake_activation.config import WakeActivationConfig


def test_config_defaults():
    cfg = WakeActivationConfig()
    assert cfg.mqtt_url.startswith("mqtt://")
    assert cfg.audio_fanout_path == Path("/tmp/tars/audio-fanout.sock")
    assert math.isclose(cfg.wake_detection_threshold, 0.55)
    assert cfg.health_topic == "wake/health"


def test_config_from_env_rejects_unknown_keys():
    with pytest.raises(ValueError):
        WakeActivationConfig.from_env({"MQTT_URL": "mqtt://example", "UNKNOWN": "1"})


def test_config_from_env_overrides_values():
    env = {
        "MQTT_URL": "mqtt://demo:pass@mqtt:1884",
        "WAKE_AUDIO_FANOUT": "/var/run/demo.sock",
        "WAKE_IDEAL_TIMEOUT_SEC": "ignored",  # Should be ignored because not expected
    }
    cfg = WakeActivationConfig.from_env({k: v for k, v in env.items() if not k.startswith("WAKE_IDEAL")})
    assert cfg.mqtt_url == "mqtt://demo:pass@mqtt:1884"
    assert cfg.audio_fanout_path == Path("/var/run/demo.sock")
