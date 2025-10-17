"""Configuration loader for the pygame UI.

Prefers TOML via Python 3.11+ tomllib, supports env overrides. Behavior unchanged.
"""

import copy
import os
from typing import Any

from tars.contracts.v1 import (  # type: ignore[import]
    TOPIC_LLM_RESPONSE,
    TOPIC_STT_AUDIO_FFT,
    TOPIC_STT_FINAL,
    TOPIC_STT_PARTIAL,
    TOPIC_TTS_STATUS,
)

# Python 3.11 has tomllib in stdlib
try:
    import tomllib  # type: ignore
except Exception:  # pragma: no cover
    tomllib = None  # Fallback handled below


DEFAULT_CONFIG: dict[str, Any] = {
    "mqtt": {
        "url": "mqtt://tars:pass@127.0.0.1:1883",
    },
    "ui": {
        "width": 480,
        "height": 800,
        "fps": 30,
        "num_bars": 64,
        "font": "Arial",
        "fullscreen": False,
    },
    "layout": {
        "file": "layout.json",
        "rotation": 0,
    },
    "topics": {
        "audio": TOPIC_STT_AUDIO_FFT,
        "partial": TOPIC_STT_PARTIAL,
        "final": TOPIC_STT_FINAL,
        "tts": TOPIC_TTS_STATUS,
        "llm_response": TOPIC_LLM_RESPONSE,
    },
    "fft_ws": {
        "enabled": True,
        "url": "ws://0.0.0.0:8765/fft",
        "retry_seconds": 5.0,
    },
}


def _deep_merge(dst: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v
    return dst


def _load_toml(path: str) -> dict[str, Any]:
    if not path or not os.path.exists(path):
        return {}
    if tomllib is None:
        raise RuntimeError(
            "tomllib not available; running on Python < 3.11? Please upgrade or provide env-based config."
        )
    with open(path, "rb") as f:
        return tomllib.load(f) or {}


def load_config() -> dict[str, Any]:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    # Search order:
    # 1. UI_CONFIG env variable
    # 2. /config/ui.toml (Docker mount)
    # 3. ./ui.toml (current working directory)
    # 4. ../../ui.toml (two levels up from src/ui/ - for development)
    candidates = [
        os.getenv("UI_CONFIG"),
        "/config/ui.toml",
        "ui.toml",  # Current working directory
        os.path.join(os.path.dirname(__file__), "..", "..", "ui.toml"),  # App root
    ]
    for p in candidates:
        try:
            data = _load_toml(p) if p else {}
        except Exception:
            data = {}
        if data:
            _deep_merge(cfg, data)

    # Optional env overrides (kept minimal)
    env_map = {
        ("mqtt", "url"): os.getenv("MQTT_URL"),
        ("ui", "width"): os.getenv("UI_WIDTH"),
        ("ui", "height"): os.getenv("UI_HEIGHT"),
        ("ui", "fps"): os.getenv("UI_FPS"),
        ("ui", "num_bars"): os.getenv("UI_NUM_BARS"),
        ("ui", "font"): os.getenv("UI_FONT"),
        ("ui", "fullscreen"): os.getenv("UI_FULLSCREEN"),
        ("layout", "file"): os.getenv("UI_LAYOUT_FILE"),
        ("layout", "rotation"): os.getenv("UI_LAYOUT_ROTATION"),
        ("topics", "audio"): os.getenv("UI_AUDIO_TOPIC"),
        ("topics", "partial"): os.getenv("UI_PARTIAL_TOPIC"),
        ("topics", "final"): os.getenv("UI_FINAL_TOPIC"),
        ("topics", "tts"): os.getenv("UI_TTS_TOPIC"),
        ("topics", "llm_response"): os.getenv("UI_LLM_RESPONSE_TOPIC"),
        ("fft_ws", "enabled"): os.getenv("UI_FFT_WS_ENABLE"),
        ("fft_ws", "url"): os.getenv("UI_FFT_WS_URL"),
        ("fft_ws", "retry_seconds"): os.getenv("UI_FFT_WS_RETRY"),
    }
    for (section, key), val in env_map.items():
        if val is None:
            continue
        # Cast some numeric envs
        if (section, key) in {("ui", "width"), ("ui", "height"), ("ui", "fps"), ("ui", "num_bars")}:
            try:
                val = int(val)
            except Exception:
                continue
        if (section, key) == ("ui", "fullscreen"):
            val = str(val).strip().lower() in {"1", "true", "yes", "on"}
        if (section, key) == ("fft_ws", "enabled"):
            val = str(val).strip().lower() in {"1", "true", "yes", "on"}
        if (section, key) == ("fft_ws", "retry_seconds"):
            try:
                val = float(val)
            except Exception:
                continue
        if (section, key) == ("layout", "rotation"):
            try:
                val = int(val)
            except Exception:
                continue
        cfg.setdefault(section, {})[key] = val

    return cfg
