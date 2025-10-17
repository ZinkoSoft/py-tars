from __future__ import annotations

import time
import uuid

from pydantic import BaseModel, Field

# Event types (legacy - prefer topic constants)
EVENT_TYPE_STT_FINAL = "stt.final"
EVENT_TYPE_STT_PARTIAL = "stt.partial"

# MQTT Topic constants
TOPIC_STT_FINAL = "stt/final"
TOPIC_STT_PARTIAL = "stt/partial"
TOPIC_STT_AUDIO_FFT = "stt/audio_fft"


class FinalTranscript(BaseModel):
    """Transcription result emitted by STT service."""

    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    text: str
    lang: str = "en"
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    utt_id: str | None = None
    ts: float = Field(default_factory=time.time)
    is_final: bool = True

    model_config = {"extra": "forbid"}


class PartialTranscript(BaseModel):
    """Streaming partial emitted while an utterance is in progress."""

    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    text: str
    lang: str = "en"
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    utt_id: str | None = None
    ts: float = Field(default_factory=time.time)
    is_final: bool = False

    model_config = {"extra": "forbid"}


class AudioFFTData(BaseModel):
    """Audio FFT data for visualization."""

    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    fft_data: list[float] = Field(description="FFT magnitude values")
    sample_rate: int = Field(ge=1, description="Audio sample rate in Hz")
    ts: float = Field(default_factory=time.time)

    model_config = {"extra": "forbid"}
