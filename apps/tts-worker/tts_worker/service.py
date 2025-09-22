from __future__ import annotations

import asyncio
import logging
import time
from urllib.parse import urlparse

import asyncio_mqtt as mqtt
import orjson as json

from .config import MQTT_URL, TTS_STREAMING, TTS_PIPELINE
from .piper_synth import PiperSynth


logger = logging.getLogger("tts-worker")


def parse_mqtt(url: str):
    u = urlparse(url)
    return (u.hostname or "127.0.0.1", u.port or 1883, u.username, u.password)


class TTSService:
    def __init__(self, synth: PiperSynth):
        self.synth = synth

    async def run(self):
        host, port, username, password = parse_mqtt(MQTT_URL)
        logger.info(f"Connecting to MQTT {host}:{port}")
        async with mqtt.Client(hostname=host, port=port, username=username, password=password, client_id="tars-tts") as client:
            logger.info(f"Connected to MQTT {host}:{port} as tars-tts")
            await client.publish("system/health/tts", json.dumps({"ok": True, "event": "ready"}))
            await client.subscribe("tts/say")
            logger.info("Subscribed to tts/say, ready to process messages")
            async with client.messages() as messages:
                async for msg in messages:
                    try:
                        data = json.loads(msg.payload)
                        text = data.get("text", "").strip()
                        stt_ts = data.get("stt_ts") or data.get("timestamp")
                        if not text:
                            continue
                        await self._speak(client, text, stt_ts)
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        await client.publish("system/health/tts", json.dumps({"ok": False, "err": str(e)}))

    async def _speak(self, mqtt_client: mqtt.Client, text: str, stt_ts: float | None):
        # Notify start
        start_msg = json.dumps({"event": "speaking_start", "text": text, "timestamp": time.time()})
        await mqtt_client.publish("tts/status", start_msg)
        logger.info(f"Published TTS start status: {start_msg}")

        t0 = time.time()
        elapsed = self.synth.synth_and_play(text, streaming=bool(TTS_STREAMING), pipeline=bool(TTS_PIPELINE))
        t1 = time.time()
        if stt_ts is not None:
            logger.info(f"TTS time: {(t1 - stt_ts):.3f}s from STT final to playback-finished; time-to-first-audio ~{(elapsed if TTS_STREAMING else 0.0):.3f}s")
        else:
            logger.info(f"TTS playback finished in {(t1 - t0):.3f}s")

        # Notify end
        end_msg = json.dumps({"event": "speaking_end", "text": text, "timestamp": time.time()})
        await mqtt_client.publish("tts/status", end_msg)
        logger.info(f"Published TTS end status: {end_msg}")
