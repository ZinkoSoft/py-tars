from __future__ import annotations

import os

MQTT_URL = os.getenv("MQTT_URL", "mqtt://tars:pass@127.0.0.1:1883")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Storage
MEMORY_DIR = os.getenv("MEMORY_DIR", "/data")
MEMORY_FILE = os.getenv("MEMORY_FILE", "memory.pickle.gz")

# Retrieval strategy
RAG_STRATEGY = os.getenv("RAG_STRATEGY", "hybrid")  # naive | hybrid
TOP_K = int(os.getenv("MEMORY_TOP_K", "5"))
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

# Topics
TOPIC_STT_FINAL = os.getenv("TOPIC_STT_FINAL", "stt/final")
TOPIC_TTS_SAY = os.getenv("TOPIC_TTS_SAY", "tts/say")
TOPIC_QUERY = os.getenv("TOPIC_MEMORY_QUERY", "memory/query")
TOPIC_RESULTS = os.getenv("TOPIC_MEMORY_RESULTS", "memory/results")
TOPIC_HEALTH = os.getenv("TOPIC_MEMORY_HEALTH", "system/health/memory")
