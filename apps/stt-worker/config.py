import os
from typing import Set

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MQTT_URL = os.getenv("MQTT_URL", "mqtt://tars:pass@127.0.0.1:1883")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
MODEL_PATH = "/app/models"
STT_BACKEND = os.getenv("STT_BACKEND", "whisper")  # whisper | ws | openai
WS_URL = os.getenv("WS_URL", "ws://127.0.0.1:9000/stt")
AUDIO_FANOUT_PATH = os.getenv("AUDIO_FANOUT_PATH", "/tmp/tars/audio-fanout.sock")
AUDIO_FANOUT_RATE = int(os.getenv("AUDIO_FANOUT_RATE", "16000"))
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))
CHUNK_DURATION_MS = int(os.getenv("CHUNK_DURATION_MS", "30"))
VAD_AGGRESSIVENESS = int(os.getenv("VAD_AGGRESSIVENESS", "2"))
SILENCE_THRESHOLD_MS = int(os.getenv("SILENCE_THRESHOLD_MS", "1000"))
POST_PUBLISH_COOLDOWN_MS = int(os.getenv("POST_PUBLISH_COOLDOWN_MS", "400"))
UNMUTE_GUARD_MS = int(os.getenv("UNMUTE_GUARD_MS", "1000"))
ECHO_SUPPRESS_MATCH = int(os.getenv("ECHO_SUPPRESS_MATCH", "1"))
TTS_BASE_MUTE_MS = int(os.getenv("TTS_BASE_MUTE_MS", "1200"))
TTS_PER_CHAR_MS = float(os.getenv("TTS_PER_CHAR_MS", "45"))
TTS_MAX_MUTE_MS = int(os.getenv("TTS_MAX_MUTE_MS", "12000"))
WAKE_EVENT_FALLBACK_DELAY_MS = int(os.getenv("WAKE_EVENT_FALLBACK_DELAY_MS", "250"))
WAKE_EVENT_FALLBACK_TTL_MS = int(os.getenv("WAKE_EVENT_FALLBACK_TTL_MS", "3500"))
NOISE_MIN_DURATION_MS = int(os.getenv("NOISE_MIN_DURATION_MS", "400"))
NOISE_MIN_RMS = int(os.getenv("NOISE_MIN_RMS", "180"))
# Adaptive noise floor parameters
NOISE_FLOOR_INIT = int(os.getenv("NOISE_FLOOR_INIT", str(NOISE_MIN_RMS)))
NOISE_FLOOR_ALPHA = float(os.getenv("NOISE_FLOOR_ALPHA", "0.05"))  # EMA smoothing factor
NOISE_GATE_OFFSET = float(os.getenv("NOISE_GATE_OFFSET", "1.5"))  # gate = floor * offset
NOISE_MIN_ALPHA_RATIO = float(os.getenv("NOISE_MIN_ALPHA_RATIO", "0.55"))
NOISE_MIN_LENGTH = int(os.getenv("NOISE_MIN_LENGTH", "3"))
NOISE_MAX_PUNCT_RATIO = float(os.getenv("NOISE_MAX_PUNCT_RATIO", "0.35"))
COUGH_ACTIVE_MIN_RATIO = float(os.getenv("COUGH_ACTIVE_MIN_RATIO", "0.25"))
COUGH_MIN_DURATION_MS = int(os.getenv("COUGH_MIN_DURATION_MS", "600"))
COUGH_SUSPICIOUS_PHRASES = os.getenv("COUGH_SUSPICIOUS_PHRASES", "thank you,hello,okay,hi").split(",")
COUGH_MIN_SYLLABLES = int(os.getenv("COUGH_MIN_SYLLABLES", "2"))
NO_SPEECH_MAX = float(os.getenv("NO_SPEECH_MAX", "0.60"))
AVG_LOGPROB_MIN = float(os.getenv("AVG_LOGPROB_MIN", "-1.20"))
DICT_MATCH_MIN_RATIO = float(os.getenv("DICT_MATCH_MIN_RATIO", "0.40"))
REPEAT_COOLDOWN_SEC = float(os.getenv("REPEAT_COOLDOWN_SEC", "8"))

