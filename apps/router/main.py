from __future__ import annotations

"""Router service

Responsibilities:
- Aggregate retained health and announce system online once STT+TTS are ready.
- Handle STT final utterances: rule-based local responses or forward to LLM.
- Bridge LLM outputs (streaming and non-streaming) to TTS with sentence chunking.

Data contracts (JSON over MQTT):
- STT finals (topic: stt/final): { text, lang?, utt_id?, confidence?, timestamp?, is_final? }
- TTS say (topic: tts/say): { text, voice?, lang?, utt_id?, style?, stt_ts? }
- LLM request (topic: llm/request): { id, text, stream?, use_rag?, params? }
- LLM response (topic: llm/response): { id, reply, provider?, model? }
- LLM stream (topic: llm/stream): { id, seq, delta, done }
"""

import asyncio, os, logging, uuid, re
import orjson as json
from urllib.parse import urlparse
from dataclasses import dataclass
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
    # LLM → TTS streaming
    router_llm_tts_stream: bool = os.getenv("ROUTER_LLM_TTS_STREAM", "1").lower() in ("1", "true", "yes", "on")
    stream_min_chars: int = int(os.getenv("ROUTER_STREAM_MIN_CHARS", os.getenv("STREAM_MIN_CHARS", "60")))
    stream_max_chars: int = int(os.getenv("ROUTER_STREAM_MAX_CHARS", os.getenv("STREAM_MAX_CHARS", "240")))
    stream_boundary_chars: str = os.getenv("ROUTER_STREAM_BOUNDARY_CHARS", os.getenv("STREAM_BOUNDARY_CHARS", ".!?;:"))
    # If true, flush to TTS only when a sentence boundary is reached; ignore min/max thresholds (except final flush)
    stream_boundary_only: bool = os.getenv("ROUTER_STREAM_BOUNDARY_ONLY", "1").lower() in ("1", "true", "yes", "on")
    # Safety cap to avoid unbounded buffer growth when boundary never appears
    stream_hard_max_chars: int = int(os.getenv("ROUTER_STREAM_HARD_MAX_CHARS", "2000"))


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


class RouterService:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.ready = {"tts": False, "stt": False}
        self.announced = False
        self.llm_buf: Dict[str, str] = {}

    @staticmethod
    def parse_mqtt(url: str):
        u = urlparse(url)
        return (u.hostname or "127.0.0.1", u.port or 1883, u.username, u.password)

    async def publish(self, client: mqtt.Client, topic: str, payload: dict) -> None:
        await client.publish(topic, json.dumps(payload))

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

    async def handle_stt_final(self, client: mqtt.Client, payload: bytes) -> None:
        try:
            data = json.loads(payload)
        except Exception:
            logger.warning("Invalid STT payload (non-JSON)")
            return
        fields = {k: v for k, v in data.items() if k in {"text", "lang", "utt_id", "confidence", "timestamp", "is_final"}}
        u = Utterance(**fields)
        logger.info("Received utterance: %s", (u.text[:80] + ("..." if len(u.text) > 80 else "")))

        resp = self.rule_route(u.text)
        if resp is not None:
            say = TtsSay(text=resp["text"], voice="piper/en_US/amy", lang="en", utt_id=u.utt_id, style=resp["style"], stt_ts=u.timestamp)
            logger.info("Sending TTS response (rule): %s", (resp["text"][:50] + ("..." if len(resp["text"]) > 50 else "")))
            await self.publish(client, self.cfg.topic_tts_say, say.__dict__)
            return

        # Fallback to LLM (streaming); router will bridge output -> TTS
        req_id = u.utt_id or f"rt-{uuid.uuid4().hex[:8]}"
        llm_req = {"id": req_id, "text": u.text, "stream": True}
        logger.info("Routing to LLM: id=%s len=%d", req_id, len(u.text or ""))
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
