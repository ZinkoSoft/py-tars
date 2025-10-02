"""
Movements Package - TARS-AI Movement Sequences for ESP32

This package implements TARS-AI community movement patterns for ESP32 MicroPython.

Modules:
- config.py: Servo configuration and percentage conversion
- control.py: Low-level servo control with asyncio
- sequences.py: High-level movement sequences (step, wave, laugh, etc.)
- handler.py: MQTT command handler for movement/test topic

Based on: https://github.com/pyrater/TARS-AI
"""

__version__ = "1.0.0"
__all__ = [
    "ServoConfig",
    "ServoController", 
    "MovementSequences",
    "MovementCommandHandler",
]

# Import key classes for easy access
try:
    from .config import ServoConfig
    from .control import ServoController
    from .sequences import MovementSequences
    from .handler import MovementCommandHandler
except ImportError:
    # MicroPython may not support relative imports in all cases
    pass
