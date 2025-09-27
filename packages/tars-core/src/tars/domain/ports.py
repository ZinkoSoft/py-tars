from __future__ import annotations

from typing import AsyncIterable, Protocol


class MQTTMessage(Protocol):
    topic: str
    payload: bytes


class Publisher(Protocol):
    async def publish(self, topic: str, payload: bytes, qos: int = 0, retain: bool = False) -> None: ...


class Subscriber(Protocol):
    async def messages(self, topic: str, qos: int = 0) -> AsyncIterable[MQTTMessage]: ...
