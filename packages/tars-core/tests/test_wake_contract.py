from __future__ import annotations

import pytest
from pydantic import ValidationError

from tars.contracts.v1 import WakeEvent  # type: ignore[import]


def test_wake_event_accepts_optional_metadata() -> None:
    event = WakeEvent(
        type="wake",
        tts_id="utt-123",
        confidence=0.72,
        energy=0.18,
        cause="wake_phrase",
        ts=123.456,
    )

    data = event.model_dump()
    assert data["confidence"] == pytest.approx(0.72)
    assert data["energy"] == pytest.approx(0.18)
    assert data["cause"] == "wake_phrase"
    assert data["ts"] == pytest.approx(123.456)
    assert data["tts_id"] == "utt-123"


def test_wake_event_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        WakeEvent(type="wake", unknown="value")
