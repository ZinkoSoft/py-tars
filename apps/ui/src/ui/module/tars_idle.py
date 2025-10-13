"""TARS-inspired idle screen component: matrix rain with sci-fi elements."""

from __future__ import annotations

import random
from typing import Any

import pygame


class TarsIdle:
    """Renders a futuristic idle screen inspired by TARS from Interstellar.

    Characters spawn randomly at screen edges and flow towards the center,
    fading out as they approach like being sucked into a black hole.
    """

    def __init__(self, box) -> None:
        self.box = box
        self.font = pygame.font.SysFont("monospace", 16, bold=True)
        self.char_width, self.char_height = self.font.size("0")
        self.center_x = box.x + box.width // 2
        self.center_y = box.y + box.height // 2
        self.characters: list[dict[str, Any]] = []
        self.chars = "01ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        self.max_chars = 3000  # Limit number of active characters

    def render(self, screen: pygame.Surface, now: float, fonts: dict[str, Any]) -> None:
        # Spawn new characters randomly at edges
        if len(self.characters) < self.max_chars and random.random() > 0.85:
            self._spawn_character()

        # Update and draw characters
        to_remove = []
        for char_data in self.characters:
            # Move towards center
            dx = self.center_x - char_data["x"]
            dy = self.center_y - char_data["y"]
            dist = (dx**2 + dy**2) ** 0.5
            if dist > 0:
                char_data["x"] += (dx / dist) * char_data["speed"]
                char_data["y"] += (dy / dist) * char_data["speed"]

            # Fade based on distance to center
            fade_dist = max(self.box.width, self.box.height) / 4  # Start fading when close
            if dist < fade_dist:
                char_data["alpha"] = max(0, int(255 * (dist / fade_dist)))
            else:
                char_data["alpha"] = 255

            # Remove if at center or faded out
            if dist < 10 or char_data["alpha"] <= 0:
                to_remove.append(char_data)
                continue

            # Draw character
            color = (0, random.randint(150, 255), 0, char_data["alpha"])
            text_surf = self.font.render(char_data["char"], True, color[:3])
            text_surf.set_alpha(char_data["alpha"])
            screen.blit(
                text_surf,
                (char_data["x"] - self.char_width // 2, char_data["y"] - self.char_height // 2),
            )

        # Remove faded characters
        for char_data in to_remove:
            self.characters.remove(char_data)

    def _spawn_character(self) -> None:
        """Spawn a new character at a random edge position."""
        edge = random.choice(["left", "right", "top", "bottom"])
        if edge == "left":
            x = self.box.x
            y = random.randint(self.box.y, self.box.y + self.box.height - self.char_height)
        elif edge == "right":
            x = self.box.x + self.box.width - self.char_width
            y = random.randint(self.box.y, self.box.y + self.box.height - self.char_height)
        elif edge == "top":
            x = random.randint(self.box.x, self.box.x + self.box.width - self.char_width)
            y = self.box.y
        else:  # bottom
            x = random.randint(self.box.x, self.box.x + self.box.width - self.char_width)
            y = self.box.y + self.box.height - self.char_height

        self.characters.append(
            {
                "x": x,
                "y": y,
                "char": random.choice(self.chars),
                "alpha": 255,
                "speed": random.uniform(1.0, 3.0),
            }
        )
