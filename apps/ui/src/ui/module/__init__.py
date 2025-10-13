"""UI component modules for the TARS pygame client."""

from .layout import Box, get_layout_dimensions, load_layout_config
from .spectrum import SpectrumBars

__all__ = [
    "Box",
    "SpectrumBars",
    "get_layout_dimensions",
    "load_layout_config",
]
