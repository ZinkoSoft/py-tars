from __future__ import annotations

import time

import pytest
from pydantic import ValidationError

from wake_activation.models import (
    HealthPayload,
    MicAction,
    MicCommand,
    TtsAction,
    TtsControl,
    WakeEvent,
    WakeEventType,
)


def test_wake_event_serialization_roundtrip():
    payload = WakeEvent(
        type=WakeEventType.WAKE,
        ts=time.time(),
        confidence=0.9,
        energy=0.12,
        cause="wake_phrase",
    )
    data = payload.model_dump()
    assert data["type"] == "wake"
    restored = WakeEvent(**data)
    assert restored == payload


def test_mic_command_requires_reason():
    with pytest.raises(ValidationError):
        MicCommand(action=MicAction.UNMUTE)  # type: ignore[call-arg]


def test_tts_control_enum_values():
    ctrl = TtsControl(action=TtsAction.PAUSE, reason="wake_interrupt", id="abc123")
    assert ctrl.action == TtsAction.PAUSE
    assert ctrl.model_dump()["action"] == "pause"


def test_health_payload_defaults():
    hp = HealthPayload(ts=123.456)
    assert hp.ok is True
    assert hp.version == "0.1.0"