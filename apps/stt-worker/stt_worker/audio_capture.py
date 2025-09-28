from __future__ import annotations

"""Microphone audio capture utilities.

Wraps PyAudio to read fixed-size PCM16LE frames and supports a mute guard to
avoid capturing TTS playback. Behavior unchanged; now includes types and docs.
"""

import asyncio
import logging
import threading
import time
from queue import Empty, Queue
from typing import AsyncGenerator, Optional

import pyaudio
import webrtcvad

from .audio_fanout import AudioFanoutPublisher
from .config import CHUNK_DURATION_MS, SAMPLE_RATE, UNMUTE_GUARD_MS, VAD_AGGRESSIVENESS

logger = logging.getLogger("stt-worker.audio")


class AudioCapture:
    """Handle microphone audio capture with VAD and half-duplex mute support."""

    def __init__(self) -> None:
        self.audio = pyaudio.PyAudio()
        self.vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
        self.stream = None
        self.audio_queue: Queue[bytes] = Queue()
        self.is_recording = False
        self.is_muted = True
        self.post_unmute_guard_until: float = 0.0
        self.sample_rate = SAMPLE_RATE
        self.frame_size = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)
        self.fanout: Optional[AudioFanoutPublisher] = None

    def register_fanout(self, fanout: AudioFanoutPublisher) -> None:
        self.fanout = fanout

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
            logger.info("Microphone muted%s; flushed %s frames", f" ({reason})" if reason else "", flushed)

    def unmute(self, reason: str = "") -> None:
        if self.is_muted:
            self.is_muted = False
            self.post_unmute_guard_until = time.time() + (UNMUTE_GUARD_MS / 1000.0)
            logger.info(
                "Microphone unmuted%s; guarding for %sms",
                f" ({reason})" if reason else "",
                UNMUTE_GUARD_MS,
            )

    def start_capture(self) -> None:
        logger.info(
            "Starting audio capture: target cfg %sHz, %sms chunks",
            SAMPLE_RATE,
            CHUNK_DURATION_MS,
        )
        usb_device = None
        device_count = self.audio.get_device_count()
        logger.info("Scanning %s audio devices for USB microphone...", device_count)
        for i in range(device_count):
            device_info = self.audio.get_device_info_by_index(i)
            logger.info("Device %s: '%s' - inputs: %s", i, device_info["name"], device_info["maxInputChannels"])
            if (
                device_info["maxInputChannels"] > 0
                and ("USB" in device_info["name"] or "AIRHUG" in device_info["name"])
            ):
                supported_rates = []
                for rate in [8000, 11025, 16000, 22050, 44100, 48000]:
                    try:
                        if self.audio.is_format_supported(
                            rate=rate,
                            input_device=device_info["index"],
                            input_channels=1,
                            input_format=pyaudio.paInt16,
                        ):
                            supported_rates.append(rate)
                    except Exception:  # pragma: no cover - PyAudio probing
                        pass
                logger.info("USB mic supported rates: %s", supported_rates)
                device_info["supported_rates"] = supported_rates
                usb_device = device_info
                logger.info("Found USB microphone: %s", device_info["name"])
                break

        if usb_device is None:
            usb_device = self.audio.get_default_input_device_info()
            logger.info("No USB microphone found, using default: %s", usb_device["name"])
            sample_rate = SAMPLE_RATE
        else:
            supported_rates = usb_device.get("supported_rates", [SAMPLE_RATE])
            if 16000 in supported_rates:
                sample_rate = 16000
            elif supported_rates:
                sample_rate = max(supported_rates)
            else:
                sample_rate = SAMPLE_RATE

        logger.info("Using audio input: %s at %sHz", usb_device["name"], sample_rate)
        frame_size = int(sample_rate * CHUNK_DURATION_MS / 1000)
        self.stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            input=True,
            frames_per_buffer=frame_size,
            input_device_index=usb_device["index"],
        )
        self.sample_rate = sample_rate
        self.frame_size = frame_size
        self.is_recording = True
        threading.Thread(target=self._capture_loop, daemon=True).start()
        logger.info("Audio capture started")
        if self.is_muted:
            logger.info("Microphone starting muted; waiting for wake control to unmute")

    def _capture_loop(self) -> None:
        while self.is_recording:
            try:
                if not self.stream:
                    break
                data = self.stream.read(self.frame_size, exception_on_overflow=False)
                if self.fanout is not None:
                    self.fanout.push(data, self.sample_rate)
                now = time.time()
                if not self.is_muted and now >= self.post_unmute_guard_until:
                    self.audio_queue.put(data)
            except Exception as exc:
                logger.error("Audio capture error: %s", exc)
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
                await asyncio.sleep(0.01)
            except Exception as exc:
                logger.error("Audio chunk error: %s", exc)
                break
