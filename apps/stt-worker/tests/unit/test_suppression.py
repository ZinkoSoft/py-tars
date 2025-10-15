from __future__ import annotations

import numpy as np

from tars.contracts.v1.stt import FinalTranscript  # type: ignore[import]
from stt_worker.suppression import SuppressionState  # Import directly

SAMPLE_RATE = 16_000
FRAME_SIZE = 320


def _pcm_constant(value: int, duration_ms: int, sample_rate: int = SAMPLE_RATE) -> bytes:
    samples = int(sample_rate * duration_ms / 1000)
    arr = np.full(samples, value, dtype=np.int16)
    return arr.tobytes()


def _pcm_silence(duration_ms: int, sample_rate: int = SAMPLE_RATE) -> bytes:
    samples = int(sample_rate * duration_ms / 1000)
    return bytes(samples * 2)


def test_rejects_short_low_energy_clip():
    state = SuppressionState()
    from stt_worker.suppression import SuppressionEngine

    engine = SuppressionEngine(state)

    utterance = _pcm_silence(duration_ms=120)  # shorter and quieter than noise gates
    accepted, info = engine.evaluate(
        "hi",
        confidence=0.2,
        metrics={},
        utterance=utterance,
        sample_rate=SAMPLE_RATE,
        frame_size=FRAME_SIZE,
    )

    assert accepted is False
    reasons = info.get("reasons", [])
    assert any("dur" in reason for reason in reasons)
    assert any("rms" in reason for reason in reasons)


def test_accept_then_blocks_recent_repeat(monkeypatch):
    import time as time_module
    from stt_worker.suppression import SuppressionEngine

    state = SuppressionState()
    engine = SuppressionEngine(state)

    timeline = {"now": 1000.0}

    def _now() -> float:
        return timeline["now"]

    monkeypatch.setattr(time_module, "time", _now)

    metrics = {"avg_no_speech_prob": 0.05, "avg_logprob": -0.4}
    utterance = _pcm_constant(1500, duration_ms=800)

    text = "Hello friend"
    accepted, info = engine.evaluate(
        text,
        confidence=0.96,
        metrics=metrics,
        utterance=utterance,
        sample_rate=SAMPLE_RATE,
        frame_size=FRAME_SIZE,
    )

    assert accepted is True
    transcript = FinalTranscript(text=text, confidence=0.96)
    assert transcript.text == text

    engine.register_publication(info["norm_text"])

    timeline["now"] += 1.0
    accepted_again, info_again = engine.evaluate(
        text,
        confidence=0.94,
        metrics=metrics,
        utterance=utterance,
        sample_rate=SAMPLE_RATE,
        frame_size=FRAME_SIZE,
    )

    assert accepted_again is False
    reasons = set(info_again.get("reasons", []))
    assert {"repeat_last_published", "recent_repeat"} & reasons


def test_exact_echo_rejected():
    from stt_worker.suppression import SuppressionEngine

    state = SuppressionState()
    state.last_tts_text = "Thank you"
    engine = SuppressionEngine(state)

    metrics = {"avg_no_speech_prob": 0.05, "avg_logprob": -0.3}
    utterance = _pcm_constant(1600, duration_ms=900)

    accepted, info = engine.evaluate(
        "Thank you",
        confidence=0.9,
        metrics=metrics,
        utterance=utterance,
        sample_rate=SAMPLE_RATE,
        frame_size=FRAME_SIZE,
    )

    assert accepted is False
    assert "exact_echo" in info.get("reasons", [])
