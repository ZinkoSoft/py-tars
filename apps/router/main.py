from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import asyncio_mqtt as mqtt
from asyncio_mqtt import MqttError
import orjson
from pydantic import ValidationError

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if SRC_DIR.exists():
    src_path = str(SRC_DIR)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

from tars.adapters.mqtt_asyncio import AsyncioMQTTPublisher, AsyncioMQTTSubscriber  # type: ignore[import]
from tars.contracts.envelope import Envelope  # type: ignore[import]
from tars.contracts.registry import register  # type: ignore[import]
from tars.contracts.v1 import (  # type: ignore[import]
    FinalTranscript,
    HealthPing,
    LLMCancel,
    LLMResponse,
    LLMStreamDelta,
    WakeEvent,
)
from tars.domain.ports import Publisher  # type: ignore[import]
from tars.domain.router import RouterPolicy, RouterSettings  # type: ignore[import]
from tars.runtime.ctx import Ctx  # type: ignore[import]
from tars.runtime.dispatcher import Dispatcher  # type: ignore[import]
from tars.runtime.subscription import Sub  # type: ignore[import]



def parse_mqtt(url: str) -> tuple[str, int, str | None, str | None]:
    parsed = urlparse(url)
    return (
        parsed.hostname or "127.0.0.1",
        parsed.port or 1883,
        parsed.username,
        parsed.password,
    )


class LegacyJSONPublisher(Publisher):
    """Unwrap dispatcher envelopes into legacy MQTT payloads."""

    def __init__(self, delegate: Publisher) -> None:
        self._delegate = delegate

    async def publish(self, topic: str, payload: bytes, qos: int = 0, retain: bool = False) -> None:
        try:
            envelope = Envelope.model_validate_json(payload)
            data = envelope.data
        except ValidationError:
            data = orjson.loads(payload)
        await self._delegate.publish(topic, orjson.dumps(data), qos=qos, retain=retain)


def _build_subscriptions(settings: RouterSettings, policy: RouterPolicy) -> Iterable[Sub]:
    async def handle_health(service: str, event: HealthPing, ctx: Ctx) -> None:
        await policy.handle_health(service, event, ctx)

    async def handle_stt(event: FinalTranscript, ctx: Ctx) -> None:
        await policy.handle_stt_final(event, ctx)

    async def handle_llm_response(event: LLMResponse, ctx: Ctx) -> None:
        await policy.handle_llm_response(event, ctx)

    async def handle_llm_stream(event: LLMStreamDelta, ctx: Ctx) -> None:
        await policy.handle_llm_stream(event, ctx)

    async def handle_llm_cancel(event: LLMCancel, ctx: Ctx) -> None:
        await policy.handle_llm_cancel(event, ctx)

    async def handle_wake(event: WakeEvent, ctx: Ctx) -> None:
        await policy.handle_wake_event(event, ctx)

    return (
        Sub(settings.topic_health_tts, HealthPing, lambda evt, ctx: handle_health("tts", evt, ctx), qos=1),
        Sub(settings.topic_health_stt, HealthPing, lambda evt, ctx: handle_health("stt", evt, ctx), qos=1),
        Sub(settings.topic_stt_final, FinalTranscript, handle_stt, qos=1),
        Sub(settings.topic_llm_resp, LLMResponse, handle_llm_response, qos=1),
        Sub(settings.topic_llm_stream, LLMStreamDelta, handle_llm_stream, qos=1),
        Sub(settings.topic_llm_cancel, LLMCancel, handle_llm_cancel, qos=1),
        Sub(settings.topic_wake_event, WakeEvent, handle_wake, qos=1),
    )


async def run_router() -> None:
    settings = RouterSettings.from_env()
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("router")

    for event_type, topic in settings.as_topic_map().items():
        register(event_type, topic)

    policy = RouterPolicy(settings)
    host, port, username, password = parse_mqtt(settings.mqtt_url)
    backoff = 1.0

    while True:
        logger.info("router.mqtt.connect", extra={"host": host, "port": port})
        try:
            async with mqtt.Client(
                hostname=host,
                port=port,
                username=username,
                password=password,
                client_id="tars-router",
            ) as client:
                logger.info("router.mqtt.connected", extra={"host": host, "port": port})
                publisher = LegacyJSONPublisher(AsyncioMQTTPublisher(client))
                subscriber = AsyncioMQTTSubscriber(client)
                subs = _build_subscriptions(settings, policy)

                def ctx_factory(_envelope: Envelope) -> Ctx:
                    return Ctx(pub=publisher, policy=policy, logger=logger)

                dispatcher = Dispatcher(subscriber, subs, ctx_factory)
                ctx = Ctx(pub=publisher, policy=policy, logger=logger)
                await ctx.publish("system.health.router", HealthPing(ok=True, event="ready"), qos=1)
                backoff = 1.0
                try:
                    await dispatcher.run()
                finally:
                    await dispatcher.stop()
        except MqttError as exc:
            logger.warning("router.mqtt.disconnected", extra={"error": str(exc), "backoff": backoff})
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2.0, 8.0)
        except Exception as exc:  # pragma: no cover - safety net
            logger.error("router.run.error", exc_info=exc)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2.0, 8.0)


def main() -> None:
    asyncio.run(run_router())


if __name__ == "__main__":
    main()
