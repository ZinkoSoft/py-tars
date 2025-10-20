from __future__ import annotations

"""Microphone audio capture     def _get_pulseaudio_default_card(self) -> Optional[int]:
        \"\"\"Query PulseAudio for default source and extract ALSA card number.\"\"\"
        try:
            logger.debug("Querying PulseAudio for default source...")
            # Get default source name
            result = subprocess.run(
                ["pactl", "get-default-source"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode != 0:
                logger.debug("pactl get-default-source failed with code %d", result.returncode)
                return None
            
            source_name = result.stdout.strip()
            logger.info("PulseAudio default source: %s", source_name)ps PyAudio to read fixed-size PCM16LE frames and supports a mute guard to
avoid capturing TTS playback. Behavior unchanged; now includes types and docs.
"""

import asyncio
import logging
import subprocess
import threading
import time
from queue import Empty, Queue
from typing import AsyncGenerator, Optional

import pyaudio
import webrtcvad

from .audio_fanout import AudioFanoutPublisher
from .config import (
    AUDIO_DEVICE_NAME,
    CHUNK_DURATION_MS,
    SAMPLE_RATE,
    UNMUTE_GUARD_MS,
    VAD_AGGRESSIVENESS,
)

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
        self.device_index: Optional[int] = None  # Store for stream recreation
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
            logger.info(
                "Microphone muted%s; flushed %s frames", f" ({reason})" if reason else "", flushed
            )

    def unmute(self, reason: str = "") -> None:
        if self.is_muted:
            self.is_muted = False
            self.post_unmute_guard_until = time.time() + (UNMUTE_GUARD_MS / 1000.0)
            logger.info(
                "Microphone unmuted%s; guarding for %sms",
                f" ({reason})" if reason else "",
                UNMUTE_GUARD_MS,
            )

    def _get_pulseaudio_default_card(self) -> Optional[int]:
        """Query PulseAudio for default source and extract ALSA card number."""
        try:
            # Get default source name
            result = subprocess.run(
                ["pactl", "get-default-source"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode != 0:
                return None

            source_name = result.stdout.strip()
            logger.info("PulseAudio default source: %s", source_name)

            # Get source details to find ALSA card
            result = subprocess.run(
                ["pactl", "list", "sources"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode != 0:
                return None

            # Parse output to find card number for this source
            lines = result.stdout.split("\n")
            in_target_source = False
            for line in lines:
                if f"Name: {source_name}" in line:
                    in_target_source = True
                elif in_target_source:
                    if "alsa.card =" in line:
                        # Extract card number: alsa.card = "3"
                        card_str = line.split('"')[1]
                        card_num = int(card_str)
                        logger.info("PulseAudio default source is on ALSA card %d", card_num)
                        return card_num
                    elif line.startswith("Source #") or line.startswith("\tName:"):
                        # Moved to next source without finding card
                        break
        except Exception as e:
            logger.warning("Could not query PulseAudio for default source: %s", e)

        return None

    def start_capture(self) -> None:
        logger.info(
            "Starting audio capture: target cfg %sHz, %sms chunks",
            SAMPLE_RATE,
            CHUNK_DURATION_MS,
        )
        usb_device = None
        device_count = self.audio.get_device_count()
        logger.info("Scanning %s audio devices for USB microphone...", device_count)

        # Try to auto-detect host's default microphone via PulseAudio
        host_card = None
        if not AUDIO_DEVICE_NAME or AUDIO_DEVICE_NAME.lower() in ["auto", "pulse", "default"]:
            host_card = self._get_pulseaudio_default_card()
            if host_card is not None:
                logger.info("Auto-detected host default microphone on card %d", host_card)

        # If AUDIO_DEVICE_NAME is set and not a special auto-detect keyword, try to find it
        if AUDIO_DEVICE_NAME and AUDIO_DEVICE_NAME.lower() not in ["auto", "pulse", "default"]:
            logger.info("Looking for configured device: %s", AUDIO_DEVICE_NAME)
            # Check if it's a hardware device like "hw:3,0" or "plughw:3,0"
            if AUDIO_DEVICE_NAME.startswith(("hw:", "plughw:")):
                logger.info("Using ALSA hardware device: %s", AUDIO_DEVICE_NAME)
                usb_device = {"name": AUDIO_DEVICE_NAME, "index": -1, "use_alsa_name": True}
            else:
                # Search by name substring
                for i in range(device_count):
                    device_info = self.audio.get_device_info_by_index(i)
                    if AUDIO_DEVICE_NAME.lower() in device_info["name"].lower():
                        usb_device = device_info
                        logger.info("Found configured device: %s", device_info["name"])
                        break
                if usb_device is None:
                    logger.warning(
                        "Configured device '%s' not found, falling back to auto-detection",
                        AUDIO_DEVICE_NAME,
                    )

        # Auto-detection if no device configured or configured device not found
        if usb_device is None:
            for i in range(device_count):
                device_info = self.audio.get_device_info_by_index(i)
                logger.info(
                    "Device %s: '%s' - inputs: %s",
                    i,
                    device_info["name"],
                    device_info["maxInputChannels"],
                )

                # If we have a host card number, try to match it first
                if host_card is not None and device_info["maxInputChannels"] > 0:
                    # Check if this device name contains the card number (e.g., "hw:3,0" or "card 3")
                    if (
                        f"(hw:{host_card}," in device_info["name"]
                        or f"card {host_card}" in device_info["name"].lower()
                    ):
                        usb_device = device_info
                        logger.info("Matched host default microphone: %s", device_info["name"])
                        break

                # Fallback to USB detection
                if device_info["maxInputChannels"] > 0 and (
                    "USB" in device_info["name"] or "AIRHUG" in device_info["name"]
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

        # If auto-detection found a card but PyAudio can't enumerate it, use ALSA default (routed via PulseAudio)
        if usb_device is None and host_card is not None:
            logger.info(
                "PyAudio cannot enumerate card %d, using ALSA 'default' (routed via PulseAudio)",
                host_card,
            )
            # Don't specify device - use system default which is now routed through PulseAudio
            usb_device = None  # Will fall through to PyAudio's default

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

        # If using ALSA hardware device name (hw:X,Y or plughw:X,Y), find/create PyAudio device
        device_index = usb_device.get("index")
        if usb_device.get("use_alsa_name"):
            # Try to find the device by name in PyAudio's list
            alsa_name = usb_device["name"]
            for i in range(device_count):
                dev_info = self.audio.get_device_info_by_index(i)
                if dev_info["name"] == alsa_name:
                    device_index = i
                    logger.info("Found ALSA device '%s' at index %d", alsa_name, i)
                    break
            if device_index == -1:
                logger.error(
                    "Cannot open ALSA device '%s' - not found in PyAudio enumeration", alsa_name
                )
                raise RuntimeError(f"Audio device '{alsa_name}' not available")

        self.stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            input=True,
            frames_per_buffer=frame_size,
            input_device_index=device_index,
        )
        self.sample_rate = sample_rate
        self.frame_size = frame_size
        self.device_index = device_index  # Store for potential stream recreation
        self.is_recording = True
        threading.Thread(target=self._capture_loop, daemon=True).start()
        logger.info("Audio capture started")
        if self.is_muted:
            logger.info("Microphone starting muted; waiting for wake control to unmute")

    def _capture_loop(self) -> None:
        max_retries = 3
        retry_count = 0
        retry_delay = 2.0
        
        while self.is_recording:
            try:
                if not self.stream:
                    # Attempt to recreate stream if it was lost
                    if retry_count < max_retries:
                        logger.warning(
                            "Audio stream lost, attempting to recreate (retry %d/%d)...",
                            retry_count + 1,
                            max_retries,
                        )
                        time.sleep(retry_delay)
                        try:
                            self._reinitialize_stream()
                            logger.info("Audio stream successfully recreated")
                            retry_count = 0  # Reset on success
                            continue
                        except Exception as reinit_exc:
                            logger.error("Failed to reinitialize audio stream: %s", reinit_exc)
                            retry_count += 1
                            retry_delay = min(retry_delay * 2, 10.0)  # Exponential backoff, max 10s
                            continue
                    else:
                        logger.error("Max retries reached, stopping audio capture")
                        break
                
                data = self.stream.read(self.frame_size, exception_on_overflow=False)
                if self.fanout is not None:
                    self.fanout.push(data, self.sample_rate)
                now = time.time()
                if not self.is_muted and now >= self.post_unmute_guard_until:
                    self.audio_queue.put(data)
                
                # Reset retry state on successful read
                retry_count = 0
                retry_delay = 2.0
                
            except Exception as exc:
                logger.error("Audio capture error: %s", exc)
                # Mark stream as broken so next iteration will attempt recovery
                if self.stream:
                    try:
                        self.stream.stop_stream()
                        self.stream.close()
                    except Exception:  # pragma: no cover - cleanup errors
                        pass
                    self.stream = None

    def _reinitialize_stream(self) -> None:
        """Attempt to recreate the audio stream after a failure."""
        logger.info("Reinitializing audio stream...")
        
        # Close any existing stream
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:  # pragma: no cover - cleanup errors
                pass
            self.stream = None
        
        # Recreate PyAudio instance in case it's stale
        try:
            self.audio.terminate()
        except Exception:  # pragma: no cover - cleanup errors
            pass
        
        self.audio = pyaudio.PyAudio()
        
        # Recreate stream with saved parameters
        self.stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.frame_size,
            input_device_index=self.device_index,
        )
        logger.info(
            "Audio stream recreated: %dHz, device_index=%s",
            self.sample_rate,
            self.device_index if self.device_index is not None else "default",
        )

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
