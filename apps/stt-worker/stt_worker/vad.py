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
    VAD_ENHANCED_ANALYSIS,
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

        # Additional numpy-based speech analysis for better accuracy
        if VAD_ENHANCED_ANALYSIS:
            speech_analysis = self._analyze_speech_characteristics(audio_chunk)
            speech_like = speech_analysis.get("is_speech_like", False)

            # Combine WebRTC VAD with spectral analysis
            # Require both VAD and spectral analysis to agree, or VAD alone with strong spectral evidence
            confident_speech = has_speech and (speech_like or speech_analysis.get("speech_energy_ratio", 0) > 0.5)
        else:
            confident_speech = has_speech

        if confident_speech:
            if not self.is_speech:
                logger.info("Speech started (VAD: %s, spectral: %s)", has_speech, speech_like if VAD_ENHANCED_ANALYSIS else "disabled")
                self.is_speech = True
                self.speech_buffer = []
            self.speech_buffer.append(audio_chunk)
            self.silence_count = 0
        else:
            if self.is_speech:
                self.silence_count += 1
                self.speech_buffer.append(audio_chunk)
                if self.silence_count >= self.max_silence_chunks:
                    logger.info("Speech ended, captured %s chunks", len(self.speech_buffer))
                    utterance = b"".join(self.speech_buffer)
                    self.is_speech = False
                    self.speech_buffer = []
                    self.silence_count = 0
                    return utterance
        return None

    def _analyze_speech_characteristics(self, audio_chunk: bytes) -> dict[str, float]:
        """Analyze audio chunk for speech-like characteristics using numpy.

        Returns dict with various speech detection metrics.
        """
        try:
            arr = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32)
            if arr.size < 256:  # Need minimum samples for analysis
                return {"is_speech_like": False}

            # Normalize to [-1, 1]
            arr_norm = arr / 32768.0

            # 1. Zero-crossing rate (speech typically has higher ZCR than noise)
            zcr = np.sum(np.abs(np.diff(np.sign(arr_norm)))) / (2 * len(arr_norm))

            # 2. Spectral centroid (speech has different frequency distribution than noise)
            fft = np.fft.rfft(arr_norm)
            freqs = np.fft.rfftfreq(len(arr_norm), 1.0 / self.sample_rate)
            magnitude = np.abs(fft)
            spectral_centroid = np.sum(freqs * magnitude) / np.sum(magnitude)

            # 3. Spectral rolloff (frequency below which 85% of energy lies)
            cumsum = np.cumsum(magnitude**2)
            rolloff_idx = np.where(cumsum >= 0.85 * cumsum[-1])[0]
            spectral_rolloff = freqs[rolloff_idx[0]] if len(rolloff_idx) > 0 else 0

            # 4. Spectral flux (sudden changes in spectrum indicate speech)
            if hasattr(self, '_prev_magnitude'):
                spectral_flux = np.sum((magnitude - self._prev_magnitude)**2)
            else:
                spectral_flux = 0.0
            self._prev_magnitude = magnitude.copy()

            # 5. Energy in speech bands (300-3400 Hz is main speech range)
            speech_band_mask = (freqs >= 300) & (freqs <= 3400)
            speech_energy = np.sum(magnitude[speech_band_mask]**2)
            total_energy = np.sum(magnitude**2)
            speech_energy_ratio = speech_energy / total_energy if total_energy > 0 else 0

            # 6. RMS in different frequency bands
            low_freq_mask = freqs < 1000
            high_freq_mask = freqs > 1000
            low_rms = np.sqrt(np.mean(magnitude[low_freq_mask]**2)) if np.any(low_freq_mask) else 0
            high_rms = np.sqrt(np.mean(magnitude[high_freq_mask]**2)) if np.any(high_freq_mask) else 0

            # Speech detection heuristics
            is_speech_like = (
                zcr > 0.1 and  # High zero-crossing rate
                spectral_centroid > 1000 and spectral_centroid < 3000 and  # Speech frequency range
                speech_energy_ratio > 0.3 and  # Significant energy in speech bands
                high_rms > low_rms * 0.5  # Balanced high/low frequency energy
            )

            return {
                "is_speech_like": is_speech_like,
                "zcr": zcr,
                "spectral_centroid": spectral_centroid,
                "spectral_rolloff": spectral_rolloff,
                "spectral_flux": spectral_flux,
                "speech_energy_ratio": speech_energy_ratio,
                "low_rms": low_rms,
                "high_rms": high_rms,
            }

        except Exception as e:
            logger.debug(f"Speech analysis failed: {e}")
            return {"is_speech_like": False}

    def get_active_buffer(self) -> Optional[bytes]:
        """Get the current active speech buffer for FFT analysis.

        Returns the accumulated speech buffer if currently detecting speech,
        None otherwise.
        """
        if self.is_speech and self.speech_buffer:
            return b"".join(self.speech_buffer)
        return None
