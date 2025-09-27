from __future__ import annotations

"""Main entry for the STT worker service.

Coordinates audio capture, VAD, transcription, MQTT I/O, and optional FFT publishing.
"""
import asyncio
import logging
import os
import time
from typing import Any

import numpy as np
import orjson
from pydantic import BaseModel, ValidationError

from audio_fanout import AudioFanoutPublisher
from config import (
    LOG_LEVEL,
    MQTT_URL,
    POST_PUBLISH_COOLDOWN_MS,
    TTS_BASE_MUTE_MS,
    TTS_PER_CHAR_MS,
    TTS_MAX_MUTE_MS,
    STREAMING_PARTIALS,
    PARTIAL_INTERVAL_MS,
    PARTIAL_MIN_DURATION_MS,
    PARTIAL_MIN_CHARS,
    PARTIAL_MIN_NEW_CHARS,
    PARTIAL_ALPHA_RATIO_MIN,
    STT_BACKEND,
    UNMUTE_GUARD_MS,
    FFT_PUBLISH,
    FFT_TOPIC,
    FFT_RATE_HZ,
    FFT_BINS,
    FFT_LOG_SCALE,
    AUDIO_FANOUT_PATH,
    AUDIO_FANOUT_RATE,
    WAKE_EVENT_FALLBACK_DELAY_MS,
    WAKE_EVENT_FALLBACK_TTL_MS,
)
from audio_capture import AudioCapture
from vad import VADProcessor
from transcriber import SpeechTranscriber
from mqtt_utils import MQTTClientWrapper
from suppression import SuppressionState, SuppressionEngine
from audio_preproc import preprocess_pcm
from config import PREPROCESS_ENABLE, PREPROCESS_MIN_MS

from tars.adapters.mqtt_asyncio import AsyncioMQTTPublisher  # type: ignore[import]
from tars.contracts.envelope import Envelope  # type: ignore[import]
from tars.contracts.v1 import (  # type: ignore[import]
    EVENT_TYPE_SAY,
    EVENT_TYPE_STT_FINAL,
    EVENT_TYPE_STT_PARTIAL,
    EVENT_TYPE_TTS_STATUS,
    EVENT_TYPE_WAKE_EVENT,
    EVENT_TYPE_WAKE_MIC,
    FinalTranscript,
    HealthPing,
    PartialTranscript,
    TtsSay,
    TtsStatus,
    WakeEvent,
    WakeMicCommand,
)
from tars.domain.stt import (  # type: ignore[import]
    STTProcessResult,
    STTService,
    STTServiceConfig,
    PartialSettings,
)
from tars.runtime.publisher import publish_event  # type: ignore[import]

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("stt-worker")

EVENT_TYPE_HEALTH_STT = "system.health.stt"
SOURCE_NAME = "stt"

