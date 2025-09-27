from __future__ import annotations

import time
import uuid
from pydantic import BaseModel, Field

EVENT_TYPE_HEALTH = "system.health"


class HealthPing(BaseModel):
    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    ok: bool
    event: str | None = None
    err: str | None = None
    timestamp: float = Field(default_factory=time.time)

    model_config = {"extra": "forbid"}
