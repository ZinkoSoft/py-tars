from __future__ import annotations

import logging
import time
from urllib.parse import urlparse
import asyncio

import asyncio_mqtt as mqtt
import orjson as json
from asyncio_mqtt import MqttError
from markdown import markdown as md_render
from bs4 import BeautifulSoup
from html import unescape

import tempfile
from typing import Any

from .config import MQTT_URL, TTS_STREAMING, TTS_PIPELINE, TTS_AGGREGATE, TTS_AGGREGATE_DEBOUNCE_MS, TTS_AGGREGATE_SINGLE_WAV
from .piper_synth import PiperSynth, _spawn_player


logger = logging.getLogger("tts-worker")


def parse_mqtt(url: str):
    u = urlparse(url)
    return (u.hostname or "127.0.0.1", u.port or 1883, u.username, u.password)


class TTSService:
    def __init__(self, synth: Any):
        self.synth = synth
        # Aggregation state
        self._agg_id: str | None = None
        self._agg_texts: list[str] = []
        self._agg_timer: asyncio.TimerHandle | None = None
        # Ensure only one playback happens at a time to avoid overlapping audio
        self._play_lock = asyncio.Lock()

    def _cancel_timer(self):
        try:
            if self._agg_timer and not self._agg_timer.cancelled():
                self._agg_timer.cancel()
        except Exception:
            pass
        self._agg_timer = None

    def _schedule_flush(self, loop: asyncio.AbstractEventLoop, client: mqtt.Client, stt_ts: float | None):
        delay = max(0.01, TTS_AGGREGATE_DEBOUNCE_MS / 1000.0)

        def _cb():
            asyncio.create_task(self._flush_aggregate(client, stt_ts))

        self._cancel_timer()
        self._agg_timer = loop.call_later(delay, _cb)

    async def _flush_aggregate(self, client: mqtt.Client, stt_ts: float | None):
        self._cancel_timer()
        if not self._agg_texts:
            return
        logger.debug("Flushing TTS aggregate: count=%d single_wav=%s", len(self._agg_texts), bool(TTS_AGGREGATE_SINGLE_WAV))
        if TTS_AGGREGATE_SINGLE_WAV:
            text = " ".join(t.strip() for t in self._agg_texts if t and t.strip())
            self._agg_texts.clear()
            self._agg_id = None
            # For a single WAV, disable streaming/pipeline to ensure a single continuous file
            await self._speak(client, text, stt_ts, streaming_override=False, pipeline_override=False)
        else:
            texts = [t.strip() for t in self._agg_texts if t and t.strip()]
            self._agg_texts.clear()
            self._agg_id = None
            for t in texts:
                await self._speak(client, t, stt_ts)

    @staticmethod
    def md_to_text(md: str) -> str:
        """Convert Markdown to plain text for clean TTS.

        - Renders Markdown to HTML using python-markdown (with a couple of safe extensions)
        - Strips HTML to text via BeautifulSoup
        - Normalizes whitespace and unescapes HTML entities
        """
        if not md:
            return ""
        try:
            html = md_render(md, extensions=["extra", "sane_lists"])  # type: ignore[arg-type]
        except Exception:
            # If markdown parsing fails for any reason, fall back to raw text
            html = md
        text = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
        return unescape(" ".join(text.split()))

    async def run(self) -> None:
        host, port, username, password = parse_mqtt(MQTT_URL)
        logger.info(f"Connecting to MQTT {host}:{port}")
        try:
            async with mqtt.Client(hostname=host, port=port, username=username, password=password, client_id="tars-tts") as client:
                logger.info(f"Connected to MQTT {host}:{port} as tars-tts")
                await client.publish("system/health/tts", json.dumps({"ok": True, "event": "ready"}), retain=True)
                await client.subscribe("tts/say")
                logger.info("Subscribed to tts/say, ready to process messages")
                async with client.messages() as messages:
                    async for msg in messages:
                        try:
                            data = json.loads(msg.payload)
                            raw_text = data.get("text", "")
                            text = self.md_to_text(raw_text)
                            stt_ts = data.get("stt_ts") or data.get("timestamp")
                            utt_id = data.get("utt_id") or ""
                            if not text:
                                continue
                            if TTS_AGGREGATE and utt_id:
                                loop = asyncio.get_running_loop()
                                if self._agg_id and self._agg_id != utt_id and self._agg_texts:
                                    # Flush previous id immediately when id changes
                                    await self._flush_aggregate(client, stt_ts)
                                self._agg_id = utt_id
                                self._agg_texts.append(text)
                                self._schedule_flush(loop, client, stt_ts)
                                continue
                            # Non-aggregated path or missing utt_id: flush any pending aggregate first
                            if self._agg_texts:
                                await self._flush_aggregate(client, stt_ts)
                            await self._speak(client, text, stt_ts)
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
                            await client.publish("system/health/tts", json.dumps({"ok": False, "err": str(e)}), retain=True)
        except MqttError as e:
            logger.info(f"MQTT disconnected: {e}; shutting down gracefully")

    async def _speak(self, mqtt_client: mqtt.Client, text: str, stt_ts: float | None, *, streaming_override: bool | None = None, pipeline_override: bool | None = None) -> None:
        if self._play_lock.locked():
            logger.debug("Playback busy; queuing next utterance (len=%d)", len(text or ""))
        async with self._play_lock:
            logger.debug("Playback start (len=%d)", len(text or ""))
            # Notify start (emit when we actually start speaking to match playback timing)
            start_msg = json.dumps({"event": "speaking_start", "text": text, "timestamp": time.time()})
            await mqtt_client.publish("tts/status", start_msg)
            logger.info(f"Published TTS start status: {start_msg}")

            t0 = time.time()
            streaming = bool(TTS_STREAMING) if streaming_override is None else bool(streaming_override)
            pipeline = bool(TTS_PIPELINE) if pipeline_override is None else bool(pipeline_override)
            # Offload blocking synthesis/playback to a thread to keep event loop responsive
            elapsed = await asyncio.to_thread(self._do_synth_and_play_blocking, text, streaming, pipeline)
            t1 = time.time()
            if stt_ts is not None:
                logger.info(f"TTS time: {(t1 - stt_ts):.3f}s from STT final to playback-finished; time-to-first-audio ~{(elapsed if TTS_STREAMING else 0.0):.3f}s")
            else:
                logger.info(f"TTS playback finished in {(t1 - t0):.3f}s")

            # Notify end
            end_msg = json.dumps({"event": "speaking_end", "text": text, "timestamp": time.time()})
            await mqtt_client.publish("tts/status", end_msg)
            logger.info(f"Published TTS end status: {end_msg}")
            logger.debug("Playback end (len=%d)", len(text or ""))

    # ----- blocking helper (runs in thread) -----
    def _do_synth_and_play_blocking(self, text: str, streaming: bool, pipeline: bool) -> float:
        t0 = time.time()
        # If the synthesizer supports explicit single-WAV synthesis and streaming is disabled,
        # honor the "single WAV" path (used by aggregation) even for external providers.
        if not streaming and hasattr(self.synth, "synth_to_wav"):
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
                self.synth.synth_to_wav(text, f.name)
                p = _spawn_player(args=[f.name])
                p.wait()
            return time.time() - t0
        # Otherwise use provider's synth_and_play API
        try:
            return self.synth.synth_and_play(text, streaming=streaming, pipeline=pipeline)
        except TypeError:
            return self.synth.synth_and_play(text)
