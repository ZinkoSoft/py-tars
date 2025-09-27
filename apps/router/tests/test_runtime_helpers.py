from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import uuid4

import pytest

from tars.contracts.envelope import Envelope  # type: ignore[import]
from tars.domain.ports import Publisher  # type: ignore[import]
from tars.runtime.publisher import publish_event  # type: ignore[import]
from tars.adapters.mqtt_asyncio import MessageDeduplicator  # type: ignore[import]


class DummyPublisher(Publisher):
    def __init__(self) -> None:
        self.calls: list[tuple[str, bytes, int, bool]] = []

    async def publish(self, topic: str, payload: bytes, qos: int = 0, retain: bool = False) -> None:
        self.calls.append((topic, payload, qos, retain))


@pytest.mark.asyncio
async def test_publish_event_wraps_envelope() -> None:
    publisher = DummyPublisher()
    logger = logging.getLogger("router-tests")
    event_type = "llm.request"
    payload = {"text": "Ping"}

    message_id = await publish_event(publisher, logger, event_type, payload, source="unit-test")

    assert message_id
    assert len(publisher.calls) == 1
    topic, raw_payload, qos, retain = publisher.calls[0]
    assert topic == "llm/request"
    assert qos == 1
    assert retain is False

    envelope = Envelope.model_validate_json(raw_payload)
    assert envelope.id == message_id
    assert envelope.type == event_type
    assert envelope.source == "unit-test"
    assert envelope.data == payload


@pytest.mark.asyncio
async def test_publish_event_respects_correlation_id() -> None:
    publisher = DummyPublisher()
    logger = logging.getLogger("router-tests")
    event_type = "llm.request"
    payload = {"text": "Reuse this id"}
    correlation_id = uuid4().hex

    message_id = await publish_event(
        publisher,
        logger,
        event_type,
        payload,
        correlate=correlation_id,
        source="unit-test",
        retain=True,
    )

    assert message_id == correlation_id
    assert len(publisher.calls) == 1
    topic, raw_payload, qos, retain = publisher.calls[0]
    assert topic == "llm/request"
    assert qos == 1
    assert retain is True

    envelope = Envelope.model_validate_json(raw_payload)
    assert envelope.id == correlation_id
    assert envelope.type == event_type
    assert envelope.data == payload


def _make_payload(
    message_id: str | None = None,
    *,
    event_type: str = "tests.dedupe",
    payload: dict[str, Any] | None = None,
) -> bytes:
    envelope = Envelope.new(
        event_type=event_type,
        data=payload or {"value": uuid4().hex},
        correlate=message_id,
    )
    return envelope.model_dump_json().encode()


def test_message_deduplicator_detects_duplicates() -> None:
    dedupe = MessageDeduplicator(ttl=60.0, max_entries=32)
    payload = _make_payload("env-1")

    assert dedupe.is_duplicate(payload) is False
    assert dedupe.is_duplicate(payload) is True
    assert dedupe.is_duplicate(_make_payload("env-2")) is False


def test_message_deduplicator_enforces_capacity() -> None:
    dedupe = MessageDeduplicator(ttl=60.0, max_entries=2)
    payload1 = _make_payload("env-1")
    payload2 = _make_payload("env-2")
    payload3 = _make_payload("env-3")

    assert dedupe.is_duplicate(payload1) is False
    assert dedupe.is_duplicate(payload2) is False
    assert dedupe.is_duplicate(payload3) is False

    assert dedupe.is_duplicate(payload1) is False


@pytest.mark.asyncio
async def test_message_deduplicator_respects_ttl() -> None:
    dedupe = MessageDeduplicator(ttl=0.05, max_entries=32)
    payload = _make_payload("env-ttl")

    assert dedupe.is_duplicate(payload) is False
    assert dedupe.is_duplicate(payload) is True

    await asyncio.sleep(0.06)

    assert dedupe.is_duplicate(payload) is False


def test_message_deduplicator_ignores_malformed_payloads() -> None:
    dedupe = MessageDeduplicator(ttl=60.0, max_entries=32)

    assert dedupe.is_duplicate(b"not-json") is False
    assert dedupe.is_duplicate(b"{}") is False