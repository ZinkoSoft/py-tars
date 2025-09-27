from __future__ import annotations

import uuid
from pydantic import BaseModel, Field


EVENT_TYPE_SAY = "tts.say"


class TtsSay(BaseModel):
    """Command asking the TTS worker to speak text."""

    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    text: str
    voice: str | None = None
    lang: str | None = None
    utt_id: str | None = None
    style: str | None = None
    stt_ts: float | None = None
    wake_ack: bool | None = None

    model_config = {"extra": "forbid"}
