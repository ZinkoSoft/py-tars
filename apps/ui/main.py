"""Pygame-based UI for TARS: displays spectrum, partials/finals, and TTS text."""
import logging
import queue
import time
from pathlib import Path
from typing import Any

import pygame

from urllib.parse import urlparse
from config import load_config
from fft_ws_client import FFTWebsocketClient
from mqtt_bridge import MqttBridge
from module.layout import Box, get_layout_dimensions, load_layout_config
from module.spectrum import SpectrumBars
from module.tars_idle import TarsIdle

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


FULLSCREEN = _as_bool(CFG["ui"].get("fullscreen", False))
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

class UI:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("TARS UI")
        flags = pygame.FULLSCREEN if FULLSCREEN else 0
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        if FULLSCREEN:
            pygame.mouse.set_visible(False)
        self.width, self.height = self.screen.get_size()
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(FONT_NAME, 22)
        self.big_font = pygame.font.SysFont(FONT_NAME, 28)
        self.last_partial = ""
        self.last_final = ""
        self.last_tts = ""
        self.boot_message = "System Online"
        self.boot_message_started = time.monotonic()
        self.boot_message_duration = 3.0
        self.components: dict[str, Any] = {}
        self.spectrum_component: SpectrumBars | None = None

        layout_cfg = CFG.get("layout", {}) or {}
        layout_file = str(layout_cfg.get("file", "layout.json"))
        rotation = int(layout_cfg.get("rotation", 0) or 0)
        layout_data = load_layout_config(Path(__file__).resolve().parent, layout_file)
        boxes = get_layout_dimensions(layout_data, self.width, self.height, rotation)
        if not boxes:
            logger.info("No layout boxes defined; using full-width spectrum fallback")
            fallback_box = Box(
                name="spectrum",
                x=20,
                y=int(self.height * 0.65),
                width=self.width - 40,
                height=int(self.height * 0.3),
                rotation=rotation,
                original_width=self.width - 40,
                original_height=int(self.height * 0.3),
            )
            boxes = [fallback_box]

        for box in boxes:
            key = box.name.lower()
            if key == "spectrum":
                component = SpectrumBars(box, NUM_BARS)
                self.components[key] = component
                self.spectrum_component = component
            elif key == "tars_idle":
                component = TarsIdle(box)
                self.components[key] = component
            else:
                logger.info("Unhandled layout component '%s'", box.name)

    def render(self):
        self.screen.fill((5, 5, 8))
        now = time.monotonic()
        fonts = {"small": self.font, "large": self.big_font}

        # Render background components first
        if "tars_idle" in self.components:
            try:
                self.components["tars_idle"].render(self.screen, now, fonts)
            except Exception as exc:  # pragma: no cover - defensive rendering guard
                logger.error("Component tars_idle render failed: %s", exc)

        for key, component in self.components.items():
            if key == "tars_idle":
                continue
            try:
                component.render(self.screen, now, fonts)
            except Exception as exc:  # pragma: no cover - defensive rendering guard
                logger.error("Component %s render failed: %s", component.__class__.__name__, exc)

        spectrum_top = self.height
        if self.spectrum_component is not None:
            spectrum_top = min(spectrum_top, self.spectrum_component.box.y)

        upper_height = max(120, spectrum_top - 40)
        transcript_y = max(20, int(upper_height * 0.35))
        response_y = max(transcript_y + self.big_font.get_linesize() * 2, int(upper_height * 0.6))
        response_y = min(response_y, spectrum_top - self.font.get_linesize() - 10)

        # Middle transcript
        txt_surface = self.big_font.render(self.last_partial or self.last_final, True, (240, 240, 240))
        self.screen.blit(txt_surface, (20, transcript_y))
        # Bottom AI response
        active_tts = self.last_tts
        if self.boot_message:
            elapsed = time.monotonic() - self.boot_message_started
            if elapsed <= self.boot_message_duration and not self.last_tts:
                active_tts = self.boot_message
            else:
                self.boot_message = ""
        tts_surface = self.font.render(active_tts, True, (180, 220, 180))
        self.screen.blit(tts_surface, (20, response_y))
        pygame.display.flip()

def main():
    event_queue = queue.Queue(maxsize=256)
    use_ws = FFT_WS_ENABLED and bool(FFT_WS_URL)
    topics = {
        "partial": PARTIAL_TOPIC,
        "final": FINAL_TOPIC,
        "tts": TTS_TOPIC,
        "audio": AUDIO_TOPIC,
    }
    bridge = MqttBridge(
        event_queue,
        host=host,
        port=port,
        topics=topics,
        username=username,
        password=password,
        subscribe_audio=not use_ws,
    )
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
                    if ui.spectrum_component is not None:
                        ui.spectrum_component.update(fft_vals)
            ui.render()
            ui.clock.tick(FPS)
    finally:
        pygame.quit()
        bridge.stop()
        if fft_client:
            fft_client.stop()


if __name__ == "__main__":
    main()
