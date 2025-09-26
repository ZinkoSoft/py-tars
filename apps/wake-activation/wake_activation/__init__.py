"""Wake activation service package."""

from .config import WakeActivationConfig
from .detector import DetectorUnavailableError, WakeDetector, create_wake_detector
from .models import WakeEvent, MicCommand, TtsControl
from .service import WakeActivationService

__all__ = [
    "WakeActivationConfig",
    "WakeEvent",
    "MicCommand",
    "TtsControl",
    "WakeDetector",
    "create_wake_detector",
    "DetectorUnavailableError",
    "WakeActivationService",
]
