"""Layout helpers for positioning UI components."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List

logger = logging.getLogger("tars.ui.layout")


@dataclass(slots=True)
class Box:
    """Represents an allocated rectangular region for a UI component."""

    name: str
    x: int
    y: int
    width: int
    height: int
    rotation: int
    original_width: int
    original_height: int

    def to_rect(self) -> tuple[int, int, int, int]:
        """Return a tuple representation suitable for pygame.Rect."""
        return (self.x, self.y, self.width, self.height)


def load_layout_config(base_dir: Path | str, config_file: str) -> Dict[str, Any]:
    """Load the JSON layout configuration relative to *base_dir*.

    Args:
        base_dir: Base directory to resolve the layout file against.
        config_file: File name or path to the layout JSON file.

    Returns:
        Parsed layout dictionary. Returns an empty layout on failure.
    """

    base_path = Path(base_dir)
    candidate_paths: Iterable[Path] = (
        base_path / config_file,
        Path(config_file),
    )
    for path in candidate_paths:
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to load layout config from %s: %s", path, exc)
            break
    logger.warning("Layout config %s not found; using default layout", config_file)
    return {"landscape": [], "portrait": []}


def get_layout_dimensions(
    layout_config: Dict[str, Any],
    screen_width: int,
    screen_height: int,
    rotation: int,
) -> List[Box]:
    """Calculate physical box dimensions for layout entries.

    The layout file stores normalized coordinates (0-1) for each orientation.
    This helper converts them into pixel-based `Box` objects, handling rotation
    semantics so layouts can be defined once and reused across orientations.

    Args:
        layout_config: Parsed layout JSON.
        screen_width: Physical screen width in pixels.
        screen_height: Physical screen height in pixels.
        rotation: Display rotation in degrees (0, 90, 180, 270).

    Returns:
        A list of `Box` instances ready for rendering.
    """

    rotation = rotation % 360
    is_landscape = rotation in (0, 180)
    preferred_keys: List[str]
    if is_landscape:
        preferred_keys = ["landscape", "horizontal", "default"]
    else:
        preferred_keys = ["portrait", "vertical", "default"]

    layout_entries: List[Dict[str, Any]] = []
    for key in preferred_keys:
        entries = layout_config.get(key)
        if isinstance(entries, list) and entries:
            layout_entries = entries
            break
    if not layout_entries:
        # Fallback to first available list in config
        for value in layout_config.values():
            if isinstance(value, list):
                layout_entries = value
                break
    if not layout_entries:
        return []

    if rotation in (0, 180):
        logical_width, logical_height = screen_width, screen_height
    else:
        logical_width, logical_height = screen_height, screen_width

    boxes: List[Box] = []
    for entry in layout_entries:
        try:
            name = str(entry["name"])
            x_frac = float(entry.get("x", 0.0))
            y_frac = float(entry.get("y", 0.0))
            width_frac = float(entry.get("width", 0.0))
            height_frac = float(entry.get("height", 0.0))
        except (KeyError, ValueError, TypeError):
            logger.warning("Invalid layout entry skipped: %s", entry)
            continue

        logical_x = x_frac * logical_width
        logical_y = y_frac * logical_height
        logical_w = width_frac * logical_width
        logical_h = height_frac * logical_height

        if rotation == 0:
            physical_x = int(logical_x)
            physical_y = int(logical_y)
            physical_w = int(logical_w)
            physical_h = int(logical_h)
        elif rotation == 180:
            physical_x = int(screen_width - logical_x - logical_w)
            physical_y = int(screen_height - logical_y - logical_h)
            physical_w = int(logical_w)
            physical_h = int(logical_h)
        elif rotation == 90:
            physical_x = int(logical_y)
            physical_y = int(logical_width - logical_x - logical_w)
            physical_w = int(logical_h)
            physical_h = int(logical_w)
        else:  # rotation == 270
            physical_x = int(logical_height - logical_y - logical_h)
            physical_y = int(logical_x)
            physical_w = int(logical_h)
            physical_h = int(logical_w)

        boxes.append(
            Box(
                name=name,
                x=max(0, physical_x),
                y=max(0, physical_y),
                width=max(0, physical_w),
                height=max(0, physical_h),
                rotation=rotation,
                original_width=int(logical_w),
                original_height=int(logical_h),
            )
        )

    return boxes
