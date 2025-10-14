from __future__ import annotations

import os
import re


def getenv(name: str, default: str) -> str:
    val = os.getenv(name)
    return default if val is None or val == "" else val


def getenv_list(name: str, default: str) -> tuple[str, ...]:
    raw = getenv(name, default)
    if not raw:
        return ()
    parts = re.split(r"[|,]", raw)
    return tuple(p.strip() for p in parts if p.strip())


LOG_LEVEL = getenv("LOG_LEVEL", "INFO")
MQTT_URL = getenv("MQTT_URL", "mqtt://tars:pass@127.0.0.1:1883")
PIPER_VOICE = getenv("PIPER_VOICE", "/voices/TARS.onnx")
TTS_STREAMING = int(getenv("TTS_STREAMING", "0"))  # default to reliable file playback
TTS_PIPELINE = int(
    getenv("TTS_PIPELINE", "1")
)  # play sentence-by-sentence to reduce time-to-first-audio

# Optional: play audio with simpleaudio instead of paplay/aplay subprocesses (0/1)
TTS_SIMPLEAUDIO = int(getenv("TTS_SIMPLEAUDIO", "0"))

# Optional: number of concurrent synthesis workers when pipeline mode is on (>=1)
# When >1 and not streaming, sentences will be synthesized in parallel and played in order
TTS_CONCURRENCY = int(getenv("TTS_CONCURRENCY", "1"))

# Aggregate consecutive tts/say messages with the same utt_id to reduce pauses between sentences
TTS_AGGREGATE = int(getenv("TTS_AGGREGATE", "1"))
TTS_AGGREGATE_DEBOUNCE_MS = int(getenv("TTS_AGGREGATE_DEBOUNCE_MS", "150"))
# When aggregating, synthesize as a single WAV (pipeline disabled) to avoid playback gaps
TTS_AGGREGATE_SINGLE_WAV = int(getenv("TTS_AGGREGATE_SINGLE_WAV", "1"))

# Cache wake acknowledgements and common phrases as WAVs for fast replay
TTS_WAKE_CACHE_ENABLE = int(getenv("TTS_WAKE_CACHE_ENABLE", "1"))
TTS_WAKE_CACHE_DIR = getenv("TTS_WAKE_CACHE_DIR", "data/tts-cache")
TTS_WAKE_CACHE_MAX = int(getenv("TTS_WAKE_CACHE_MAX", "16"))

# Collect all texts to preload into cache
_wake_ack_texts = getenv_list(
    "TTS_WAKE_ACK_TEXTS",
    getenv("ROUTER_WAKE_ACK_CHOICES", ""),
)
_online_text = getenv("ONLINE_ANNOUNCE_TEXT", "System online.")
# Combine wake acks and online text for preloading
TTS_WAKE_ACK_TEXTS = _wake_ack_texts + (_online_text,) if _online_text else _wake_ack_texts

# External TTS provider selection and settings
# Options: "piper" (default), "elevenlabs"
TTS_PROVIDER = getenv("TTS_PROVIDER", "piper").lower()

# ElevenLabs configuration
ELEVEN_API_BASE = getenv("ELEVEN_API_BASE", "https://api.elevenlabs.io/v1")
ELEVEN_API_KEY = getenv("ELEVEN_API_KEY", "")
ELEVEN_VOICE_ID = getenv("ELEVEN_VOICE_ID", "")  # required when TTS_PROVIDER=elevenlabs
ELEVEN_MODEL_ID = getenv("ELEVEN_MODEL_ID", "eleven_multilingual_v2")
ELEVEN_OPTIMIZE_STREAMING = int(
    getenv("ELEVEN_OPTIMIZE_STREAMING", "0")
)  # 0/1/2/3 per ElevenLabs docs
