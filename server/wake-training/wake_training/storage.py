from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable
import uuid
from .models import RecordingMetadata, RecordingResponse, RecordingUpdate

from .models import DatasetCreateRequest, DatasetDetail, DatasetSummary


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
        return self._build_detail(dataset_dir)

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
        # Placeholder: duration will be calculated after metadata pipeline lands.
        # For now, return 0.0 seconds.
        return 0.0
