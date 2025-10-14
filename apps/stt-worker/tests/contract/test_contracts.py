from __future__ import annotations

import time
from typing import Any, List, Tuple

import pytest

from tars.contracts.envelope import Envelope  # type: ignore[import]
from tars.contracts.v1 import (  # type: ignore[import]
    EVENT_TYPE_STT_FINAL,
    EVENT_TYPE_STT_PARTIAL,
    FinalTranscript,
    PartialTranscript,
)
from tars.runtime.publisher import publish_event  # type: ignore[import]


class FakePublisher:
    def __init__(self) -> None:
        self.calls: List[Tuple[str, bytes, int, bool]] = []

    async def publish(self, topic: str, payload: bytes, qos: int = 0, retain: bool = False) -> None:
        self.calls.append((topic, payload, qos, retain))


class FakeLogger:
    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - noop
        return None

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - noop
        return None

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - noop
        return None

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - noop
        return None


def test_final_transcript_defaults() -> None:
    before = time.time()
    result = FinalTranscript(text="hello there", confidence=0.75)
    after = time.time()

    assert result.is_final is True
    assert result.lang == "en"
    assert before <= result.ts <= after
    assert len(result.message_id) == 32


def test_partial_transcript_round_trip() -> None:
    before = time.time()
    partial = PartialTranscript(text="working", confidence=0.42)
    after = time.time()

    assert partial.is_final is False
    assert before <= partial.ts <= after

    envelope = Envelope.new(event_type=EVENT_TYPE_STT_PARTIAL, data=partial)
    decoded = PartialTranscript.model_validate(envelope.data)

    assert decoded.text == "working"
    assert decoded.confidence == pytest.approx(0.42)
    assert decoded.lang == "en"


@pytest.mark.asyncio
async def test_publish_event_wraps_envelope() -> None:
    publisher = FakePublisher()
    logger = FakeLogger()
    transcript = FinalTranscript(text="router ready", confidence=0.88)

    message_id = await publish_event(
        publisher,
        logger,
        EVENT_TYPE_STT_FINAL,
        transcript,
        source="stt",
    )

    assert publisher.calls, "publish should be invoked"
    topic, payload, qos, retain = publisher.calls[0]
    assert topic == "stt/final"
    assert qos == 1
    assert retain is False

    envelope = Envelope.model_validate_json(payload)
    assert envelope.type == EVENT_TYPE_STT_FINAL
    assert envelope.source == "stt"
    assert envelope.id == message_id
    assert envelope.data["text"] == "router ready"
    assert envelope.data["is_final"] is True
