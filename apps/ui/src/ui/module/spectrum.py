"""Spectrum visualization component."""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

import numpy as np
import pygame

from .layout import Box


@dataclass(slots=True)
class SpectrumBars:
    """Render and manage a smoothed FFT bar visualization."""

    box: Box
    num_bars: int
    fade_threshold: float = 1.0
    fade_duration: float = 1.5
    background_color: tuple[int, int, int] = (20, 20, 35)
    min_intensity: float = 0.25
    values: np.ndarray = field(init=False)
    last_update: float | None = field(default=None, init=False)
    alpha: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self.values = np.zeros(self.num_bars, dtype=np.float32)

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(self.box.x, self.box.y, self.box.width, self.box.height)

    def update(self, fft_values: Iterable[float]) -> None:
        arr = np.asarray(list(fft_values), dtype=np.float32)
        if arr.size == 0:
            self.values *= 0.9
            return
        resampled = np.interp(
            np.linspace(0, len(arr) - 1, self.num_bars),
            np.arange(len(arr)),
            arr,
        )
        self.values = 0.8 * self.values + 0.2 * resampled
        self.last_update = time.monotonic()
        self.alpha = 1.0

    def _current_intensity(self, now: float) -> float:
        if self.last_update is None:
            return 0.0
        inactivity = max(0.0, now - self.last_update)
        if inactivity <= self.fade_threshold:
            return 1.0
        fade = 1.0 - (inactivity - self.fade_threshold) / self.fade_duration
        return max(0.0, fade)

    def render(
        self, surface: pygame.Surface, now: float, fonts: Mapping[str, pygame.font.Font]
    ) -> None:
        intensity = self._current_intensity(now)
        self.alpha = intensity
        if intensity <= 0.0:
            # Hidden when no activity
            return

        pygame.draw.rect(surface, self.background_color, self.rect, border_radius=6)

        bar_width = self.rect.width / max(1, self.num_bars)
        for index, value in enumerate(self.values):
            height = int(value * self.rect.height * intensity)
            if height <= 0:
                continue
            x = int(self.rect.x + index * bar_width)
            y = self.rect.y + (self.rect.height - height)
            grad = index / max(1, self.num_bars - 1)
            scale = max(self.min_intensity, intensity)
            color = (
                int(255 * grad * scale),
                int(180 * scale),
                int((255 - 255 * grad) * scale),
            )
            width_px = max(1, int(round(bar_width)))
            pygame.draw.rect(
                surface,
                color,
                pygame.Rect(x, y, width_px, height),
                border_radius=2,
            )


class SineWaveVisualizer:
    """Render a 3D perspective sine wave visualization based on FFT spectrum data."""

    def __init__(
        self,
        box: Box,
        rotation: int = 0,
        depth: int = 22,
        decay: float = 0.9,
        perspective_shift: tuple[int, int] = (-2, 5),
        padding: int = 10,
        target_fps: float = 30.0,
        fade_threshold: float = 1.0,
        fade_duration: float = 1.5,
    ):
        """
        Initialize the sine wave visualizer.

        Args:
            box: Layout box defining position and dimensions
            rotation: Display rotation (90, 270 will swap width/height)
            depth: Number of historical wave frames to keep (default: 22)
            decay: Decay factor for fade effect on historical waves (default: 0.9)
            perspective_shift: (x, y) offset per depth layer for 3D effect (default: (-2, 5))
            padding: Horizontal padding from edges (default: 10)
            target_fps: Target frame rate for updates (default: 30.0)
            fade_threshold: Seconds of inactivity before fade starts (default: 1.0)
            fade_duration: Duration of fade out in seconds (default: 1.5)
        """
        self.box = box
        if rotation in (90, 270):
            self.width, self.height = box.height, box.width
        else:
            self.width = box.width
            self.height = box.height
        self.max_amplitude = 70
        self.wave_history: deque[list[tuple[int, int]]] = deque(maxlen=depth)
        self.decay = decay
        self.perspective_shift = perspective_shift
        self.padding = padding
        self.target_fps = target_fps
        self.fade_threshold = fade_threshold
        self.fade_duration = fade_duration
        self.last_update: float | None = None
        self.alpha: float = 1.0

    def _current_intensity(self, now: float) -> float:
        """
        Calculate current fade intensity based on time since last update.

        Args:
            now: Current monotonic time

        Returns:
            Intensity value between 0.0 (fully faded) and 1.0 (fully visible)
        """
        if self.last_update is None:
            return 0.0
        inactivity = max(0.0, now - self.last_update)
        if inactivity <= self.fade_threshold:
            return 1.0
        fade = 1.0 - (inactivity - self.fade_threshold) / self.fade_duration
        return max(0.0, fade)

    def update(self, spectrum: np.ndarray) -> None:
        """
        Update the sine wave visualization state with new spectrum data.

        Args:
            spectrum: FFT spectrum data (numpy array of floats)
        """
        now = time.monotonic()

        # Check if we have meaningful spectrum data (check max amplitude, not just any())
        # Use a threshold to filter out background noise
        max_val = np.max(spectrum) if spectrum.size > 0 else 0.0
        has_data = max_val > 0.1  # Increased threshold to better distinguish audio from noise

        # Only update last_update timestamp when we have actual audio data
        if has_data:
            self.last_update = now
            self.alpha = 1.0

        if has_data:
            spectrum = np.clip(spectrum, 0, np.max(spectrum))
            spectrum = spectrum / np.max(spectrum)
            sinewave_points: list[tuple[int, int]] = []

            for x in range(self.padding, self.width - self.padding):
                width_adj = max(2, self.width - 2 * self.padding)
                freq_bin = int((x - self.padding) * len(spectrum) / width_adj)
                amplitude = spectrum[freq_bin] * self.max_amplitude
                t = (x - self.padding) / width_adj

                y = amplitude * math.sin(2 * math.pi * t * 3) + (self.height // 2)
                sinewave_points.append((x, int(y)))

            self.wave_history.appendleft(sinewave_points.copy())

    def render(
        self, surface: pygame.Surface, now: float, fonts: Mapping[str, pygame.font.Font]
    ) -> None:
        """
        Render the sine wave visualization to the surface.

        Args:
            surface: Surface to render to
            now: Current monotonic time
            fonts: Font mapping (unused)
        """
        # Calculate current fade intensity
        intensity = self._current_intensity(now)

        # Skip rendering if fully faded out
        if intensity <= 0.0:
            return

        # Render all historical waves with perspective, fade, and intensity
        for i, wave in enumerate(reversed(self.wave_history)):
            base_alpha = int(255 * (1 - self.decay**i))
            # Apply fade-out intensity to alpha
            alpha = int(base_alpha * intensity)
            color = (255, 255, 255, alpha)
            x_shift = self.perspective_shift[0] * i
            y_shift = self.perspective_shift[1] * i
            for j in range(1, len(wave)):
                start_pos = (wave[j - 1][0] + x_shift, wave[j - 1][1] + y_shift)
                end_pos = (wave[j][0] + x_shift, wave[j][1] + y_shift)
                pygame.draw.line(surface, color, start_pos, end_pos, 2)
