from __future__ import annotations

import os

from tars.contracts.v1 import (  # type: ignore[import]
    TOPIC_CHARACTER_GET,
    TOPIC_CHARACTER_RESULT,
    TOPIC_LLM_CANCEL,
    TOPIC_LLM_REQUEST,
    TOPIC_LLM_RESPONSE,
    TOPIC_LLM_STREAM,
    TOPIC_LLM_TOOLS_REGISTRY,
    TOPIC_LLM_TOOL_CALL_REQUEST,
    TOPIC_LLM_TOOL_CALL_RESULT,
    TOPIC_MEMORY_QUERY,
    TOPIC_MEMORY_RESULTS,
    TOPIC_SYSTEM_CHARACTER_CURRENT,
    TOPIC_TTS_SAY,
)


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


def env_csv(key: str, default: str = "") -> list[str]:
    raw = os.getenv(key, default)
    return [item.strip() for item in raw.split(",") if item and item.strip()]


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
OPENAI_RESPONSES_MODELS = env_csv(
    "OPENAI_RESPONSES_MODELS",
    "gpt-4.1*,gpt-4o-mini*,gpt-5*,gpt-5-mini,gpt-5-nano",
)
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
# Enhanced RAG features
RAG_MAX_TOKENS = env_int("RAG_MAX_TOKENS", 2000)  # Token budget for RAG results
RAG_INCLUDE_CONTEXT = env_bool("RAG_INCLUDE_CONTEXT", True)  # Include surrounding conversation
RAG_CONTEXT_WINDOW = env_int("RAG_CONTEXT_WINDOW", 1)  # Number of prev/next entries
RAG_STRATEGY = env_str("RAG_STRATEGY", "hybrid")  # "hybrid", "recent", "similarity"
RAG_DYNAMIC_PROMPTS = env_bool("RAG_DYNAMIC_PROMPTS", True)  # Enable token-aware prompt building
RAG_CACHE_TTL = env_int("RAG_CACHE_TTL", 300)  # Cache TTL in seconds (default 5 minutes)

# Topics - use constants from tars-core (re-export for backward compatibility)
# These can still be overridden via environment if needed, but default to contract constants
TOPIC_LLM_REQUEST = TOPIC_LLM_REQUEST
TOPIC_LLM_RESPONSE = TOPIC_LLM_RESPONSE
TOPIC_LLM_STREAM = TOPIC_LLM_STREAM
TOPIC_LLM_CANCEL = TOPIC_LLM_CANCEL
TOPIC_HEALTH = env_str("TOPIC_HEALTH", "system/health/llm")
TOPIC_MEMORY_QUERY = TOPIC_MEMORY_QUERY
TOPIC_MEMORY_RESULTS = TOPIC_MEMORY_RESULTS

# Character (persona) topic
TOPIC_CHARACTER_CURRENT = TOPIC_SYSTEM_CHARACTER_CURRENT
TOPIC_CHARACTER_GET = TOPIC_CHARACTER_GET
TOPIC_CHARACTER_RESULT = TOPIC_CHARACTER_RESULT

# Tool calling
TOOL_CALLING_ENABLED = env_bool("TOOL_CALLING_ENABLED", False)
TOPIC_TOOLS_REGISTRY = TOPIC_LLM_TOOLS_REGISTRY
TOPIC_TOOL_CALL_REQUEST = TOPIC_LLM_TOOL_CALL_REQUEST
TOPIC_TOOL_CALL_RESULT = TOPIC_LLM_TOOL_CALL_RESULT

# Optional: forward streaming chunks to TTS as sentences (now disabled; router bridges LLM->TTS)
LLM_TTS_STREAM = env_bool("LLM_TTS_STREAM", False)
TOPIC_TTS_SAY = TOPIC_TTS_SAY
STREAM_MIN_CHARS = env_int("STREAM_MIN_CHARS", 60)
STREAM_MAX_CHARS = env_int("STREAM_MAX_CHARS", 240)
STREAM_BOUNDARY_CHARS = env_str("STREAM_BOUNDARY_CHARS", ".!?;:")
