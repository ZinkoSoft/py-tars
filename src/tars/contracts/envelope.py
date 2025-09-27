from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class Envelope(BaseModel):
    """Wrapper adding metadata around event payloads."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    type: str
    ts: float = Field(default_factory=time.time)
    source: str = "router"
    data: dict[str, Any]

    model_config = {"extra": "forbid"}

    @classmethod
    def new(
        cls,
        *,
        event_type: str,
        data: Any,
        correlate: str | None = None,
        source: str = "router",
    ) -> "Envelope":
        payload = data.model_dump() if hasattr(data, "model_dump") else data
        return cls(id=correlate or uuid.uuid4().hex, type=event_type, data=payload, source=source)
