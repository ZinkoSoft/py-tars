from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import AsyncIterable
from typing import Optional

import asyncio_mqtt as mqtt
from pydantic import ValidationError

from tars.contracts.envelope import Envelope
from tars.domain.ports import Publisher, Subscriber


class AsyncioMQTTPublisher(Publisher):
    """Publisher implementation backed by an asyncio-mqtt client."""

    def __init__(self, client: mqtt.Client) -> None:
        self._client = client

    async def publish(self, topic: str, payload: bytes, qos: int = 0, retain: bool = False) -> None:
        await self._client.publish(topic, payload, qos=qos, retain=retain)


class AsyncioMQTTSubscriber(Subscriber):
    """Subscriber implementation backed by an asyncio-mqtt client."""

    def __init__(
        self,
        client: mqtt.Client,
        *,
        dedupe_ttl: float = 30.0,
        dedupe_max_entries: int = 2048,
    ) -> None:
        self._client = client
        self._dedupe = (
            MessageDeduplicator(ttl=dedupe_ttl, max_entries=dedupe_max_entries)
            if dedupe_ttl > 0 and dedupe_max_entries > 0
            else None
        )

    async def messages(self, topic: str, qos: int = 0) -> AsyncIterable[mqtt.Message]:
        manager = self._client.filtered_messages(topic)
        await self._client.subscribe(topic, qos=qos)

        async with manager as messages:
            async for message in messages:
                if self._dedupe and self._dedupe.is_duplicate(message.payload):
                    continue
                yield message


class MessageDeduplicator:
    """Deduplicate messages using envelope ids with a TTL-bound cache."""

    def __init__(self, *, ttl: float, max_entries: int) -> None:
        self._ttl = ttl
        self._max_entries = max_entries
        self._seen: "OrderedDict[str, float]" = OrderedDict()

    def is_duplicate(self, payload: bytes) -> bool:
        message_id = self._extract_message_id(payload)
        if not message_id:
            return False

        now = time.monotonic()
        self._evict_expired(now)
        if message_id in self._seen:
            self._seen.move_to_end(message_id)
            self._seen[message_id] = now
            return True

        self._seen[message_id] = now
        if len(self._seen) > self._max_entries:
            self._seen.popitem(last=False)
        return False

    def _evict_expired(self, now: float) -> None:
        cutoff = now - self._ttl
        while self._seen:
            oldest_key, oldest_ts = next(iter(self._seen.items()))
            if oldest_ts >= cutoff:
                break
            self._seen.popitem(last=False)

    @staticmethod
    def _extract_message_id(payload: bytes) -> Optional[str]:
        try:
            envelope = Envelope.model_validate_json(payload)
        except ValidationError:
            return None
        if not envelope.id:
            return None
        return envelope.id
