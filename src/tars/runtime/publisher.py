from __future__ import annotations

from typing import Any

from tars.contracts.envelope import Envelope
from tars.contracts.registry import resolve_topic
from tars.domain.ports import Publisher

from .logging import Logger


async def publish_event(
    publisher: Publisher,
    logger: Logger,
    event_type: str,
    data: Any,
    *,
    correlate: str | None = None,
    qos: int = 1,
    retain: bool = False,
    source: str | None = None,
) -> str:
    """Publish an event using the shared contracts envelope.

    Args:
        publisher: Low-level MQTT publisher implementation.
        logger: Structured logger for diagnostics.
        event_type: Event type identifier (matches registry key).
        data: Payload model (Pydantic) or serializable mapping.
        correlate: Optional correlation/message id to reuse.
        qos: QoS level (defaults to 1 for at-least-once semantics).
        retain: Whether the MQTT broker should retain the message.
        source: Optional override for the envelope source field.

    Returns:
        The message id used for the published envelope.
    """

    envelope = Envelope.new(event_type=event_type, data=data, correlate=correlate, source=source or "router")
    topic = resolve_topic(event_type)
    logger.debug(
        "event.publish",
        extra={"event_type": event_type, "topic": topic, "qos": qos, "retain": retain, "message_id": envelope.id},
    )
    await publisher.publish(topic, envelope.model_dump_json().encode(), qos=qos, retain=retain)
    return envelope.id
