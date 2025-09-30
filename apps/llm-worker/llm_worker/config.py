from __future__ import annotations

import os


def env_str(key: str, default: str | None = None) -> str:
    v = os.getenv(key, default if default is not None else "")
    return v


def env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except Exception:
        return default


def env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except Exception:
        return default


def env_bool(key: str, default: bool = False) -> bool:
    v = os.getenv(key)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "on")


MQTT_URL = env_str("MQTT_URL", "mqtt://127.0.0.1:1883")
LOG_LEVEL = env_str("LLM_LOG_LEVEL", "INFO")

# Provider selection
LLM_PROVIDER = env_str("LLM_PROVIDER", "openai")
LLM_MODEL = env_str("LLM_MODEL", "gpt-4o-mini")
LLM_MAX_TOKENS = env_int("LLM_MAX_TOKENS", 256)
LLM_TEMPERATURE = env_float("LLM_TEMPERATURE", 0.7)
LLM_TOP_P = env_float("LLM_TOP_P", 1.0)
LLM_TOP_K = env_int("LLM_TOP_K", 0)
LLM_CTX_WINDOW = env_int("LLM_CTX_WINDOW", 8192)
LLM_DEVICE = env_str("LLM_DEVICE", "cpu")

# Provider creds/urls
OPENAI_API_KEY = env_str("OPENAI_API_KEY", "")
OPENAI_BASE_URL = env_str("OPENAI_BASE_URL", "")
LLM_SERVER_URL = env_str("LLM_SERVER_URL", "")
GEMINI_API_KEY = env_str("GEMINI_API_KEY", "")
GEMINI_BASE_URL = env_str("GEMINI_BASE_URL", "")
DASHSCOPE_API_KEY = env_str("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL = env_str("DASHSCOPE_BASE_URL", "")

# RAG
RAG_ENABLED = env_bool("RAG_ENABLED", False)
RAG_TOP_K = env_int("RAG_TOP_K", 5)
RAG_PROMPT_TEMPLATE = env_str(
    "RAG_PROMPT_TEMPLATE",
    "You are TARS. Use the following context to answer the user.\nContext:\n{context}\n\nUser: {user}\nAssistant:",
)

# Topics
TOPIC_LLM_REQUEST = env_str("TOPIC_LLM_REQUEST", "llm/request")
TOPIC_LLM_RESPONSE = env_str("TOPIC_LLM_RESPONSE", "llm/response")
TOPIC_LLM_STREAM = env_str("TOPIC_LLM_STREAM", "llm/stream")
TOPIC_LLM_CANCEL = env_str("TOPIC_LLM_CANCEL", "llm/cancel")
TOPIC_HEALTH = env_str("TOPIC_HEALTH", "system/health/llm")
TOPIC_MEMORY_QUERY = env_str("TOPIC_MEMORY_QUERY", "memory/query")
TOPIC_MEMORY_RESULTS = env_str("TOPIC_MEMORY_RESULTS", "memory/results")

# Character (persona) topic
TOPIC_CHARACTER_CURRENT = env_str("TOPIC_CHARACTER_CURRENT", "system/character/current")
TOPIC_CHARACTER_GET = env_str("TOPIC_CHARACTER_GET", "character/get")
TOPIC_CHARACTER_RESULT = env_str("TOPIC_CHARACTER_RESULT", "character/result")

# Tool calling
TOOL_CALLING_ENABLED = env_bool("TOOL_CALLING_ENABLED", False)
TOPIC_TOOLS_REGISTRY = env_str("TOPIC_TOOLS_REGISTRY", "llm/tools/registry")
TOPIC_TOOL_CALL_REQUEST = env_str("TOPIC_TOOL_CALL_REQUEST", "llm/tool.call.request")
TOPIC_TOOL_CALL_RESULT = env_str("TOPIC_TOOL_CALL_RESULT", "llm/tool.call.result")

# Optional: forward streaming chunks to TTS as sentences (now disabled; router bridges LLM->TTS)
LLM_TTS_STREAM = env_bool("LLM_TTS_STREAM", False)
TOPIC_TTS_SAY = env_str("TOPIC_TTS_SAY", "tts/say")
STREAM_MIN_CHARS = env_int("STREAM_MIN_CHARS", 60)
STREAM_MAX_CHARS = env_int("STREAM_MAX_CHARS", 240)
STREAM_BOUNDARY_CHARS = env_str("STREAM_BOUNDARY_CHARS", ".!?;:")
