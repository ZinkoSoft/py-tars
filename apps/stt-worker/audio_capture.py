from __future__ import annotations

"""Microphone audio capture utilities.

Wraps PyAudio to read fixed-size PCM16LE frames and supports a mute guard to
avoid capturing TTS playback. Behavior unchanged; now includes types and docs.
"""

import logging
import os
import time
import threading
from queue import Queue, Empty
import pyaudio
import webrtcvad
from typing import AsyncGenerator

from config import CHUNK_DURATION_MS, UNMUTE_GUARD_MS, SAMPLE_RATE, VAD_AGGRESSIVENESS

logger = logging.getLogger("stt-worker.audio")

class AudioCapture:
    """Handle microphone audio capture with VAD and half-duplex mute support."""

    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
        self.stream = None
        self.audio_queue = Queue()
        self.is_recording = False
        self.is_muted = False
        self.post_unmute_guard_until: float = 0.0

    def mute(self, reason: str = "") -> None:
        if not self.is_muted:
            self.is_muted = True
            flushed = 0
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                    flushed += 1
                except Empty:
                    break
            logger.info(f"Microphone muted{f' ({reason})' if reason else ''}; flushed {flushed} frames")

    def unmute(self, reason: str = "") -> None:
        if self.is_muted:
            self.is_muted = False
            self.post_unmute_guard_until = time.time() + (UNMUTE_GUARD_MS / 1000.0)
            logger.info(f"Microphone unmuted{f' ({reason})' if reason else ''}; guarding for {UNMUTE_GUARD_MS}ms")

    def start_capture(self) -> None:
        logger.info(f"Starting audio capture: target cfg {SAMPLE_RATE}Hz, {CHUNK_DURATION_MS}ms chunks")
        usb_device = None
        device_count = self.audio.get_device_count()
        logger.info(f"Scanning {device_count} audio devices for USB microphone...")
        for i in range(device_count):
            device_info = self.audio.get_device_info_by_index(i)
            logger.info(f"Device {i}: '{device_info['name']}' - inputs: {device_info['maxInputChannels']}")
            if (device_info['maxInputChannels'] > 0 and ("USB" in device_info['name'] or "AIRHUG" in device_info['name'])):
                supported_rates = []
                for rate in [8000, 11025, 16000, 22050, 44100, 48000]:
                    try:
                        if self.audio.is_format_supported(rate=rate, input_device=device_info['index'], input_channels=1, input_format=pyaudio.paInt16):
                            supported_rates.append(rate)
                    except Exception:
                        pass
                logger.info(f"USB mic supported rates: {supported_rates}")
                device_info['supported_rates'] = supported_rates
                usb_device = device_info
                logger.info(f"Found USB microphone: {device_info['name']}")
                break

        if usb_device is None:
            usb_device = self.audio.get_default_input_device_info()
            logger.info(f"No USB microphone found, using default: {usb_device['name']}")
            sample_rate = SAMPLE_RATE
        else:
            supported_rates = usb_device.get('supported_rates', [SAMPLE_RATE])
            if 16000 in supported_rates:
                sample_rate = 16000
            elif supported_rates:
                sample_rate = max(supported_rates)
            else:
                sample_rate = SAMPLE_RATE

        logger.info(f"Using audio input: {usb_device['name']} at {sample_rate}Hz")
        frame_size = int(sample_rate * CHUNK_DURATION_MS / 1000)
        self.stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            input=True,
            frames_per_buffer=frame_size,
            input_device_index=usb_device['index']
        )
        self.sample_rate = sample_rate
        self.frame_size = frame_size
        self.is_recording = True
        threading.Thread(target=self._capture_loop, daemon=True).start()
        logger.info("Audio capture started")

    def _capture_loop(self) -> None:
        while self.is_recording:
            try:
                data = self.stream.read(self.frame_size, exception_on_overflow=False)
                now = time.time()
                if not self.is_muted and now >= self.post_unmute_guard_until:
                    self.audio_queue.put(data)
            except Exception as e:
                logger.error(f"Audio capture error: {e}")
                break

    def stop_capture(self) -> None:
        self.is_recording = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.audio.terminate()
        logger.info("Audio capture stopped")

    async def get_audio_chunks(self) -> AsyncGenerator[bytes, None]:
        while True:
            try:
                chunk = self.audio_queue.get(timeout=0.1)
                yield chunk
            except Empty:
                import asyncio
                await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"Audio chunk error: {e}")
                break
