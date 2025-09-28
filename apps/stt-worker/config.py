import os
from typing import Set

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MQTT_URL = os.getenv("MQTT_URL", "mqtt://tars:pass@127.0.0.1:1883")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
MODEL_PATH = "/app/models"
STT_BACKEND = os.getenv("STT_BACKEND", "whisper")  # whisper | ws | openai
"""Compatibility shim re-exporting packaged configuration constants."""

from stt_worker.config import *  # type: ignore[F403]
from stt_worker.config import __all__ as _STT_CONFIG_ALL

__all__ = list(_STT_CONFIG_ALL)
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))
