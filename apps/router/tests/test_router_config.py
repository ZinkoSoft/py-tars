from __future__ import annotations

import pytest

from tars.domain.router.config import RouterSettings  # type: ignore[import]


def test_router_settings_from_env_defaults() -> None:
    defaults = RouterSettings()
    settings = RouterSettings.from_env(env={})

    assert settings.mqtt_url == defaults.mqtt_url
    assert settings.online_announce == defaults.online_announce
    assert settings.stream_min_chars == defaults.stream_min_chars
    assert settings.wake_phrases == defaults.wake_phrases
    assert settings.wake_ack_choices == defaults.wake_ack_choices


def test_router_settings_from_env_overrides() -> None:
    env = {
        "MQTT_URL": "mqtt://user:pass@example.com:1884",
        "ONLINE_ANNOUNCE": "false",
        "STREAM_MIN_CHARS": "120",
        "ROUTER_STREAM_MAX_CHARS": "400",
        "ROUTER_STREAM_BOUNDARY_ONLY": "0",
    }
    settings = RouterSettings.from_env(env=env)

    assert settings.mqtt_url == "mqtt://user:pass@example.com:1884"
    assert settings.online_announce is False
    assert settings.stream_min_chars == 120
    assert settings.stream_max_chars == 400
    assert settings.stream_boundary_only is False


def test_router_settings_uses_aliases_for_wake_phrases() -> None:
    env = {
        "WAKE_PHRASES": "hey jarvis|ok tars",
    }
    settings = RouterSettings.from_env(env=env)

    assert settings.wake_phrases == ("hey jarvis", "ok tars")


@pytest.mark.parametrize(
    "value,expected",
    [("1", True), ("0", False), ("yes", True), ("off", False)],
)
def test_router_settings_bool_parsing(value: str, expected: bool) -> None:
    env = {"ROUTER_WAKE_ACK_ENABLED": value}
    settings = RouterSettings.from_env(env=env)
    assert settings.wake_ack_enabled is expected
