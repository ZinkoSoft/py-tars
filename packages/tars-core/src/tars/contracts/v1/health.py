from __future__ import annotations

import time
import uuid
from pydantic import BaseModel, Field

# Event types (legacy - prefer topic constants)
EVENT_TYPE_HEALTH = "system.health"

# MQTT Topic constants
TOPIC_SYSTEM_HEALTH_PREFIX = "system/health/"  # Append service name


class HealthPing(BaseModel):
    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    ok: bool
    event: str | None = None
    err: str | None = None
    timestamp: float = Field(default_factory=time.time)

    model_config = {"extra": "forbid"}
