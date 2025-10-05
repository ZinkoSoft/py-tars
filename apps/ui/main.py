import os
# NEW (add near the top)
import ctypes
import numpy as np
os.environ.setdefault("PYOPENGL_PLATFORM", "egl")  # belt + suspenders
"""Pygame-based UI for TARS: displays spectrum, partials/finals, and TTS text."""
import logging
import queue
import time
from pathlib import Path
from typing import Any

import pygame
from pygame.locals import DOUBLEBUF, OPENGL
from pydantic import ValidationError
from OpenGL.GL import (
    glClear, glClearColor, glEnable, glBlendFunc, glViewport, 
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, GL_BLEND,
    GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_FLOAT, 
    GL_TEXTURE_MIN_FILTER, GL_TEXTURE_MAG_FILTER
)

from OpenGL.GL import (
    GL_VERTEX_SHADER, GL_FRAGMENT_SHADER, GL_COMPILE_STATUS, GL_LINK_STATUS,
    glCreateShader, glShaderSource, glCompileShader, glGetShaderiv, glGetShaderInfoLog,
    glCreateProgram, glAttachShader, glLinkProgram, glGetProgramiv, glGetProgramInfoLog,
    glDeleteShader, glUseProgram, glGetUniformLocation, glUniform2f,
    glEnableVertexAttribArray, glVertexAttribPointer, glDrawArrays,
    glGenBuffers, glBindBuffer, glBufferData, GL_ARRAY_BUFFER, GL_STATIC_DRAW,
    glActiveTexture, glBindTexture, glTexParameteri, glTexImage2D, glTexSubImage2D,
    glGenTextures, glPixelStorei, GL_UNPACK_ALIGNMENT, GL_TEXTURE0, GL_TEXTURE_2D,
    GL_LINEAR, GL_RGBA, GL_UNSIGNED_BYTE, GL_TRIANGLE_STRIP
)


from urllib.parse import urlparse
from config import load_config
from fft_ws_client import FFTWebsocketClient
from mqtt_bridge import MqttBridge
from module.layout import Box, get_layout_dimensions, load_layout_config
from module.spectrum import SpectrumBars, SineWaveVisualizer
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

VERT_SRC = r"""
#version 300 es
precision mediump float;
layout(location=0) in vec2 a_pos_px;   // pixel coords
layout(location=1) in vec2 a_uv;
uniform vec2 u_resolution;              // (width,height)
out vec2 v_uv;
void main() {
    vec2 zeroToOne = a_pos_px / u_resolution;
    vec2 clip = zeroToOne * 2.0 - 1.0;
    clip.y = -clip.y;                   // top-left origin like pygame
    v_uv = a_uv;
    gl_Position = vec4(clip, 0.0, 1.0);
}
"""

FRAG_SRC = r"""
#version 300 es
precision mediump float;

in vec2 v_uv;
uniform sampler2D u_tex;
uniform float u_rotation_deg;  // e.g. 0, 90, 180, 270
uniform bool  u_flip_v;        // flip texture vertically if source is top-left

out vec4 outColor;

vec2 rotate_uv(vec2 uv, float deg) {
    float r = radians(deg);
    float s = sin(r), c = cos(r);
    // rotate around center of the texture
    vec2 centered = uv - 0.5;
    vec2 rotated  = mat2(c, -s, s, c) * centered;
    return rotated + 0.5;
}

void main() {
    vec2 uv = v_uv;
    if (u_flip_v) {
        uv.y = 1.0 - uv.y;  // convert top-left source to OpenGL bottom-left
    }
    uv = rotate_uv(uv, u_rotation_deg);
    outColor = texture(u_tex, uv);
}
"""

def _compile_shader(src, kind):
    sh = glCreateShader(kind)
    glShaderSource(sh, src)
    glCompileShader(sh)
    ok = glGetShaderiv(sh, GL_COMPILE_STATUS)
    if not ok:
        raise RuntimeError(glGetShaderInfoLog(sh).decode())
    return sh

