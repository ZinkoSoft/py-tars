from __future__ import annotations

"""Simple rule-based router that consumes STT and produces TTS requests via MQTT.

Enhancements:
- Aggregates service health and announces online via TTS once STT and TTS are ready.
- Bridges LLM outputs to TTS: consumes llm/stream or llm/response and emits sentence chunks to tts/say.
"""
import asyncio, os, logging, uuid
import orjson as json
from urllib.parse import urlparse
try:
    import uvloop
    uvloop.install()
except Exception:
    pass
from contextlib import AsyncExitStack
from dataclasses import dataclass
import asyncio_mqtt as mqtt
from asyncio_mqtt import MqttError

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("router")

MQTT_URL = os.getenv("MQTT_URL", "mqtt://tars:pass@127.0.0.1:1883")
# Online announcement config
ONLINE_ANNOUNCE = int(os.getenv("ONLINE_ANNOUNCE", "1"))
ONLINE_ANNOUNCE_TEXT = os.getenv("ONLINE_ANNOUNCE_TEXT", "System online.")
HEALTH_TTS_TOPIC = "system/health/tts"
HEALTH_STT_TOPIC = "system/health/stt"

# LLM -> TTS bridge config
ROUTER_LLM_TTS_STREAM = os.getenv("ROUTER_LLM_TTS_STREAM", "1").lower() in ("1", "true", "yes", "on")
LLM_STREAM_TOPIC = os.getenv("TOPIC_LLM_STREAM", "llm/stream")
LLM_RESPONSE_TOPIC = os.getenv("TOPIC_LLM_RESPONSE", "llm/response")
LLM_CANCEL_TOPIC = os.getenv("TOPIC_LLM_CANCEL", "llm/cancel")
LLM_REQUEST_TOPIC = os.getenv("TOPIC_LLM_REQUEST", "llm/request")
TTS_SAY_TOPIC = os.getenv("TOPIC_TTS_SAY", "tts/say")
STREAM_MIN_CHARS = int(os.getenv("ROUTER_STREAM_MIN_CHARS", os.getenv("STREAM_MIN_CHARS", "60")))
STREAM_MAX_CHARS = int(os.getenv("ROUTER_STREAM_MAX_CHARS", os.getenv("STREAM_MAX_CHARS", "240")))
STREAM_BOUNDARY_CHARS = os.getenv("ROUTER_STREAM_BOUNDARY_CHARS", os.getenv("STREAM_BOUNDARY_CHARS", ".!?;:") )

def parse_mqtt(url: str):
    u = urlparse(url)
    return (u.hostname or '127.0.0.1', u.port or 1883, u.username, u.password)

@dataclass
class Utterance:
    text: str
    lang: str = "en"
    utt_id: str | None = None
    confidence: float | None = None
    timestamp: float | None = None
    is_final: bool = True

def rule_route(text: str) -> dict | None:
    t = text.lower().strip()
    logger.debug(f"Processing rule routing for: {text[:50]}{'...' if len(text) > 50 else ''}")
    
    if any(x in t for x in ["what time", "time is it"]):
        from datetime import datetime
        now = datetime.now().strftime("%-I:%M %p")
        logger.info("Triggered time query rule")
        return {"text": f"It is {now}.", "style": "neutral"}
    
    if t.startswith("say "):
        logger.info("Triggered echo rule")
        return {"text": text[4:], "style": "neutral"}
    
    if "hello" in t or "hi" in t:
        logger.info("Triggered greeting rule")
        return {"text": "Hello! How can I help?", "style": "friendly"}
    
    logger.debug("No rule matched, will use fallback")
    return None

async def publish(c: mqtt.Client, topic: str, payload: dict) -> None:
    await c.publish(topic, json.dumps(payload))


