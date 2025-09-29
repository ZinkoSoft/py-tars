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

from .audio_capture import AudioCapture
from .audio_fanout import AudioFanoutPublisher
from .audio_preproc import preprocess_pcm
from .config import (
    AUDIO_FANOUT_PATH,
    AUDIO_FANOUT_RATE,
    CHUNK_DURATION_MS,
    FFT_BINS,
    FFT_LOG_SCALE,
    FFT_PUBLISH,
    FFT_RATE_HZ,
    FFT_TOPIC,
    FFT_WS_ENABLE,
    FFT_WS_HOST,
    FFT_WS_PATH,
    FFT_WS_PORT,
    LOG_LEVEL,
    MQTT_URL,
    PARTIAL_ALPHA_RATIO_MIN,
    PARTIAL_INTERVAL_MS,
    PARTIAL_MIN_CHARS,
    PARTIAL_MIN_DURATION_MS,
    PARTIAL_MIN_NEW_CHARS,
    POST_PUBLISH_COOLDOWN_MS,
    PREPROCESS_ENABLE,
    PREPROCESS_MIN_MS,
    SAMPLE_RATE,
    STREAMING_PARTIALS,
    STT_BACKEND,
    TTS_BASE_MUTE_MS,
    TTS_MAX_MUTE_MS,
    TTS_PER_CHAR_MS,
    UNMUTE_GUARD_MS,
    VAD_AGGRESSIVENESS,
    WAKE_EVENT_FALLBACK_DELAY_MS,
    WAKE_EVENT_FALLBACK_TTL_MS,
)
from .mqtt_utils import MQTTClientWrapper
from .fft_ws import FFTWebSocketServer
from .suppression import SuppressionEngine, SuppressionState
from .transcriber import SpeechTranscriber
from .vad import VADProcessor
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
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("stt-worker")

EVENT_TYPE_HEALTH_STT = "system.health.stt"
SOURCE_NAME = "stt"