# Optional quality upgrades (opt-in)
# Use syllapy for better syllable counting in suppression (0/1)
SUPPRESS_USE_SYLLAPY = int(os.getenv("SUPPRESS_USE_SYLLAPY", "0"))
# Use rapidfuzz for fuzzy echo matching in suppression (0/1)
SUPPRESS_USE_RAPIDFUZZ = int(os.getenv("SUPPRESS_USE_RAPIDFUZZ", "0"))
# Minimum similarity ratio (0..1) for echo fuzzy match when enabled
ECHO_FUZZ_MIN_RATIO = float(os.getenv("ECHO_FUZZ_MIN_RATIO", "0.85"))

# Streaming partial transcription options
STREAMING_PARTIALS = int(os.getenv("STREAMING_PARTIALS", "1"))  # 1 to enable live partial transcripts
PARTIAL_INTERVAL_MS = int(os.getenv("PARTIAL_INTERVAL_MS", "600"))  # how often to attempt partial decode during active speech
PARTIAL_MIN_DURATION_MS = int(os.getenv("PARTIAL_MIN_DURATION_MS", "500"))  # don't partial until buffer has this much audio
PARTIAL_MIN_CHARS = int(os.getenv("PARTIAL_MIN_CHARS", "4"))  # minimum characters to publish a partial
PARTIAL_MIN_NEW_CHARS = int(os.getenv("PARTIAL_MIN_NEW_CHARS", "2"))  # require at least this many new chars vs last partial
PARTIAL_ALPHA_RATIO_MIN = float(os.getenv("PARTIAL_ALPHA_RATIO_MIN", "0.5"))  # basic quality gate for partials

# Server-side partials tail window (used by WS server); defined here for centralized env management
TAIL_WINDOW_SEC = float(os.getenv("TAIL_WINDOW_SEC", "6.0"))

# UI spectrum/FFT publishing
FFT_PUBLISH = int(os.getenv("FFT_PUBLISH", "1"))
FFT_TOPIC = os.getenv("FFT_TOPIC", "stt/audio_fft")
FFT_RATE_HZ = float(os.getenv("FFT_RATE_HZ", "12"))
FFT_BINS = int(os.getenv("FFT_BINS", "64"))
FFT_LOG_SCALE = int(os.getenv("FFT_LOG_SCALE", "1"))  # 1 to use log magnitude scaling

COMMON_WORDS: Set[str] = set(
    "the a an and of to you i it is that in we for on with this my your yes no thanks thank hello hi ok okay please what who where when why how can do are was were have has had just really sure right time date day weather play stop start open close tell give set make turn off on up down volume name today now current temperature".split()
)
# Optional: extend common words from env to improve domain acceptance in dict_ratio heuristic
_COMMON_WORDS_EXTRA = os.getenv("COMMON_WORDS_EXTRA", "")
if _COMMON_WORDS_EXTRA:
    try:
        extra_tokens = [w.strip().lower() for w in _COMMON_WORDS_EXTRA.split(",")]
        COMMON_WORDS.update(w for w in extra_tokens if w)
    except Exception:
        pass

# OpenAI STT offload (optional)
# When STT_BACKEND=="openai", raw PCM chunks are assembled into WAV and sent to OpenAI-compatible API
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # do not log
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
# Default to Whisper API; allow gpt-4o(-mini)-transcribe or other compatible models via env
OPENAI_STT_MODEL = os.getenv("OPENAI_STT_MODEL", "whisper-1")
OPENAI_TIMEOUT_S = float(os.getenv("OPENAI_TIMEOUT_S", "30"))

# Optional FFmpeg preprocessing (disabled by default)
# Enable to trim silence, reduce noise, and normalize audio before STT.
# Filters default explanation:
# - silenceremove: trim leading/trailing silence (at least 2s, threshold -35dB)
# - arnndn (if available at runtime) or afftdn: gentle denoise
# - loudnorm: EBU R128 loudness normalization to -18 LUFS (single pass)
PREPROCESS_ENABLE = int(os.getenv("PREPROCESS_ENABLE", "0"))
PREPROCESS_MIN_MS = int(os.getenv("PREPROCESS_MIN_MS", "600"))  # skip very short clips
PREPROCESS_TIMEOUT_S = float(os.getenv("PREPROCESS_TIMEOUT_S", "6"))
# Note: arnndn requires rnnoise model not present by default on slim images; fallback to afftdn
_DEFAULT_FILTERS = (
    "silenceremove=start_periods=1:start_silence=2:start_threshold=-35dB:"
    "detection=peak,"
    "afftdn=nf=-25,"
    "loudnorm=I=-18:TP=-2:LRA=11"
)
PREPROCESS_FILTERS = os.getenv("PREPROCESS_FILTERS", _DEFAULT_FILTERS)
