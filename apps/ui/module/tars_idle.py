"""TARS-inspired idle screen component: matrix rain with sci-fi elements."""
from __future__ import annotations

import random
import time
from typing import Any

import pygame


class TarsIdle:
    """Renders a futuristic idle screen inspired by TARS from Interstellar.

    Features falling matrix-like code rain in green, with occasional geometric shapes.
    """

    def __init__(self, box) -> None:
        self.box = box
        self.font = pygame.font.SysFont("monospace", 16, bold=True)
        self.char_width, self.char_height = self.font.size("0")
        self.rows = max(1, box.height // self.char_height)
        self.positions_rtl: list[int] = [box.width for _ in range(self.rows)]  # Right to left
        self.positions_ltr: list[int] = [0 for _ in range(self.rows)]  # Left to right
        self.chars = "01ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

    def render(self, screen: pygame.Surface, now: float, fonts: dict[str, Any]) -> None:
        # Update positions (right to left)
        for i in range(len(self.positions_rtl)):
            if random.random() > 0.975:  # Chance to reset
                self.positions_rtl[i] = self.box.width
            self.positions_rtl[i] -= 1  # Move left
            if self.positions_rtl[i] < -self.char_width:
                self.positions_rtl[i] = self.box.width

        # Update positions (left to right)
        for i in range(len(self.positions_ltr)):
            if random.random() > 0.975:  # Chance to reset
                self.positions_ltr[i] = 0
            self.positions_ltr[i] += 1  # Move right
            if self.positions_ltr[i] > self.box.width:
                self.positions_ltr[i] = 0

        # Draw chars (right to left)
        for i, pos in enumerate(self.positions_rtl):
            if pos >= 0:
                char = random.choice(self.chars)
                color = (0, random.randint(150, 255), 0)  # Green variations
                text_surf = self.font.render(char, True, color)
                x = self.box.x + pos
                y = self.box.y + i * self.char_height
                if x >= self.box.x and x < self.box.x + self.box.width:
                    screen.blit(text_surf, (x, y))

        # Draw chars (left to right)
        for i, pos in enumerate(self.positions_ltr):
            if pos <= self.box.width:
                char = random.choice(self.chars)
                color = (0, random.randint(150, 255), 0)  # Green variations
                text_surf = self.font.render(char, True, color)
                x = self.box.x + pos
                y = self.box.y + i * self.char_height
                if x >= self.box.x and x < self.box.x + self.box.width:
                    screen.blit(text_surf, (x, y))