class STTWorker:
    def __init__(self):
        self.audio_capture = AudioCapture()
        self.transcriber = SpeechTranscriber()
        self.vad_processor: VADProcessor | None = None
        self.mqtt = MQTTClientWrapper(MQTT_URL)
        self.state = SuppressionState()
        self.suppress_engine = SuppressionEngine(self.state)
        self.pending_tts = False
        self.recent_unmute_time = 0.0
        self.fallback_unmute_task = None
        self._partials_task = None
        self._fft_task = None
        self._wake_ttl_task: asyncio.Task | None = None
        self._wake_fallback_task: asyncio.Task | None = None
        self.audio_fanout: AudioFanoutPublisher | None = None
        self._publisher: AsyncioMQTTPublisher | None = None
        self.service: STTService | None = None

    async def initialize(self):
        if os.path.exists("/host-models"):
            try:
                os.system("cp -r /app/models/* /host-models/ 2>/dev/null || true")
            except Exception as e:
                logger.warning(f"Could not save models to host: {e}")
        await self.mqtt.connect()
        if not self.mqtt.client:
            raise RuntimeError("MQTT client unavailable after connect")
        self._publisher = AsyncioMQTTPublisher(self.mqtt.client)
        await self.publish_health(True, "STT service ready")
        await self.mqtt.subscribe_stream('tts/status', self._handle_tts_status)
        # Also listen to tts/say to preemptively mute and set echo context, in case we miss 'speaking_start'
        await self.mqtt.subscribe_stream('tts/say', self._handle_tts_say)
        await self.mqtt.subscribe_stream('wake/mic', self._handle_wake_mic)
        await self.mqtt.subscribe_stream('wake/event', self._handle_wake_event)
        self.audio_fanout = AudioFanoutPublisher(AUDIO_FANOUT_PATH, target_sample_rate=AUDIO_FANOUT_RATE)
        await self.audio_fanout.start()
        self.audio_capture.register_fanout(self.audio_fanout)
        # For WS/OpenAI backends we open a network call per utterance; avoid partials to reduce overhead
        self._enable_partials = STREAMING_PARTIALS and STT_BACKEND not in {"ws", "openai"}
        if self._enable_partials:
            logger.info(f"Streaming partial transcripts enabled (interval={PARTIAL_INTERVAL_MS}ms)")
        else:
            logger.info("Streaming partial transcripts disabled")

    async def publish_health(self, ok: bool, message: str = ""):
        event_text = message or ("ready" if ok else "")
        err_text = None if ok else (message or "error")
        payload = HealthPing(ok=ok, event=event_text, err=err_text)
        await self._publish_event(EVENT_TYPE_HEALTH_STT, payload, retain=True)

    async def publish_transcript(self, transcript: FinalTranscript):
        message_id = await self._publish_event(EVENT_TYPE_STT_FINAL, transcript, qos=1)
        text = transcript.text
        preview = text[:60] + ('...' if len(text) > 60 else '')
        logger.info(
            "Published final transcript: %s",
            preview,
            extra={"message_id": message_id},
        )

    async def _publish_event(self, event_type: str, data: Any, *, qos: int = 1, retain: bool = False) -> str | None:
        publisher = self._publisher
        if publisher is None:
            logger.warning("MQTT publisher unavailable; dropping %s", event_type)
            return None
        try:
            return await publish_event(
                publisher,
                logger,
                event_type,
                data,
                qos=qos,
                retain=retain,
                source=SOURCE_NAME,
            )
        except Exception as exc:
            logger.error("Failed to publish %s: %s", event_type, exc)
            return None

    @staticmethod
    def _decode_event(
        payload: bytes,
        model: type[BaseModel],
        *,
        event_type: str | None = None,
    ) -> BaseModel | None:
        try:
            envelope = Envelope.model_validate_json(payload)
            raw = envelope.data
            if event_type and envelope.type != event_type:
                logger.debug(
                    "Envelope type mismatch: expected=%s actual=%s",
                    event_type,
                    envelope.type,
                )
        except ValidationError:
            try:
                raw = orjson.loads(payload)
            except orjson.JSONDecodeError as exc:
                logger.error("Failed to decode %s payload: %s", model.__name__, exc)
                return None

        try:
            return model.model_validate(raw)
        except ValidationError as exc:
            logger.error("Invalid %s payload: %s", model.__name__, exc)
            return None

    async def _handle_tts_status(self, payload: bytes):
        status = self._decode_event(payload, TtsStatus, event_type=EVENT_TYPE_TTS_STATUS)
        if status is None:
            return

        text = status.text or ""
        wake_ack = bool(status.wake_ack)

        if status.event == "speaking_start":
            if wake_ack:
                logger.debug("Wake ack speaking_start received; keeping microphone unmuted")
                self.pending_tts = False
                if self.audio_capture.is_muted:
                    self.audio_capture.unmute("tts wake_ack start")
                    self.recent_unmute_time = time.time()
                return
            self.state.last_tts_text = text.strip()
            self.pending_tts = True
            self.audio_capture.mute("tts speaking_start")
            if self.fallback_unmute_task and not self.fallback_unmute_task.done():
                self.fallback_unmute_task.cancel()
        elif status.event == "speaking_end":
            if wake_ack:
                logger.debug("Wake ack speaking_end received; no mute adjustments needed")
                return

            async def delayed_unmute() -> None:
                await asyncio.sleep(0.2)
                self.pending_tts = False
                self.audio_capture.unmute("tts speaking_end")
                self.recent_unmute_time = time.time()

            asyncio.create_task(delayed_unmute())

    async def _handle_tts_say(self, payload: bytes):
        """When a TTS request is published, proactively mute to avoid capturing the TTS audio.
        Also reschedule a conservative fallback unmute based on the outgoing TTS text length.
        """
        say = self._decode_event(payload, TtsSay, event_type=EVENT_TYPE_SAY)
        if say is None:
            return

        text = (say.text or "").strip()
        if say.wake_ack:
            logger.debug("Wake ack TTS received; ensuring microphone is unmuted")
            self.pending_tts = False
            self.audio_capture.unmute("wake/ack")
            self.recent_unmute_time = time.time()
            return
        if not text:
            return

        self.state.last_tts_text = text
        self.pending_tts = True
        self.audio_capture.mute("tts say")
        # Reschedule fallback unmute based on the TTS text itself (more accurate than STT text)
        if self.fallback_unmute_task and not self.fallback_unmute_task.done():
            self.fallback_unmute_task.cancel()

        async def fallback_unmute_tts() -> None:
            try:
                await asyncio.sleep(TTS_MAX_MUTE_MS / 1000.0)
                # If we never saw speaking_end, fail safe by unmuting but clear pending flag
                if self.audio_capture.is_muted and self.pending_tts:
                    self.pending_tts = False
                    self.audio_capture.unmute("tts say fallback-timeout")
                    self.recent_unmute_time = time.time()
            except asyncio.CancelledError:
                pass

        self.fallback_unmute_task = asyncio.create_task(fallback_unmute_tts())

    async def _handle_wake_mic(self, payload: bytes):
        command = self._decode_event(payload, WakeMicCommand, event_type=EVENT_TYPE_WAKE_MIC)
        if command is None:
            return

        action = command.action
        reason = (command.reason or "wake").strip() or "wake"
        ttl_ms = command.ttl_ms

        logger.info(
            "Wake mic command received: action=%s reason=%s ttl_ms=%s muted=%s",
            action,
            reason,
            ttl_ms,
            self.audio_capture.is_muted,
        )

        self._cancel_wake_fallback()

        if self._wake_ttl_task and not self._wake_ttl_task.done():
            self._wake_ttl_task.cancel()
            self._wake_ttl_task = None

        if action == "unmute":
            if self.fallback_unmute_task and not self.fallback_unmute_task.done():
                self.fallback_unmute_task.cancel()
                self.fallback_unmute_task = None
            self.pending_tts = False
            self.audio_capture.unmute(f"wake/{reason}")
            self.recent_unmute_time = time.time()
            logger.info("Microphone state after wake unmute: muted=%s", self.audio_capture.is_muted)
            logger.info("Wake control unmuted microphone")
            if isinstance(ttl_ms, (int, float)) and ttl_ms > 0:
                self._wake_ttl_task = asyncio.create_task(self._schedule_wake_ttl("mute", ttl_ms, reason))
        else:
            self.audio_capture.mute(f"wake/{reason}")
            logger.info("Wake control muted microphone")
            if isinstance(ttl_ms, (int, float)) and ttl_ms > 0:
                self._wake_ttl_task = asyncio.create_task(self._schedule_wake_ttl("unmute", ttl_ms, reason))

    def _cancel_wake_fallback(self) -> None:
        task = getattr(self, "_wake_fallback_task", None)
        if task and not task.done():
            task.cancel()
        self._wake_fallback_task = None

    def _schedule_wake_fallback(self, event_type: str, delay_ms: int | None = None) -> None:
        if WAKE_EVENT_FALLBACK_DELAY_MS <= 0 and delay_ms is None:
            return
        self._cancel_wake_fallback()

        delay = (delay_ms if delay_ms is not None else WAKE_EVENT_FALLBACK_DELAY_MS) / 1000.0
        delay = max(0.0, delay)
        ttl_ms = max(0, WAKE_EVENT_FALLBACK_TTL_MS)

        async def _fallback() -> None:
            try:
                if delay:
                    await asyncio.sleep(delay)
                if not self.audio_capture.is_muted:
                    return
                logger.warning(
                    "Wake event (%s) did not produce wake/mic unmute within %.0fms; forcing microphone open",
                    event_type,
                    delay * 1000.0,
                )
                if self.fallback_unmute_task and not self.fallback_unmute_task.done():
                    self.fallback_unmute_task.cancel()
                    self.fallback_unmute_task = None
                self.pending_tts = False
                self.audio_capture.unmute(f"wake-event/{event_type}")
                self.recent_unmute_time = time.time()
                if ttl_ms > 0:
                    if self._wake_ttl_task and not self._wake_ttl_task.done():
                        self._wake_ttl_task.cancel()
                    self._wake_ttl_task = asyncio.create_task(
                        self._schedule_wake_ttl('mute', ttl_ms, f"{event_type}-fallback")
                    )
            except asyncio.CancelledError:
                pass

        self._wake_fallback_task = asyncio.create_task(_fallback())

    async def _handle_wake_event(self, payload: bytes):
        event = self._decode_event(payload, WakeEvent, event_type=EVENT_TYPE_WAKE_EVENT)
        if event is None:
            return

        event_type = (event.type or "").lower()
        if event_type in {'wake', 'interrupt'}:
            logger.debug("Wake event (%s) received; arming microphone fallback", event_type)
            delay_override = 0 if event_type == 'interrupt' else None
            self._schedule_wake_fallback(event_type, delay_override)
        elif event_type in {'timeout', 'cancelled', 'resume'}:
            self._cancel_wake_fallback()
        else:
            logger.debug("Ignoring wake/event type=%s", event_type)

    async def _schedule_wake_ttl(self, next_action: str, ttl_ms: float, reason: str) -> None:
        try:
            await asyncio.sleep(ttl_ms / 1000.0)
            if next_action == 'mute':
                self.audio_capture.mute(f"wake/ttl/{reason}")
            else:
                self.audio_capture.unmute(f"wake/ttl/{reason}")
                self.pending_tts = False
                self.recent_unmute_time = time.time()
        except asyncio.CancelledError:
            pass

    async def process_audio_stream(self):
        logger.debug("Starting audio processing loop")
        service = self.service
        if service is None:
            raise RuntimeError("STT service not initialized")

        async for chunk in self.audio_capture.get_audio_chunks():
            # Always yield control so MQTT pings/heartbeats and other tasks can run
            await asyncio.sleep(0)
            now = time.time()
            if self.pending_tts:
                continue
            if service.in_cooldown(now):
                continue
            if self.recent_unmute_time and (now - self.recent_unmute_time) < (UNMUTE_GUARD_MS / 1000.0):
                np_chunk = np.frombuffer(chunk, dtype=np.int16)
                if np_chunk.size:
                    rms = float(np.sqrt(np.mean(np_chunk.astype(np.float32) ** 2)))
                    if rms < 120:
                        continue

            result = await service.process_chunk(chunk, now=now)
            if result.error:
                logger.error(result.error)
                await self.publish_health(False, result.error)
                self.audio_capture.unmute("error")
                continue

            if not result.final:
                if result.candidate_text and result.rejection_reasons:
                    logger.info(
                        "Discarded '%s' reasons=%s",
                        result.candidate_text,
                        result.rejection_reasons,
                    )
                continue

            final = result.final
            text = final.text
            confidence = final.confidence
            logger.info(
                "Transcribed: '%s'%s",
                text,
                f" (conf {confidence:.2f})" if confidence is not None else "",
            )
            self.audio_capture.mute("post-transcription")

            # Use conservative cap; per-char estimates can be too short
            unmute_at = now + (TTS_MAX_MUTE_MS / 1000.0)
            if self.fallback_unmute_task and not self.fallback_unmute_task.done():
                self.fallback_unmute_task.cancel()

            async def fallback_unmute(ts: float = unmute_at) -> None:
                try:
                    await asyncio.sleep(max(0, ts - time.time()))
                    if self.audio_capture.is_muted and not self.pending_tts:
                        self.audio_capture.unmute("fallback-timeout")
                except asyncio.CancelledError:
                    pass

            self.fallback_unmute_task = asyncio.create_task(fallback_unmute())
            await self.publish_transcript(final)

    async def run(self):
        try:
            await self.initialize()
            self.audio_capture.start_capture()
            self.vad_processor = VADProcessor(self.audio_capture.sample_rate, self.audio_capture.frame_size)
            partial_settings = PartialSettings(
                enabled=bool(self._enable_partials),
                min_duration_ms=PARTIAL_MIN_DURATION_MS,
                min_chars=PARTIAL_MIN_CHARS,
                min_new_chars=PARTIAL_MIN_NEW_CHARS,
                alpha_ratio_min=PARTIAL_ALPHA_RATIO_MIN,
            )
            service_config = STTServiceConfig(
                post_publish_cooldown_ms=POST_PUBLISH_COOLDOWN_MS,
                preprocess_min_ms=PREPROCESS_MIN_MS,
                partials=partial_settings,
            )
            preprocess_fn = preprocess_pcm if PREPROCESS_ENABLE else None
            if not self.vad_processor:
                raise RuntimeError("VAD processor failed to initialize")
            self.service = STTService(
                vad=self.vad_processor,
                transcriber=self.transcriber,
                suppression=self.suppress_engine,
                sample_rate=self.audio_capture.sample_rate,
                frame_size=self.audio_capture.frame_size,
                config=service_config,
                preprocess=preprocess_fn,
            )
            if self.service.partials_enabled:
                self._partials_task = asyncio.create_task(self._partials_loop())
            if FFT_PUBLISH:
                self._fft_task = asyncio.create_task(self._fft_loop())
            await self.process_audio_stream()
        except Exception as e:
            logger.error(f"STT worker error: {e}")
            await self.publish_health(False, f"Worker error: {e}")
        finally:
            self.audio_capture.stop_capture()
            if self.audio_fanout is not None:
                await self.audio_fanout.close()
            if self._wake_fallback_task and not self._wake_fallback_task.done():
                self._wake_fallback_task.cancel()
            if self._wake_ttl_task and not self._wake_ttl_task.done():
                self._wake_ttl_task.cancel()
            await self.mqtt.disconnect()
            self._publisher = None
            self.service = None

    async def _partials_loop(self):
        interval = PARTIAL_INTERVAL_MS / 1000.0
        while True:
            await asyncio.sleep(interval)
            service = self.service
            if not service or not service.partials_enabled:
                continue
            if not self.vad_processor or not self.vad_processor.is_speech:
                continue
            if self.pending_tts or self.audio_capture.is_muted:
                continue
            # Basic guard after unmute
            if self.recent_unmute_time and (time.time() - self.recent_unmute_time) < (UNMUTE_GUARD_MS / 1000.0):
                continue
            partial = await service.maybe_partial()
            if not partial:
                continue
            message_id = await self._publish_event(
                EVENT_TYPE_STT_PARTIAL,
                partial,
                qos=0,
            )
            logger.debug(
                "Published partial: %s",
                partial.text[:60] + ('...' if len(partial.text) > 60 else ''),
                extra={"message_id": message_id},
            )

    async def _fft_loop(self):
        """Publish a compact FFT magnitude array for UI visualization."""
        period = 1.0 / max(1e-3, FFT_RATE_HZ)
        bins = max(8, min(512, FFT_BINS))
        window = np.hanning(1024)
        last_pub = 0.0
        while True:
            await asyncio.sleep(0.01)
            now = time.time()
            if now - last_pub < period:
                continue
            last_pub = now
            # Use the active buffer if speaking, else skip to avoid noise-only visuals
            buf = self.vad_processor.get_active_buffer() if self.vad_processor else None
            if not buf:
                continue
            # Convert to float32 mono signal
            x = np.frombuffer(buf, dtype=np.int16).astype(np.float32)
            if x.size < 256:
                continue
            # Take the last 1024 samples for FFT
            segment = x[-1024:]
            segment = segment - np.mean(segment)
            segment = segment * window[: segment.size]
            spec = np.fft.rfft(segment)
            mag = np.abs(spec)
            # Convert to dB-like scale if requested
            if FFT_LOG_SCALE:
                mag = 20.0 * np.log10(1e-6 + mag)
                # Normalize to [0,1]
                mag -= mag.min()
                denom = (mag.max() - mag.min()) or 1.0
                mag = mag / denom
            else:
                # Linear normalize
                mag = mag / (np.max(mag) or 1.0)
            # Keep only positive frequencies and downsample to bins
            pos = mag[: len(mag)]
            idx = np.linspace(0, len(pos) - 1, bins)
            down = np.interp(idx, np.arange(len(pos)), pos)
            try:
                await self.mqtt.safe_publish(FFT_TOPIC, {"fft": down.tolist(), "ts": now})
            except Exception:
                # Non-fatal
                pass

async def main():
    logger.info("Starting TARS STT Worker")
    worker = STTWorker()
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())