class STTWorker:
    def __init__(self) -> None:
        self.audio_capture = AudioCapture()
        self.transcriber = SpeechTranscriber()
        self.vad_processor: VADProcessor | None = None
        self.mqtt = MQTTClientWrapper(MQTT_URL)
        self.state = SuppressionState()
        self.suppress_engine = SuppressionEngine(self.state)
        self.pending_tts = False
        self.recent_unmute_time = 0.0
        self.fallback_unmute_task: asyncio.Task | None = None
        self._partials_task: asyncio.Task | None = None
        self._fft_task: asyncio.Task | None = None
        self._wake_ttl_task: asyncio.Task | None = None
        self._wake_fallback_task: asyncio.Task | None = None
        self.audio_fanout: AudioFanoutPublisher | None = None
        self._publisher: AsyncioMQTTPublisher | None = None
        self.service: STTService | None = None
        self._enable_partials = False
        self._resume_after_tts = False
        self._fft_ws: FFTWebSocketServer | None = None

    async def initialize(self) -> None:
        if os.path.exists("/host-models"):
            try:
                os.system("cp -r /app/models/* /host-models/ 2>/dev/null || true")
            except Exception as exc:  # pragma: no cover - best effort
                logger.warning("Could not save models to host: %s", exc)
        await self.mqtt.connect()
        if not self.mqtt.client:
            raise RuntimeError("MQTT client unavailable after connect")
        self._publisher = AsyncioMQTTPublisher(self.mqtt.client)
        await self.publish_health(True, "STT service ready")
        await self.mqtt.subscribe_stream("tts/status", self._handle_tts_status)
        await self.mqtt.subscribe_stream("tts/say", self._handle_tts_say)
        await self.mqtt.subscribe_stream("wake/mic", self._handle_wake_mic)
        await self.mqtt.subscribe_stream("wake/event", self._handle_wake_event)
        self.audio_fanout = AudioFanoutPublisher(
            AUDIO_FANOUT_PATH,
            target_sample_rate=AUDIO_FANOUT_RATE,
        )
        await self.audio_fanout.start()
        self.audio_capture.register_fanout(self.audio_fanout)
        self._enable_partials = STREAMING_PARTIALS and STT_BACKEND not in {"ws", "openai"}
        if self._enable_partials:
            logger.info(
                "Streaming partial transcripts enabled (interval=%sms)",
                PARTIAL_INTERVAL_MS,
            )
        else:
            logger.info("Streaming partial transcripts disabled")

        if FFT_WS_ENABLE:
            try:
                self._fft_ws = FFTWebSocketServer(FFT_WS_HOST, FFT_WS_PORT, FFT_WS_PATH)
                await self._fft_ws.start()
            except Exception as exc:  # pragma: no cover - startup best effort
                logger.error("Unable to start FFT websocket server: %s", exc)
                self._fft_ws = None
        else:
            self._fft_ws = None

    async def publish_health(self, ok: bool, message: str = "") -> None:
        event_text = message or ("ready" if ok else "")
        err_text = None if ok else (message or "error")
        payload = HealthPing(ok=ok, event=event_text, err=err_text)
        await self._publish_event(EVENT_TYPE_HEALTH_STT, payload, retain=True)

    async def publish_transcript(self, transcript: FinalTranscript) -> None:
        message_id = await self._publish_event(EVENT_TYPE_STT_FINAL, transcript, qos=1)
        text = transcript.text
        preview = text[:60] + ("..." if len(text) > 60 else "")
        logger.info(
            "Published final transcript: %s",
            preview,
            extra={"message_id": message_id},
        )

    async def _publish_event(
        self,
        event_type: str,
        data: Any,
        *,
        qos: int = 1,
        retain: bool = False,
    ) -> str | None:
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
        except Exception as exc:  # pragma: no cover - best effort logging
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

    def _remember_tts_resume_state(self) -> None:
        if not self.audio_capture.is_muted and not self._resume_after_tts:
            self._resume_after_tts = True

    async def _handle_tts_status(self, payload: bytes) -> None:
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
                self._resume_after_tts = False
                return
            self.state.last_tts_text = text.strip()
            self._remember_tts_resume_state()
            self.pending_tts = True
            self.audio_capture.mute("tts speaking_start")
            if self.fallback_unmute_task and not self.fallback_unmute_task.done():
                self.fallback_unmute_task.cancel()
            self.fallback_unmute_task = None
        elif status.event == "speaking_end":
            if wake_ack:
                logger.debug("Wake ack speaking_end received; no mute adjustments needed")
                self._resume_after_tts = False
                return

            async def delayed_unmute() -> None:
                await asyncio.sleep(0.2)
                self.pending_tts = False
                resume = self._resume_after_tts
                self._resume_after_tts = False
                if resume:
                    self.audio_capture.unmute("tts speaking_end")
                    self.recent_unmute_time = time.time()
                else:
                    logger.debug("Skipping TTS auto-unmute; microphone was muted before playback")

            if self.fallback_unmute_task and not self.fallback_unmute_task.done():
                self.fallback_unmute_task.cancel()
            self.fallback_unmute_task = None

            asyncio.create_task(delayed_unmute())

    async def _handle_tts_say(self, payload: bytes) -> None:
        say = self._decode_event(payload, TtsSay, event_type=EVENT_TYPE_SAY)
        if say is None:
            return

        text = (say.text or "").strip()
        if say.wake_ack:
            logger.debug("Wake ack TTS received; ensuring microphone is unmuted")
            self.pending_tts = False
            self.audio_capture.unmute("wake/ack")
            self.recent_unmute_time = time.time()
            self._resume_after_tts = False
            return
        if not text:
            return

        self.state.last_tts_text = text
        self._remember_tts_resume_state()
        self.pending_tts = True
        self.audio_capture.mute("tts say")
        if self.fallback_unmute_task and not self.fallback_unmute_task.done():
            self.fallback_unmute_task.cancel()
        self.fallback_unmute_task = None

        async def fallback_unmute_tts() -> None:
            try:
                await asyncio.sleep(TTS_MAX_MUTE_MS / 1000.0)
                if self.audio_capture.is_muted and self.pending_tts:
                    self.pending_tts = False
                    resume = self._resume_after_tts
                    self._resume_after_tts = False
                    if resume:
                        self.audio_capture.unmute("tts say fallback-timeout")
                        self.recent_unmute_time = time.time()
                    else:
                        logger.debug("Skipping fallback TTS auto-unmute; microphone was muted before playback")
            except asyncio.CancelledError:  # pragma: no cover - task cleanup
                pass
            finally:
                self.fallback_unmute_task = None

        self.fallback_unmute_task = asyncio.create_task(fallback_unmute_tts())

    async def _handle_wake_mic(self, payload: bytes) -> None:
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
        task = self._wake_fallback_task
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
                        self._schedule_wake_ttl("mute", ttl_ms, f"{event_type}-fallback"),
                    )
            except asyncio.CancelledError:  # pragma: no cover - task cleanup
                pass

        self._wake_fallback_task = asyncio.create_task(_fallback())

    async def _handle_wake_event(self, payload: bytes) -> None:
        event = self._decode_event(payload, WakeEvent, event_type=EVENT_TYPE_WAKE_EVENT)
        if event is None:
            return

        event_type = (event.type or "").lower()
        if event_type in {"wake", "interrupt"}:
            logger.debug("Wake event (%s) received; arming microphone fallback", event_type)
            delay_override = 0 if event_type == "interrupt" else None
            self._schedule_wake_fallback(event_type, delay_override)
        elif event_type in {"timeout", "cancelled", "resume"}:
            self._cancel_wake_fallback()
        else:
            logger.debug("Ignoring wake/event type=%s", event_type)

    async def _schedule_wake_ttl(self, next_action: str, ttl_ms: float, reason: str) -> None:
        try:
            await asyncio.sleep(ttl_ms / 1000.0)
            if next_action == "mute":
                self.audio_capture.mute(f"wake/ttl/{reason}")
            else:
                self.audio_capture.unmute(f"wake/ttl/{reason}")
                self.pending_tts = False
                self.recent_unmute_time = time.time()
        except asyncio.CancelledError:  # pragma: no cover - task cleanup
            pass

    async def process_audio_stream(self) -> None:
        logger.debug("Starting audio processing loop")
        service = self.service
        if service is None:
            raise RuntimeError("STT service not initialized")

        async for chunk in self.audio_capture.get_audio_chunks():
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
                    if rms < 180:  # Match NOISE_MIN_RMS threshold
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

            unmute_at = now + (TTS_MAX_MUTE_MS / 1000.0)
            if self.fallback_unmute_task and not self.fallback_unmute_task.done():
                self.fallback_unmute_task.cancel()

            async def fallback_unmute(ts: float = unmute_at) -> None:
                try:
                    await asyncio.sleep(max(0, ts - time.time()))
                    if self.audio_capture.is_muted and not self.pending_tts:
                        self.audio_capture.unmute("fallback-timeout")
                except asyncio.CancelledError:  # pragma: no cover
                    pass

            self.fallback_unmute_task = asyncio.create_task(fallback_unmute())
            await self.publish_transcript(final)

    async def run(self) -> None:
        try:
            await self.initialize()
            self.audio_capture.start_capture()
            self.vad_processor = VADProcessor(
                self.audio_capture.sample_rate,
                self.audio_capture.frame_size,
            )
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
            if FFT_PUBLISH or self._fft_ws is not None:
                self._fft_task = asyncio.create_task(self._fft_loop())
            await self.process_audio_stream()
        except Exception as exc:  # pragma: no cover - safety net
            logger.error("STT worker error: %s", exc)
            await self.publish_health(False, f"Worker error: {exc}")
        finally:
            self.audio_capture.stop_capture()
            if self.audio_fanout is not None:
                await self.audio_fanout.close()
            if self._wake_fallback_task and not self._wake_fallback_task.done():
                self._wake_fallback_task.cancel()
            if self._wake_ttl_task and not self._wake_ttl_task.done():
                self._wake_ttl_task.cancel()
            if self._fft_task and not self._fft_task.done():
                self._fft_task.cancel()
            self._fft_task = None
            if self._fft_ws is not None:
                try:
                    await self._fft_ws.stop()
                except Exception as exc:  # pragma: no cover - best effort cleanup
                    logger.debug("Error shutting down FFT websocket: %s", exc)
                self._fft_ws = None
            await self.mqtt.disconnect()
            self._publisher = None
            self.service = None

    async def _partials_loop(self) -> None:
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
                partial.text[:60] + ("..." if len(partial.text) > 60 else ""),
                extra={"message_id": message_id},
            )

    async def _fft_loop(self) -> None:
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
            buf = self.vad_processor.get_active_buffer() if self.vad_processor else None
            if not buf:
                continue
            x = np.frombuffer(buf, dtype=np.int16).astype(np.float32)
            if x.size < 256:
                continue
            segment = x[-1024:]
            segment = segment - np.mean(segment)
            segment = segment * window[: segment.size]
            spec = np.fft.rfft(segment)
            mag = np.abs(spec)
            if FFT_LOG_SCALE:
                mag = 20.0 * np.log10(1e-6 + mag)
                mag -= mag.min()
                denom = (mag.max() - mag.min()) or 1.0
                mag = mag / denom
            else:
                mag = mag / (np.max(mag) or 1.0)
            pos = mag[: len(mag)]
            idx = np.linspace(0, len(pos) - 1, bins)
            down = np.interp(idx, np.arange(len(pos)), pos)
            payload = {"fft": down.tolist(), "ts": now}
            if FFT_PUBLISH:
                try:
                    await self.mqtt.safe_publish(FFT_TOPIC, payload)
                except Exception:  # pragma: no cover - best effort
                    pass
            if self._fft_ws is not None:
                try:
                    await self._fft_ws.broadcast(payload)
                except Exception as exc:  # pragma: no cover - best effort
                    logger.debug("FFT websocket broadcast failed: %s", exc)


def main() -> None:
    logger.info("Starting TARS STT Worker")
    worker = STTWorker()
    asyncio.run(worker.run())


__all__ = ["STTWorker", "main"]
