"""Configuration loader for the pygame UI.

Prefers TOML via Python 3.11+ tomllib, supports env overrides. Behavior unchanged.
"""
import os
import copy
from typing import Any, Dict

# Python 3.11 has tomllib in stdlib
try:
    import tomllib  # type: ignore
except Exception:  # pragma: no cover
    tomllib = None  # Fallback handled below


DEFAULT_CONFIG: Dict[str, Any] = {
    "mqtt": {
        "url": "mqtt://tars:pass@127.0.0.1:1883",
    },
    "ui": {
        "width": 800,
        "height": 480,
        "fps": 30,
        "num_bars": 64,
        "font": "Arial",
    },
    "topics": {
        "audio": "stt/audio_fft",
        "partial": "stt/partial",
        "final": "stt/final",
        "tts": "tts/status",
    },
}


def _deep_merge(dst: Dict[str, Any], src: Dict[str, Any]) -> Dict[str, Any]:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = v
    return dst


def _load_toml(path: str) -> Dict[str, Any]:
    if not path or not os.path.exists(path):
        return {}
    if tomllib is None:
        raise RuntimeError("tomllib not available; running on Python < 3.11? Please upgrade or provide env-based config.")
    with open(path, "rb") as f:
        return tomllib.load(f) or {}


def load_config() -> Dict[str, Any]:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    # Search order: UI_CONFIG env -> /config/ui.toml -> local ui.toml next to this file
    candidates = [
        os.getenv("UI_CONFIG"),
        "/config/ui.toml",
        os.path.join(os.path.dirname(__file__), "ui.toml"),
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
        ("topics", "audio"): os.getenv("UI_AUDIO_TOPIC"),
        ("topics", "partial"): os.getenv("UI_PARTIAL_TOPIC"),
        ("topics", "final"): os.getenv("UI_FINAL_TOPIC"),
        ("topics", "tts"): os.getenv("UI_TTS_TOPIC"),
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
        cfg.setdefault(section, {})[key] = val

    return cfg
