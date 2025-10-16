from __future__ import annotations

import uuid
import time
from typing import Literal, Optional

from pydantic import BaseModel, Field

# Event types (legacy - prefer topic constants)
EVENT_TYPE_SAY = "tts.say"
EVENT_TYPE_TTS_STATUS = "tts.status"

# MQTT Topic constants
TOPIC_TTS_SAY = "tts/say"
TOPIC_TTS_STATUS = "tts/status"


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
    system_announce: bool | None = None  # System announcements don't open response windows

    model_config = {"extra": "forbid"}


class TtsStatus(BaseModel):
    """Status transition emitted by the TTS worker."""

    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    event: Literal[
        "speaking_start",
        "speaking_end",
        "paused",
        "resumed",
        "stopped",
    ]
    text: str = ""
    timestamp: float = Field(default_factory=time.time)
    utt_id: Optional[str] = None
    reason: Optional[str] = None
    wake_ack: Optional[bool] = None
    system_announce: Optional[bool] = None  # System announcements don't open response windows

    model_config = {"extra": "forbid"}
