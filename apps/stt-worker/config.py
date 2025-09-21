import os
from typing import Set

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MQTT_URL = os.getenv("MQTT_URL", "mqtt://tars:pass@127.0.0.1:1883")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
MODEL_PATH = "/app/models"
STT_BACKEND = os.getenv("STT_BACKEND", "whisper")  # whisper | ws
WS_URL = os.getenv("WS_URL", "ws://127.0.0.1:9000/stt")
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))
CHUNK_DURATION_MS = int(os.getenv("CHUNK_DURATION_MS", "30"))
VAD_AGGRESSIVENESS = int(os.getenv("VAD_AGGRESSIVENESS", "2"))
SILENCE_THRESHOLD_MS = int(os.getenv("SILENCE_THRESHOLD_MS", "1000"))
POST_PUBLISH_COOLDOWN_MS = int(os.getenv("POST_PUBLISH_COOLDOWN_MS", "400"))
UNMUTE_GUARD_MS = int(os.getenv("UNMUTE_GUARD_MS", "300"))
ECHO_SUPPRESS_MATCH = int(os.getenv("ECHO_SUPPRESS_MATCH", "1"))
TTS_BASE_MUTE_MS = int(os.getenv("TTS_BASE_MUTE_MS", "1200"))
TTS_PER_CHAR_MS = float(os.getenv("TTS_PER_CHAR_MS", "45"))
TTS_MAX_MUTE_MS = int(os.getenv("TTS_MAX_MUTE_MS", "6000"))
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

# Streaming partial transcription options
STREAMING_PARTIALS = int(os.getenv("STREAMING_PARTIALS", "0"))  # 1 to enable live partial transcripts
PARTIAL_INTERVAL_MS = int(os.getenv("PARTIAL_INTERVAL_MS", "600"))  # how often to attempt partial decode during active speech
PARTIAL_MIN_DURATION_MS = int(os.getenv("PARTIAL_MIN_DURATION_MS", "500"))  # don't partial until buffer has this much audio
PARTIAL_MIN_CHARS = int(os.getenv("PARTIAL_MIN_CHARS", "4"))  # minimum characters to publish a partial
PARTIAL_MIN_NEW_CHARS = int(os.getenv("PARTIAL_MIN_NEW_CHARS", "2"))  # require at least this many new chars vs last partial
PARTIAL_ALPHA_RATIO_MIN = float(os.getenv("PARTIAL_ALPHA_RATIO_MIN", "0.5"))  # basic quality gate for partials

COMMON_WORDS: Set[str] = set(
    "the a an and of to you i it is that in we for on with this my your yes no thanks thank hello hi ok okay please what who where when why how can do are was were have has had just really sure right time date day weather play stop start open close tell give set make turn off on up down volume name today now current temperature".split()
)
