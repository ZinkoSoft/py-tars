from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

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
