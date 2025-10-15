from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


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
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    energy: float | None = Field(default=None, ge=0.0)
    tts_id: str | None = Field(default=None, description="Active TTS identifier, if any")
    cause: str | None = Field(
        default=None, description="Reason for the event (wake_phrase, silence, etc.)"
    )
    ts: float = Field(description="Monotonic timestamp in seconds")


class MicAction(str, Enum):
    MUTE = "mute"
    UNMUTE = "unmute"


class MicCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: MicAction
    reason: str
    ttl_ms: int | None = Field(default=None, ge=0)


class TtsAction(str, Enum):
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"


class TtsControl(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: TtsAction
    reason: str
    id: str | None = Field(default=None, description="Identifier of the utterance being controlled")


class HealthPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool = True
    version: str = "0.1.0"
    ts: float
