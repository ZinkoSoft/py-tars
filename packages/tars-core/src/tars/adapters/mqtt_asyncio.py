from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import AsyncIterable
from dataclasses import dataclass
from typing import Optional

import asyncio_mqtt as mqtt
import orjson
from pydantic import ValidationError

from tars.contracts.envelope import Envelope
from tars.domain.ports import Publisher, Subscriber

@dataclass(slots=True)
class MQTTSubscriberOptions:
    """Configuration for MQTT subscriber behavior."""

    dedupe_ttl: float = 30.0
    dedupe_max_entries: int = 2048


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
        options: MQTTSubscriberOptions | None = None,
    ) -> None:
        self._client = client
        opts = options or MQTTSubscriberOptions()
        self._dedupe = (
            MessageDeduplicator(ttl=opts.dedupe_ttl, max_entries=opts.dedupe_max_entries)
            if opts.dedupe_ttl > 0 and opts.dedupe_max_entries > 0
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
        key_parts = [envelope.type, envelope.id]
        if isinstance(envelope.data, dict):
            seq = envelope.data.get("seq")
            if isinstance(seq, int):
                key_parts.append(f"seq={seq}")
            else:
                try:
                    digest = orjson.dumps(envelope.data, option=orjson.OPT_SORT_KEYS)
                except Exception:  # pragma: no cover - defensive
                    digest = repr(envelope.data).encode()
                key_parts.append(f"hash={hash(digest)}")
        return "|".join(map(str, key_parts))
