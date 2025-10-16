from __future__ import annotations

import os

from tars.contracts.v1 import (  # type: ignore[import]
    TOPIC_CHARACTER_GET,
    TOPIC_CHARACTER_RESULT,
    TOPIC_CHARACTER_UPDATE,
    TOPIC_MEMORY_QUERY,
    TOPIC_MEMORY_RESULTS,
    TOPIC_STT_FINAL,
    TOPIC_SYSTEM_CHARACTER_CURRENT,
    TOPIC_TTS_SAY,
)

MQTT_URL = os.getenv("MQTT_URL", "mqtt://tars:pass@127.0.0.1:1883")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Storage
MEMORY_DIR = os.getenv("MEMORY_DIR", "/data")
MEMORY_FILE = os.getenv("MEMORY_FILE", "memory.pickle.gz")

# Retrieval strategy
RAG_STRATEGY = os.getenv("RAG_STRATEGY", "hybrid")  # naive | hybrid
TOP_K = int(os.getenv("MEMORY_TOP_K", "5"))
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# Character config
CHARACTER_NAME = os.getenv("CHARACTER_NAME", "TARS")
CHARACTER_DIR = os.getenv("CHARACTER_DIR", "/config/characters")
CHARACTER_STORE_FILE = os.getenv("CHARACTER_STORE_FILE", "character.json")

# Topics - use constants from tars-core, allow override via env
TOPIC_STT_FINAL = os.getenv("TOPIC_STT_FINAL", TOPIC_STT_FINAL)
TOPIC_TTS_SAY = os.getenv("TOPIC_TTS_SAY", TOPIC_TTS_SAY)
TOPIC_QUERY = os.getenv("TOPIC_MEMORY_QUERY", TOPIC_MEMORY_QUERY)
TOPIC_RESULTS = os.getenv("TOPIC_MEMORY_RESULTS", TOPIC_MEMORY_RESULTS)
TOPIC_HEALTH = os.getenv("TOPIC_MEMORY_HEALTH", "system/health/memory")

# Character topics
TOPIC_CHAR_GET = os.getenv("TOPIC_CHARACTER_GET", TOPIC_CHARACTER_GET)
TOPIC_CHAR_RESULT = os.getenv("TOPIC_CHARACTER_RESULT", TOPIC_CHARACTER_RESULT)
TOPIC_CHAR_CURRENT = os.getenv("TOPIC_CHARACTER_CURRENT", TOPIC_SYSTEM_CHARACTER_CURRENT)
TOPIC_CHAR_UPDATE = os.getenv("TOPIC_CHARACTER_UPDATE", TOPIC_CHARACTER_UPDATE)
