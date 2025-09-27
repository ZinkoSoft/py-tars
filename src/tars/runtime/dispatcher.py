from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from typing import Any, Optional, Tuple

import orjson
from pydantic import ValidationError

from tars.contracts.envelope import Envelope
from tars.contracts.registry import resolve_event
from tars.runtime.subscription import Sub

if True:  # type-checking alias
    from tars.domain.ports import Subscriber
    from tars.runtime.logging import Logger


class Dispatcher:
    """Fan out subscribed messages to typed handlers with backpressure controls."""

    def __init__(
        self,
        sub_client: "Subscriber",
        subs: Iterable[Sub],
        ctx_factory: Callable[[Envelope], Any],
        *,
        logger: Optional["Logger"] = None,
        queue_maxsize: int = 256,
        overflow_strategy: str = "drop_oldest",
        handler_timeout: float = 30.0,
        worker_count: int = 1,
    ) -> None:
        self._sub_client = sub_client
        self._subs = list(subs)
        self._ctx_factory = ctx_factory
        self._logger = logger
        self._queue: asyncio.Queue[Tuple[Sub, Envelope, Any]] = asyncio.Queue(maxsize=max(1, queue_maxsize))
        self._overflow_strategy = overflow_strategy
        self._handler_timeout = handler_timeout
        self._worker_count = max(1, worker_count)
        self._pump_tasks: list[asyncio.Task[Any]] = []
        self._worker_tasks: list[asyncio.Task[Any]] = []

    async def run(self) -> None:
        if self._worker_tasks or self._pump_tasks:
            raise RuntimeError("Dispatcher already running")
        self._pump_tasks = [asyncio.create_task(self._pump(sub)) for sub in self._subs]
        self._worker_tasks = [asyncio.create_task(self._dispatch_loop()) for _ in range(self._worker_count)]
        try:
            await asyncio.gather(*self._pump_tasks, *self._worker_tasks)
        finally:
            await self.stop()

    async def stop(self) -> None:
        for task in self._pump_tasks + self._worker_tasks:
            task.cancel()
        if self._pump_tasks or self._worker_tasks:
            await asyncio.gather(*self._pump_tasks, *self._worker_tasks, return_exceptions=True)
        self._pump_tasks.clear()
        self._worker_tasks.clear()

        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except asyncio.QueueEmpty:  # pragma: no cover - defensive
                break

    async def _pump(self, sub: Sub) -> None:
        async for msg in self._sub_client.messages(sub.topic, qos=sub.qos):
            try:
                envelope = Envelope.model_validate_json(msg.payload)
                payload_model = sub.model.model_validate(envelope.data)
            except ValidationError:
                try:
                    raw = orjson.loads(msg.payload)
                except orjson.JSONDecodeError as exc:
                    self._log_decode_error(sub.topic, f"decode_failed: {exc}")
                    continue
                try:
                    payload_model = sub.model.model_validate(raw)
                except ValidationError as exc:
                    self._log_decode_error(sub.topic, f"validation_failed: {exc}")
                    continue
                try:
                    event_type = resolve_event(sub.topic)
                except KeyError as exc:
                    self._log_decode_error(sub.topic, f"unknown_topic: {exc}")
                    continue
                envelope = Envelope.new(event_type=event_type, data=payload_model)

            await self._enqueue(sub, envelope, payload_model)

    async def _enqueue(self, sub: Sub, envelope: Envelope, payload: Any) -> None:
        try:
            self._queue.put_nowait((sub, envelope, payload))
            return
        except asyncio.QueueFull:
            pass

        strategy = self._overflow_strategy
        if strategy == "drop_oldest":
            try:
                dropped_sub, dropped_env, _ = self._queue.get_nowait()
            except asyncio.QueueEmpty:  # pragma: no cover - defensive
                self._log_overflow("drop_oldest_empty", sub.topic, envelope.id)
            else:
                self._queue.task_done()
                self._log_overflow("drop_oldest", dropped_sub.topic, dropped_env.id)
                try:
                    self._queue.put_nowait((sub, envelope, payload))
                    return
                except asyncio.QueueFull:  # pragma: no cover - race
                    self._log_overflow("drop_new_after_drop_oldest", sub.topic, envelope.id)
                    return
        elif strategy == "drop_new":
            self._log_overflow("drop_new", sub.topic, envelope.id)
            return

        self._log_overflow("block_wait", sub.topic, envelope.id)
        try:
            await asyncio.wait_for(self._queue.put((sub, envelope, payload)), timeout=self._handler_timeout)
        except asyncio.TimeoutError:
            self._log_overflow("block_timeout", sub.topic, envelope.id)

    async def _dispatch_loop(self) -> None:
        while True:
            sub, envelope, payload = await self._queue.get()
            try:
                await self._deliver(sub, envelope, payload)
            finally:
                self._queue.task_done()

    async def _deliver(self, sub: Sub, envelope: Envelope, payload: Any) -> None:
        try:
            ctx = self._ctx_factory(envelope)
            await asyncio.wait_for(sub.handler(payload, ctx), timeout=self._handler_timeout)
        except asyncio.TimeoutError:
            self._log_handler_error(sub.topic, "handler_timeout", envelope.id)
        except ValidationError as exc:
            self._log_handler_error(sub.topic, f"payload_revalidate_failed: {exc}", envelope.id)
        except Exception as exc:  # pragma: no cover - safety net
            self._log_handler_error(sub.topic, str(exc), envelope.id)

    def _log_overflow(self, mode: str, topic: str, envelope_id: str) -> None:
        if self._logger:
            self._logger.warning(
                "dispatcher.queue.overflow",
                extra={"mode": mode, "topic": topic, "envelope_id": envelope_id, "size": self._queue.qsize()},
            )
        else:
            print(f"[dispatcher] queue overflow mode={mode} topic={topic} envelope={envelope_id} size={self._queue.qsize()}")

    def _log_handler_error(self, topic: str, error: str, envelope_id: str) -> None:
        if self._logger:
            self._logger.error(
                "dispatcher.handler.error",
                extra={"topic": topic, "error": error, "envelope_id": envelope_id},
            )
        else:
            print(f"[dispatcher] handler error on topic={topic}: {error}")

    def _log_decode_error(self, topic: str, error: str) -> None:
        if self._logger:
            self._logger.warning("dispatcher.decode.error", extra={"topic": topic, "error": error})
        else:
            print(f"[dispatcher] decode error on topic={topic}: {error}")