# --- LLM -> TTS helpers ---
def _should_flush(buf: str, incoming: str = "") -> bool:
    # Flush when boundary punctuation present (no min length),
    # or when adding incoming would exceed max, or buffer already over min
    if any(ch in buf for ch in STREAM_BOUNDARY_CHARS):
        return True
    if len(buf) >= STREAM_MIN_CHARS:
        return True
    return len(buf) + len(incoming) >= STREAM_MAX_CHARS


def _split_on_boundary(text: str) -> tuple[str, str]:
    # Split at last boundary in text; return (sentence, remainder)
    idx = max((text.rfind(ch) for ch in STREAM_BOUNDARY_CHARS), default=-1)
    if idx >= 0:
        return text[: idx + 1].strip(), text[idx + 1 :].lstrip()
    return "", text

async def handle_utterance(c: mqtt.Client, payload: bytes) -> None:
    data = json.loads(payload)
    # Filter out any extra fields that Utterance doesn't expect
    utterance_fields = {k: v for k, v in data.items() if k in ['text', 'lang', 'utt_id', 'confidence', 'timestamp', 'is_final']}
    u = Utterance(**utterance_fields)
    logger.info(f"Received utterance: {u.text[:80]}{'...' if len(u.text) > 80 else ''}")
    
    resp = rule_route(u.text)
    if resp is not None:
        # Rule hit: speak locally via TTS
        out = {
            "text": resp["text"],
            "voice": "piper/en_US/amy",
            "lang": "en",
            "utt_id": u.utt_id,
            "style": resp["style"],
            "stt_ts": u.timestamp,
        }
        logger.info(f"Sending TTS response (rule): {resp['text'][:50]}{'...' if len(resp['text']) > 50 else ''}")
        await publish(c, TTS_SAY_TOPIC, out)
        return

    # No rule: route to LLM (streaming); router will bridge llm output -> tts
    req_id = u.utt_id or f"rt-{uuid.uuid4().hex[:8]}"
    llm_req = {"id": req_id, "text": u.text, "stream": True}
    logger.info("Routing to LLM: id=%s len=%d", req_id, len(u.text or ""))
    await publish(c, LLM_REQUEST_TOPIC, llm_req)

