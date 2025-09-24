from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, Field


class Settings(BaseModel):
    data_root: Path = Field(default=Path("/data/wake-training"), alias="WAKE_TRAINING_DATA_DIR")
    log_level: str = Field(default="INFO", alias="WAKE_TRAINING_LOG_LEVEL")

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


def load_settings(env: Mapping[str, Any] | None = None) -> Settings:
    """Load settings from a mapping (defaults to process env).

    Using aliases allows env var keys like WAKE_TRAINING_DATA_DIR to map to fields.
    """
    source: Mapping[str, Any] = env or os.environ
    # Pydantic will match aliases from this mapping when populate_by_name is enabled
    return Settings.model_validate(dict(source))
