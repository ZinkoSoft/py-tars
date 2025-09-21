import os
import math
import time
import pygame
import numpy as np
import threading
import queue
import orjson
import paho.mqtt.client as mqtt

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
PARTIAL_TOPIC = CFG["topics"]["partial"]
FINAL_TOPIC = CFG["topics"]["final"]
TTS_TOPIC = CFG["topics"]["tts"]

u = urlparse(MQTT_URL)
host = u.hostname or "127.0.0.1"
port = u.port or 1883
username = u.username
password = u.password

class MqttBridge:
    def __init__(self):
        self.client = mqtt.Client(client_id="tars-ui")
        if username and password:
            self.client.username_pw_set(username, password)
        self.q = queue.Queue(maxsize=128)
        self.client.on_message = self._on_message

    def _on_message(self, client, userdata, msg):
        try:
            payload = orjson.loads(msg.payload)
        except Exception:
            payload = {}
        self.q.put((msg.topic, payload))

    def start(self):
        self.client.connect(host, port, 60)
        self.client.subscribe([(PARTIAL_TOPIC, 0), (FINAL_TOPIC, 0), (TTS_TOPIC, 0), (AUDIO_TOPIC, 0)])
        threading.Thread(target=self.client.loop_forever, daemon=True).start()

    def poll(self):
        try:
            return self.q.get_nowait()
        except queue.Empty:
            return None, None

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
    bridge = MqttBridge()
    bridge.start()
    ui = UI()

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
            elif topic == AUDIO_TOPIC:
                fft_vals = payload.get("fft") or []
                ui.update_spectrum_from_fft(fft_vals)
        ui.render()
        ui.clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()
