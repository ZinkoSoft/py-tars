from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Deque, Optional, Protocol, TYPE_CHECKING, runtime_checkable

import numpy as np
from numpy.typing import NDArray

__all__ = [
    "DetectorUnavailableError",
    "DetectionResult",
    "WakeDetector",
    "create_wake_detector",
]

OpenWakeWordModel = Any

if TYPE_CHECKING:  # pragma: no cover - typing-only import
    try:
        from openwakeword.model import Model as OpenWakeWordModel
    except Exception:  # pragma: no cover - optional dependency not installed during type checking
        pass


try:  # pragma: no cover - handled via optional dependency
    from openwakeword import Model as RuntimeOpenWakeWordModel
except Exception:  # pragma: no cover - import failure path tested via unit tests
    RuntimeOpenWakeWordModel = None  # type: ignore[assignment]


_FRAME_SAMPLES = 1280
_SAMPLE_RATE = 16_000
_INT16_MAX = 32767.0


class DetectorUnavailableError(RuntimeError):
    """Raised when the wake detector cannot be created."""


@dataclass(slots=True)
class DetectionResult:
    """Represents a positive wake detection."""

    score: float
    energy: float
    ts: float


@runtime_checkable
class WakeBackend(Protocol):
    @property
    def frame_samples(self) -> int: ...

    @property
    def sample_rate(self) -> int: ...

    def process(self, frame: NDArray[np.int16]) -> float: ...

    def reset(self) -> None: ...


class _OpenWakeWordBackend:
    """Thin wrapper around the openWakeWord model."""

    def __init__(self, model: Any, label: str) -> None:
        self._model = model
        self._label = label

    @property
    def frame_samples(self) -> int:
        return _FRAME_SAMPLES

    @property
    def sample_rate(self) -> int:
        return _SAMPLE_RATE

    def process(self, frame: NDArray[np.int16]) -> float:
        predictions = self._model.predict(frame)
        return float(predictions.get(self._label, 0.0))

    def reset(self) -> None:
        self._model.reset()


class WakeDetector:
    """Stateful wake-word detector with retrigger and energy tracking."""

    def __init__(
        self,
        backend: WakeBackend,
        *,
        threshold: float,
        min_retrigger_sec: float,
        energy_window_ms: int,
    ) -> None:
        self._backend = backend
        self._threshold = threshold
        self._min_retrigger_sec = max(0.0, min_retrigger_sec)
        self._energy_window_samples = max(
            backend.frame_samples,
            int(max(1, energy_window_ms) * backend.sample_rate / 1000),
        )
        self._byte_buffer = bytearray()
        self._frame_bytes = backend.frame_samples * 2
        self._last_trigger_ts: Optional[float] = None

        self._energy_samples = 0
        self._energy_sum_sq = 0.0
        self._energy_window: Deque[tuple[int, float]] = deque()

    @property
    def frame_samples(self) -> int:
        return self._backend.frame_samples

    @property
    def sample_rate(self) -> int:
        return self._backend.sample_rate

    def reset(self) -> None:
        self._backend.reset()
        self._byte_buffer.clear()
        self._last_trigger_ts = None
        self._energy_samples = 0
        self._energy_sum_sq = 0.0
        self._energy_window.clear()

    def process_frame(self, frame: NDArray[np.float32], *, ts: float) -> Optional[DetectionResult]:
        """Process a normalized audio frame; return detection when threshold is met."""

        if frame.ndim != 1:
            raise ValueError("Audio frame must be one-dimensional")

        self._accumulate_energy(frame)
        self._enqueue_frame(frame)

        max_score: Optional[float] = None
        while len(self._byte_buffer) >= self._frame_bytes:
            chunk_bytes = self._byte_buffer[: self._frame_bytes]
            del self._byte_buffer[: self._frame_bytes]
            chunk = np.frombuffer(chunk_bytes, dtype=np.int16)
            score = float(self._backend.process(chunk))
            if max_score is None or score > max_score:
                max_score = score

        if max_score is None:
            return None

        if max_score < self._threshold:
            return None

        if self._last_trigger_ts is not None and ts - self._last_trigger_ts < self._min_retrigger_sec:
            return None

        self._last_trigger_ts = ts
        return DetectionResult(score=max_score, energy=self.current_energy, ts=ts)

    @property
    def current_energy(self) -> float:
        if self._energy_samples == 0:
            return 0.0
        return math.sqrt(self._energy_sum_sq / self._energy_samples)

    def _accumulate_energy(self, frame: NDArray[np.float32]) -> None:
        samples = frame.size
        power = float(np.dot(frame, frame))
        self._energy_window.append((samples, power))
        self._energy_samples += samples
        self._energy_sum_sq += power
        while self._energy_samples > self._energy_window_samples:
            old_samples, old_power = self._energy_window.popleft()
            self._energy_samples -= old_samples
            self._energy_sum_sq -= old_power

    def _enqueue_frame(self, frame: NDArray[np.float32]) -> None:
        clipped = np.clip(frame, -1.0, 1.0)
        int_frame = np.rint(clipped * _INT16_MAX).astype(np.int16)
        self._byte_buffer.extend(int_frame.tobytes())


def create_wake_detector(
    model_path: Path,
    *,
    threshold: float,
    min_retrigger_sec: float,
    energy_window_ms: int,
) -> WakeDetector:
    """Create a wake detector backed by openWakeWord."""

    if RuntimeOpenWakeWordModel is None:
        raise DetectorUnavailableError(
            "openwakeword is not installed. Install the 'openwakeword' extra to enable wake detection."
        )

    if not model_path.exists():
        raise DetectorUnavailableError(f"Wake model not found at {model_path}")

    inference_framework = "onnx" if model_path.suffix.lower() == ".onnx" else "tflite"

    try:
        model = RuntimeOpenWakeWordModel(
            wakeword_models=[str(model_path)],
            inference_framework=inference_framework,
            enable_speex_noise_suppression=False,
            vad_threshold=0,
        )
    except ValueError as exc:  # pragma: no cover - depends on environment packages
        raise DetectorUnavailableError(str(exc)) from exc

    label = next(iter(model.models.keys()))

    backend = _OpenWakeWordBackend(model, label)
    return WakeDetector(
        backend,
        threshold=threshold,
        min_retrigger_sec=min_retrigger_sec,
        energy_window_ms=energy_window_ms,
    )