async def main() -> None:
    host, port, user, pwd = parse_mqtt(MQTT_URL)
    logger.info(f"Connecting to MQTT {host}:{port}")
    try:
        async with mqtt.Client(hostname=host, port=port, username=user, password=pwd, client_id="tars-router") as client:
            logger.info(f"Connected to MQTT {host}:{port} as tars-router")
            await publish(client, "system/health/router", {"ok": True, "event": "ready"})
            # Prepare message stream first to avoid missing retained messages
            # Use unfiltered_messages for broader compatibility across asyncio-mqtt versions
            async with client.unfiltered_messages() as mstream:
                # Subscribe to STT output, LLM outputs, and health topics for readiness aggregation
                topics = [
                    "stt/final",
                    HEALTH_TTS_TOPIC,
                    HEALTH_STT_TOPIC,
                    # LLM outputs (router will bridge to TTS)
                    LLM_STREAM_TOPIC,
                    LLM_RESPONSE_TOPIC,
                    LLM_CANCEL_TOPIC,
                ]
                for t in topics:
                    await client.subscribe(t)
                    logger.info(f"Subscribed to {t}")
                # Track readiness and announce once
                ready = {"tts": False, "stt": False}
                announced = False
                # LLM streaming buffers per request id
                llm_buf: dict[str, str] = {}
                async for m in mstream:
                    try:
                        topic = getattr(m, "topic", None)
                        # Normalize topic to string
                        if isinstance(topic, (bytes, bytearray)):
                            topic = topic.decode("utf-8", "ignore")
                        if not topic:
                            continue
                        if topic in (HEALTH_TTS_TOPIC, HEALTH_STT_TOPIC):
                            try:
                                data = json.loads(m.payload)
                            except Exception:
                                data = {}
                            ok = bool(data.get("ok", False))
                            if topic == HEALTH_TTS_TOPIC:
                                prev = ready["tts"]
                                ready["tts"] = ready["tts"] or ok
                                if ready["tts"] != prev:
                                    logger.info(f"Health TTS updated: ok={ok} -> state={ready}")
                            elif topic == HEALTH_STT_TOPIC:
                                prev = ready["stt"]
                                ready["stt"] = ready["stt"] or ok
                                if ready["stt"] != prev:
                                    logger.info(f"Health STT updated: ok={ok} -> state={ready}")
                            # Announce online once both ready and feature enabled
                            if ONLINE_ANNOUNCE and ready["tts"] and ready["stt"] and not announced:
                                announced = True
                                logger.info("All core services ready; announcing online")
                                await publish(client, TTS_SAY_TOPIC, {"text": ONLINE_ANNOUNCE_TEXT, "voice": "piper/en_US/amy", "lang": "en", "utt_id": "boot", "style": "neutral"})
                            continue

                        # Handle STT finals
                        if topic == "stt/final":
                            await handle_utterance(client, m.payload)
                            continue

                        # Handle LLM cancel (clear buffers)
                        if topic == LLM_CANCEL_TOPIC:
                            try:
                                data = json.loads(m.payload)
                            except Exception:
                                data = {}
                            cid = str(data.get("id") or "")
                            if cid and cid in llm_buf:
                                logger.info("Cancel received for id=%s; clearing buffer", cid)
                                llm_buf.pop(cid, None)
                            continue

                        # Bridge non-streamed LLM responses to TTS
                        if topic == LLM_RESPONSE_TOPIC:
                            if not ROUTER_LLM_TTS_STREAM:
                                # Even if streaming bridge disabled, non-stream direct responses can be spoken
                                pass
                            try:
                                data = json.loads(m.payload)
                            except Exception:
                                data = {}
                            text = (data.get("reply") or "").strip()
                            if text:
                                logger.info("LLM response -> TTS (len=%d)", len(text))
                                await publish(client, TTS_SAY_TOPIC, {"text": text})
                            continue

                        # Bridge streamed LLM deltas to TTS sentence chunks
                        if ROUTER_LLM_TTS_STREAM and topic == LLM_STREAM_TOPIC:
                            try:
                                data = json.loads(m.payload)
                            except Exception:
                                data = {}
                            rid = str(data.get("id") or "")
                            done = bool(data.get("done", False))
                            delta = (data.get("delta") or "")
                            if not rid:
                                continue
                            buf = llm_buf.get(rid, "")
                            if delta:
                                buf += delta
                                # Flush on boundaries; handle multiple in one go
                                flushed_any = False
                                while _should_flush(buf):
                                    sent, remainder = _split_on_boundary(buf)
                                    if not sent:
                                        # No boundary found; fallback: take a slice up to STREAM_MAX_CHARS or entire buf
                                        cut = min(len(buf), STREAM_MAX_CHARS)
                                        if cut <= 0:
                                            break
                                        sent, remainder = buf[:cut].strip(), buf[cut:].lstrip()
                                        if not sent:
                                            break
                                    logger.info("LLM stream -> TTS chunk (len=%d)", len(sent))
                                    await publish(client, TTS_SAY_TOPIC, {"text": sent})
                                    buf = remainder
                                    flushed_any = True
                                # Store remainder
                                llm_buf[rid] = buf
                                if not flushed_any:
                                    logger.debug("Buffered LLM id=%s len=%d", rid, len(buf))
                            if done:
                                final = llm_buf.pop(rid, "").strip()
                                if final:
                                    logger.info("LLM stream done -> final TTS chunk (len=%d)", len(final))
                                    await publish(client, TTS_SAY_TOPIC, {"text": final})
                            continue
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        await publish(client, "system/health/router", {"ok": False, "err": str(e)})
    except MqttError as e:
        logger.info(f"MQTT disconnected: {e}; shutting down gracefully")

if __name__ == "__main__":
    asyncio.run(main())
