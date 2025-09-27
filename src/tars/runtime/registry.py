from __future__ import annotations

from typing import Mapping

from tars.contracts.registry import register


def register_topics(mapping: Mapping[str, str]) -> None:
    """Register event type to topic mappings with the contracts registry.

    Args:
        mapping: Dictionary mapping event type strings to MQTT topics.
    """

    for event_type, topic in mapping.items():
        register(event_type, topic)


__all__ = ["register_topics"]
