import asyncio
import logging
import os
import time
import numpy as np
import orjson

from config import LOG_LEVEL, MQTT_URL, POST_PUBLISH_COOLDOWN_MS, TTS_BASE_MUTE_MS, TTS_PER_CHAR_MS, TTS_MAX_MUTE_MS
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

    async def initialize(self):
        if os.path.exists("/host-models"):
            try:
                os.system("cp -r /app/models/* /host-models/ 2>/dev/null || true")
            except Exception as e:
                logger.warning(f"Could not save models to host: {e}")
        await self.mqtt.connect()
        await self.publish_health(True, "STT service ready")
        await self.mqtt.subscribe_stream('tts/status', self._handle_tts_status)

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

    async def process_audio_stream(self):
        logger.info("Starting audio processing loop")
        async for chunk in self.audio_capture.get_audio_chunks():
            # Cooldown gating
            if self.state.cooldown_until and time.time() < self.state.cooldown_until:
                continue
            if self.pending_tts:
                continue
            if self.recent_unmute_time and (time.time() - self.recent_unmute_time) < 0.4:
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
            est_ms = int(min(TTS_MAX_MUTE_MS, TTS_BASE_MUTE_MS + len(text) * TTS_PER_CHAR_MS))
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

    async def run(self):
        try:
            await self.initialize()
            self.audio_capture.start_capture()
            self.vad_processor = VADProcessor(self.audio_capture.sample_rate, self.audio_capture.frame_size)
            await self.process_audio_stream()
        except Exception as e:
            logger.error(f"STT worker error: {e}")
            await self.publish_health(False, f"Worker error: {e}")
        finally:
            self.audio_capture.stop_capture()
            await self.mqtt.disconnect()

async def main():
    logger.info("Starting TARS STT Worker")
    worker = STTWorker()
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())