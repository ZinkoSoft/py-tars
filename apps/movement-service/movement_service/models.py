from __future__ import annotations

import time
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ConfigDict


class MovementAction(str, Enum):
    RESET = "reset"
    DISABLE = "disable"
    STEP_FORWARD = "step_forward"
    STEP_BACKWARD = "step_backward"
    TURN_LEFT = "turn_left"
    TURN_RIGHT = "turn_right"
    BALANCE = "balance"
    LAUGH = "laugh"
    SWING_LEGS = "swing_legs"
    POSE = "pose"
    BOW = "bow"


class MovementCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    command: MovementAction
    params: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=lambda: time.time())


class MovementFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    seq: int = Field(ge=0)
    total: int = Field(ge=1)
    duration_ms: int = Field(default=200, ge=0, le=10_000)
    hold_ms: int = Field(default=0, ge=0, le=10_000)
    channels: dict[int, int] = Field(default_factory=dict)
    disable_after: bool = False
    done: bool = False


class MovementState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    event: str
    seq: int | None = None
    detail: str | None = None
    timestamp: float = Field(default_factory=lambda: time.time())
