from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

try:  # pragma: no cover - optional dependency guard
    import torch
except ModuleNotFoundError as exc:  # pragma: no cover - handled in ensure_torch
    torch = None  # type: ignore[assignment]
    _TORCH_IMPORT_ERROR = exc
else:  # pragma: no cover - ensure symbol exists even with coverage skips
    _TORCH_IMPORT_ERROR = None

from .trainer import TrainingConfig, _WakeWordNet, _load_waveform


class InferenceError(RuntimeError):
    """Raised when wake-word inference cannot be performed."""


@dataclass
class InferenceResult:
    probability: float
    threshold: float
    logits: float
    is_wake: bool
    sample_rate: int
    clip_duration_sec: float
    trained_at: str | None
    best_epoch: int | None


def run_clip_inference(model_path: Path, clip_path: Path) -> InferenceResult:
    """Evaluate a single clip against a trained wake-word model.

    Args:
        model_path: Path to the exported ``wake_model.pt`` artifact produced by training.
        clip_path: Path to the WAV clip to score.

    Returns:
        InferenceResult containing probability, logits, and decision metadata.

    Raises:
        InferenceError: When the model artifact is missing, malformed, or PyTorch is unavailable.
    """

    _ensure_torch()

    if not model_path.exists():
        raise InferenceError(f"Model artifact not found: {model_path}")
    if not clip_path.exists():
        raise InferenceError(f"Clip not found: {clip_path}")

    try:
        checkpoint = torch.load(model_path, map_location="cpu")  # type: ignore[union-attr]
    except Exception as exc:  # pragma: no cover - Torch surface
        raise InferenceError(f"Failed to load model checkpoint: {model_path.name}") from exc

    config_data = checkpoint.get("config") or checkpoint.get("hyperparameters")
    if not config_data:
        raise InferenceError("Model checkpoint missing training configuration")

    try:
        config = TrainingConfig.model_validate(config_data)
    except Exception as exc:
        raise InferenceError("Invalid training configuration in checkpoint") from exc

    threshold = float(checkpoint.get("threshold", config.threshold))
    state_dict = checkpoint.get("state_dict")
    if not isinstance(state_dict, dict):
        raise InferenceError("Model checkpoint missing state_dict")

    waveform = _load_waveform(clip_path, config)
    tensor = torch.from_numpy(np.asarray(waveform, dtype=np.float32)).unsqueeze(0).unsqueeze(0)  # type: ignore[union-attr]

    model = _WakeWordNet()
    try:
        model.load_state_dict(state_dict)
    except Exception as exc:  # pragma: no cover - surface torch error
        raise InferenceError("Failed to load model weights from checkpoint") from exc
    model.eval()

    with torch.no_grad():  # type: ignore[union-attr]
        logits_tensor = model(tensor).squeeze()
        logits = float(logits_tensor.item())

    probability = 1.0 / (1.0 + math.exp(-logits))
    is_wake = probability >= threshold

    trained_at_raw = checkpoint.get("trained_at")
    trained_at = str(trained_at_raw) if trained_at_raw is not None else None

    best_epoch_raw = checkpoint.get("best_epoch")
    best_epoch: int | None
    if isinstance(best_epoch_raw, (int, float)):
        best_epoch = int(best_epoch_raw)
    elif isinstance(best_epoch_raw, str) and best_epoch_raw.isdigit():
        best_epoch = int(best_epoch_raw)
    else:
        best_epoch = None

    return InferenceResult(
        probability=probability,
        threshold=threshold,
        logits=logits,
        is_wake=is_wake,
        sample_rate=config.sample_rate,
        clip_duration_sec=config.clip_duration_sec,
        trained_at=trained_at,
        best_epoch=best_epoch,
    )


def _ensure_torch() -> None:
    if torch is None:  # pragma: no cover - dependent on runtime optional dep
        raise InferenceError(
            "Wake-word inference requires the 'torch' package. Install torch to enable inference.",
        ) from _TORCH_IMPORT_ERROR
