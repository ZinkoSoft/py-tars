from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class DatasetSummary(BaseModel):
    name: str
    created_at: datetime
    clip_count: int = 0
    total_duration_sec: float = 0.0


class DatasetDetail(DatasetSummary):
    path: Path = Field(repr=False)
    deleted_clips: int = 0


class DatasetCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: Optional[str] = None


class HealthResponse(BaseModel):
    status: str = "ok"
    data_root: Path
