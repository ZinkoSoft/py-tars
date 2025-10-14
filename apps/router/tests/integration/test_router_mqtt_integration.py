from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import suppress
from dataclasses import dataclass
from typing import AsyncIterator, Dict

import orjson
import pytest

from tars.adapters.mqtt_asyncio import AsyncioMQTTSubscriber  # type: ignore[import]
from tars.contracts.v1 import LLMResponse  # type: ignore[import]
from tars.runtime.dispatcher import Dispatcher  # type: ignore[import]
from tars.runtime.subscription import Sub  # type: ignore[import]


class _DummyLogger:
    def debug(self, *args, **kwargs):  # pragma: no cover - no-op
        return None

    def info(self, *args, **kwargs):  # pragma: no cover - no-op
        return None

    def warning(self, *args, **kwargs):  # pragma: no cover - no-op
        return None

    def error(self, *args, **kwargs):  # pragma: no cover - no-op
        return None


_SENTINEL = object()


@dataclass(slots=True)
class _FakeMessage:
    payload: bytes
    topic: str


class _TopicQueue:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[object] = asyncio.Queue()

    def get_iterator(self) -> AsyncIterator[_FakeMessage]:
        async def _gen() -> AsyncIterator[_FakeMessage]:
            while True:
                item = await self.queue.get()
                if item is _SENTINEL:
                    break
                yield item  # type: ignore[misc]

        return _gen()


class _FakeMessageManager:
    def __init__(self, topic_queue: _TopicQueue) -> None:
        self._queue = topic_queue

    async def __aenter__(self) -> AsyncIterator[_FakeMessage]:
        return self._queue.get_iterator()

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        await self._queue.queue.put(_SENTINEL)
        return False


class _FakeBroker:
    def __init__(self) -> None:
        self._topics: Dict[str, _TopicQueue] = defaultdict(_TopicQueue)

    def get_queue(self, topic: str) -> _TopicQueue:
        return self._topics[topic]

    def create_client(self) -> "_FakeClient":
        return _FakeClient(self)

    async def publish(self, topic: str, payload: bytes) -> None:
        await self.get_queue(topic).queue.put(_FakeMessage(payload=payload, topic=topic))


class _FakeClient:
    def __init__(self, broker: _FakeBroker) -> None:
        self._broker = broker

    def filtered_messages(self, topic: str) -> _FakeMessageManager:
        return _FakeMessageManager(self._broker.get_queue(topic))

    async def subscribe(self, topic: str, qos: int = 0) -> None:  # pragma: no cover - no-op
        self._broker.get_queue(topic)

    async def publish(self, topic: str, payload: bytes, qos: int = 0, retain: bool = False) -> None:
        await self._broker.publish(topic, payload)


@pytest.mark.asyncio
async def test_router_consumes_llm_response_from_fake_broker() -> None:
    broker = _FakeBroker()
    client = broker.create_client()
    subscriber = AsyncioMQTTSubscriber(client)

    received: list[LLMResponse] = []
    handled = asyncio.Event()

    async def handle_llm_response(evt: LLMResponse, ctx):
        received.append(evt)
        handled.set()

    sub = Sub("llm/response", LLMResponse, handle_llm_response, qos=1)
    dispatcher = Dispatcher(
        subscriber,
        (sub,),
        lambda envelope: {},
        logger=_DummyLogger(),
        queue_maxsize=4,
    )

    run_task = asyncio.create_task(dispatcher.run())
    try:
        await asyncio.sleep(0.05)
        envelope_payload = {
            "id": "f1a38edf910f42608ae577ed92a9d86b",
            "type": "llm.response",
            "ts": 1759161986.60541,
            "source": "llm-worker",
            "data": {
                "message_id": "99e465b6fec14eeb9b7b6c0ea6c7fe52",
                "id": "rt-b0fdb783",
                "reply": "The capital of Idaho is Boise. Need directions?",
                "error": None,
                "provider": "openai",
                "model": "gpt-4o-mini",
                "tokens": None,
            },
        }
        await broker.publish("llm/response", orjson.dumps(envelope_payload))

        await asyncio.wait_for(handled.wait(), timeout=1.0)
        assert len(received) == 1
        event = received[0]
        assert event.id == "rt-b0fdb783"
        assert event.reply == "The capital of Idaho is Boise. Need directions?"
        assert event.provider == "openai"
        assert event.model == "gpt-4o-mini"
    finally:
        await dispatcher.stop()
        run_task.cancel()
        with suppress(asyncio.CancelledError):
            await run_task
