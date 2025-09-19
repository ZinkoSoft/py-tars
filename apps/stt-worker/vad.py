import logging
import webrtcvad
from typing import Optional

from config import VAD_AGGRESSIVENESS, SILENCE_THRESHOLD_MS, CHUNK_DURATION_MS

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

    def process_chunk(self, audio_chunk: bytes) -> Optional[bytes]:
        if len(audio_chunk) != self.frame_size * 2:
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
