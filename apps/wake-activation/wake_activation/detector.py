from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Deque, Optional, Protocol, TYPE_CHECKING, runtime_checkable
import logging

import numpy as np
from numpy.typing import NDArray

from .npu_utils import check_npu_availability, log_npu_status

logger = logging.getLogger(__name__)

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

try:  # pragma: no cover - NPU support is optional
    from rknnlite.api import RKNNLite
except Exception:  # pragma: no cover - NPU not available
    RKNNLite = None  # type: ignore[assignment]


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
    effective_threshold: Optional[float] = None


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


class _RKNNBackend:
    """NPU-accelerated backend using RKNN Lite2 for RK3588."""

    def __init__(self, model_path: str, core_mask: int = 0) -> None:
        if RKNNLite is None:
            raise DetectorUnavailableError("rknn-toolkit-lite2 is not installed. Install it to enable NPU acceleration.")
        
        self._rknn = RKNNLite()
        self._model_path = model_path
        self._core_mask = core_mask
        self._is_initialized = False
        
        # Load and initialize the RKNN model
        ret = self._rknn.load_rknn(model_path)
        if ret != 0:
            raise DetectorUnavailableError(f"Failed to load RKNN model from {model_path}")
        
        # Initialize runtime with specified NPU cores
        ret = self._rknn.init_runtime(core_mask=core_mask)
        if ret != 0:
            self._rknn.release()
            raise DetectorUnavailableError(f"Failed to initialize RKNN runtime with core mask {core_mask}")
        
        self._is_initialized = True

    @property
    def frame_samples(self) -> int:
        return _FRAME_SAMPLES

    @property
    def sample_rate(self) -> int:
        return _SAMPLE_RATE

    def process(self, frame: NDArray[np.int16]) -> float:
        if not self._is_initialized:
            return 0.0
        
        # Convert int16 frame to float32 and normalize to [-1, 1] range
        # This matches the expected input format for most RKNN wake word models
        frame_float = frame.astype(np.float32) / _INT16_MAX
        
        # Ensure proper shape for RKNN inference (add batch dimension if needed)
        if frame_float.ndim == 1:
            frame_float = frame_float.reshape(1, -1)
        
        try:
            # Run inference on NPU
            outputs = self._rknn.inference(inputs=[frame_float])
            if outputs and len(outputs) > 0:
                # Assume single output with wake word probability
                prediction = outputs[0]
                if prediction.ndim > 0:
                    return float(prediction.flatten()[0])
                return float(prediction)
            return 0.0
        except Exception:
            # Fallback gracefully on NPU inference errors
            return 0.0

    def reset(self) -> None:
        # RKNN doesn't require explicit reset, but we could reinitialize if needed
        pass

    def __del__(self) -> None:
        if hasattr(self, '_rknn') and self._is_initialized:
            try:
                self._rknn.release()
            except Exception:
                pass  # Ignore cleanup errors


