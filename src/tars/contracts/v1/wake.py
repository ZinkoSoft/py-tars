from __future__ import annotations

import uuid
from pydantic import BaseModel, Field

EVENT_TYPE_WAKE_EVENT = "wake.event"


class WakeEvent(BaseModel):
    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    type: str
    tts_id: str | None = None

    model_config = {"extra": "forbid"}
