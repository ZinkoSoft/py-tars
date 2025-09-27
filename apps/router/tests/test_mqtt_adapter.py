from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

import pytest

SRC_DIR = Path(__file__).resolve().parents[3] / "src"
if SRC_DIR.exists():
    src_path = str(SRC_DIR)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

from tars.adapters.mqtt_asyncio import (  # type: ignore[import]
    AsyncioMQTTSubscriber,
    MQTTSubscriberOptions,
)
from tars.contracts.envelope import Envelope  # type: ignore[import]


@dataclass
class FakeMessage:
    payload: bytes


class _AsyncIterator:
    def __init__(self, messages: Iterable[FakeMessage]) -> None:
        self._iterator = iter(messages)

    def __aiter__(self) -> "_AsyncIterator":
        return self

    async def __anext__(self) -> FakeMessage:
        try:
            return next(self._iterator)
        except StopIteration as exc:  # pragma: no cover - normal termination
            raise StopAsyncIteration from exc


class FakeManager:
    def __init__(self, messages: Iterable[FakeMessage]) -> None:
        self._messages = list(messages)

    async def __aenter__(self) -> "FakeManager":  # pragma: no cover - trivial
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - trivial
        return None

    def __aiter__(self) -> _AsyncIterator:
        return _AsyncIterator(self._messages)


class FakeClient:
    def __init__(self, messages: Iterable[FakeMessage]) -> None:
        self._messages = list(messages)
        self.subscriptions: List[tuple[str, int]] = []

    def filtered_messages(self, topic: str) -> FakeManager:
        return FakeManager(self._messages)

    async def subscribe(self, topic: str, qos: int = 0) -> None:
        self.subscriptions.append((topic, qos))


def _make_payload(message_id: str) -> bytes:
    envelope = Envelope.new(event_type="tests.event", data={"id": message_id}, correlate=message_id)
    return envelope.model_dump_json().encode()


@pytest.mark.asyncio
async def test_subscriber_dedupes_messages() -> None:
    payload = _make_payload("dup-1")
    messages = [FakeMessage(payload), FakeMessage(payload)]
    client = FakeClient(messages)
    subscriber = AsyncioMQTTSubscriber(
        client,
        options=MQTTSubscriberOptions(dedupe_ttl=60.0, dedupe_max_entries=10),
    )

    delivered: list[FakeMessage] = []
    async for msg in subscriber.messages("tests/event", qos=1):
        delivered.append(msg)

    assert client.subscriptions == [("tests/event", 1)]
    assert len(delivered) == 1
    assert delivered[0].payload == payload


@pytest.mark.asyncio
async def test_subscriber_allows_duplicates_when_dedupe_disabled() -> None:
    payload = _make_payload("dup-2")
    messages = [FakeMessage(payload), FakeMessage(payload)]
    client = FakeClient(messages)
    subscriber = AsyncioMQTTSubscriber(
        client,
        options=MQTTSubscriberOptions(dedupe_ttl=0.0, dedupe_max_entries=10),
    )

    delivered: list[FakeMessage] = []
    async for msg in subscriber.messages("tests/event", qos=1):
        delivered.append(msg)

    assert client.subscriptions == [("tests/event", 1)]
    assert len(delivered) == 2
    assert all(message.payload == payload for message in delivered)
