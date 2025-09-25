from __future__ import annotations

import copy
import json
import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Sequence

import numpy as np
import soundfile as sf
import torch
from pydantic import BaseModel, Field
from scipy.signal import resample_poly
from torch import nn
from torch.utils.data import DataLoader, Dataset


class TrainingError(RuntimeError):
    """Raised when training cannot proceed due to invalid input or runtime failures."""


class TrainingConfig(BaseModel):
    sample_rate: int = Field(default=16_000, ge=8_000, le=48_000)
    clip_duration_sec: float = Field(default=1.5, ge=0.5, le=4.0)
    batch_size: int = Field(default=16, ge=1, le=256)
    epochs: int = Field(default=25, ge=1, le=200)
    learning_rate: float = Field(default=1e-3, gt=0.0)
    weight_decay: float = Field(default=1e-4, ge=0.0)
    validation_split: float = Field(default=0.2, gt=0.0, lt=0.5)
    noise_mix_prob: float = Field(default=0.3, ge=0.0, le=1.0)
    noise_mix_level: float = Field(default=0.2, ge=0.0, le=1.0)
    amplitude_jitter: float = Field(default=0.15, ge=0.0, le=0.75)
    time_shift_ms: float = Field(default=100.0, ge=0.0, le=250.0)
    patience: int = Field(default=5, ge=1, le=25)
    num_workers: int = Field(default=0, ge=0, le=4)
    threshold: float = Field(default=0.5, ge=0.05, le=0.95)
    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    device: str = Field(default="auto")

    @property
    def clip_samples(self) -> int:
        return int(self.sample_rate * self.clip_duration_sec)


@dataclass
class TrainingResult:
    export_dir: Path
    metrics: dict[str, float]
    artifact_paths: dict[str, str]
    threshold: float
    config: dict
    best_epoch: int

    def metadata(self) -> dict:
        return {
            "export_dir": str(self.export_dir),
            "metrics": self.metrics,
            "threshold": self.threshold,
            "artifacts": self.artifact_paths,
            "hyperparameters": self.config,
            "best_epoch": self.best_epoch,
        }


@dataclass
class _AudioExample:
    waveform: np.ndarray
    label: int


