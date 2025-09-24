from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, Field, field_validator


class Settings(BaseModel):
    data_root: Path = Field(default=Path("/data/wake-training"), alias="WAKE_TRAINING_DATA_DIR")
    log_level: str = Field(default="INFO", alias="WAKE_TRAINING_LOG_LEVEL")
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"],
        alias="WAKE_TRAINING_CORS_ORIGINS",
        description="Comma-separated list of origins allowed to access the API",
    )

    model_config = {
        "populate_by_name": True,
        "extra": "ignore",
    }

    def ensure_directories(self) -> None:
        self.data_root.mkdir(parents=True, exist_ok=True)
        (self.data_root / "datasets").mkdir(parents=True, exist_ok=True)
        (self.data_root / "jobs").mkdir(parents=True, exist_ok=True)
        (self.data_root / "scratch").mkdir(parents=True, exist_ok=True)
        (self.data_root / "transfers").mkdir(parents=True, exist_ok=True)

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _coerce_origins(cls, value: Any) -> list[str]:
        if value in (None, ""):
            return []
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",")]
            return [part for part in parts if part]
        if isinstance(value, (list, tuple, set)):
            return [str(part) for part in value if str(part)]
        return []


def load_settings(env: Mapping[str, Any] | None = None) -> Settings:
    """Load settings from a mapping (defaults to process env).

    Using aliases allows env var keys like WAKE_TRAINING_DATA_DIR to map to fields.
    """
    source: Mapping[str, Any] = env or os.environ
    # Pydantic will match aliases from this mapping when populate_by_name is enabled
    return Settings.model_validate(dict(source))
