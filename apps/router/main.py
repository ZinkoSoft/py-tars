import asyncio, os, logging
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

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("router")

MQTT_URL = os.getenv("MQTT_URL", "mqtt://tars:pass@127.0.0.1:1883")

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

async def publish(c: mqtt.Client, topic: str, payload: dict):
    await c.publish(topic, json.dumps(payload))

async def handle_utterance(c: mqtt.Client, payload: bytes):
    data = json.loads(payload)
    # Filter out any extra fields that Utterance doesn't expect
    utterance_fields = {k: v for k, v in data.items() if k in ['text', 'lang', 'utt_id', 'confidence', 'timestamp', 'is_final']}
    u = Utterance(**utterance_fields)
    logger.info(f"Received utterance: {u.text[:80]}{'...' if len(u.text) > 80 else ''}")
    
    resp = rule_route(u.text)
    if resp is None:
        # fallback smalltalk – keep it local and short for now
        logger.info("Using fallback response")
        resp = {"text": f"Roger that. {u.text}", "style": "neutral"}
    
    # Include STT timestamp to track end-to-end latency on the TTS side
    out = {
        "text": resp["text"],
        "voice": "piper/en_US/amy",
        "lang": "en",
        "utt_id": u.utt_id,
        "style": resp["style"],
        "stt_ts": u.timestamp
    }
    logger.info(f"Sending TTS response: {resp['text'][:50]}{'...' if len(resp['text']) > 50 else ''}")
    await publish(c, "tts/say", out)

async def main():
    host, port, user, pwd = parse_mqtt(MQTT_URL)
    logger.info(f"Connecting to MQTT {host}:{port}")
    async with mqtt.Client(hostname=host, port=port, username=user, password=pwd, client_id="tars-router") as client:
        logger.info(f"Connected to MQTT {host}:{port} as tars-router")
        await publish(client, "system/health/router", {"ok": True, "event": "ready"})
        await client.subscribe("stt/final")
        logger.info("Subscribed to stt/final, ready to process messages")
        msgs = client.messages()
        async with msgs as mstream:
            # warm TTS
            logger.info("Sending startup message to TTS")
            await publish(client, "tts/say", {"text": "Systems ready.", "voice": "piper/en_US/amy", "lang": "en", "utt_id": "boot", "style": "neutral"})
            async for m in mstream:
                try:
                    await handle_utterance(client, m.payload)
                except Exception as e:
                    logger.error(f"Error processing utterance: {e}")
                    await publish(client, "system/health/router", {"ok": False, "err": str(e)})

if __name__ == "__main__":
    asyncio.run(main())
