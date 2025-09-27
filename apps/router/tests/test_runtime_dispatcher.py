from __future__ import annotations

import asyncio
from typing import Any, AsyncIterable

import pytest
from pydantic import BaseModel

from tars.contracts.envelope import Envelope  # type: ignore[import]
from tars.domain.ports import Subscriber  # type: ignore[import]
from tars.runtime.dispatcher import Dispatcher  # type: ignore[import]
from tars.runtime.subscription import Sub  # type: ignore[import]


def _sample_envelope(text: str) -> Envelope:
    return Envelope.new(event_type="tests.dispatcher", data={"text": text})


class SampleEvent(BaseModel):
    text: str


class DummySubscriber(Subscriber):
    async def messages(self, topic: str, qos: int = 0) -> AsyncIterable[Any]:  # pragma: no cover - unused helper
        raise AssertionError("messages should not be invoked in unit tests")


class CaptureLogger:
    def __init__(self) -> None:
        self.warnings: list[dict[str, Any]] = []
        self.errors: list[dict[str, Any]] = []

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - unused
        return None

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - unused
        return None

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        payload = {"msg": msg, "args": args, "kwargs": kwargs}
        self.warnings.append(payload)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        payload = {"msg": msg, "args": args, "kwargs": kwargs}
        self.errors.append(payload)


def _make_dispatcher(
    *,
    queue_maxsize: int = 1,
    overflow_strategy: str = "drop_oldest",
    handler_timeout: float = 0.1,
    logger: CaptureLogger | None = None,
) -> tuple[Dispatcher, Sub, CaptureLogger]:
    captured_logger = logger or CaptureLogger()

    async def handler(event: SampleEvent, ctx: Any) -> None:
        return None

    sub = Sub("tests/topic", SampleEvent, handler, qos=1)
    dispatcher = Dispatcher(
        DummySubscriber(),
        (sub,),
        lambda envelope: {"envelope_id": envelope.id},
        logger=captured_logger,
        queue_maxsize=queue_maxsize,
        overflow_strategy=overflow_strategy,
        handler_timeout=handler_timeout,
    )
    return dispatcher, sub, captured_logger


@pytest.mark.asyncio
async def test_dispatcher_drop_new_overflow_keeps_existing_message() -> None:
    dispatcher, sub, _logger = _make_dispatcher(overflow_strategy="drop_new")

    env_first = _sample_envelope("first")
    payload_first = SampleEvent(text="first")
    env_second = _sample_envelope("second")
    payload_second = SampleEvent(text="second")

    await dispatcher._enqueue(sub, env_first, payload_first)
    await dispatcher._enqueue(sub, env_second, payload_second)

    assert dispatcher._queue.qsize() == 1
    queued_sub, queued_env, queued_payload = dispatcher._queue.get_nowait()
    dispatcher._queue.task_done()
    assert queued_env.id == env_first.id
    assert queued_payload.text == "first"
    assert queued_sub is sub


@pytest.mark.asyncio
async def test_dispatcher_drop_oldest_overflow_replaces_entry() -> None:
    dispatcher, sub, _logger = _make_dispatcher(overflow_strategy="drop_oldest")

    env_first = _sample_envelope("old")
    env_second = _sample_envelope("new")

    await dispatcher._enqueue(sub, env_first, SampleEvent(text="old"))
    await dispatcher._enqueue(sub, env_second, SampleEvent(text="new"))

    assert dispatcher._queue.qsize() == 1
    queued_sub, queued_env, queued_payload = dispatcher._queue.get_nowait()
    dispatcher._queue.task_done()
    assert queued_env.id == env_second.id
    assert queued_payload.text == "new"
    assert queued_sub is sub


@pytest.mark.asyncio
async def test_dispatcher_block_strategy_waits_for_capacity() -> None:
    dispatcher, sub, _logger = _make_dispatcher(overflow_strategy="block", handler_timeout=0.5)

    env_first = _sample_envelope("hold")
    env_second = _sample_envelope("after-space")

    await dispatcher._enqueue(sub, env_first, SampleEvent(text="hold"))

    async def free_space() -> None:
        await asyncio.sleep(0.02)
        queued = dispatcher._queue.get_nowait()
        dispatcher._queue.task_done()
        return queued

    free_task = asyncio.create_task(free_space())
    await dispatcher._enqueue(sub, env_second, SampleEvent(text="after"))
    await free_task

    assert dispatcher._queue.qsize() == 1
    queued_sub, queued_env, queued_payload = dispatcher._queue.get_nowait()
    dispatcher._queue.task_done()
    assert queued_env.id == env_second.id
    assert queued_payload.text == "after"
    assert queued_sub is sub


@pytest.mark.asyncio
async def test_dispatcher_block_strategy_honors_timeout() -> None:
    dispatcher, sub, logger = _make_dispatcher(overflow_strategy="block", handler_timeout=0.05)

    env_first = _sample_envelope("stay")
    env_second = _sample_envelope("timeout")

    await dispatcher._enqueue(sub, env_first, SampleEvent(text="stay"))

    start = asyncio.get_event_loop().time()
    await dispatcher._enqueue(sub, env_second, SampleEvent(text="timeout"))
    elapsed = asyncio.get_event_loop().time() - start

    assert elapsed >= 0.05
    assert dispatcher._queue.qsize() == 1
    queued_sub, queued_env, queued_payload = dispatcher._queue.get_nowait()
    dispatcher._queue.task_done()
    assert queued_env.id == env_first.id
    assert queued_payload.text == "stay"
    assert queued_sub is sub

    assert any(record["kwargs"].get("extra", {}).get("mode") == "block_timeout" for record in logger.warnings)


@pytest.mark.asyncio
async def test_dispatcher_handler_timeout_logs_error() -> None:
    logger = CaptureLogger()
    dispatcher, sub, _ = _make_dispatcher(handler_timeout=0.02, logger=logger)

    async def slow_handler(event: SampleEvent, ctx: Any) -> None:
        await asyncio.sleep(0.05)

    new_sub = Sub(sub.topic, SampleEvent, slow_handler, qos=1)
    dispatcher._subs = [new_sub]

    envelope = _sample_envelope("slow")
    await dispatcher._deliver(new_sub, envelope, SampleEvent(text="slow"))
