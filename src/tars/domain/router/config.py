from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple


@dataclass(slots=True)
class RouterSettings:
    mqtt_url: str = "mqtt://tars:pass@127.0.0.1:1883"
    online_announce: bool = True
    online_text: str = "System online."
    topic_health_tts: str = "system/health/tts"
    topic_health_stt: str = "system/health/stt"
    topic_health_router: str = "system/health/router"
    topic_stt_final: str = "stt/final"
    topic_tts_say: str = "tts/say"
    topic_llm_req: str = "llm/request"
    topic_llm_resp: str = "llm/response"
    topic_llm_stream: str = "llm/stream"
    topic_llm_cancel: str = "llm/cancel"
    topic_wake_event: str = "wake/event"
    router_llm_tts_stream: bool = True
    stream_min_chars: int = 60
    stream_max_chars: int = 240
    stream_boundary_chars: str = ".!?;:"
    stream_boundary_only: bool = True
    stream_hard_max_chars: int = 2000
    wake_phrases_raw: str = "hey tars"
    wake_window_sec: float = 8.0
    wake_ack_enabled: bool = True
    wake_ack_text: str = "Yes?"
    wake_ack_choices_raw: str = "Hmm?|Huh?|Yes?"
    wake_ack_style: str = "friendly"
    wake_reprompt_text: str = ""
    wake_interrupt_text: str = ""
    wake_resume_text: str = ""
    wake_cancel_text: str = ""
    wake_timeout_text: str = ""
    live_mode_default: bool = False
    live_mode_enter_phrase: str = "enter live mode"
    live_mode_exit_phrase: str = "exit live mode"
    live_mode_enter_ack: str = "Live mode enabled."
    live_mode_exit_ack: str = "Live mode disabled."
    live_mode_active_hint: str = "Live mode is already active."
    live_mode_inactive_hint: str = "Live mode is already off."
    wake_phrases: Tuple[str, ...] = field(init=False)
    wake_ack_choices: Tuple[str, ...] = field(init=False)

    def __post_init__(self) -> None:
        phrases = [p.strip().lower() for p in self.wake_phrases_raw.split("|") if p.strip()]
        self.wake_phrases = tuple(phrases) if phrases else ("hey tars",)
        self.live_mode_enter_phrase = self.live_mode_enter_phrase.strip().lower()
        self.live_mode_exit_phrase = self.live_mode_exit_phrase.strip().lower()
        self.wake_ack_enabled = bool(self.wake_ack_enabled)
        self.wake_ack_text = (self.wake_ack_text or "").strip()
        self.wake_ack_style = (self.wake_ack_style or "neutral").strip() or "neutral"
        ack_choices = [p.strip() for p in self.wake_ack_choices_raw.split("|") if p.strip()]
        default_choices: Tuple[str, ...] = ("Hmm?", "Huh?", "Yes?")
        if not ack_choices:
            ack_choices = list(default_choices)
        self.wake_ack_choices = tuple(ack_choices)
        if not self.wake_ack_text and self.wake_ack_choices:
            self.wake_ack_text = self.wake_ack_choices[0]
        if not self.wake_ack_enabled:
            self.wake_ack_choices = ()
            self.wake_ack_text = ""
        self.wake_reprompt_text = self.wake_reprompt_text.strip()
        self.wake_interrupt_text = self.wake_interrupt_text.strip()
        self.wake_resume_text = self.wake_resume_text.strip()
        self.wake_cancel_text = self.wake_cancel_text.strip()
        self.wake_timeout_text = self.wake_timeout_text.strip()

    def as_topic_map(self) -> dict[str, str]:
        """Return event type -> topic mapping for registry registration."""

        return {
            "stt.final": self.topic_stt_final,
            "tts.say": self.topic_tts_say,
            "llm.request": self.topic_llm_req,
            "llm.response": self.topic_llm_resp,
            "llm.stream": self.topic_llm_stream,
            "llm.cancel": self.topic_llm_cancel,
            "wake.event": self.topic_wake_event,
            "system.health.tts": self.topic_health_tts,
            "system.health.stt": self.topic_health_stt,
            "system.health.router": self.topic_health_router,
        }
