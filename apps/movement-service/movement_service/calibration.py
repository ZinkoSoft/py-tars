from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ServoRange(BaseModel):
    minimum: int = Field(ge=0, le=4095)
    maximum: int = Field(ge=0, le=4095)

    def interpolate(self, percent: float) -> int:
        clamped = max(1.0, min(100.0, percent))
        if self.maximum >= self.minimum:
            value = self.minimum + ((self.maximum - self.minimum) * (clamped - 1.0) / 99.0)
        else:
            value = self.minimum - ((self.minimum - self.maximum) * (clamped - 1.0) / 99.0)
        return int(round(value))


class MovementCalibration(BaseModel):
    lift: ServoRange = Field(default=ServoRange(minimum=260, maximum=480))
    starboard: ServoRange = Field(default=ServoRange(minimum=310, maximum=520))
    port: ServoRange = Field(default=ServoRange(minimum=300, maximum=510))
    neutral_hold_ms: int = Field(default=200, ge=0, le=2000)

    @classmethod
    def load(cls, path: str | None) -> "MovementCalibration":
        if not path:
            return cls()
        candidate = Path(path)
        if not candidate.exists():
            raise FileNotFoundError(f"Calibration file not found: {candidate}")
        data = json.loads(candidate.read_text(encoding="utf-8"))
        return cls.model_validate(data)

    def to_channels(self, height_percent: float | None, starboard_percent: float | None, port_percent: float | None) -> dict[int, int]:
        channels: dict[int, int] = {}
        if height_percent not in (None, 0):
            channels[0] = self.lift.interpolate(float(height_percent))
        if starboard_percent not in (None, 0):
            channels[1] = self.starboard.interpolate(float(starboard_percent))
        if port_percent not in (None, 0):
            channels[2] = self.port.interpolate(float(port_percent))
        return channels
