from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
import sys

import pytest

SRC_DIR = Path(__file__).resolve().parents[3] / "src"
if SRC_DIR.exists():
    src_path = str(SRC_DIR)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

from tars.domain.stt import (  # type: ignore[import]
    PartialSettings,
    STTService,
    STTServiceConfig,
)


class FakeVAD:
    """Minimal VAD stub returning queued utterances and exposing an active buffer."""

    def __init__(self) -> None:
        self.is_speech = False
        self._utterances: deque[bytes] = deque()
        self._active_buffer: bytes = b""
        self._lock = Lock()

    def queue_utterance(self, utterance: bytes) -> None:
        with self._lock:
            self._utterances.append(utterance)

    def process_chunk(self, chunk: bytes) -> bytes | None:  # pragma: no cover - exercised via to_thread
        with self._lock:
            if self._utterances:
                return self._utterances.popleft()
        return None

    def set_active(self, buffer_bytes: bytes, *, is_speech: bool = True) -> None:
        with self._lock:
            self._active_buffer = buffer_bytes
        self.is_speech = is_speech

    def get_active_buffer(self) -> bytes:
        with self._lock:
            return self._active_buffer


class FakeTranscriber:
    """Thread-safe transcriber stub yielding predetermined responses."""

    def __init__(self, responses: list[tuple[str, float | None, dict[str, float]]]):
        self._responses: deque[tuple[str, float | None, dict[str, float]]] = deque(responses)
        self.calls: int = 0
        self._lock = Lock()

    def transcribe(self, audio: bytes, sample_rate: int) -> tuple[str, float | None, dict[str, float]]:  # pragma: no cover - exercised via to_thread
        with self._lock:
            self.calls += 1
            if self._responses:
                return self._responses.popleft()
        return "", None, {}

    def queue(self, response: tuple[str, float | None, dict[str, float]]) -> None:
        with self._lock:
            self._responses.append(response)


@dataclass
class FakeSuppressionState:
    cooldown_until: float = 0.0


class FakeSuppressionEngine:
    def __init__(self, *, accept: bool = True, reasons: list[str] | None = None) -> None:
        self.state = FakeSuppressionState()
        self.accept = accept
        self.reasons = reasons or []
        self.registered: list[str] = []
        self.last_evaluated: list[str] = []

    def evaluate(
        self,
        text: str,
        confidence: float | None,
        metrics: dict[str, float],
        utterance: bytes,
        sample_rate: int,
        frame_size: int,
    ) -> tuple[bool, dict[str, object]]:
        self.last_evaluated.append(text)
        if self.accept:
            return True, {}
        return False, {"reasons": list(self.reasons)}

    def register_publication(self, norm_text: str) -> None:
        self.registered.append(norm_text)


def _make_service(
    *,
    vad: FakeVAD,
    transcriber: FakeTranscriber,
    suppression: FakeSuppressionEngine,
    partials: PartialSettings,
    sample_rate: int = 16000,
    frame_size: int = 320,
) -> STTService:
    config = STTServiceConfig(
        post_publish_cooldown_ms=1500,
        preprocess_min_ms=0,
        partials=partials,
    )
    return STTService(
        vad=vad,
        transcriber=transcriber,
        suppression=suppression,
        sample_rate=sample_rate,
        frame_size=frame_size,
        config=config,
        preprocess=None,
    )


@pytest.mark.asyncio
async def test_process_chunk_accepts_candidate_sets_cooldown():
    vad = FakeVAD()
    utterance = b"\x01\x00" * 4000
    vad.queue_utterance(utterance)
    transcriber = FakeTranscriber([
        ("Hello World", 0.92, {"avg_no_speech_prob": 0.05}),
    ])
    suppression = FakeSuppressionEngine(accept=True)
    service = _make_service(
        vad=vad,
        transcriber=transcriber,
        suppression=suppression,
        partials=PartialSettings(enabled=False, min_duration_ms=0, min_chars=0, min_new_chars=0, alpha_ratio_min=0.0),
    )

    result = await service.process_chunk(b"\x00" * 640, now=100.0)

    assert result.final is not None
    assert result.final.text == "Hello World"
    assert result.confidence == pytest.approx(0.92)
    assert suppression.registered == ["hello world"]
    assert suppression.state.cooldown_until > 100.0
    assert service.in_cooldown(now=100.1) is True


@pytest.mark.asyncio
async def test_process_chunk_rejected_returns_reasons():
    vad = FakeVAD()
    vad.queue_utterance(b"\x01\x00" * 4000)
    transcriber = FakeTranscriber([
        ("Noisy", 0.4, {}),
    ])
    suppression = FakeSuppressionEngine(accept=False, reasons=["noise"])
    service = _make_service(
        vad=vad,
        transcriber=transcriber,
        suppression=suppression,
        partials=PartialSettings(enabled=False, min_duration_ms=0, min_chars=0, min_new_chars=0, alpha_ratio_min=0.0),
    )

    result = await service.process_chunk(b"\x00" * 640, now=10.0)

    assert result.final is None
    assert result.candidate_text == "Noisy"
    assert result.rejection_reasons == ("noise",)
    assert suppression.registered == []
    assert suppression.state.cooldown_until == 0.0


@pytest.mark.asyncio
async def test_maybe_partial_streaming_thresholds_and_deltas():
    sample_rate = 16000
    vad = FakeVAD()
    buffer_bytes = (b"\x01\x00" * int(sample_rate * 0.25))
    vad.set_active(buffer_bytes, is_speech=True)
    transcriber = FakeTranscriber([
        ("hello there", 0.6, {}),
        ("hello there", 0.6, {}),
        ("hello there friend", 0.6, {}),
    ])
    suppression = FakeSuppressionEngine()
    partials = PartialSettings(enabled=True, min_duration_ms=100, min_chars=4, min_new_chars=2, alpha_ratio_min=0.5)
    service = _make_service(
        vad=vad,
        transcriber=transcriber,
        suppression=suppression,
        partials=partials,
    )

    first = await service.maybe_partial()
    assert first is not None
    assert first.text == "hello there"

    second = await service.maybe_partial()
    assert second is None  # unchanged text rejected

    vad.set_active(buffer_bytes + b"\x02\x00" * 100, is_speech=True)
    third = await service.maybe_partial()
    assert third is not None
    assert third.text == "hello there friend"


@pytest.mark.asyncio
async def test_final_transcript_resets_partial_history():
    sample_rate = 16000
    vad = FakeVAD()
    buffer_bytes = (b"\x01\x00" * int(sample_rate * 0.2))
    vad.set_active(buffer_bytes, is_speech=True)
    utterance = b"\x01\x00" * 4000
    vad.queue_utterance(utterance)

    transcriber = FakeTranscriber([
        ("hello again", 0.5, {}),
        ("HELLO AGAIN", 0.9, {}),
        ("hello again", 0.6, {}),
    ])
    suppression = FakeSuppressionEngine(accept=True)
    partials = PartialSettings(enabled=True, min_duration_ms=100, min_chars=4, min_new_chars=2, alpha_ratio_min=0.5)
    service = _make_service(
        vad=vad,
        transcriber=transcriber,
        suppression=suppression,
        partials=partials,
    )

    partial_before = await service.maybe_partial()
    assert partial_before is not None
    assert partial_before.text == "hello again"

    # Publish final transcript; partial buffer should reset
    result = await service.process_chunk(b"\x00" * 640, now=5.0)
    assert result.final is not None

    vad.set_active(buffer_bytes, is_speech=True)
    partial_after = await service.maybe_partial()
    assert partial_after is not None
    assert partial_after.text == "hello again"
