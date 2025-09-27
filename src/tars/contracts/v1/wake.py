from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

EVENT_TYPE_WAKE_EVENT = "wake.event"
EVENT_TYPE_WAKE_MIC = "wake.mic"


class WakeEvent(BaseModel):
    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    type: str
    tts_id: str | None = None

    model_config = {"extra": "forbid"}


class WakeMicCommand(BaseModel):
    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    action: Literal["mute", "unmute"]
    reason: str = "wake"
    ttl_ms: int | None = Field(default=None, ge=0)

    model_config = {"extra": "forbid"}
