from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from typing import Any

import orjson
from pydantic import ValidationError

from tars.contracts.envelope import Envelope
from tars.contracts.registry import resolve_event
from tars.runtime.subscription import Sub

if True:  # type-checking alias
    from tars.domain.ports import Subscriber


class Dispatcher:
    """Fan out subscribed messages to typed handlers."""

    def __init__(self, sub_client: "Subscriber", subs: Iterable[Sub], ctx_factory: Callable[[Envelope], Any]) -> None:
        self._sub_client = sub_client
        self._subs = list(subs)
        self._ctx_factory = ctx_factory
        self._tasks: list[asyncio.Task[Any]] = []

    async def run(self) -> None:
        if self._tasks:
            raise RuntimeError("Dispatcher already running")
        self._tasks = [asyncio.create_task(self._pump(sub)) for sub in self._subs]
        try:
            await asyncio.gather(*self._tasks)
        finally:
            await self.stop()

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _pump(self, sub: Sub) -> None:
        async for msg in self._sub_client.messages(sub.topic, qos=sub.qos):
            try:
                envelope = Envelope.model_validate_json(msg.payload)
                payload_model = sub.model.model_validate(envelope.data)
            except ValidationError:
                try:
                    raw = orjson.loads(msg.payload)
                except orjson.JSONDecodeError as exc:  # pragma: no cover - debug aid, will be logged later
                    print(f"[dispatcher] payload decode error on topic={sub.topic}: {exc}")
                    continue
                try:
                    payload_model = sub.model.model_validate(raw)
                except ValidationError as exc:
                    print(f"[dispatcher] validation error on topic={sub.topic}: {exc}")
                    continue
                try:
                    event_type = resolve_event(sub.topic)
                except KeyError as exc:  # pragma: no cover - debug aid until registry is complete
                    print(f"[dispatcher] unknown topic mapping for {sub.topic}: {exc}")
                    continue
                envelope = Envelope.new(event_type=event_type, data=payload_model)
            try:
                ctx = self._ctx_factory(envelope)
                await sub.handler(payload_model, ctx)
            except Exception as exc:  # pragma: no cover - to be replaced with structured logging
                print(f"[dispatcher] handler error on topic={sub.topic}: {exc}")
