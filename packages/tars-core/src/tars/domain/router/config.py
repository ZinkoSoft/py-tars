from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Tuple

from tars.runtime import env as runtime_env


@dataclass(slots=True)
class RouterStreamSettings:
    queue_maxsize: int = 256
    queue_overflow: str = "drop_oldest"  # drop_oldest | drop_new | block
    handler_timeout_sec: float = 30.0


@dataclass(slots=True)
class RouterSettings:
    mqtt_url: str = "mqtt://tars:pass@127.0.0.1:1883"
    online_announce: bool = True
    online_text: str = "System online."
    tts_voice: str = "piper/en_US/amy"
    topic_health_tts: str = "system/health/tts"
    topic_health_stt: str = "system/health/stt"
    topic_health_router: str = "system/health/router"
    topic_stt_final: str = "stt/final"
    topic_tts_say: str = "tts/say"
    topic_tts_status: str = "tts/status"
    topic_llm_req: str = "llm/request"
    topic_llm_resp: str = "llm/response"
    topic_llm_stream: str = "llm/stream"
    topic_llm_cancel: str = "llm/cancel"
    topic_wake_event: str = "wake/event"
    topic_movement_test: str = "movement/test"
    topic_movement_stop: str = "movement/stop"
    topic_movement_status: str = "movement/status"
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
    stream_settings: RouterStreamSettings = field(default_factory=RouterStreamSettings)
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
        self.tts_voice = (self.tts_voice or "").strip() or "piper/en_US/amy"
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
            "tts.status": self.topic_tts_status,
            "llm.request": self.topic_llm_req,
            "llm.response": self.topic_llm_resp,
            "llm.stream": self.topic_llm_stream,
            "llm.cancel": self.topic_llm_cancel,
            "wake.event": self.topic_wake_event,
            "movement.test": self.topic_movement_test,
            "movement.stop": self.topic_movement_stop,
            "movement.status": self.topic_movement_status,
            "system.health.tts": self.topic_health_tts,
            "system.health.stt": self.topic_health_stt,
            "system.health.router": self.topic_health_router,
        }

    @classmethod
    def from_env(
        cls,
        *,
        env: Mapping[str, str] | None = None,
    ) -> "RouterSettings":
        defaults = cls()
        get_str = runtime_env.get_str
        get_bool = runtime_env.get_bool
        get_int = runtime_env.get_int
        get_float = runtime_env.get_float

        stream_settings = RouterStreamSettings(
            queue_maxsize=runtime_env.get_int(
                "ROUTER_QUEUE_MAXSIZE",
                defaults.stream_settings.queue_maxsize,
                env=env,
            ),
            queue_overflow=runtime_env.get_str(
                "ROUTER_QUEUE_OVERFLOW",
                defaults.stream_settings.queue_overflow,
                env=env,
            ),
            handler_timeout_sec=runtime_env.get_float(
                "ROUTER_HANDLER_TIMEOUT",
                defaults.stream_settings.handler_timeout_sec,
                env=env,
            ),
        )

        return cls(
            mqtt_url=get_str("MQTT_URL", defaults.mqtt_url, env=env),
            online_announce=get_bool("ONLINE_ANNOUNCE", defaults.online_announce, env=env),
            online_text=get_str("ONLINE_ANNOUNCE_TEXT", defaults.online_text, env=env),
            topic_health_tts=get_str("TOPIC_HEALTH_TTS", defaults.topic_health_tts, env=env),
            topic_health_stt=get_str("TOPIC_HEALTH_STT", defaults.topic_health_stt, env=env),
            topic_health_router=get_str("TOPIC_HEALTH_ROUTER", defaults.topic_health_router, env=env),
            topic_stt_final=get_str("TOPIC_STT_FINAL", defaults.topic_stt_final, env=env),
            topic_tts_say=get_str("TOPIC_TTS_SAY", defaults.topic_tts_say, env=env),
            topic_tts_status=get_str("TOPIC_TTS_STATUS", defaults.topic_tts_status, env=env),
            topic_llm_req=get_str("TOPIC_LLM_REQUEST", defaults.topic_llm_req, env=env),
            topic_llm_resp=get_str("TOPIC_LLM_RESPONSE", defaults.topic_llm_resp, env=env),
            topic_llm_stream=get_str("TOPIC_LLM_STREAM", defaults.topic_llm_stream, env=env),
            topic_llm_cancel=get_str("TOPIC_LLM_CANCEL", defaults.topic_llm_cancel, env=env),
            topic_wake_event=get_str("TOPIC_WAKE_EVENT", defaults.topic_wake_event, env=env),
            topic_movement_test=get_str("TOPIC_MOVEMENT_TEST", defaults.topic_movement_test, env=env),
            topic_movement_stop=get_str("TOPIC_MOVEMENT_STOP", defaults.topic_movement_stop, env=env),
            topic_movement_status=get_str("TOPIC_MOVEMENT_STATUS", defaults.topic_movement_status, env=env),
            tts_voice=get_str(
                "ROUTER_TTS_VOICE",
                defaults.tts_voice,
                env=env,
                aliases=("PIPER_VOICE",),
            ),
            router_llm_tts_stream=get_bool("ROUTER_LLM_TTS_STREAM", defaults.router_llm_tts_stream, env=env),
            stream_min_chars=get_int(
                "ROUTER_STREAM_MIN_CHARS",
                defaults.stream_min_chars,
                env=env,
                aliases=("STREAM_MIN_CHARS",),
            ),
            stream_max_chars=get_int(
                "ROUTER_STREAM_MAX_CHARS",
                defaults.stream_max_chars,
                env=env,
                aliases=("STREAM_MAX_CHARS",),
            ),
            stream_boundary_chars=get_str(
                "ROUTER_STREAM_BOUNDARY_CHARS",
                defaults.stream_boundary_chars,
                env=env,
                aliases=("STREAM_BOUNDARY_CHARS",),
            ),
            stream_boundary_only=get_bool(
                "ROUTER_STREAM_BOUNDARY_ONLY",
                defaults.stream_boundary_only,
                env=env,
            ),
            stream_hard_max_chars=get_int(
                "ROUTER_STREAM_HARD_MAX_CHARS",
                defaults.stream_hard_max_chars,
                env=env,
            ),
            wake_phrases_raw=get_str(
                "ROUTER_WAKE_PHRASES",
                defaults.wake_phrases_raw,
                env=env,
                aliases=("WAKE_PHRASES",),
            ),
            wake_window_sec=get_float("ROUTER_WAKE_WINDOW_SEC", defaults.wake_window_sec, env=env),
            wake_ack_enabled=get_bool("ROUTER_WAKE_ACK_ENABLED", defaults.wake_ack_enabled, env=env),
            wake_ack_text=get_str("ROUTER_WAKE_ACK_TEXT", defaults.wake_ack_text, env=env),
            wake_ack_choices_raw=get_str(
                "ROUTER_WAKE_ACK_CHOICES",
                defaults.wake_ack_choices_raw,
                env=env,
                aliases=("WAKE_ACK_CHOICES",),
            ),
            wake_ack_style=get_str("ROUTER_WAKE_ACK_STYLE", defaults.wake_ack_style, env=env),
            wake_reprompt_text=get_str("ROUTER_WAKE_REPROMPT_TEXT", defaults.wake_reprompt_text, env=env),
            wake_interrupt_text=get_str("ROUTER_WAKE_INTERRUPT_TEXT", defaults.wake_interrupt_text, env=env),
            wake_resume_text=get_str("ROUTER_WAKE_RESUME_TEXT", defaults.wake_resume_text, env=env),
            wake_cancel_text=get_str("ROUTER_WAKE_CANCEL_TEXT", defaults.wake_cancel_text, env=env),
            wake_timeout_text=get_str("ROUTER_WAKE_TIMEOUT_TEXT", defaults.wake_timeout_text, env=env),
            live_mode_default=get_bool("ROUTER_LIVE_MODE_DEFAULT", defaults.live_mode_default, env=env),
            live_mode_enter_phrase=get_str("ROUTER_LIVE_MODE_ENTER_PHRASE", defaults.live_mode_enter_phrase, env=env),
            live_mode_exit_phrase=get_str("ROUTER_LIVE_MODE_EXIT_PHRASE", defaults.live_mode_exit_phrase, env=env),
            live_mode_enter_ack=get_str("ROUTER_LIVE_MODE_ENTER_ACK", defaults.live_mode_enter_ack, env=env),
            live_mode_exit_ack=get_str("ROUTER_LIVE_MODE_EXIT_ACK", defaults.live_mode_exit_ack, env=env),
            live_mode_active_hint=get_str("ROUTER_LIVE_MODE_ACTIVE_HINT", defaults.live_mode_active_hint, env=env),
            live_mode_inactive_hint=get_str("ROUTER_LIVE_MODE_INACTIVE_HINT", defaults.live_mode_inactive_hint, env=env),
            stream_settings=stream_settings,
        )
