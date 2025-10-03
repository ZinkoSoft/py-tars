"""Pygame-based UI for TARS: displays spectrum, partials/finals, and TTS text."""
import logging
import queue
import time
from pathlib import Path
from typing import Any

import pygame
from pydantic import ValidationError

from urllib.parse import urlparse
from config import load_config
from fft_ws_client import FFTWebsocketClient
from mqtt_bridge import MqttBridge
from module.layout import Box, get_layout_dimensions, load_layout_config
from module.spectrum import SpectrumBars
from module.tars_idle import TarsIdle

# Import typed contracts
from tars.contracts.envelope import Envelope
from tars.contracts.v1.stt import FinalTranscript, PartialTranscript
from tars.contracts.v1.llm import LLMResponse
from tars.contracts.v1.tts import TtsStatus

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
LLM_RESPONSE_TOPIC = CFG["topics"]["llm_response"]

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

print("========== TARS UI STARTING ==========")
print(f"MQTT Topics: final={FINAL_TOPIC}, llm={LLM_RESPONSE_TOPIC}, tts={TTS_TOPIC}")
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger("tars.ui")
print("========== LOGGING CONFIGURED ==========")

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
        self.small_font = pygame.font.SysFont(FONT_NAME, 18)
        self.last_partial = ""
        self.last_final = ""
        self.last_final_time = 0.0
        self.last_llm_response = ""
        self.last_llm_response_time = 0.0
        self.last_tts = ""
        self.tts_speaking = False
        self.tts_ended_time = 0.0
        self.boot_message = "System Online"
        self.boot_message_started = time.monotonic()
        self.boot_message_duration = 3.0
        # Fade durations
        self.stt_fade_duration = 3.0  # STT fades after 3 seconds
        self.llm_fade_duration = 4.0  # LLM fades after TTS ends + 4 seconds
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

        # Calculate positions
        margin = 20
        top_y = 20
        
        # STT Final text (top right) - fades out after 3 seconds
        if self.last_final:
            stt_elapsed = now - self.last_final_time
            if stt_elapsed < self.stt_fade_duration:
                # Calculate fade alpha (255 -> 0 over fade duration)
                fade_progress = stt_elapsed / self.stt_fade_duration
                alpha = int(255 * (1.0 - fade_progress))
                alpha = max(0, min(255, alpha))
                
                # Render STT text (right-aligned)
                stt_text = f"You: {self.last_final}"
                stt_surface = self.small_font.render(stt_text, True, (200, 200, 255))
                stt_surface.set_alpha(alpha)
                stt_x = self.width - stt_surface.get_width() - margin
                self.screen.blit(stt_surface, (stt_x, top_y))
            else:
                # Clear after fade duration
                self.last_final = ""
        
        # LLM Response (below STT, left-aligned) - fades out after TTS ends
        if self.last_llm_response:
            # Calculate alpha based on TTS state
            alpha = 255  # Default: full opacity
            
            # If TTS has ended, start fading
            if not self.tts_speaking and self.tts_ended_time > 0:
                llm_elapsed = now - self.tts_ended_time
                if llm_elapsed < self.llm_fade_duration:
                    # Calculate fade alpha
                    fade_progress = llm_elapsed / self.llm_fade_duration
                    alpha = int(255 * (1.0 - fade_progress))
                    alpha = max(0, min(255, alpha))
                else:
                    # Clear after fade duration
                    self.last_llm_response = ""
                    alpha = 0
            
            # Render LLM response if alpha > 0
            if alpha > 0:
                self._render_wrapped_text(
                    self.last_llm_response,
                    margin,
                    top_y + 30,
                    self.width - margin * 2,
                    (180, 255, 180),
                    alpha
                )
        
        # Boot message (backwards compatible)
        if self.boot_message:
            elapsed = time.monotonic() - self.boot_message_started
            if elapsed <= self.boot_message_duration and not self.last_llm_response:
                boot_surface = self.font.render(self.boot_message, True, (180, 220, 180))
                self.screen.blit(boot_surface, (margin, top_y + 30))
            else:
                self.boot_message = ""
        
        pygame.display.flip()

    def _render_wrapped_text(self, text: str, x: int, y: int, max_width: int, color: tuple, alpha: int):
        """Render text with word wrapping and alpha transparency."""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            current_line.append(word)
            test_line = " ".join(current_line)
            test_surface = self.font.render(test_line, True, color)
            
            if test_surface.get_width() > max_width:
                if len(current_line) > 1:
                    # Line too long, render previous line
                    current_line.pop()
                    lines.append(" ".join(current_line))
                    current_line = [word]
                else:
                    # Single word too long, render it anyway
                    lines.append(test_line)
                    current_line = []
        
        if current_line:
            lines.append(" ".join(current_line))
        
        # Render each line
        line_height = self.font.get_linesize()
        for i, line in enumerate(lines):
            line_surface = self.font.render(line, True, color)
            line_surface.set_alpha(alpha)
            self.screen.blit(line_surface, (x, y + i * line_height))

