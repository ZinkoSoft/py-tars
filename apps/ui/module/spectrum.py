"""Spectrum visualization component."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterable, Mapping

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

    def render(self, surface: pygame.Surface, now: float, fonts: Mapping[str, pygame.font.Font]) -> None:
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
