from __future__ import annotations

import io
import logging
import os
import tempfile
import time
from typing import Optional

import httpx

from .base import TTSExternalService

# Reuse existing player helper for consistency
from tts_worker.piper_synth import _spawn_player


logger = logging.getLogger("tts-worker.elevenlabs")


class ElevenLabsTTS(TTSExternalService):
    """ElevenLabs HTTP TTS provider.

    Minimal implementation that supports synth-to-file and immediate playback.
    Streaming via HTTP chunks is emulated by piping the response body to paplay/aplay.
    """

    def __init__(
        self,
        api_key: str,
        voice_id: str,
        *,
        api_base: str = "https://api.elevenlabs.io/v1",
        model_id: str = "eleven_multilingual_v2",
        optimize_streaming: int = 0,
        timeout: float = 30.0,
    ) -> None:
        if not api_key:
            raise ValueError("ELEVEN_API_KEY is required for ElevenLabsTTS")
        if not voice_id:
            raise ValueError("ELEVEN_VOICE_ID is required for ElevenLabsTTS")
        self.api_key = api_key
        self.voice_id = voice_id
        self.api_base = api_base.rstrip("/")
        self.model_id = model_id
        self.optimize_streaming = int(optimize_streaming)
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)
        # Safe, informative startup log (no secrets)
        logger.info(
            "ElevenLabsTTS initialized",
            extra={
                "service": "tts",
                "provider": "elevenlabs",
                "voice_id": self.voice_id,
                "model_id": self.model_id,
                "optimize_streaming": self.optimize_streaming,
                "api_base": self.api_base,
            },
        )

    # ----- TTSExternalService -----
    def synth_and_play(self, text: str) -> float:
        t0 = time.time()
        logger.info(
            "ElevenLabs synth_and_play invoked",
            extra={
                "service": "tts",
                "provider": "elevenlabs",
                "mode": "auto",
                "text_len": len(text or ""),
            },
        )
        # Try streaming playback first for lower latency
        try:
            self._stream_and_play(text)
            dt = time.time() - t0
            logger.info(
                "ElevenLabs streaming playback finished",
                extra={"service": "tts", "provider": "elevenlabs", "path": "stream", "duration_s": round(dt, 3)},
            )
            return dt
        except Exception as e:
            logger.warning(f"ElevenLabs HTTP stream failed: {e}; falling back to file synthesis")
        # Fallback to file path
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
            t1 = time.time()
            self.synth_to_wav(text, f.name)
            p = _spawn_player(args=[f.name], role="playback")
            p.wait()
        dt = time.time() - t0
        logger.info(
            "ElevenLabs file playback finished",
            extra={
                "service": "tts",
                "provider": "elevenlabs",
                "path": "file",
                "synth_s": round(time.time() - t1, 3),
                "duration_s": round(dt, 3),
            },
        )
        return dt

    def synth_to_wav(self, text: str, wav_path: str) -> None:
        url = f"{self.api_base}/text-to-speech/{self.voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "accept": "audio/wav",
            "content-type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": self.model_id,
            "optimize_streaming_latency": self.optimize_streaming,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        logger.info(
            "ElevenLabs synth_to_wav request",
            extra={
                "service": "tts",
                "provider": "elevenlabs",
                "endpoint": "/text-to-speech",
                "voice_id": self.voice_id,
                "model_id": self.model_id,
                "text_len": len(text or ""),
            },
        )
        bytes_total = 0
        t0 = time.time()
        with self._client.stream("POST", url, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            with open(wav_path, "wb") as out:
                for chunk in resp.iter_bytes():
                    if chunk:
                        out.write(chunk)
                        bytes_total += len(chunk)
        logger.info(
            "ElevenLabs synth_to_wav complete",
            extra={
                "service": "tts",
                "provider": "elevenlabs",
                "bytes": bytes_total,
                "duration_s": round(time.time() - t0, 3),
                "wav_path": os.path.basename(wav_path),
            },
        )

    # ----- internals -----
    def _stream_and_play(self, text: str) -> None:
        url = f"{self.api_base}/text-to-speech/{self.voice_id}/stream"
        headers = {
            "xi-api-key": self.api_key,
            "accept": "audio/wav",
            "content-type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": self.model_id,
            "optimize_streaming_latency": self.optimize_streaming,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        logger.info(
            "ElevenLabs streaming request",
            extra={
                "service": "tts",
                "provider": "elevenlabs",
                "endpoint": "/text-to-speech/stream",
                "voice_id": self.voice_id,
                "model_id": self.model_id,
                "text_len": len(text or ""),
            },
        )
        bytes_total = 0
        t0 = time.time()
        with self._client.stream("POST", url, headers=headers, json=payload) as resp:
            resp.raise_for_status()
            # Pipe directly to player stdin
            p = _spawn_player(role="stream-player")
            assert p.stdin is not None
            try:
                for chunk in resp.iter_bytes():
                    if not chunk:
                        continue
                    p.stdin.write(chunk)
                    bytes_total += len(chunk)
                try:
                    p.stdin.flush()
                except Exception:
                    pass
                p.stdin.close()
            finally:
                p.wait()
        logger.info(
            "ElevenLabs streaming finished",
            extra={
                "service": "tts",
                "provider": "elevenlabs",
                "bytes": bytes_total,
                "duration_s": round(time.time() - t0, 3),
            },
        )
