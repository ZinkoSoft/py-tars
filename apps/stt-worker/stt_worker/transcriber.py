from __future__ import annotations

"""STT transcription backends: local Whisper, WebSocket proxy, or OpenAI API.

Public entry point is SpeechTranscriber; behavior unchanged. Added typing and docs.
Async wrappers added to prevent blocking event loop during CPU-bound transcription.
"""

import asyncio
import io
import logging
import wave
from typing import Any, Dict, Tuple

import numpy as np
import orjson

from .config import (
    MODEL_PATH,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_STT_MODEL,
    OPENAI_TIMEOUT_S,
    STT_BACKEND,
    WHISPER_MODEL,
    WS_URL,
)

logger = logging.getLogger("stt-worker.transcriber")

__all__ = ["SpeechTranscriber"]


class _LocalWhisperTranscriber:
    """Local Faster-Whisper implementation (CPU only by default)."""

    def __init__(self) -> None:
        from faster_whisper import WhisperModel  # lazy import to avoid requiring package for WS backend

        logger.info("Loading Whisper model: %s", WHISPER_MODEL)
        self.model = WhisperModel(
            WHISPER_MODEL,
            device="cpu",
            compute_type="int8",
            download_root=MODEL_PATH,
            local_files_only=False,
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
                audio_np,
            )
        segments, info = self.model.transcribe(
            audio_np,
            language="en",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            vad_filter=False,
            word_timestamps=False,
        )
        seg_list = list(segments)
        text = " ".join(s.text.strip() for s in seg_list)
        confidence = getattr(info, "language_probability", None)
        no_speech_vals = []
        logprob_vals = []
        for s in seg_list:
            ns = getattr(s, "no_speech_prob", None)
            if ns is not None:
                no_speech_vals.append(ns)
            lp = getattr(s, "avg_logprob", None)
            if lp is not None:
                logprob_vals.append(lp)
        metrics = {
            "avg_no_speech_prob": float(sum(no_speech_vals) / len(no_speech_vals)) if no_speech_vals else None,
            "avg_logprob": float(sum(logprob_vals) / len(logprob_vals)) if logprob_vals else None,
            "num_segments": len(seg_list),
        }
        return text, confidence, metrics


class _WebSocketTranscriber:
    """Synchronous WebSocket client for offloaded STT service."""

    def __init__(self, ws_url: str) -> None:
        self.ws_url = ws_url

    def transcribe(self, audio_data: bytes, input_sample_rate: int) -> Tuple[str, float, Dict[str, Any]]:
        # Synchronous round-trip using websockets.sync to avoid interfering with asyncio loop
        from websockets.sync.client import connect

        text_out: str = ""
        conf_out = None
        with connect(self.ws_url, max_size=None) as ws:
            # Send init as text frame
            ws.send(
                orjson.dumps(
                    {
                        "type": "init",
                        "sample_rate": input_sample_rate,
                        "lang": "en",
                        "enable_partials": False,
                    }
                ).decode()
            )
            # Send audio as binary frame
            ws.send(audio_data)
            # Signal end as text frame
            ws.send(orjson.dumps({"type": "end"}).decode())
            # Drain until final
            while True:
                msg = ws.recv()
                if isinstance(msg, (bytes, bytearray)):
                    continue
                try:
                    data = orjson.loads(msg)
                except Exception:
                    continue
                if data.get("type") == "final":
                    text_out = data.get("text", "") or ""
                    conf_out = data.get("confidence")
                    break

        return text_out, conf_out, {"backend": "ws"}


class _OpenAITranscriber:
    """Synchronous HTTP client for OpenAI-compatible audio transcription.

    Sends a short WAV built from PCM16 to the /audio/transcriptions endpoint.
    This is called from a worker thread by the main loop; keep it blocking here.
    """

    def __init__(self, base_url: str, api_key: str, model: str, timeout_s: float = 30.0):
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for STT_BACKEND=openai")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s

    @staticmethod
    def _pcm_to_wav_bytes(pcm_bytes: bytes, sample_rate: int) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
        return buf.getvalue()

    def transcribe(self, audio_data: bytes, input_sample_rate: int) -> Tuple[str, float, Dict[str, Any]]:
        import httpx

        # Prefer sending native sample rate; OpenAI server handles resampling; keep file concise
        wav_bytes = self._pcm_to_wav_bytes(audio_data, input_sample_rate)
        url = f"{self.base_url}/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        # Multipart form; 'file' must look like a file upload
        files = {
            "file": ("audio.wav", wav_bytes, "audio/wav"),
        }
        data = {
            "model": self.model,
            "response_format": "json",
            "temperature": "0",
            "language": "en",
        }
        # Use a short-lived client per call to avoid shared state; keep timeouts conservative
        with httpx.Client(timeout=self.timeout_s) as client:
            resp = client.post(url, headers=headers, data=data, files=files)
            resp.raise_for_status()
            payload = resp.json()
        # OpenAI whisper returns { text: "..." }. Some providers include confidence; default None
        text = payload.get("text") or payload.get("transcript") or ""
        conf = payload.get("confidence")
        return text, conf, {"backend": "openai", "provider": "openai", "model": self.model}


class SpeechTranscriber:
    """Facade selecting the configured STT backend.

    Use transcribe(audio_data, input_sample_rate) to obtain (text, confidence, metrics).
    For async contexts, use transcribe_async() to avoid blocking the event loop.
    """

    def __init__(self) -> None:
        if STT_BACKEND == "ws":
            logger.info("Using WebSocket STT backend: %s", WS_URL)
            self._impl = _WebSocketTranscriber(WS_URL)
        elif STT_BACKEND == "openai":
            logger.info(
                "Using OpenAI STT backend: base=%s, model=%s",
                OPENAI_BASE_URL,
                OPENAI_STT_MODEL,
            )
            # Do not log the API key
            self._impl = _OpenAITranscriber(
                base_url=OPENAI_BASE_URL,
                api_key=OPENAI_API_KEY,
                model=OPENAI_STT_MODEL,
                timeout_s=OPENAI_TIMEOUT_S,
            )
        else:
            self._impl = _LocalWhisperTranscriber()

    def transcribe(self, audio_data: bytes, input_sample_rate: int) -> Tuple[str, float, Dict[str, Any]]:
        """Synchronous transcription (blocks for CPU-bound Whisper inference).
        
        For async contexts, prefer transcribe_async() to avoid blocking the event loop.
        """
        return self._impl.transcribe(audio_data, input_sample_rate)

    async def transcribe_async(self, audio_data: bytes, input_sample_rate: int) -> Tuple[str, float, Dict[str, Any]]:
        """Async wrapper for transcription using asyncio.to_thread().
        
        Offloads CPU-bound work to a thread pool, keeping the event loop responsive.
        Recommended for all async contexts (e.g., within service event handlers).
        
        Args:
            audio_data: Raw PCM16 audio bytes
            input_sample_rate: Sample rate of the input audio
            
        Returns:
            Tuple of (text, confidence, metrics)
        """
        return await asyncio.to_thread(self._impl.transcribe, audio_data, input_sample_rate)
