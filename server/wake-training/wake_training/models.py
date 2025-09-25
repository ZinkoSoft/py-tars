from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from .compat import StrEnum

from pydantic import BaseModel, Field, model_validator


class DatasetSummary(BaseModel):
    name: str
    created_at: datetime
    clip_count: int = 0
    total_duration_sec: float = 0.0
    description: Optional[str] = None


class DatasetDetail(DatasetSummary):
    path: Path = Field(repr=False)
    deleted_clips: int = 0


class DatasetMetrics(BaseModel):
    """Aggregate dataset metrics.

    Counts reflect only active clips (in clips/, not trash/).
    Durations are summed over active clips and may be 0.0 when audio
    parsing is unavailable.
    """
    name: str
    clip_count: int = 0
    total_duration_sec: float = 0.0
    positives: int = 0
    negatives: int = 0
    noise: int = 0


class DatasetCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: Optional[str] = None


class DatasetUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    description: Optional[str] = None

    @model_validator(mode="after")
    def ensure_fields_present(cls, values: "DatasetUpdateRequest") -> "DatasetUpdateRequest":
        if values.name is None and values.description is None:
            raise ValueError("At least one field must be provided for update")
        return values


class HealthResponse(BaseModel):
    status: str = "ok"
    data_root: Path


class RecordingLabel(StrEnum):
    positive = "positive"
    negative = "negative"
    noise = "noise"


class RecordingMetadata(BaseModel):
    label: RecordingLabel = RecordingLabel.positive
    speaker: Optional[str] = None
    notes: Optional[str] = None


class RecordingResponse(BaseModel):
    clip_id: str
    filename: str
    dataset: str
    label: RecordingLabel
    path: Path


class RecordingUpdate(BaseModel):
    """Partial update for a recording's metadata.

    All fields are optional; only provided fields will be updated.
    """
    label: Optional[RecordingLabel] = None
    speaker: Optional[str] = None
    notes: Optional[str] = None
