from __future__ import annotations

"""Microphone audio capture utilities.

Wraps PyAudio to read fixed-size PCM16LE frames and supports a mute guard to
avoid capturing TTS playback. Behavior unchanged; now includes types and docs.
"""

import logging
import time
import threading
from queue import Queue, Empty
from typing import AsyncGenerator, Optional

import pyaudio
import webrtcvad

from audio_fanout import AudioFanoutPublisher
from config import CHUNK_DURATION_MS, UNMUTE_GUARD_MS, SAMPLE_RATE, VAD_AGGRESSIVENESS

logger = logging.getLogger("stt-worker.audio")

class AudioCapture:
    """Handle microphone audio capture with VAD and half-duplex mute support."""

    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
        self.stream = None
        """Compatibility shim re-exporting packaged audio capture implementation."""

        from stt_worker.audio_capture import AudioCapture

        __all__ = ["AudioCapture"]
        self.fanout: Optional[AudioFanoutPublisher] = None
