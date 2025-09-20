import logging
import numpy as np
import orjson
from typing import Tuple, Dict, Any

from config import WHISPER_MODEL, MODEL_PATH, STT_BACKEND, WS_URL

logger = logging.getLogger("stt-worker.transcriber")

class _LocalWhisperTranscriber:
    def __init__(self):
        from faster_whisper import WhisperModel  # lazy import to avoid requiring package for WS backend
        logger.info(f"Loading Whisper model: {WHISPER_MODEL}")
        self.model = WhisperModel(
            WHISPER_MODEL,
            device="cpu",
            compute_type="int8",
            download_root=MODEL_PATH,
            local_files_only=False
        )
        logger.info("Whisper model loaded successfully")

    def transcribe(self, audio_data: bytes, input_sample_rate: int) -> Tuple[str, float, Dict[str, Any]]:
        audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        if input_sample_rate != 16000:
            original_length = len(audio_np)
            target_length = int(original_length * 16000 / input_sample_rate)
            audio_np = np.interp(
                np.linspace(0, original_length - 1, target_length),
                np.arange(original_length),
                audio_np
            )
        segments, info = self.model.transcribe(
            audio_np,
            language="en",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=False,
            word_timestamps=False
        )
        seg_list = list(segments)
        text = " ".join(s.text.strip() for s in seg_list)
        confidence = getattr(info, 'language_probability', None)
        no_speech_vals = []
        logprob_vals = []
        for s in seg_list:
            ns = getattr(s, 'no_speech_prob', None)
            if ns is not None:
                no_speech_vals.append(ns)
            lp = getattr(s, 'avg_logprob', None)
            if lp is not None:
                logprob_vals.append(lp)
        metrics = {
            "avg_no_speech_prob": float(sum(no_speech_vals)/len(no_speech_vals)) if no_speech_vals else None,
            "avg_logprob": float(sum(logprob_vals)/len(logprob_vals)) if logprob_vals else None,
            "num_segments": len(seg_list)
        }
        return text, confidence, metrics


class _WebSocketTranscriber:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url

    def transcribe(self, audio_data: bytes, input_sample_rate: int) -> Tuple[str, float, Dict[str, Any]]:
        # Synchronous round-trip: open WS, send init + audio + end, wait final
        # This is kept simple to integrate without changing the STT worker orchestration.
        import websockets
        import asyncio

        async def _do():
            async with websockets.connect(self.ws_url, max_size=None) as ws:
                await ws.send(orjson.dumps({
                    "type": "init",
                    "sample_rate": input_sample_rate,
                    "lang": "en",
                    "enable_partials": False
                }))
                await ws.send(audio_data)
                await ws.send(orjson.dumps({"type": "end"}))
                # Read until we get a final
                while True:
                    msg = await ws.recv()
                    if isinstance(msg, (bytes, bytearray)):
                        continue
                    data = orjson.loads(msg)
                    if data.get("type") == "final":
                        return data.get("text", ""), data.get("confidence")

        text, conf = asyncio.get_event_loop().run_until_complete(_do())
        # Return empty metrics for WS backend (server can compute if needed)
        return text or "", conf, {"backend": "ws"}


class SpeechTranscriber:
    def __init__(self):
        if STT_BACKEND == "ws":
            logger.info(f"Using WebSocket STT backend: {WS_URL}")
            self._impl = _WebSocketTranscriber(WS_URL)
        else:
            self._impl = _LocalWhisperTranscriber()

    def transcribe(self, audio_data: bytes, input_sample_rate: int) -> Tuple[str, float, Dict[str, Any]]:
        return self._impl.transcribe(audio_data, input_sample_rate)