def _make_program():
    vs = _compile_shader(VERT_SRC, GL_VERTEX_SHADER)
    fs = _compile_shader(FRAG_SRC, GL_FRAGMENT_SHADER)
    prog = glCreateProgram()
    glAttachShader(prog, vs); glAttachShader(prog, fs); glLinkProgram(prog)
    ok = glGetProgramiv(prog, GL_LINK_STATUS)
    if not ok:
        raise RuntimeError(glGetProgramInfoLog(prog).decode())
    glDeleteShader(vs); glDeleteShader(fs)
    return prog

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
        flags = DOUBLEBUF | OPENGL
        if FULLSCREEN:
            flags |= pygame.FULLSCREEN

        # Request a GLES3 context (works with Panfrost on RK3588)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_ES)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 0)

        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        if FULLSCREEN:
            pygame.mouse.set_visible(False)
        self.width, self.height = WIDTH, HEIGHT

        # ---- initialize GL state + pipeline
        self._init_opengl()

        # Offscreen pygame surface you already render text/shapes onto
        self.offscreen_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)

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
        self.stt_fade_duration = 3.0
        self.llm_fade_duration = 4.0
        self.components: dict[str, Any] = {}
        self.spectrum_component: SpectrumBars | SineWaveVisualizer | None = None

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
            elif key == "sinewave":
                component = SineWaveVisualizer(
                    box=box,
                    rotation=rotation,
                    depth=22,
                    decay=0.9,
                    perspective_shift=(-2, 5),
                    padding=20,  # Positive padding = margin from edges (zoomed out)
                    target_fps=30.0,  # Increased from 10 to 30 FPS
                )
                self.components[key] = component
                self.spectrum_component = component  # Treat as spectrum component for FFT updates
            elif key == "tars_idle":
                component = TarsIdle(box)
                self.components[key] = component
            else:
                logger.info("Unhandled layout component '%s'", box.name)

    def _init_opengl(self):
        """Initialize GLES3 state, shader program, quad VBO, and a texture we update each frame."""
        glViewport(0, 0, self.width, self.height)
        glClearColor(0.02, 0.02, 0.03, 1.0)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Compile/link the tiny shader pipeline
        self.prog = _make_program()
        glUseProgram(self.prog)
        self.u_rotation = glGetUniformLocation(self.prog, "u_rotation_deg")
        self.u_flip_v   = glGetUniformLocation(self.prog, "u_flip_v")
        self.u_resolution = glGetUniformLocation(self.prog, "u_resolution")
        self.u_tex = glGetUniformLocation(self.prog, "u_tex")  # (sampler; defaults to unit 0)

        # Fullscreen quad as a TRIANGLE_STRIP: (x, y, u, v) in pixels + UVs
        quad = np.array([
            0,            0,             0, 0,
            self.width,   0,             1, 0,
            0,            self.height,    0, 1,
            self.width,   self.height,    1, 1,
        ], dtype=np.float32)

        self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, quad.nbytes, quad, GL_STATIC_DRAW)

        stride = 4 * 4  # 4 floats per vertex
        # a_pos_px at location 0
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 2, GL_FLOAT, False, stride, ctypes.c_void_p(0))
        # a_uv at location 1
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 2, GL_FLOAT, False, stride, ctypes.c_void_p(8))

        # Create a texture we’ll update with the Pygame surface each frame
        self.tex = glGenTextures(1)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        # allocate storage (no data yet)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.width, self.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)

    def _blit_surface_via_gles(self, surface: pygame.Surface):
        # NOTE: third arg is now False — do NOT pre-flip in CPU
        pixels = pygame.image.tostring(surface, "RGBA", False)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.tex)
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.width, self.height,
                    GL_RGBA, GL_UNSIGNED_BYTE, pixels)
        glUseProgram(self.prog)
        glUniform2f(self.u_resolution, float(self.width), float(self.height))
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)

    def render(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # Draw into the pygame surface (unchanged app logic)
        self.offscreen_surface.fill((5, 5, 8))
        now = time.monotonic()
        fonts = {"small": self.font, "large": self.big_font}

        if "tars_idle" in self.components:
            try:
                self.components["tars_idle"].render(self.offscreen_surface, now, fonts)
            except Exception as exc:
                logger.error("Component tars_idle render failed: %s", exc)

        for key, component in self.components.items():
            if key == "tars_idle":
                continue
            try:
                # Handle SineWaveVisualizer which renders directly like SpectrumBars
                if isinstance(component, SineWaveVisualizer):
                    component.render(self.offscreen_surface, now, fonts)
                else:
                    component.render(self.offscreen_surface, now, fonts)
            except Exception as exc:
                logger.error("Component %s render failed: %s", component.__class__.__name__, exc)

        spectrum_top = self.height
        if self.spectrum_component is not None and hasattr(self.spectrum_component, 'box'):
            spectrum_top = min(spectrum_top, self.spectrum_component.box.y)

        margin = 20
        top_y = 20

        # STT Final text (fade)
        if self.last_final:
            stt_elapsed = now - self.last_final_time
            if stt_elapsed < self.stt_fade_duration:
                fade_progress = stt_elapsed / self.stt_fade_duration
                alpha = int(255 * (1.0 - fade_progress))
                alpha = max(0, min(255, alpha))
                stt_text = f"You: {self.last_final}"
                stt_surface = self.small_font.render(stt_text, True, (200, 200, 255))
                stt_surface.set_alpha(alpha)
                stt_x = self.width - stt_surface.get_width() - margin
                self.offscreen_surface.blit(stt_surface, (stt_x, top_y))
            else:
                self.last_final = ""

        # LLM response (fade after TTS ends)
        if self.last_llm_response:
            alpha = 255
            if not self.tts_speaking and self.tts_ended_time > 0:
                llm_elapsed = now - self.tts_ended_time
                if llm_elapsed < self.llm_fade_duration:
                    fade_progress = llm_elapsed / self.llm_fade_duration
                    alpha = int(255 * (1.0 - fade_progress))
                    alpha = max(0, min(255, alpha))
                else:
                    self.last_llm_response = ""
                    alpha = 0
            if alpha > 0:
                self._render_wrapped_text(
                    self.last_llm_response,
                    margin,
                    top_y + 30,
                    self.width - margin * 2,
                    (180, 255, 180),
                    alpha
                )

        if self.boot_message:
            elapsed = time.monotonic() - self.boot_message_started
            if elapsed <= self.boot_message_duration and not self.last_llm_response:
                boot_surface = self.font.render(self.boot_message, True, (180, 220, 180))
                self.offscreen_surface.blit(boot_surface, (margin, top_y + 30))
            else:
                self.boot_message = ""

        # Upload the pygame surface and draw the textured quad
        self._blit_surface_via_gles(self.offscreen_surface)
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
        
        # Render each line to offscreen surface
        line_height = self.font.get_linesize()
        for i, line in enumerate(lines):
            line_surface = self.font.render(line, True, color)
            line_surface.set_alpha(alpha)
            self.offscreen_surface.blit(line_surface, (x, y + i * line_height))

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
                            if isinstance(ui.spectrum_component, SineWaveVisualizer):
                                # SineWaveVisualizer updates state like SpectrumBars
                                spectrum_array = np.array(fft_vals, dtype=np.float32)
                                ui.spectrum_component.update(spectrum_array)
                            else:
                                # SpectrumBars updates internal state
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
