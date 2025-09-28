"""Pygame-based UI for TARS: displays spectrum, partials/finals, and TTS text."""
import logging
import queue
import threading
import time
from typing import Any

import numpy as np
import orjson
import paho.mqtt.client as mqtt
import pygame
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

from urllib.parse import urlparse
from config import load_config

CFG = load_config()

MQTT_URL = CFG["mqtt"]["url"]
WIDTH = int(CFG["ui"]["width"])
HEIGHT = int(CFG["ui"]["height"])
FPS = int(CFG["ui"]["fps"])
NUM_BARS = int(CFG["ui"]["num_bars"])
FONT_NAME = CFG["ui"]["font"]

AUDIO_TOPIC = CFG["topics"]["audio"]
AUDIO_EVENT = AUDIO_TOPIC or "__fft__"
PARTIAL_TOPIC = CFG["topics"]["partial"]
FINAL_TOPIC = CFG["topics"]["final"]
TTS_TOPIC = CFG["topics"]["tts"]

FFT_WS_CFG = CFG.get("fft_ws", {})


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


FFT_WS_ENABLED = _as_bool(FFT_WS_CFG.get("enabled", True))
FFT_WS_URL = str(FFT_WS_CFG.get("url", "") or "")
try:
    FFT_WS_RETRY = float(FFT_WS_CFG.get("retry_seconds", 5.0) or 5.0)
except (TypeError, ValueError):
    FFT_WS_RETRY = 5.0

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tars.ui")

u = urlparse(MQTT_URL)
host = u.hostname or "127.0.0.1"
port = u.port or 1883
username = u.username
password = u.password

class MqttBridge:
    def __init__(self, event_queue: queue.Queue, *, subscribe_audio: bool) -> None:
        self.client = mqtt.Client(client_id="tars-ui")
        if username and password:
            self.client.username_pw_set(username, password)
        self.q = event_queue
        self._subscribe_audio = subscribe_audio and bool(AUDIO_TOPIC)
        self.client.on_message = self._on_message
        self._thread: threading.Thread | None = None

    def _on_message(self, client, userdata, msg):
        try:
            payload = orjson.loads(msg.payload)
        except Exception:
            payload = {}
        try:
            self.q.put_nowait((msg.topic, payload))
        except queue.Full:
            logger.debug("UI event queue full; dropping MQTT message from %s", msg.topic)

    def start(self):
        self.client.connect(host, port, 60)
        topics = [(PARTIAL_TOPIC, 0), (FINAL_TOPIC, 0), (TTS_TOPIC, 0)]
        if self._subscribe_audio:
            topics.append((AUDIO_TOPIC, 0))
        if topics:
            self.client.subscribe(topics)
        self._thread = threading.Thread(target=self.client.loop_forever, daemon=True)
        self._thread.start()

    def poll(self):
        try:
            return self.q.get_nowait()
        except queue.Empty:
            return None, None

    def stop(self) -> None:
        try:
            self.client.disconnect()
        except Exception:
            pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)


class FFTWebsocketClient:
    def __init__(
        self,
        url: str,
        target_topic: str,
        event_queue: queue.Queue,
        *,
        retry_seconds: float = 5.0,
    ) -> None:
        self.url = url
        self.target_topic = target_topic
        self.q = event_queue
        self.retry_seconds = max(1.0, float(retry_seconds))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="fft-ws", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                logger.info("Connecting to FFT websocket %s", self.url)
                with connect(
                    self.url,
                    ping_interval=20.0,
                    ping_timeout=20.0,
                    close_timeout=1.0,
                ) as ws:
                    logger.info("FFT websocket connected")
                    while not self._stop.is_set():
                        try:
                            message = ws.recv()
                        except ConnectionClosed as exc:
                            logger.warning("FFT websocket closed: %s", exc)
                            break
                        if message is None:
                            break
                        try:
                            data = orjson.loads(message)
                        except Exception:
                            continue
                        try:
                            self.q.put_nowait((self.target_topic, data))
                        except queue.Full:
                            logger.debug("UI event queue full; dropping websocket frame")
            except Exception as exc:
                if self._stop.is_set():
                    break
                logger.warning(
                    "FFT websocket connection error: %s; retrying in %.1fs",
                    exc,
                    self.retry_seconds,
                )
                time.sleep(self.retry_seconds)
            else:
                if not self._stop.is_set():
                    time.sleep(self.retry_seconds)


class UI:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("TARS UI")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(FONT_NAME, 22)
        self.big_font = pygame.font.SysFont(FONT_NAME, 28)
        self.last_partial = ""
        self.last_final = ""
        self.last_tts = ""
        self.spectrum = np.zeros(NUM_BARS, dtype=np.float32)

    def draw_bars(self, values: np.ndarray, surface):
        # Normalize
        v = values.copy()
        if np.max(v) > 0:
            v /= np.max(v)
        bar_w = WIDTH / NUM_BARS
        for i, val in enumerate(v):
            h = int(val * (HEIGHT * 0.4))
            x = int(i * bar_w)
            y = int(HEIGHT * 0.35) - h
            color = (int(255 * i / NUM_BARS), 180, 255 - int(255 * i / NUM_BARS))
            pygame.draw.rect(surface, color, pygame.Rect(x, y, int(bar_w) - 2, h))

    def render(self):
        self.screen.fill((5, 5, 8))
        # Top spectrum
        self.draw_bars(self.spectrum, self.screen)
        # Middle transcript
        txt_surface = self.big_font.render(self.last_partial or self.last_final, True, (240, 240, 240))
        self.screen.blit(txt_surface, (20, int(HEIGHT * 0.45)))
        # Bottom AI response
        tts_surface = self.font.render(self.last_tts, True, (180, 220, 180))
        self.screen.blit(tts_surface, (20, int(HEIGHT * 0.75)))
        pygame.display.flip()

    def update_spectrum_from_fft(self, fft_array):
        # Expecting an array (list) of magnitude values; resample to NUM_BARS
        arr = np.array(fft_array, dtype=np.float32)
        if arr.size == 0:
            self.spectrum *= 0.9
            return
        resampled = np.interp(np.linspace(0, len(arr) - 1, NUM_BARS), np.arange(len(arr)), arr)
        # Smooth a bit
        self.spectrum = 0.8 * self.spectrum + 0.2 * resampled


def main():
    event_queue = queue.Queue(maxsize=256)
    use_ws = FFT_WS_ENABLED and bool(FFT_WS_URL)
    bridge = MqttBridge(event_queue, subscribe_audio=not use_ws)
    bridge.start()
    fft_client: FFTWebsocketClient | None = None
    if use_ws:
        fft_client = FFTWebsocketClient(FFT_WS_URL, AUDIO_EVENT, event_queue, retry_seconds=FFT_WS_RETRY)
        fft_client.start()
    ui = UI()

    try:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            topic, payload = bridge.poll()
            if topic:
                if topic == PARTIAL_TOPIC:
                    ui.last_partial = payload.get("text", "")
                elif topic == FINAL_TOPIC:
                    ui.last_final = payload.get("text", "")
                    ui.last_partial = ""
                elif topic == TTS_TOPIC:
                    ev = payload.get("event")
                    if ev == "speaking_start":
                        ui.last_tts = payload.get("text", "")
                elif topic == AUDIO_EVENT:
                    fft_vals = payload.get("fft") or []
                    ui.update_spectrum_from_fft(fft_vals)
            ui.render()
            ui.clock.tick(FPS)
    finally:
        pygame.quit()
        bridge.stop()
        if fft_client:
            fft_client.stop()

if __name__ == "__main__":
    main()
