from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class WakeEventType(str, Enum):
    WAKE = "wake"
    INTERRUPT = "interrupt"
    TIMEOUT = "timeout"
    RESUME = "resume"
    CANCELLED = "cancelled"
    ERROR = "error"


class WakeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: WakeEventType = Field(description="Type of wake lifecycle event")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    energy: Optional[float] = Field(default=None, ge=0.0)
    tts_id: Optional[str] = Field(default=None, description="Active TTS identifier, if any")
    cause: Optional[str] = Field(default=None, description="Reason for the event (wake_phrase, silence, etc.)")
    ts: float = Field(description="Monotonic timestamp in seconds")


class MicAction(str, Enum):
    MUTE = "mute"
    UNMUTE = "unmute"


class MicCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: MicAction
    reason: str
    ttl_ms: Optional[int] = Field(default=None, ge=0)


class TtsAction(str, Enum):
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"


class TtsControl(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: TtsAction
    reason: str
    id: Optional[str] = Field(default=None, description="Identifier of the utterance being controlled")


class HealthPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool = True
    version: str = "0.1.0"
    ts: float
