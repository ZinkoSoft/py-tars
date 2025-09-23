from __future__ import annotations

import os


def getenv(name: str, default: str) -> str:
    val = os.getenv(name)
    return default if val is None or val == "" else val


LOG_LEVEL = getenv("LOG_LEVEL", "INFO")
MQTT_URL = getenv("MQTT_URL", "mqtt://tars:pass@127.0.0.1:1883")
PIPER_VOICE = getenv("PIPER_VOICE", "/voices/TARS.onnx")
TTS_STREAMING = int(getenv("TTS_STREAMING", "0"))  # default to reliable file playback
TTS_PIPELINE = int(getenv("TTS_PIPELINE", "1"))  # play sentence-by-sentence to reduce time-to-first-audio

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
