"""Versioned event contracts (v1)."""

from .health import EVENT_TYPE_HEALTH, HealthPing
from .llm import (
	EVENT_TYPE_LLM_CANCEL,
	EVENT_TYPE_LLM_REQUEST,
	EVENT_TYPE_LLM_RESPONSE,
	EVENT_TYPE_LLM_STREAM,
	BaseLLMMessage,
	LLMCancel,
	LLMRequest,
	LLMResponse,
	LLMStreamDelta,
)
from .stt import EVENT_TYPE_STT_FINAL, EVENT_TYPE_STT_PARTIAL, FinalTranscript, PartialTranscript
from .tts import EVENT_TYPE_SAY, EVENT_TYPE_TTS_STATUS, TtsSay, TtsStatus
from .wake import EVENT_TYPE_WAKE_EVENT, EVENT_TYPE_WAKE_MIC, WakeEvent, WakeMicCommand

__all__ = [
	"EVENT_TYPE_HEALTH",
	"HealthPing",
	"EVENT_TYPE_LLM_CANCEL",
	"EVENT_TYPE_LLM_REQUEST",
	"EVENT_TYPE_LLM_RESPONSE",
	"EVENT_TYPE_LLM_STREAM",
	"BaseLLMMessage",
	"LLMCancel",
	"LLMRequest",
	"LLMResponse",
	"LLMStreamDelta",
	"EVENT_TYPE_STT_FINAL",
	"EVENT_TYPE_STT_PARTIAL",
	"FinalTranscript",
	"PartialTranscript",
	"EVENT_TYPE_SAY",
	"EVENT_TYPE_TTS_STATUS",
	"TtsSay",
	"TtsStatus",
	"EVENT_TYPE_WAKE_EVENT",
	"EVENT_TYPE_WAKE_MIC",
	"WakeEvent",
	"WakeMicCommand",
]
