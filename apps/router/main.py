from __future__ import annotations

"""Router service

Responsibilities:
- Aggregate retained health and announce system online once STT+TTS are ready.
- Handle STT final utterances: rule-based local responses or forward to LLM.
- Enforce wake-word/live-mode gating so we only contact the LLM when explicitly requested.
- Bridge LLM outputs (streaming and non-streaming) to TTS with sentence chunking.

Data contracts (JSON over MQTT):
- STT finals (topic: stt/final): { text, lang?, utt_id?, confidence?, timestamp?, is_final? }
- TTS say (topic: tts/say): { text, voice?, lang?, utt_id?, style?, stt_ts? }
- LLM request (topic: llm/request): { id, text, stream?, use_rag?, params? }
- LLM response (topic: llm/response): { id, reply, provider?, model? }
- LLM stream (topic: llm/stream): { id, seq, delta, done }
"""

import asyncio, os, logging, uuid, re, time, itertools
import orjson as json
from urllib.parse import urlparse
from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict

try:
    import uvloop
    uvloop.install()
except Exception:
    pass

import asyncio_mqtt as mqtt
from asyncio_mqtt import MqttError


# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("router")


@dataclass
class Config:
    mqtt_url: str = os.getenv("MQTT_URL", "mqtt://tars:pass@127.0.0.1:1883")
    online_announce: bool = os.getenv("ONLINE_ANNOUNCE", "1").lower() in ("1", "true", "yes", "on")
    online_text: str = os.getenv("ONLINE_ANNOUNCE_TEXT", "System online.")
    # Topics
    topic_health_tts: str = os.getenv("TOPIC_HEALTH_TTS", "system/health/tts")
    topic_health_stt: str = os.getenv("TOPIC_HEALTH_STT", "system/health/stt")
    topic_stt_final: str = os.getenv("TOPIC_STT_FINAL", "stt/final")
    topic_tts_say: str = os.getenv("TOPIC_TTS_SAY", "tts/say")
    topic_llm_req: str = os.getenv("TOPIC_LLM_REQUEST", "llm/request")
    topic_llm_resp: str = os.getenv("TOPIC_LLM_RESPONSE", "llm/response")
    topic_llm_stream: str = os.getenv("TOPIC_LLM_STREAM", "llm/stream")
    topic_llm_cancel: str = os.getenv("TOPIC_LLM_CANCEL", "llm/cancel")
    topic_wake_event: str = os.getenv("TOPIC_WAKE_EVENT", "wake/event")
    # LLM → TTS streaming
    router_llm_tts_stream: bool = os.getenv("ROUTER_LLM_TTS_STREAM", "1").lower() in ("1", "true", "yes", "on")
    stream_min_chars: int = int(os.getenv("ROUTER_STREAM_MIN_CHARS", os.getenv("STREAM_MIN_CHARS", "60")))
    stream_max_chars: int = int(os.getenv("ROUTER_STREAM_MAX_CHARS", os.getenv("STREAM_MAX_CHARS", "240")))
    stream_boundary_chars: str = os.getenv("ROUTER_STREAM_BOUNDARY_CHARS", os.getenv("STREAM_BOUNDARY_CHARS", ".!?;:"))
    # If true, flush to TTS only when a sentence boundary is reached; ignore min/max thresholds (except final flush)
    stream_boundary_only: bool = os.getenv("ROUTER_STREAM_BOUNDARY_ONLY", "1").lower() in ("1", "true", "yes", "on")
    # Safety cap to avoid unbounded buffer growth when boundary never appears
    stream_hard_max_chars: int = int(os.getenv("ROUTER_STREAM_HARD_MAX_CHARS", "2000"))
    # Wake word + live mode gating
    wake_phrases_raw: str = os.getenv("ROUTER_WAKE_PHRASES", os.getenv("WAKE_PHRASES", "hey tars"))
    wake_window_sec: float = float(os.getenv("ROUTER_WAKE_WINDOW_SEC", "8"))
    wake_ack_enabled: bool = os.getenv("ROUTER_WAKE_ACK_ENABLED", "1").lower() in ("1", "true", "yes", "on")
    wake_ack_text: str = os.getenv("ROUTER_WAKE_ACK_TEXT", "Yes?")
    wake_ack_choices_raw: str = os.getenv("ROUTER_WAKE_ACK_CHOICES", os.getenv("WAKE_ACK_CHOICES", "Hmm?|Huh?|Yes?"))
    wake_ack_style: str = os.getenv("ROUTER_WAKE_ACK_STYLE", "friendly")
    wake_reprompt_text: str = os.getenv("ROUTER_WAKE_REPROMPT_TEXT", "")
    wake_interrupt_text: str = os.getenv("ROUTER_WAKE_INTERRUPT_TEXT", "")
    wake_resume_text: str = os.getenv("ROUTER_WAKE_RESUME_TEXT", "")
    wake_cancel_text: str = os.getenv("ROUTER_WAKE_CANCEL_TEXT", "")
    wake_timeout_text: str = os.getenv("ROUTER_WAKE_TIMEOUT_TEXT", "")
    live_mode_default: bool = os.getenv("ROUTER_LIVE_MODE_DEFAULT", "0").lower() in ("1", "true", "yes", "on")
    live_mode_enter_phrase: str = os.getenv("ROUTER_LIVE_MODE_ENTER_PHRASE", "enter live mode")
    live_mode_exit_phrase: str = os.getenv("ROUTER_LIVE_MODE_EXIT_PHRASE", "exit live mode")
    live_mode_enter_ack: str = os.getenv("ROUTER_LIVE_MODE_ENTER_ACK", "Live mode enabled.")
    live_mode_exit_ack: str = os.getenv("ROUTER_LIVE_MODE_EXIT_ACK", "Live mode disabled.")
    live_mode_active_hint: str = os.getenv("ROUTER_LIVE_MODE_ACTIVE_HINT", "Live mode is already active.")
    live_mode_inactive_hint: str = os.getenv("ROUTER_LIVE_MODE_INACTIVE_HINT", "Live mode is already off.")
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


