from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from .compat import StrEnum


class TrainingJobStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class TrainingJob(BaseModel):
    """Metadata describing a wake-word training job."""

    model_config = ConfigDict(extra="forbid")

    id: str
    dataset: str
    status: TrainingJobStatus = TrainingJobStatus.queued
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    config: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class TrainingJobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(min_length=1, max_length=128)
    config_overrides: Optional[dict[str, Any]] = None


class JobLogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    message: str
    raw: str


class JobLogChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    offset: int = Field(ge=0)
    next_offset: int = Field(ge=0)
    total_size: int = Field(ge=0)
    has_more: bool = False
    entries: list[JobLogEntry] = Field(default_factory=list)


class JobStorage:
    """Filesystem-backed persistence for training jobs."""

    JOB_FILENAME = "job.json"
    LOG_FILENAME = "logs.txt"

    def __init__(self, root: Path) -> None:
        self.root = root
        self.jobs_root = self.root / "jobs"
        self.jobs_root.mkdir(parents=True, exist_ok=True)

    def create_job(
        self,
        dataset: str,
        config: Optional[dict[str, Any]] = None,
    ) -> tuple[TrainingJob, JobLogChunk]:
        dataset_dir = self.root / "datasets" / dataset
        if not dataset_dir.exists():
            raise FileNotFoundError(dataset)
        job_id = uuid.uuid4().hex
        job_dir = self.jobs_root / job_id
        job_dir.mkdir(parents=True, exist_ok=False)
        now = datetime.now(tz=timezone.utc)
        job = TrainingJob(
            id=job_id,
            dataset=dataset,
            status=TrainingJobStatus.queued,
            created_at=now,
            updated_at=now,
            config=config or {},
        )
        self._write_job(job, job_dir)
        self._init_log(job_dir)
        log_chunk = self.append_log(job_id, "Job created and queued")
        return job, log_chunk

    def get_job(self, job_id: str) -> TrainingJob:
        job_dir = self.jobs_root / job_id
        if not job_dir.exists():
            raise FileNotFoundError(job_id)
        job_path = job_dir / self.JOB_FILENAME
        try:
            data = json.loads(job_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:  # pragma: no cover - defensive
            raise FileNotFoundError(job_id) from exc
        return TrainingJob.model_validate(data)

    def list_jobs(self) -> list[TrainingJob]:
        jobs: list[TrainingJob] = []
        for job_dir in sorted(self.jobs_root.glob("*")):
            if not job_dir.is_dir():
                continue
            try:
                jobs.append(self.get_job(job_dir.name))
            except FileNotFoundError:
                continue
        return jobs

    def update_status(
        self,
        job_id: str,
        status: TrainingJobStatus,
        error: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> TrainingJob:
        job_dir = self.jobs_root / job_id
        if not job_dir.exists():
            raise FileNotFoundError(job_id)
        job = self.get_job(job_id)
        job.status = status
        job.error = error
        if metadata:
            job.config.update(metadata)
        job.updated_at = datetime.now(tz=timezone.utc)
        self._write_job(job, job_dir)
        return job

    def append_log(self, job_id: str, message: str) -> JobLogChunk:
        job_dir = self.jobs_root / job_id
        if not job_dir.exists():
            raise FileNotFoundError(job_id)
        timestamp = datetime.now(tz=timezone.utc)
        log_path = job_dir / self.LOG_FILENAME
        log_line = f"[{timestamp.isoformat()}] {message}"
        encoded = (log_line + "\n").encode("utf-8")
        offset = log_path.stat().st_size if log_path.exists() else 0
        with log_path.open("ab") as handle:
            handle.write(encoded)
        total_size = offset + len(encoded)
        entry = JobLogEntry(timestamp=timestamp, message=message, raw=log_line)
        return JobLogChunk(
            job_id=job_id,
            offset=offset,
            next_offset=total_size,
            total_size=total_size,
            has_more=False,
            entries=[entry],
        )

    def read_log(self, job_id: str) -> str:
        job_dir = self.jobs_root / job_id
        if not job_dir.exists():
            raise FileNotFoundError(job_id)
        log_path = job_dir / self.LOG_FILENAME
        try:
            return log_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise FileNotFoundError(job_id) from exc

    def read_log_chunk(
        self,
        job_id: str,
        *,
        offset: int = 0,
        limit: Optional[int] = 16384,
    ) -> JobLogChunk:
        if offset < 0:
            raise ValueError("offset must be >= 0")
        if limit is not None and limit <= 0:
            raise ValueError("limit must be > 0 when provided")

        job_dir = self.jobs_root / job_id
        if not job_dir.exists():
            raise FileNotFoundError(job_id)
        log_path = job_dir / self.LOG_FILENAME
        if not log_path.exists():
            raise FileNotFoundError(job_id)

        total_size = log_path.stat().st_size
        start = min(offset, total_size)

        data = b""
        with log_path.open("rb") as handle:
            handle.seek(start)
            if limit is None:
                data = handle.read()
            else:
                data = handle.read(limit)
                if start + len(data) < total_size:
                    data += handle.readline()

        next_offset = start + len(data)
        text = data.decode("utf-8")
        entries: list[JobLogEntry] = []
        for raw_line in text.splitlines():
            if not raw_line.strip():
                continue
            entries.append(self._parse_log_line(raw_line))

        has_more = next_offset < total_size
        return JobLogChunk(
            job_id=job_id,
            offset=start,
            next_offset=next_offset,
            total_size=total_size,
            has_more=has_more,
            entries=entries,
        )

    def get_job_dir(self, job_id: str) -> Path:
        job_dir = self.jobs_root / job_id
        if not job_dir.exists():
            raise FileNotFoundError(job_id)
        return job_dir

    def _write_job(self, job: TrainingJob, job_dir: Path) -> None:
        payload = job.model_dump(mode="json")
        job_path = job_dir / self.JOB_FILENAME
        job_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _init_log(self, job_dir: Path) -> None:
        log_path = job_dir / self.LOG_FILENAME
        if not log_path.exists():
            log_path.write_text("", encoding="utf-8")

    @staticmethod
    def _parse_log_line(line: str) -> JobLogEntry:
        raw = line.rstrip("\n")
        if raw.startswith("[") and "] " in raw:
            prefix, message = raw[1:].split("] ", 1)
            try:
                timestamp = datetime.fromisoformat(prefix)
            except ValueError:
                timestamp = datetime.now(tz=timezone.utc)
        else:
            message = raw
            timestamp = datetime.now(tz=timezone.utc)
        return JobLogEntry(timestamp=timestamp, message=message, raw=raw)