class WakeDetector:
    """Stateful wake-word detector with retrigger and energy tracking."""

    def __init__(
        self,
        backend: WakeBackend,
        *,
        threshold: float,
        min_retrigger_sec: float,
        energy_window_ms: int,
        energy_boost_factor: float = 1.0,
        low_energy_threshold_factor: float = 0.8,
        background_noise_sensitivity: bool = False,
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
        
        # Enhanced sensitivity settings
        self._energy_boost_factor = max(0.1, energy_boost_factor)
        self._low_energy_threshold_factor = max(0.1, min(1.0, low_energy_threshold_factor))
        self._background_noise_sensitivity = background_noise_sensitivity
        self._recent_energy_history: Deque[float] = deque(maxlen=50)  # Track energy for adaptive thresholds

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
        self._recent_energy_history.clear()

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

        # Adaptive threshold based on energy and environment
        current_energy = self.current_energy
        self._recent_energy_history.append(current_energy)
        
        # Calculate adaptive threshold
        effective_threshold = self._calculate_adaptive_threshold(max_score, current_energy)

        if max_score < effective_threshold:
            return None

        if self._last_trigger_ts is not None and ts - self._last_trigger_ts < self._min_retrigger_sec:
            return None

        self._last_trigger_ts = ts
        # Apply energy boost to reported energy for better UI feedback
        reported_energy = current_energy * self._energy_boost_factor
        return DetectionResult(
            score=max_score, 
            energy=reported_energy, 
            ts=ts, 
            effective_threshold=effective_threshold
        )

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

    def _calculate_adaptive_threshold(self, score: float, current_energy: float) -> float:
        """Calculate adaptive threshold based on energy and environmental conditions."""
        base_threshold = self._threshold
        
        if not self._background_noise_sensitivity:
            return base_threshold
            
        # If we have enough energy history, adapt threshold
        if len(self._recent_energy_history) < 10:
            return base_threshold
            
        # Calculate recent average energy
        recent_energies = list(self._recent_energy_history)
        avg_energy = sum(recent_energies) / len(recent_energies)
        
        # For low energy environments, lower the threshold
        if current_energy < avg_energy * 0.5:  # Current energy is much lower than average
            adapted_threshold = base_threshold * self._low_energy_threshold_factor
        else:
            adapted_threshold = base_threshold
            
        # Additional boost for very confident scores in low energy
        if score > 0.7 and current_energy < avg_energy * 0.3:
            adapted_threshold *= 0.8  # Even more sensitive for high confidence in quiet environments
            
        return max(0.1, adapted_threshold)  # Never go below 0.1


def create_wake_detector(
    model_path: Path,
    *,
    threshold: float,
    min_retrigger_sec: float,
    energy_window_ms: int,
    enable_speex_noise_suppression: bool,
    vad_threshold: float,
    energy_boost_factor: float = 1.0,
    low_energy_threshold_factor: float = 0.8,
    background_noise_sensitivity: bool = False,
    use_npu: bool = False,
    npu_core_mask: int = 0,
) -> WakeDetector:
    """Create a wake detector with optional NPU acceleration.
    
    Args:
        model_path: Path to the wake word model (.tflite for CPU, .rknn for NPU)
        threshold: Detection threshold (0.0-1.0)
        min_retrigger_sec: Minimum time between detections
        energy_window_ms: Energy window for adaptive thresholds
        enable_speex_noise_suppression: Enable Speex noise suppression (CPU only)
        vad_threshold: VAD threshold (CPU only)
        energy_boost_factor: Energy boost for UI feedback
        low_energy_threshold_factor: Threshold reduction in low energy
        background_noise_sensitivity: Enable adaptive thresholds
        use_npu: Use NPU acceleration if available
        npu_core_mask: NPU core mask (0=auto, 1=core0, 2=core1, 4=core2, 7=all cores)
    
    Returns:
        Configured WakeDetector instance
    
    Raises:
        DetectorUnavailableError: If the requested backend is not available
    """
    if use_npu:
        # Check NPU availability and log status
        npu_available, status = check_npu_availability()
        if not npu_available:
            logger.warning("NPU requested but not available, falling back to CPU")
            logger.debug(f"NPU status: {status}")
            # Fall back to CPU with original model path if NPU model doesn't exist
            fallback_path = model_path.with_suffix('.tflite') if model_path.suffix == '.rknn' else model_path
            return create_cpu_wake_detector(
                model_path=fallback_path,
                threshold=threshold,
                min_retrigger_sec=min_retrigger_sec,
                energy_window_ms=energy_window_ms,
                enable_speex_noise_suppression=enable_speex_noise_suppression,
                vad_threshold=vad_threshold,
                energy_boost_factor=energy_boost_factor,
                low_energy_threshold_factor=low_energy_threshold_factor,
                background_noise_sensitivity=background_noise_sensitivity,
            )
        else:
            logger.info("NPU available, using NPU acceleration for wake detection")
            return create_npu_wake_detector(
                model_path=model_path,
                threshold=threshold,
                min_retrigger_sec=min_retrigger_sec,
                energy_window_ms=energy_window_ms,
                energy_boost_factor=energy_boost_factor,
                low_energy_threshold_factor=low_energy_threshold_factor,
                background_noise_sensitivity=background_noise_sensitivity,
                npu_core_mask=npu_core_mask,
            )
    else:
        return create_cpu_wake_detector(
            model_path=model_path,
            threshold=threshold,
            min_retrigger_sec=min_retrigger_sec,
            energy_window_ms=energy_window_ms,
            enable_speex_noise_suppression=enable_speex_noise_suppression,
            vad_threshold=vad_threshold,
            energy_boost_factor=energy_boost_factor,
            low_energy_threshold_factor=low_energy_threshold_factor,
            background_noise_sensitivity=background_noise_sensitivity,
        )


def create_cpu_wake_detector(
    model_path: Path,
    *,
    threshold: float,
    min_retrigger_sec: float,
    energy_window_ms: int,
    enable_speex_noise_suppression: bool,
    vad_threshold: float,
    energy_boost_factor: float = 1.0,
    low_energy_threshold_factor: float = 0.8,
    background_noise_sensitivity: bool = False,
) -> WakeDetector:
    """Create a CPU-based wake detector using openWakeWord."""

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
            enable_speex_noise_suppression=enable_speex_noise_suppression,
            vad_threshold=vad_threshold,
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
        energy_boost_factor=energy_boost_factor,
        low_energy_threshold_factor=low_energy_threshold_factor,
        background_noise_sensitivity=background_noise_sensitivity,
    )


def create_npu_wake_detector(
    model_path: Path,
    *,
    threshold: float,
    min_retrigger_sec: float,
    energy_window_ms: int,
    energy_boost_factor: float = 1.0,
    low_energy_threshold_factor: float = 0.8,
    background_noise_sensitivity: bool = False,
    npu_core_mask: int = 0,
) -> WakeDetector:
    """Create an NPU-accelerated wake detector using RKNN.
    
    Args:
        model_path: Path to .rknn model file
        threshold: Detection threshold
        min_retrigger_sec: Minimum time between detections  
        energy_window_ms: Energy window for adaptive thresholds
        energy_boost_factor: Energy boost for UI feedback
        low_energy_threshold_factor: Threshold reduction in low energy
        background_noise_sensitivity: Enable adaptive thresholds
        npu_core_mask: NPU core selection (0=auto, 1-7=specific cores)
    
    Returns:
        WakeDetector using NPU backend
        
    Raises:
        DetectorUnavailableError: If NPU is not available or model loading fails
    """
    if not model_path.exists():
        raise DetectorUnavailableError(f"RKNN model not found at {model_path}")
    
    if model_path.suffix.lower() != ".rknn":
        raise DetectorUnavailableError(f"Expected .rknn model, got {model_path.suffix}")

    backend = _RKNNBackend(str(model_path), npu_core_mask)
    return WakeDetector(
        backend,
        threshold=threshold,
        min_retrigger_sec=min_retrigger_sec,
        energy_window_ms=energy_window_ms,
        energy_boost_factor=energy_boost_factor,
        low_energy_threshold_factor=low_energy_threshold_factor,
        background_noise_sensitivity=background_noise_sensitivity,
    )