def main():
    event_queue = queue.Queue(maxsize=256)
    use_ws = FFT_WS_ENABLED and bool(FFT_WS_URL)
    topics = {
        "partial": PARTIAL_TOPIC,
        "final": FINAL_TOPIC,
        "tts": TTS_TOPIC,
        "llm_response": LLM_RESPONSE_TOPIC,
        "audio": AUDIO_TOPIC,
    }
    logger.info(f"UI Topics config: {topics}")
    logger.info(f"MQTT connection: host={host}, port={port}, user={username}")
    bridge = MqttBridge(
        event_queue,
        host=host,
        port=port,
        topics=topics,
        username=username,
        password=password,
        subscribe_audio=not use_ws,
    )
    logger.info("Starting MQTT bridge...")
    bridge.start()
    logger.info("MQTT bridge started")
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
                # Only log non-FFT messages to avoid spam
                if topic != AUDIO_EVENT:
                    logger.info(f"RX topic={topic}")
                
                try:
                    if topic == PARTIAL_TOPIC:
                        # Parse envelope and extract PartialTranscript
                        envelope = Envelope.model_validate(payload)
                        partial = PartialTranscript.model_validate(envelope.data)
                        ui.last_partial = partial.text
                        logger.info(f"STT Partial: {ui.last_partial}")
                    
                    elif topic == FINAL_TOPIC:
                        # Parse envelope and extract FinalTranscript
                        envelope = Envelope.model_validate(payload)
                        final = FinalTranscript.model_validate(envelope.data)
                        ui.last_final = final.text
                        ui.last_final_time = time.monotonic()
                        ui.last_partial = ""
                        logger.info(f"STT Final: {ui.last_final}")
                    
                    elif topic == LLM_RESPONSE_TOPIC:
                        # Parse envelope and extract LLMResponse
                        envelope = Envelope.model_validate(payload)
                        llm_response = LLMResponse.model_validate(envelope.data)
                        if llm_response.reply:
                            ui.last_llm_response = llm_response.reply
                            ui.last_llm_response_time = time.monotonic()
                            ui.tts_ended_time = 0.0  # Reset fade timer
                            logger.info(f"Set LLM response to: {ui.last_llm_response}")
                        elif llm_response.error:
                            logger.error(f"LLM error: {llm_response.error}")
                    
                    elif topic == TTS_TOPIC:
                        # Parse envelope and extract TtsStatus
                        envelope = Envelope.model_validate(payload)
                        tts_status = TtsStatus.model_validate(envelope.data)
                        logger.info(f"TTS event: {tts_status.event}, speaking={ui.tts_speaking}")
                        if tts_status.event == "speaking_start":
                            ui.last_tts = tts_status.text
                            ui.tts_speaking = True
                        elif tts_status.event == "speaking_end":
                            ui.tts_speaking = False
                            ui.tts_ended_time = time.monotonic()
                    
                    elif topic == AUDIO_EVENT:
                        # FFT data is not wrapped in envelope
                        fft_vals = payload.get("fft") or []
                        if ui.spectrum_component is not None:
                            ui.spectrum_component.update(fft_vals)
                
                except ValidationError as e:
                    logger.error(f"Invalid payload for topic {topic}: {e}")
                except Exception as e:
                    logger.error(f"Error processing topic {topic}: {e}")
            ui.render()
            ui.clock.tick(FPS)
    finally:
        pygame.quit()
        bridge.stop()
        if fft_client:
            fft_client.stop()


if __name__ == "__main__":
    main()
