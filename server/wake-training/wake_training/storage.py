from __future__ import annotations

import contextlib
import json
import shutil
import uuid
import wave
from datetime import datetime
from pathlib import Path
from typing import Iterable

try:  # pragma: no cover - optional dependency, covered indirectly via metrics tests
    import soundfile as sf  # type: ignore
except Exception:  # pragma: no cover - fallback when soundfile missing
    sf = None

from .models import (
    DatasetCreateRequest,
    DatasetDetail,
    DatasetMetrics,
    DatasetSummary,
    DatasetUpdateRequest,
    RecordingMetadata,
    RecordingResponse,
    RecordingUpdate,
)


DATASET_META_FILENAME = "manifest.json"


class DatasetStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.datasets_root = self.root / "datasets"
        self.datasets_root.mkdir(parents=True, exist_ok=True)

    def list_datasets(self) -> list[DatasetSummary]:
        summaries: list[DatasetSummary] = []
        for dataset_dir in sorted(self.datasets_root.glob("*")):
            if not dataset_dir.is_dir():
                continue
            summaries.append(self._build_summary(dataset_dir))
        return summaries

    def get_dataset(self, name: str) -> DatasetDetail:
        dataset_dir = self.datasets_root / name
        if not dataset_dir.exists():
            raise FileNotFoundError(name)
        return self._build_detail(dataset_dir)

    def create_dataset(self, payload: DatasetCreateRequest) -> DatasetDetail:
        dataset_dir = self.datasets_root / payload.name
        dataset_dir.mkdir(parents=True, exist_ok=False)
        meta_path = dataset_dir / DATASET_META_FILENAME
        manifest = {
            "name": payload.name,
            "description": payload.description,
            "created_at": datetime.utcnow().isoformat(),
        }
        meta_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (dataset_dir / "clips").mkdir(parents=True, exist_ok=True)
        (dataset_dir / "trash").mkdir(parents=True, exist_ok=True)
        self._recompute_metrics(dataset_dir)
        return self._build_detail(dataset_dir)

    def update_dataset(self, name: str, payload: DatasetUpdateRequest) -> DatasetDetail:
        dataset_dir = self.datasets_root / name
        if not dataset_dir.exists():
            raise FileNotFoundError(name)

        target_dir = dataset_dir
        new_name = payload.name
        if new_name and new_name != name:
            target_dir = self.datasets_root / new_name
            if target_dir.exists():
                raise FileExistsError(new_name)
            dataset_dir.rename(target_dir)
            dataset_dir = target_dir

        manifest = self._read_manifest(dataset_dir)
        if new_name:
            manifest["name"] = new_name
        if payload.description is not None:
            manifest["description"] = payload.description
        manifest.setdefault("created_at", datetime.utcnow().isoformat())
        meta_path = dataset_dir / DATASET_META_FILENAME
        meta_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        # Update metrics to ensure they exist at new location
        self._recompute_metrics(dataset_dir)
        return self._build_detail(dataset_dir)

    def delete_dataset(self, name: str) -> None:
        dataset_dir = self.datasets_root / name
        if not dataset_dir.exists():
            raise FileNotFoundError(name)
        shutil.rmtree(dataset_dir)

    def save_recording(
        self,
        dataset_name: str,
        content: bytes,
        filename: str | None,
        meta: RecordingMetadata | None = None,
    ) -> RecordingResponse:
        dataset_dir = self.datasets_root / dataset_name
        if not dataset_dir.exists():
            raise FileNotFoundError(dataset_name)
        clips_dir = dataset_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)

        clip_id = uuid.uuid4().hex
        out_name = f"{clip_id}.wav"
        if filename and filename.lower().endswith(".wav"):
            # keep .wav suffix but use our id to avoid collisions
            out_name = f"{clip_id}.wav"
        out_path = clips_dir / out_name
        out_path.write_bytes(content)

        # update labels.json
        labels_path = dataset_dir / "labels.json"
        labels: dict[str, dict] = {}
        if labels_path.exists():
            try:
                labels = json.loads(labels_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                labels = {}
        labels[clip_id] = {
            "filename": out_name,
            "label": (meta.label if meta else None) or "positive",
            "speaker": getattr(meta, "speaker", None),
            "notes": getattr(meta, "notes", None),
            "created_at": datetime.utcnow().isoformat(),
        }
        labels_path.write_text(json.dumps(labels, indent=2), encoding="utf-8")
        # recompute metrics after mutation
        self._recompute_metrics(dataset_dir)

        return RecordingResponse(
            clip_id=clip_id,
            filename=out_name,
            dataset=dataset_name,
            label=(meta.label if meta else None) or "positive",
            path=out_path,
        )

    def delete_recording(self, dataset_name: str, clip_id: str) -> None:
        """Soft-delete a recording by moving it to the dataset's trash directory.

        Also marks the item as deleted in labels.json by adding a deleted_at timestamp.
        If the clip is already in trash, this is a no-op.
        Raises FileNotFoundError if dataset or clip not found.
        """
        dataset_dir = self.datasets_root / dataset_name
        if not dataset_dir.exists():
            raise FileNotFoundError(dataset_name)
        clips_dir = dataset_dir / "clips"
        trash_dir = dataset_dir / "trash"
        trash_dir.mkdir(parents=True, exist_ok=True)

        src = clips_dir / f"{clip_id}.wav"
        dst = trash_dir / f"{clip_id}.wav"
        if not src.exists() and not dst.exists():
            raise FileNotFoundError(clip_id)
        if src.exists():
            src.replace(dst)

        labels_path = dataset_dir / "labels.json"
        labels = self._read_labels(labels_path)
        if clip_id in labels:
            labels[clip_id]["deleted_at"] = datetime.utcnow().isoformat()
            labels_path.write_text(json.dumps(labels, indent=2), encoding="utf-8")
        # recompute metrics after mutation
        self._recompute_metrics(dataset_dir)

    def restore_recording(self, dataset_name: str, clip_id: str) -> None:
        """Restore a soft-deleted recording from trash back to clips.

        Clears the deleted_at marker in labels.json.
        Raises FileNotFoundError if dataset or clip not found in trash.
        """
        dataset_dir = self.datasets_root / dataset_name
        if not dataset_dir.exists():
            raise FileNotFoundError(dataset_name)
        clips_dir = dataset_dir / "clips"
        trash_dir = dataset_dir / "trash"
        clips_dir.mkdir(parents=True, exist_ok=True)

        src = trash_dir / f"{clip_id}.wav"
        dst = clips_dir / f"{clip_id}.wav"
        if not src.exists():
            raise FileNotFoundError(clip_id)
        src.replace(dst)

        labels_path = dataset_dir / "labels.json"
        labels = self._read_labels(labels_path)
        if clip_id in labels and "deleted_at" in labels[clip_id]:
            labels[clip_id].pop("deleted_at", None)
            labels_path.write_text(json.dumps(labels, indent=2), encoding="utf-8")
        # recompute metrics after mutation
        self._recompute_metrics(dataset_dir)

    def update_recording(self, dataset_name: str, clip_id: str, patch: RecordingUpdate) -> None:
        """Update recording metadata fields present in patch.

        Raises FileNotFoundError if dataset or clip not found in labels.
        """
        dataset_dir = self.datasets_root / dataset_name
        if not dataset_dir.exists():
            raise FileNotFoundError(dataset_name)
        labels_path = dataset_dir / "labels.json"
        labels = self._read_labels(labels_path)
        if clip_id not in labels:
            # Require existing metadata to update
            raise FileNotFoundError(clip_id)
        data = labels[clip_id]
        if patch.label is not None:
            data["label"] = patch.label
        if patch.speaker is not None:
            data["speaker"] = patch.speaker
        if patch.notes is not None:
            data["notes"] = patch.notes
        data["updated_at"] = datetime.utcnow().isoformat()
        labels_path.write_text(json.dumps(labels, indent=2), encoding="utf-8")
        # recompute metrics after mutation
        self._recompute_metrics(dataset_dir)

    def get_metrics(self, dataset_name: str) -> DatasetMetrics:
        dataset_dir = self.datasets_root / dataset_name
        if not dataset_dir.exists():
            raise FileNotFoundError(dataset_name)
        metrics_path = dataset_dir / "metrics.json"
        if metrics_path.exists():
            try:
                data = json.loads(metrics_path.read_text(encoding="utf-8"))
                return DatasetMetrics(**data)
            except Exception:
                pass
        # compute on the fly if missing/corrupt
        return self._recompute_metrics(dataset_dir)

    def _recompute_metrics(self, dataset_dir: Path) -> DatasetMetrics:
        """Recompute aggregate metrics from labels.json and clips/trash.

        Only counts clips present in clips/ and not marked deleted in labels.
        """
        name = dataset_dir.name
        clips_dir = dataset_dir / "clips"
        trash_dir = dataset_dir / "trash"
        labels_path = dataset_dir / "labels.json"
        labels = self._read_labels(labels_path)

        active_ids: set[str] = set()
        if clips_dir.exists():
            for p in clips_dir.glob("*.wav"):
                active_ids.add(p.stem)

        # remove any ids that are actually in trash (source of truth is FS)
        if trash_dir.exists():
            for p in trash_dir.glob("*.wav"):
                active_ids.discard(p.stem)

        positives = negatives = noise = 0
        for cid in active_ids:
            meta = labels.get(cid, {})
            if meta.get("label") == "positive":
                positives += 1
            elif meta.get("label") == "negative":
                negatives += 1
            elif meta.get("label") == "noise":
                noise += 1

        # For now duration is 0.0 until audio parsing lands.
        metrics = DatasetMetrics(
            name=name,
            clip_count=len(active_ids),
            total_duration_sec=0.0,
            positives=positives,
            negatives=negatives,
            noise=noise,
        )
        metrics_path = dataset_dir / "metrics.json"
        metrics_path.write_text(json.dumps(metrics.model_dump(), indent=2), encoding="utf-8")
        return metrics

    @staticmethod
    def _read_labels(labels_path: Path) -> dict:
        if not labels_path.exists():
            return {}
        try:
            return json.loads(labels_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _build_summary(self, dataset_dir: Path) -> DatasetSummary:
        manifest = self._read_manifest(dataset_dir)
        clips_dir = dataset_dir / "clips"
        clip_files = list(clips_dir.glob("*.wav")) if clips_dir.exists() else []
        total_duration = self._sum_durations(clip_files)
        created_at = self._parse_created_at(manifest, dataset_dir)
        return DatasetSummary(
            name=dataset_dir.name,
            created_at=created_at,
            clip_count=len(clip_files),
            total_duration_sec=total_duration,
        )

    def _build_detail(self, dataset_dir: Path) -> DatasetDetail:
        summary = self._build_summary(dataset_dir)
        trash_dir = dataset_dir / "trash"
        deleted_count = len(list(trash_dir.glob("*.wav"))) if trash_dir.exists() else 0
        return DatasetDetail(
            **summary.model_dump(),
            path=dataset_dir,
            deleted_clips=deleted_count,
        )

    def _read_manifest(self, dataset_dir: Path) -> dict[str, str]:
        meta_path = dataset_dir / DATASET_META_FILENAME
        if not meta_path.exists():
            return {}
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _parse_created_at(manifest: dict[str, str], dataset_dir: Path) -> datetime:
        raw = manifest.get("created_at")
        if raw:
            try:
                return datetime.fromisoformat(raw)
            except ValueError:
                pass
        return datetime.utcfromtimestamp(dataset_dir.stat().st_ctime)

    @staticmethod
    def _sum_durations(files: Iterable[Path]) -> float:
        total = 0.0
        for path in files:
            # Prefer soundfile for accurate metadata, fall back to wave module.
            if sf is not None:
                try:
                    info = sf.info(str(path))
                    if info.samplerate:
                        total += info.frames / float(info.samplerate)
                        continue
                except Exception:  # pragma: no cover - handled by fallback
                    pass
            try:
                with contextlib.closing(wave.open(str(path), "rb")) as wf:
                    frames = wf.getnframes()
                    rate = wf.getframerate()
                    if rate:
                        total += frames / float(rate)
            except Exception:  # pragma: no cover - ignore unreadable files
                continue
        return total