@dataclass
class Utterance:
    text: str
    lang: str = "en"
    utt_id: Optional[str] = None
    confidence: Optional[float] = None
    timestamp: Optional[float] = None
    is_final: bool = True


@dataclass
class TtsSay:
    text: str
    voice: Optional[str] = None
    lang: Optional[str] = None
    utt_id: Optional[str] = None
    style: Optional[str] = None
    stt_ts: Optional[float] = None
    wake_ack: Optional[bool] = None


class RouterService:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.ready = {"tts": False, "stt": False}
        self.announced = False
        self.llm_buf: Dict[str, str] = {}
        self.live_mode: bool = cfg.live_mode_default
        self.wake_active_until: float = 0.0
        self.wake_session_active: bool = False
        wake_pattern = "|".join(re.escape(phrase) for phrase in self.cfg.wake_phrases)
        self.wake_regex = re.compile(rf"^\s*(?:{wake_pattern})\b[\s,]*", re.IGNORECASE)
        self._wake_ack_cycle = itertools.cycle(self.cfg.wake_ack_choices) if self.cfg.wake_ack_choices else None

    @staticmethod
    def parse_mqtt(url: str):
        u = urlparse(url)
        return (u.hostname or "127.0.0.1", u.port or 1883, u.username, u.password)

    async def publish(self, client: mqtt.Client, topic: str, payload: dict) -> None:
        await client.publish(topic, json.dumps(payload))

    async def _speak(
        self,
        client: mqtt.Client,
        text: str,
        style: str = "neutral",
        utt_id: Optional[str] = None,
        wake_ack: bool | None = None,
    ) -> None:
        if not text:
            return
        say = TtsSay(
            text=text,
            voice="piper/en_US/amy",
            lang="en",
            utt_id=utt_id,
            style=style,
            wake_ack=wake_ack,
        )
        await self.publish(client, self.cfg.topic_tts_say, say.__dict__)

    @staticmethod
    def _normalize_command(text: str) -> str:
        cleaned = re.sub(r"[^a-z0-9\s]", "", text.lower())
        return re.sub(r"\s+", " ", cleaned).strip()

    def _strip_wake_phrase(self, text: str) -> Optional[str]:
        match = self.wake_regex.match(text)
        if not match:
            return None
        remainder = text[match.end():].strip()
        return remainder

    def _open_wake_window(self) -> None:
        self.wake_session_active = True
        self.wake_active_until = time.monotonic() + self.cfg.wake_window_sec

    def _close_wake_window(self) -> None:
        self.wake_session_active = False
        self.wake_active_until = 0.0

    # ---------- Rule routing ----------
    @staticmethod
    def rule_route(text: str) -> Optional[dict]:
        t = text.lower().strip()
        logger.debug("Processing rule routing for: %s", (text[:50] + ("..." if len(text) > 50 else "")))

        if any(x in t for x in ("what time", "time is it")):
            from datetime import datetime

            now = datetime.now().strftime("%-I:%M %p")
            logger.info("Triggered time query rule")
            return {"text": f"It is {now}.", "style": "neutral"}

        if t.startswith("say "):
            logger.info("Triggered echo rule")
            return {"text": text[4:], "style": "neutral"}

        # Only match greetings as standalone words to avoid false positives like 'hi' in 'third'
        if re.search(r"\b(hello|hi|hey|hiya|howdy)\b", t):
            logger.info("Triggered greeting rule")
            return {"text": "Hello! How can I help?", "style": "friendly"}

        logger.debug("No rule matched, will use LLM fallback")
        return None

    # ---------- LLM streaming helpers ----------
    def _should_flush(self, buf: str, incoming: str = "") -> bool:
        # If configured, only flush when we have a sentence boundary present in the buffer
        if self.cfg.stream_boundary_only:
            return any(ch in buf for ch in self.cfg.stream_boundary_chars)
        # Otherwise allow early flush based on thresholds
        if any(ch in buf for ch in self.cfg.stream_boundary_chars):
            return True
        if len(buf) >= self.cfg.stream_min_chars:
            return True
        return len(buf) + len(incoming) >= self.cfg.stream_max_chars

    def _split_on_boundary(self, text: str) -> Tuple[str, str]:
        # Prefer a boundary character that is followed by whitespace or end-of-string
        idx = -1
        for i in range(len(text) - 1, -1, -1):
            ch = text[i]
            if ch in self.cfg.stream_boundary_chars:
                if i == len(text) - 1 or text[i + 1].isspace():
                    idx = i
                    break
        # If not found, fall back to any boundary character (last occurrence)
        if idx < 0:
            idx = max((text.rfind(ch) for ch in self.cfg.stream_boundary_chars), default=-1)
        if idx >= 0:
            return text[: idx + 1].strip(), text[idx + 1 :].lstrip()
        return "", text

    # ---------- Handlers ----------
    async def handle_health(self, client: mqtt.Client, topic: str, payload: bytes) -> None:
        try:
            data = json.loads(payload)
        except Exception:
            data = {}
        ok = bool(data.get("ok", False))
        if topic == self.cfg.topic_health_tts:
            prev = self.ready["tts"]
            self.ready["tts"] = self.ready["tts"] or ok
            if self.ready["tts"] != prev:
                logger.info("Health TTS updated: ok=%s -> state=%s", ok, self.ready)
        elif topic == self.cfg.topic_health_stt:
            prev = self.ready["stt"]
            self.ready["stt"] = self.ready["stt"] or ok
            if self.ready["stt"] != prev:
                logger.info("Health STT updated: ok=%s -> state=%s", ok, self.ready)

        if self.cfg.online_announce and self.ready["tts"] and self.ready["stt"] and not self.announced:
            self.announced = True
            logger.info("All core services ready; announcing online")
            await self.publish(
                client,
                self.cfg.topic_tts_say,
                TtsSay(
                    text=self.cfg.online_text,
                    voice="piper/en_US/amy",
                    lang="en",
                    utt_id="boot",
                    style="neutral",
                ).__dict__,
            )

    async def handle_wake_event(self, client: mqtt.Client, payload: bytes) -> None:
        try:
            data = json.loads(payload)
        except Exception:
            logger.warning("Invalid wake/event payload (non-JSON)")
            return

        event_type = str(data.get("type") or "").lower()
        tts_id = data.get("tts_id")

        if event_type == "wake":
            logger.info("Wake event received; opening window for %.1fs", self.cfg.wake_window_sec)
            self._open_wake_window()
            ack_text = None
            if self._wake_ack_cycle is not None:
                ack_text = next(self._wake_ack_cycle)
            elif self.cfg.wake_ack_text:
                ack_text = self.cfg.wake_ack_text
            if ack_text:
                ack_utt_id = tts_id or f"wake-ack-{int(time.time() * 1000)}"
                logger.debug("Wake ack utterance id=%s text=%s", ack_utt_id, ack_text)
                await self._speak(client, ack_text, style=self.cfg.wake_ack_style, utt_id=ack_utt_id, wake_ack=True)
            if self.cfg.wake_reprompt_text:
                await self._speak(client, self.cfg.wake_reprompt_text, utt_id=tts_id)
        elif event_type == "interrupt":
            logger.info("Wake interrupt event; keeping window open for %.1fs", self.cfg.wake_window_sec)
            self._open_wake_window()
            if self.cfg.wake_interrupt_text:
                await self._speak(client, self.cfg.wake_interrupt_text, utt_id=tts_id)
        elif event_type == "resume":
            logger.info("Wake resume event received; closing window")
            self._close_wake_window()
            if self.cfg.wake_resume_text:
                await self._speak(client, self.cfg.wake_resume_text, utt_id=tts_id)
        elif event_type == "cancelled":
            logger.info("Wake cancelled event received; closing window")
            self._close_wake_window()
            if self.cfg.wake_cancel_text:
                await self._speak(client, self.cfg.wake_cancel_text, utt_id=tts_id)
        elif event_type == "timeout":
            logger.info("Wake timeout event received; closing window")
            self._close_wake_window()
            if self.cfg.wake_timeout_text:
                await self._speak(client, self.cfg.wake_timeout_text, utt_id=tts_id)
        else:
            logger.debug("Ignoring wake/event type=%s", event_type)

    async def handle_stt_final(self, client: mqtt.Client, payload: bytes) -> None:
        try:
            data = json.loads(payload)
        except Exception:
            logger.warning("Invalid STT payload (non-JSON)")
            return
        fields = {k: v for k, v in data.items() if k in {"text", "lang", "utt_id", "confidence", "timestamp", "is_final"}}
        u = Utterance(**fields)
        logger.info("Received utterance: %s", (u.text[:80] + ("..." if len(u.text) > 80 else "")))

        if not u.text or not u.text.strip():
            return

        raw_text = u.text.strip()
        now = time.monotonic()

        if self.wake_session_active and now > self.wake_active_until:
            logger.info("Wake window expired (%.1fs past deadline)", now - self.wake_active_until)
            self._close_wake_window()

        candidate_text = raw_text
        remainder = self._strip_wake_phrase(raw_text)
        if remainder is not None and remainder:
            candidate_text = remainder

        window_active = self.wake_session_active
        gating_reason: Optional[str] = None
        if self.live_mode:
            gating_reason = "live-mode"
        elif window_active:
            gating_reason = "wake-event"

        if not self.live_mode and not window_active:
            logger.info("Dropping utterance outside wake session: %s", candidate_text)
            return

        norm_candidate = self._normalize_command(candidate_text)

        if norm_candidate == self.cfg.live_mode_enter_phrase:
            if self.live_mode:
                logger.info("Live mode already active")
                await self._speak(client, self.cfg.live_mode_active_hint, utt_id=u.utt_id)
            else:
                logger.info("Enabling live mode via command")
                self.live_mode = True
                self._close_wake_window()
                await self._speak(client, self.cfg.live_mode_enter_ack, utt_id=u.utt_id)
            return

        if norm_candidate == self.cfg.live_mode_exit_phrase:
            if not self.live_mode:
                logger.info("Live mode already inactive")
                await self._speak(client, self.cfg.live_mode_inactive_hint, utt_id=u.utt_id)
            else:
                logger.info("Disabling live mode via command")
                self.live_mode = False
                self._close_wake_window()
                await self._speak(client, self.cfg.live_mode_exit_ack, utt_id=u.utt_id)
            return

        if window_active:
            self._close_wake_window()

        logger.debug("Routing utterance via %s", gating_reason or "wake")

        resp = self.rule_route(candidate_text)
        if resp is not None:
            say = TtsSay(text=resp["text"], voice="piper/en_US/amy", lang="en", utt_id=u.utt_id, style=resp["style"], stt_ts=u.timestamp)
            logger.info("Sending TTS response (rule): %s", (resp["text"][:50] + ("..." if len(resp["text"]) > 50 else "")))
            await self.publish(client, self.cfg.topic_tts_say, say.__dict__)
            return

        # Fallback to LLM (streaming); router will bridge output -> TTS
        req_id = u.utt_id or f"rt-{uuid.uuid4().hex[:8]}"
        llm_req = {"id": req_id, "text": candidate_text, "stream": True}
        logger.info("Routing to LLM (%s): id=%s len=%d", gating_reason, req_id, len(candidate_text or ""))
        await self.publish(client, self.cfg.topic_llm_req, llm_req)

    async def handle_llm_cancel(self, _client: mqtt.Client, payload: bytes) -> None:
        try:
            data = json.loads(payload)
        except Exception:
            data = {}
        rid = str(data.get("id") or "")
        if rid and rid in self.llm_buf:
            logger.info("Cancel received for id=%s; clearing buffer", rid)
            self.llm_buf.pop(rid, None)

    async def handle_llm_response(self, client: mqtt.Client, payload: bytes) -> None:
        try:
            data = json.loads(payload)
        except Exception:
            data = {}
        rid = str(data.get("id") or "")
        text = (data.get("reply") or "").strip()
        if not text:
            return
        logger.info("LLM response -> TTS (len=%d)", len(text))
        await self.publish(client, self.cfg.topic_tts_say, TtsSay(text=text, utt_id=rid or None).__dict__)

    async def handle_llm_stream(self, client: mqtt.Client, payload: bytes) -> None:
        if not self.cfg.router_llm_tts_stream:
            return
        try:
            data = json.loads(payload)
        except Exception:
            data = {}
        rid = str(data.get("id") or "")
        done = bool(data.get("done", False))
        delta = (data.get("delta") or "")
        if not rid:
            return
        buf = self.llm_buf.get(rid, "")
        if delta:
            buf += delta
            flushed_any = False
            # Only flush when a boundary is reached (or thresholds when not in boundary-only mode)
            while self._should_flush(buf):
                sent, remainder = self._split_on_boundary(buf)
                if not sent:
                    # In boundary-only mode, avoid forced mid-sentence cuts; break and wait for more tokens
                    if self.cfg.stream_boundary_only:
                        break
                    # Fallback: enforce a max chunk size when not boundary-only
                    cut = min(len(buf), self.cfg.stream_max_chars)
                    if cut <= 0:
                        break
                    sent, remainder = buf[:cut].strip(), buf[cut:].lstrip()
                    if not sent:
                        break
                logger.info("LLM stream -> TTS chunk (len=%d)", len(sent))
                await self.publish(client, self.cfg.topic_tts_say, TtsSay(text=sent, utt_id=rid or None).__dict__)
                buf = remainder
                flushed_any = True
            self.llm_buf[rid] = buf
            if not flushed_any:
                logger.debug("Buffered LLM id=%s len=%d", rid, len(buf))
            # Safety: if boundary never appears and buffer grows too large, perform a soft cut at whitespace
            if self.cfg.stream_boundary_only and len(buf) > self.cfg.stream_hard_max_chars:
                # Find last whitespace within hard cap window to cut
                cut_idx = buf.rfind(" ", 0, self.cfg.stream_hard_max_chars)
                if cut_idx <= 0:
                    cut_idx = self.cfg.stream_hard_max_chars
                sent, remainder = buf[:cut_idx].strip(), buf[cut_idx:].lstrip()
                if sent:
                    logger.info("LLM stream (safety cut) -> TTS chunk (len=%d)", len(sent))
                    await self.publish(client, self.cfg.topic_tts_say, TtsSay(text=sent).__dict__)
                    self.llm_buf[rid] = remainder
        if done:
            final = self.llm_buf.pop(rid, "").strip()
            if final:
                logger.info("LLM stream done -> final TTS chunk (len=%d)", len(final))
                await self.publish(client, self.cfg.topic_tts_say, TtsSay(text=final, utt_id=rid or None).__dict__)

    # ---------- Main loop ----------
    async def run(self) -> None:
        host, port, user, pwd = self.parse_mqtt(self.cfg.mqtt_url)
        backoff = 1.0
        while True:
            logger.info("Connecting to MQTT %s:%s", host, port)
            try:
                async with mqtt.Client(hostname=host, port=port, username=user, password=pwd, client_id="tars-router") as client:
                    logger.info("Connected to MQTT %s:%s as tars-router", host, port)
                    await self.publish(client, "system/health/router", {"ok": True, "event": "ready"})
                    # Reset announce state on reconnect? Keep it sticky so we don't re-announce.

                    # Use unfiltered_messages for broad compatibility and to ensure retained messages are captured
                    async with client.unfiltered_messages() as mstream:
                        # Subscribe to topics
                        topics = [
                            self.cfg.topic_stt_final,
                            self.cfg.topic_health_tts,
                            self.cfg.topic_health_stt,
                            self.cfg.topic_llm_stream,
                            self.cfg.topic_llm_resp,
                            self.cfg.topic_llm_cancel,
                            self.cfg.topic_wake_event,
                        ]
                        for t in topics:
                            await client.subscribe(t)
                            logger.info("Subscribed to %s", t)

                        backoff = 1.0  # reset backoff after successful connect
                        async for m in mstream:
                            topic = getattr(m, "topic", "")
                            if isinstance(topic, (bytes, bytearray)):
                                topic = topic.decode("utf-8", "ignore")
                            try:
                                if topic in (self.cfg.topic_health_tts, self.cfg.topic_health_stt):
                                    await self.handle_health(client, topic, m.payload)
                                elif topic == self.cfg.topic_stt_final:
                                    await self.handle_stt_final(client, m.payload)
                                elif topic == self.cfg.topic_llm_cancel:
                                    await self.handle_llm_cancel(client, m.payload)
                                elif topic == self.cfg.topic_llm_resp:
                                    await self.handle_llm_response(client, m.payload)
                                elif topic == self.cfg.topic_llm_stream:
                                    await self.handle_llm_stream(client, m.payload)
                                elif topic == self.cfg.topic_wake_event:
                                    await self.handle_wake_event(client, m.payload)
                            except Exception as e:
                                logger.error("Error processing message: %s", e)
                                await self.publish(client, "system/health/router", {"ok": False, "err": str(e)})
            except MqttError as e:
                logger.info("MQTT disconnected: %s; retrying in %.1fs", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 8.0)


def main() -> None:
    svc = RouterService(Config())
    asyncio.run(svc.run())


if __name__ == "__main__":
    main()
