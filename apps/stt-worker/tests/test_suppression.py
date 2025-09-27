from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

SRC_DIR = Path(__file__).resolve().parents[3] / "src"
if SRC_DIR.exists():
    src_path = str(SRC_DIR)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

from tars.contracts.v1.stt import FinalTranscript  # type: ignore[import]

SAMPLE_RATE = 16_000
FRAME_SIZE = 320


def _load_suppression_module() -> ModuleType:
    module_name = "stt_worker_suppression_test"
    if module_name in sys.modules:
        return sys.modules[module_name]
    module_path = Path(__file__).resolve().parents[1] / "suppression.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore[assignment]
    return module


def _pcm_constant(value: int, duration_ms: int, sample_rate: int = SAMPLE_RATE) -> bytes:
    samples = int(sample_rate * duration_ms / 1000)
    arr = np.full(samples, value, dtype=np.int16)
    return arr.tobytes()


def _pcm_silence(duration_ms: int, sample_rate: int = SAMPLE_RATE) -> bytes:
    samples = int(sample_rate * duration_ms / 1000)
    return bytes(samples * 2)


def test_rejects_short_low_energy_clip():
    suppression = _load_suppression_module()
    state = suppression.SuppressionState()
    engine = suppression.SuppressionEngine(state)

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
    suppression = _load_suppression_module()
    state = suppression.SuppressionState()
    engine = suppression.SuppressionEngine(state)

    timeline = {"now": 1000.0}

    def _now() -> float:
        return timeline["now"]

    monkeypatch.setattr(suppression.time, "time", _now)

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
    suppression = _load_suppression_module()
    state = suppression.SuppressionState()
    state.last_tts_text = "Thank you"
    engine = suppression.SuppressionEngine(state)

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
