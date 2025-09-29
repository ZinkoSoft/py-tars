from __future__ import annotations

"""Voice activity detection utilities.

This module wraps webrtcvad with additional gating via an adaptive noise floor.
Behavior is unchanged; types and docstrings were added for clarity.
"""

import logging
from typing import Optional

import numpy as np
import webrtcvad

from .config import (
    CHUNK_DURATION_MS,
    NOISE_FLOOR_ALPHA,
    NOISE_FLOOR_INIT,
    NOISE_GATE_OFFSET,
    NOISE_MIN_RMS,
    SILENCE_THRESHOLD_MS,
    VAD_AGGRESSIVENESS,
)

logger = logging.getLogger("stt-worker.vad")


class VADProcessor:
    """Voice Activity Detection processor.

    Args:
        sample_rate: PCM sample rate in Hz.
        frame_size: Frame size in samples (16-bit mono) per chunk.
    """

    def __init__(self, sample_rate: int, frame_size: int):
        self.vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
        self.sample_rate = sample_rate
        self.frame_size = frame_size
        self.is_speech = False
        self.speech_buffer: list[bytes] = []
        self.silence_count = 0
        self.max_silence_chunks = SILENCE_THRESHOLD_MS // CHUNK_DURATION_MS
        # Adaptive noise floor state (RMS units)
        self.noise_floor = float(NOISE_FLOOR_INIT)
        self.last_rms = 0.0

    def process_chunk(self, audio_chunk: bytes) -> Optional[bytes]:
        """Process a single PCM16LE chunk and return a completed utterance if detected.

        Returns None if speech has not ended yet or the frame is discarded.
        """
        if len(audio_chunk) != self.frame_size * 2:
            return None

        # Compute RMS
        try:
            arr = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32)
            rms = float(np.sqrt(np.mean(arr**2))) if arr.size else 0.0
        except Exception:
            return None

        # Update adaptive noise floor using EMA when not in speech (or during trailing silence)
        if not self.is_speech:
            self.noise_floor = (1.0 - NOISE_FLOOR_ALPHA) * self.noise_floor + NOISE_FLOOR_ALPHA * rms
        else:
            # During speech, avoid training the floor to high levels; decay slowly toward current rms but more conservatively
            decay_rate = NOISE_FLOOR_ALPHA * 0.1  # Much slower decay during speech
            self.noise_floor = max(
                self.noise_floor * (1.0 - decay_rate),
                min(self.noise_floor, rms),
            )
        self.last_rms = rms

        # Adaptive gate: require rms above floor * offset OR above absolute minimum
        gate = max(NOISE_MIN_RMS, self.noise_floor * NOISE_GATE_OFFSET)
        if not self.is_speech and rms < gate:
            return None

        try:
            has_speech = self.vad.is_speech(audio_chunk, self.sample_rate)
        except Exception:
            return None
        if has_speech:
            if not self.is_speech:
                logger.debug("Speech started")
                self.is_speech = True
                self.speech_buffer = []
            self.speech_buffer.append(audio_chunk)
            self.silence_count = 0
        else:
            if self.is_speech:
                self.silence_count += 1
                self.speech_buffer.append(audio_chunk)
                if self.silence_count >= self.max_silence_chunks:
                    logger.debug("Speech ended, captured %s chunks", len(self.speech_buffer))
                    utterance = b"".join(self.speech_buffer)
                    self.is_speech = False
                    self.speech_buffer = []
                    self.silence_count = 0
                    return utterance
        return None

    def get_active_buffer(self) -> bytes:
        """Return current buffered speech bytes if speech is ongoing.

        Trailing silence may be included while actively speaking to maintain continuity.
        """
        if self.is_speech and self.speech_buffer:
            return b"".join(self.speech_buffer)
        return b""
