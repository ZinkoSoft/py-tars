import logging
import webrtcvad
from typing import Optional

import numpy as np

from config import (
    VAD_AGGRESSIVENESS,
    SILENCE_THRESHOLD_MS,
    CHUNK_DURATION_MS,
    NOISE_MIN_RMS,
    NOISE_FLOOR_INIT,
    NOISE_FLOOR_ALPHA,
    NOISE_GATE_OFFSET,
)

logger = logging.getLogger("stt-worker.vad")

class VADProcessor:
    """Voice Activity Detection processor"""

    def __init__(self, sample_rate: int, frame_size: int):
        self.vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
        self.sample_rate = sample_rate
        self.frame_size = frame_size
        self.is_speech = False
        self.speech_buffer = []
        self.silence_count = 0
        self.max_silence_chunks = SILENCE_THRESHOLD_MS // CHUNK_DURATION_MS
        # Adaptive noise floor state (RMS units)
        self.noise_floor = float(NOISE_FLOOR_INIT)
        self.last_rms = 0.0

    def process_chunk(self, audio_chunk: bytes) -> Optional[bytes]:
        if len(audio_chunk) != self.frame_size * 2:
            return None

        # Compute RMS
        try:
            arr = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32)
            rms = float(np.sqrt(np.mean(arr ** 2))) if arr.size else 0.0
        except Exception:
            return None

        # Update adaptive noise floor using EMA when not in speech (or during trailing silence)
        if not self.is_speech:
            self.noise_floor = (1.0 - NOISE_FLOOR_ALPHA) * self.noise_floor + NOISE_FLOOR_ALPHA * rms
        else:
            # During speech, avoid training the floor to high levels; optionally decay slightly toward current rms
            self.noise_floor = max(self.noise_floor * (1.0 - NOISE_FLOOR_ALPHA * 0.25), min(self.noise_floor, rms))
        self.last_rms = rms

        # Adaptive gate: require rms above floor * offset OR above absolute minimum
        gate = max(NOISE_MIN_RMS, self.noise_floor * NOISE_GATE_OFFSET)
        if not self.is_speech and rms < gate:
            logger.debug(f"Dropping frame: rms={rms:.1f} < gate={gate:.1f} (floor={self.noise_floor:.1f})")
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
                    logger.debug(f"Speech ended, captured {len(self.speech_buffer)} chunks")
                    utterance = b''.join(self.speech_buffer)
                    self.is_speech = False
                    self.speech_buffer = []
                    self.silence_count = 0
                    return utterance
        return None

    def get_active_buffer(self) -> bytes:
        """Return current buffered speech bytes (excluding trailing silence) if speech ongoing."""
        if self.is_speech and self.speech_buffer:
            return b''.join(self.speech_buffer)
        return b''
