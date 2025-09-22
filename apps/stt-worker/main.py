import asyncio
import logging
import os
import time
import numpy as np
import orjson

from config import (
    LOG_LEVEL, MQTT_URL, POST_PUBLISH_COOLDOWN_MS, TTS_BASE_MUTE_MS, TTS_PER_CHAR_MS, TTS_MAX_MUTE_MS,
    STREAMING_PARTIALS, PARTIAL_INTERVAL_MS, PARTIAL_MIN_DURATION_MS, PARTIAL_MIN_CHARS, PARTIAL_MIN_NEW_CHARS,
    PARTIAL_ALPHA_RATIO_MIN, STT_BACKEND, UNMUTE_GUARD_MS,
    FFT_PUBLISH, FFT_TOPIC, FFT_RATE_HZ, FFT_BINS, FFT_LOG_SCALE
)
from audio_capture import AudioCapture
from vad import VADProcessor
from transcriber import SpeechTranscriber
from mqtt_utils import MQTTClientWrapper
from suppression import SuppressionState, SuppressionEngine

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("stt-worker")

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
        self._last_partial_text: str = ""
        self._fft_task = None

    async def initialize(self):
        if os.path.exists("/host-models"):
            try:
                os.system("cp -r /app/models/* /host-models/ 2>/dev/null || true")
            except Exception as e:
                logger.warning(f"Could not save models to host: {e}")
        await self.mqtt.connect()
        await self.publish_health(True, "STT service ready")
        await self.mqtt.subscribe_stream('tts/status', self._handle_tts_status)
        # Also listen to tts/say to preemptively mute and set echo context, in case we miss 'speaking_start'
        await self.mqtt.subscribe_stream('tts/say', self._handle_tts_say)
        # For WS backend the current transcriber opens a new WS per call; avoid partials to reduce overhead
        self._enable_partials = STREAMING_PARTIALS and STT_BACKEND != "ws"
        if self._enable_partials:
            logger.info(f"Streaming partial transcripts enabled (interval={PARTIAL_INTERVAL_MS}ms)")
        else:
            logger.info("Streaming partial transcripts disabled")

    async def publish_health(self, ok: bool, message: str = ""):
        await self.mqtt.safe_publish('system/health/stt', {"ok": ok, "event": message, "timestamp": time.time()})

    async def publish_transcript(self, text: str, confidence: float | None):
        payload = {"text": text, "lang": "en", "confidence": confidence, "timestamp": time.time(), "is_final": True}
        await self.mqtt.safe_publish('stt/final', payload)
        logger.info(f"Published final transcript: {text[:60]}{'...' if len(text) > 60 else ''}")

    async def _handle_tts_status(self, payload: bytes):
        try:
            data = orjson.loads(payload)
            event = data.get('event')
            txt = data.get('text', '')
            if event == 'speaking_start':
                self.state.last_tts_text = txt.strip()
                self.pending_tts = True
                self.audio_capture.mute("tts speaking_start")
                if self.fallback_unmute_task and not self.fallback_unmute_task.done():
                    self.fallback_unmute_task.cancel()
            elif event == 'speaking_end':
                async def delayed_unmute():
                    await asyncio.sleep(0.2)
                    self.pending_tts = False
                    self.audio_capture.unmute("tts speaking_end")
                    self.recent_unmute_time = time.time()
                asyncio.create_task(delayed_unmute())
        except Exception as e:
            logger.error(f"Error handling TTS status: {e}")

    async def _handle_tts_say(self, payload: bytes):
        """When a TTS request is published, proactively mute to avoid capturing the TTS audio.
        Also reschedule a conservative fallback unmute based on the outgoing TTS text length.
        """
        try:
            data = orjson.loads(payload)
            txt = data.get('text', '')
            if not txt:
                return
            self.state.last_tts_text = txt.strip()
            self.pending_tts = True
            self.audio_capture.mute("tts say")
            # Reschedule fallback unmute based on the TTS text itself (more accurate than STT text)
            if self.fallback_unmute_task and not self.fallback_unmute_task.done():
                self.fallback_unmute_task.cancel()
            # Use conservative cap; avoid underestimating TTS duration
            async def fallback_unmute_tts():
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
        except Exception as e:
            logger.error(f"Error handling TTS say: {e}")

    async def process_audio_stream(self):
        logger.info("Starting audio processing loop")
        async for chunk in self.audio_capture.get_audio_chunks():
            # Cooldown gating
            if self.state.cooldown_until and time.time() < self.state.cooldown_until:
                continue
            if self.pending_tts:
                continue
            if self.recent_unmute_time and (time.time() - self.recent_unmute_time) < (UNMUTE_GUARD_MS / 1000.0):
                np_chunk = np.frombuffer(chunk, dtype=np.int16)
                if np_chunk.size:
                    rms = float(np.sqrt(np.mean(np_chunk.astype(np.float32) ** 2)))
                    if rms < 120:
                        continue
            utterance = self.vad_processor.process_chunk(chunk) if self.vad_processor else None
            if not utterance:
                continue
            try:
                text, confidence, metrics = self.transcriber.transcribe(utterance, self.audio_capture.sample_rate)
            except Exception as e:
                logger.error(f"Transcription error: {e}")
                await self.publish_health(False, f"Transcription error: {e}")
                self.audio_capture.unmute("error")
                continue
            if not text.strip():
                continue
            accepted, info = self.suppress_engine.evaluate(text, confidence, metrics, utterance, self.audio_capture.sample_rate, self.audio_capture.frame_size)
            if not accepted:
                logger.info(f"Discarded '{text.strip()}' reasons={info.get('reasons')}")
                continue
            # Publish accepted
            logger.info(f"Transcribed: '{text.strip()}'{f' (conf {confidence:.2f})' if confidence is not None else ''}")
            self.audio_capture.mute("post-transcription")
            # Use conservative cap; per-char estimates can be too short
            est_ms = int(TTS_MAX_MUTE_MS)
            unmute_at = time.time() + est_ms / 1000.0
            if self.fallback_unmute_task and not self.fallback_unmute_task.done():
                self.fallback_unmute_task.cancel()
            async def fallback_unmute(ts=unmute_at):
                try:
                    await asyncio.sleep(max(0, ts - time.time()))
                    if self.audio_capture.is_muted and not self.pending_tts:
                        self.audio_capture.unmute("fallback-timeout")
                except asyncio.CancelledError:
                    pass
            self.fallback_unmute_task = asyncio.create_task(fallback_unmute())
            self.suppress_engine.register_publication(text.strip().lower())
            await self.publish_transcript(text.strip(), confidence)
            self.state.cooldown_until = time.time() + (POST_PUBLISH_COOLDOWN_MS / 1000.0)
            # Reset partial tracking after a final utterance
            self._last_partial_text = ""

    async def run(self):
        try:
            await self.initialize()
            self.audio_capture.start_capture()
            self.vad_processor = VADProcessor(self.audio_capture.sample_rate, self.audio_capture.frame_size)
            if self._enable_partials:
                self._partials_task = asyncio.create_task(self._partials_loop())
            if FFT_PUBLISH:
                self._fft_task = asyncio.create_task(self._fft_loop())
            await self.process_audio_stream()
        except Exception as e:
            logger.error(f"STT worker error: {e}")
            await self.publish_health(False, f"Worker error: {e}")
        finally:
            self.audio_capture.stop_capture()
            await self.mqtt.disconnect()

    async def _partials_loop(self):
        interval = PARTIAL_INTERVAL_MS / 1000.0
        while True:
            await asyncio.sleep(interval)
            if not STREAMING_PARTIALS:
                continue
            if not self.vad_processor or not self.vad_processor.is_speech:
                continue
            if self.pending_tts or self.audio_capture.is_muted:
                continue
            # Basic guard after unmute
            if self.recent_unmute_time and (time.time() - self.recent_unmute_time) < (UNMUTE_GUARD_MS / 1000.0):
                continue
            buf = self.vad_processor.get_active_buffer()
            if not buf:
                continue
            duration_ms = (len(buf) / 2) / self.audio_capture.sample_rate * 1000.0
            if duration_ms < PARTIAL_MIN_DURATION_MS:
                continue
            try:
                text, confidence, metrics = self.transcriber.transcribe(buf, self.audio_capture.sample_rate)
            except Exception as e:
                logger.debug(f"Partial transcription error: {e}")
                continue
            t = text.strip()
            if not t or len(t) < PARTIAL_MIN_CHARS:
                continue
            alpha = sum(c.isalpha() for c in t)
            alpha_ratio = alpha / max(1, len(t))
            if alpha_ratio < PARTIAL_ALPHA_RATIO_MIN:
                continue
            # Require some growth
            if self._last_partial_text and (len(t) - len(self._last_partial_text)) < PARTIAL_MIN_NEW_CHARS and not t.endswith('.'):
                continue
            if t == self._last_partial_text:
                continue
            self._last_partial_text = t
            await self.mqtt.safe_publish('stt/partial', {
                "text": t,
                "lang": "en",
                "confidence": confidence,
                "timestamp": time.time(),
                "is_final": False
            })
            logger.debug(f"Published partial: {t[:60]}{'...' if len(t)>60 else ''}")

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