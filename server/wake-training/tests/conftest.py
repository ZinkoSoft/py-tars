import io
import math
from pathlib import Path
import wave
from typing import Callable

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _load_app() -> FastAPI:
    from importlib import reload

    import wake_training.main as main

    reload(main)
    return main.app

SAMPLE_RATE = 16_000


def _build_waveform(
    *,
    freq: float,
    duration: float,
    amplitude: float,
    noise: bool,
    seed: int | None,
) -> np.ndarray:
    total_samples = int(SAMPLE_RATE * duration)
    if total_samples <= 0:
        raise ValueError("Duration must be positive")
    if noise:
        rng = np.random.default_rng(seed)
        waveform = rng.normal(0.0, amplitude, total_samples)
    else:
        t = np.linspace(0.0, duration, total_samples, endpoint=False)
        waveform = amplitude * np.sin(2 * math.pi * freq * t)
    waveform = np.clip(waveform, -1.0, 1.0)
    return waveform.astype(np.float32)


def _waveform_to_bytes(waveform: np.ndarray) -> io.BytesIO:
    samples = np.clip(waveform * 32767.0, -32768, 32767).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(samples.tobytes())
    buffer.seek(0)
    return buffer


@pytest.fixture
def make_wav() -> Callable[..., io.BytesIO]:
    def _make_wav(
        *,
        freq: float = 440.0,
        duration: float = 1.0,
        amplitude: float = 0.4,
        noise: bool = False,
        seed: int | None = None,
    ) -> io.BytesIO:
        waveform = _build_waveform(
            freq=freq,
            duration=duration,
            amplitude=amplitude,
            noise=noise,
            seed=seed,
        )
        return _waveform_to_bytes(waveform)

    return _make_wav


@pytest.fixture
def client(monkeypatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("WAKE_TRAINING_DATA_DIR", str(tmp_path))
    app = _load_app()
    return TestClient(app)
