from __future__ import annotations

from typing import Final

_EVENT_TO_TOPIC: dict[str, str] = {
    "stt.final": "stt/final",
    "stt.partial": "stt/partial",
    "tts.say": "tts/say",
    "tts.status": "tts/status",
    "llm.request": "llm/request",
    "llm.response": "llm/response",
    "llm.stream": "llm/stream",
    "llm.cancel": "llm/cancel",
    "wake.event": "wake/event",
    "wake.mic": "wake/mic",
    "system.health.tts": "system/health/tts",
    "system.health.stt": "system/health/stt",
    "system.health.router": "system/health/router",
    "memory.query": "memory/query",
    "memory.results": "memory/results",
    "system.health.memory": "system/health/memory",
    "character.get": "character/get",
    "character.result": "character/result",
    "system.character.current": "system/character/current",
}

_TOPIC_TO_EVENT: dict[str, str] = {topic: event for event, topic in _EVENT_TO_TOPIC.items()}


def resolve_topic(event_type: str) -> str:
    try:
        return _EVENT_TO_TOPIC[event_type]
    except KeyError as exc:
        raise KeyError(f"Unknown event type: {event_type}") from exc


def resolve_event(topic: str) -> str:
    try:
        return _TOPIC_TO_EVENT[topic]
    except KeyError as exc:
        raise KeyError(f"Unknown topic: {topic}") from exc


def register(event_type: str, topic: str) -> None:
    """Register or override the topic mapping for an event type."""

    _EVENT_TO_TOPIC[event_type] = topic
    _TOPIC_TO_EVENT[topic] = event_type