class _WakeWordDataset(Dataset[tuple[torch.Tensor, torch.Tensor]]):
    def __init__(
        self,
        examples: Sequence[_AudioExample],
        config: TrainingConfig,
        augment: bool,
        noise_bank: Sequence[np.ndarray],
    ) -> None:
        self._examples = list(examples)
        self._config = config
        self._augment = augment
        self._noise_bank = list(noise_bank)

    def __len__(self) -> int:
        return len(self._examples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        example = self._examples[index]
        waveform = example.waveform.copy()
        if self._augment:
            waveform = _augment_waveform(
                waveform,
                self._config,
                self._noise_bank,
            )
        tensor = torch.from_numpy(waveform).unsqueeze(0)
        label = torch.tensor(float(example.label), dtype=torch.float32)
        return tensor, label


def run_training_job(
    *,
    dataset_dir: Path,
    job_dir: Path,
    dataset_name: str,
    overrides: dict | None,
    log: Callable[[str], None],
) -> TrainingResult:
    """Execute the full wake-word training pipeline.

    Args:
        dataset_dir: Directory containing dataset clips/labels.
        job_dir: Job working directory (artifacts will be written under export/).
        dataset_name: Name of the dataset, used in metadata.
        overrides: Optional config overrides supplied by the API request.
        log: Callback used to append progress updates.

    Returns:
        TrainingResult describing exported artifacts and evaluation metrics.
    """

    config = _resolve_config(overrides)
    random.seed(config.seed)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    if torch.cuda.is_available():  # pragma: no cover - depends on GPU availability
        torch.cuda.manual_seed_all(config.seed)
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

    device = _select_device(config.device)
    log(
        "Using device %s (CUDA available=%s)" %
        (device.type,
         torch.cuda.is_available()),
    )

    log("Loading dataset for training")
    examples, noise_bank = _load_dataset(dataset_dir, config)
    total = len(examples)
    positives = sum(int(item.label == 1) for item in examples)
    negatives = total - positives
    if positives == 0 or negatives == 0:
        raise TrainingError(
            "Dataset must include at least one positive and one negative/noise clip",
        )
    if total < 8:
        raise TrainingError(
            "Dataset is too small for training; add more clips (min 8 including both classes).",
        )
    log(
        f"Dataset ready with {total} clips (positives={positives}, negatives={negatives})",
    )

    train_set, val_set = _train_val_split(examples, config.validation_split, config.seed)
    log(
        "Split into %s training and %s validation clips"
        % (len(train_set), len(val_set)),
    )

    if not train_set or not val_set:
        raise TrainingError(
            "Unable to create non-empty train/validation splits; add more data.",
        )

    train_dataset = _WakeWordDataset(train_set, config, augment=True, noise_bank=noise_bank)
    val_dataset = _WakeWordDataset(val_set, config, augment=False, noise_bank=noise_bank)

    train_loader = DataLoader(
        train_dataset,
        batch_size=min(config.batch_size, len(train_dataset)),
        shuffle=True,
        num_workers=config.num_workers,
        drop_last=False,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=min(config.batch_size, len(val_dataset)),
        shuffle=False,
        num_workers=config.num_workers,
        drop_last=False,
    )

    model = _WakeWordNet()
    model.to(device)

    pos_count = sum(int(item.label == 1) for item in train_set)
    neg_count = len(train_set) - pos_count
    pos_weight = torch.tensor(
        max(neg_count, 1) / max(pos_count, 1),
        dtype=torch.float32,
        device=device,
    )
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )

    best_state = copy.deepcopy(model.state_dict())
    best_metrics: dict[str, float] | None = None
    best_epoch = 0
    best_score = -math.inf
    epochs_without_improve = 0

    for epoch in range(config.epochs):
        train_loss, train_acc = _train_one_epoch(
            model,
            criterion,
            optimizer,
            train_loader,
            device,
            config.threshold,
        )
        val_metrics = _evaluate(model, criterion, val_loader, device, config.threshold)
        log(
            "Epoch %d/%d: train_loss=%.4f train_acc=%.3f val_loss=%.4f val_acc=%.3f bal_acc=%.3f"
            % (
                epoch + 1,
                config.epochs,
                train_loss,
                train_acc,
                val_metrics["loss"],
                val_metrics["accuracy"],
                val_metrics["balanced_accuracy"],
            ),
        )

        score = val_metrics["balanced_accuracy"]
        if score > best_score:
            best_score = score
            best_state = copy.deepcopy(model.state_dict())
            best_metrics = val_metrics
            best_epoch = epoch + 1
            epochs_without_improve = 0
        else:
            epochs_without_improve += 1
            if epochs_without_improve >= config.patience:
                log(
                    f"Early stopping triggered after {epoch + 1} epochs (patience={config.patience})",
                )
                break

    if best_metrics is None:
        best_metrics = {
            "loss": float("nan"),
            "accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "false_positive_rate": 0.0,
            "true_negative_rate": 0.0,
            "true_positive_rate": 0.0,
            "balanced_accuracy": 0.0,
        }

    log(
        "Best validation balanced accuracy %.3f achieved at epoch %d"
        % (best_metrics["balanced_accuracy"], best_epoch),
    )

    export_dir = job_dir / "export"
    export_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(tz=timezone.utc).isoformat()

    model_cpu = _WakeWordNet()
    model_cpu.load_state_dict(best_state)
    model_cpu.eval()

    model_path = export_dir / "wake_model.pt"
    torch.save(
        {
            "state_dict": best_state,
            "config": config.model_dump(),
            "class_map": {"non_wake": 0, "wake": 1},
            "threshold": config.threshold,
            "trained_at": timestamp,
            "best_epoch": best_epoch,
            "metrics": best_metrics,
        },
        model_path,
    )

    scripted_path = export_dir / "wake_model_scripted.pt"
    dummy_input = torch.zeros(1, 1, config.clip_samples, dtype=torch.float32)
    traced = torch.jit.trace(model_cpu, dummy_input)
    traced.save(str(scripted_path))

    onnx_path = export_dir / "wake_model.onnx"
    torch.onnx.export(
        model_cpu,
        dummy_input,
        onnx_path,
        input_names=["waveform"],
        output_names=["logits"],
        dynamic_axes={"waveform": {2: "num_samples"}},
        opset_version=17,
    )

    metrics_path = export_dir / "metrics.json"
    metrics_payload = {
        "dataset": dataset_name,
        "timestamp": timestamp,
        "threshold": config.threshold,
        "metrics": best_metrics,
    }
    metrics_path.write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")

    config_path = export_dir / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "dataset": dataset_name,
                "trained_at": timestamp,
                "hyperparameters": config.model_dump(),
                "class_map": {"non_wake": 0, "wake": 1},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    metadata_path = export_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "dataset": dataset_name,
                "trained_at": timestamp,
                "best_epoch": best_epoch,
                "threshold": config.threshold,
                "metrics": best_metrics,
                "artifacts": {
                    "state_dict": model_path.name,
                    "scripted": scripted_path.name,
                    "onnx": onnx_path.name,
                    "metrics": metrics_path.name,
                    "config": config_path.name,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    artifact_paths = {
        "state_dict": str(model_path),
        "scripted": str(scripted_path),
        "onnx": str(onnx_path),
        "metrics": str(metrics_path),
        "config": str(config_path),
        "metadata": str(metadata_path),
    }

    return TrainingResult(
        export_dir=export_dir,
        metrics=best_metrics,
        artifact_paths=artifact_paths,
        threshold=config.threshold,
        config=config.model_dump(),
        best_epoch=best_epoch,
    )


def _resolve_config(overrides: dict | None) -> TrainingConfig:
    base = TrainingConfig()
    if not overrides:
        return base
    merged = base.model_dump()
    merged.update(overrides)
    return TrainingConfig.model_validate(merged)


def _select_device(requested: str) -> torch.device:
    if requested not in {"auto", "cpu", "cuda"}:
        raise TrainingError(f"Unsupported device setting: {requested}")
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if requested == "cuda" and not torch.cuda.is_available():
        raise TrainingError("CUDA requested but no GPU is available")
    return torch.device(requested)


def _load_dataset(dataset_dir: Path, config: TrainingConfig) -> tuple[list[_AudioExample], list[np.ndarray]]:
    labels_path = dataset_dir / "labels.json"
    if not labels_path.exists():
        raise TrainingError("Dataset is missing labels.json")

    try:
        labels = json.loads(labels_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TrainingError("labels.json is not valid JSON") from exc

    clips_dir = dataset_dir / "clips"
    if not clips_dir.exists():
        raise TrainingError("Dataset has no clips directory")

    examples: list[_AudioExample] = []
    noise_bank: list[np.ndarray] = []
    for clip_path in sorted(clips_dir.glob("*.wav")):
        clip_id = clip_path.stem
        meta = labels.get(clip_id, {})
        label_name = meta.get("label", "positive")
        label = 1 if label_name == "positive" else 0
        waveform = _load_waveform(clip_path, config)
        examples.append(_AudioExample(waveform=waveform, label=label))
        if label_name == "noise":
            noise_bank.append(waveform.copy())

    return examples, noise_bank


def _load_waveform(path: Path, config: TrainingConfig) -> np.ndarray:
    try:
        audio, sample_rate = sf.read(str(path), dtype="float32")
    except Exception as exc:  # pragma: no cover - soundfile error surfaces here
        raise TrainingError(f"Failed to read audio file: {path.name}") from exc

    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)

    if sample_rate != config.sample_rate:
        audio = resample_poly(audio, config.sample_rate, sample_rate)
    audio = np.asarray(audio, dtype=np.float32)

    desired = config.clip_samples
    if audio.size < desired:
        padding = desired - audio.size
        audio = np.pad(audio, (0, padding), mode="constant")
    elif audio.size > desired:
        audio = audio[:desired]

    peak = float(np.max(np.abs(audio)))
    if peak > 0:
        audio = audio / max(1.0, peak)
    return audio.astype(np.float32, copy=False)


def _train_val_split(
    examples: Sequence[_AudioExample],
    validation_split: float,
    seed: int,
) -> tuple[list[_AudioExample], list[_AudioExample]]:
    items = list(examples)
    rng = random.Random(seed)
    rng.shuffle(items)

    val_count = max(1, int(len(items) * validation_split))
    if val_count >= len(items):
        val_count = max(1, len(items) // 5)
    val = items[:val_count]
    train = items[val_count:]

    if not train:
        train = val
        val = []

    def has_class(data: Iterable[_AudioExample], target: int) -> bool:
        return any(example.label == target for example in data)

    if val and (not has_class(train, 0) or not has_class(train, 1)):
        for idx, example in enumerate(val):
            if example.label == 0 and not has_class(train, 0):
                train.append(example)
                val.pop(idx)
                break
            if example.label == 1 and not has_class(train, 1):
                train.append(example)
                val.pop(idx)
                break

    if not val:
        val = train[-1:]
        train = train[:-1] or train

    return train, val


def _augment_waveform(
    waveform: np.ndarray,
    config: TrainingConfig,
    noise_bank: Sequence[np.ndarray],
) -> np.ndarray:
    augmented = waveform.copy()
    rng = np.random.default_rng()

    if config.time_shift_ms > 0:
        max_shift = int(config.sample_rate * config.time_shift_ms / 1000.0)
        if max_shift > 0:
            shift = int(rng.integers(-max_shift, max_shift + 1))
            augmented = np.roll(augmented, shift)
            if shift > 0:
                augmented[:shift] = 0.0
            elif shift < 0:
                augmented[shift:] = 0.0

    if config.amplitude_jitter > 0:
        scale = float(rng.uniform(1.0 - config.amplitude_jitter, 1.0 + config.amplitude_jitter))
        augmented = augmented * scale

    if noise_bank and rng.random() < config.noise_mix_prob:
        noise = rng.choice(noise_bank)
        if noise.shape != augmented.shape:
            noise = _match_length(noise, augmented.shape[0])
        augmented = augmented + noise * config.noise_mix_level

    max_abs = float(np.max(np.abs(augmented)))
    if max_abs > 1.0:
        augmented = augmented / max_abs
    return augmented.astype(np.float32, copy=False)


def _match_length(data: np.ndarray, length: int) -> np.ndarray:
    if data.size == length:
        return data
    if data.size < length:
        pad = length - data.size
        return np.pad(data, (0, pad), mode="constant")
    return data[:length]


class _WakeWordNet(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=11, stride=2, padding=5),
            nn.BatchNorm1d(16),
            nn.ReLU(),
            nn.Conv1d(16, 32, kernel_size=11, stride=2, padding=5),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.Conv1d(32, 64, kernel_size=11, stride=2, padding=5),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(p=0.2),
            nn.Linear(32, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        return self.classifier(x)


def _train_one_epoch(
    model: nn.Module,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer,
    loader: DataLoader,
    device: torch.device,
    threshold: float,
) -> tuple[float, float]:
    model.train()
    total_loss = 0.0
    total_correct = 0
    total_samples = 0

    for waveforms, labels in loader:
        waveforms = waveforms.to(device)
        labels = labels.to(device)
        optimizer.zero_grad()
        logits = model(waveforms).squeeze(1)
        loss = criterion(logits, labels)
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * labels.size(0)
        predictions = (torch.sigmoid(logits) >= threshold).long()
        total_correct += (predictions == labels.long()).sum().item()
        total_samples += labels.size(0)

    avg_loss = total_loss / max(total_samples, 1)
    accuracy = total_correct / max(total_samples, 1)
    return avg_loss, accuracy


def _evaluate(
    model: nn.Module,
    criterion: nn.Module,
    loader: DataLoader,
    device: torch.device,
    threshold: float,
) -> dict[str, float]:
    model.eval()
    total_loss = 0.0
    total_samples = 0
    tp = fp = tn = fn = 0

    with torch.no_grad():
        for waveforms, labels in loader:
            waveforms = waveforms.to(device)
            labels = labels.to(device)
            logits = model(waveforms).squeeze(1)
            loss = criterion(logits, labels)
            total_loss += loss.item() * labels.size(0)
            total_samples += labels.size(0)

            probs = torch.sigmoid(logits)
            preds = (probs >= threshold).long()
            label_int = labels.long()

            tp += int(((preds == 1) & (label_int == 1)).sum().item())
            fp += int(((preds == 1) & (label_int == 0)).sum().item())
            tn += int(((preds == 0) & (label_int == 0)).sum().item())
            fn += int(((preds == 0) & (label_int == 1)).sum().item())

    loss = total_loss / max(total_samples, 1)
    accuracy = (tp + tn) / max(total_samples, 1)

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = (2 * precision * recall) / max(precision + recall, 1e-8) if tp else 0.0
    false_positive_rate = fp / max(fp + tn, 1)
    true_negative_rate = tn / max(fp + tn, 1)
    true_positive_rate = recall
    balanced_accuracy = (true_positive_rate + true_negative_rate) / 2

    return {
        "loss": float(loss),
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "false_positive_rate": float(false_positive_rate),
        "true_negative_rate": float(true_negative_rate),
        "true_positive_rate": float(true_positive_rate),
        "balanced_accuracy": float(balanced_accuracy),
    }
