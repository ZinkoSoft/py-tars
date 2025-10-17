from __future__ import annotations

import asyncio
import os
from typing import Iterable

from tars.adapters.mqtt_client import MQTTClient  # type: ignore[import]
from tars.adapters.mqtt_asyncio import AsyncioMQTTPublisher, AsyncioMQTTSubscriber  # type: ignore[import]
from tars.contracts.envelope import Envelope  # type: ignore[import]
from tars.contracts.v1 import (  # type: ignore[import]
    FinalTranscript,
    HealthPing,
    LLMCancel,
    LLMResponse,
    LLMStreamDelta,
    MovementStatusUpdate,
    TtsStatus,
    WakeEvent,
)
from tars.domain.router import RouterMetrics, RouterPolicy, RouterSettings  # type: ignore[import]
from tars.runtime.ctx import Ctx  # type: ignore[import]
from tars.runtime.dispatcher import Dispatcher  # type: ignore[import]
from tars.runtime.logging import configure_logging  # type: ignore[import]
from tars.runtime.registry import register_topics  # type: ignore[import]
from tars.runtime.subscription import Sub  # type: ignore[import]


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

    async def handle_tts_status(event: TtsStatus, ctx: Ctx) -> None:
        await policy.handle_tts_status(event, ctx)

    async def handle_movement_status(event: MovementStatusUpdate, ctx: Ctx) -> None:
        await policy.handle_movement_status(event, ctx)

    return (
        Sub(
            settings.topic_health_tts,
            HealthPing,
            lambda evt, ctx: handle_health("tts", evt, ctx),
            qos=1,
        ),
        Sub(
            settings.topic_health_stt,
            HealthPing,
            lambda evt, ctx: handle_health("stt", evt, ctx),
            qos=1,
        ),
        Sub(settings.topic_stt_final, FinalTranscript, handle_stt, qos=1),
        Sub(settings.topic_llm_resp, LLMResponse, handle_llm_response, qos=1),
        Sub(settings.topic_llm_stream, LLMStreamDelta, handle_llm_stream, qos=1),
        Sub(settings.topic_llm_cancel, LLMCancel, handle_llm_cancel, qos=1),
        Sub(settings.topic_wake_event, WakeEvent, handle_wake, qos=1),
        Sub(settings.topic_tts_status, TtsStatus, handle_tts_status, qos=1),
        Sub(settings.topic_movement_status, MovementStatusUpdate, handle_movement_status, qos=0),
    )


async def run_router() -> None:
    settings = RouterSettings.from_env()
    logger = configure_logging(os.getenv("LOG_LEVEL", "INFO"), name="router")

    register_topics(settings.as_topic_map())

    metrics = RouterMetrics()
    policy = RouterPolicy(settings, metrics=metrics)
    logger.info(
        "router.topics",
        extra={
            "llm_response": settings.topic_llm_resp,
            "llm_stream": settings.topic_llm_stream,
            "llm_request": settings.topic_llm_req,
            "stt_final": settings.topic_stt_final,
            "tts_say": settings.topic_tts_say,
        },
    )
    backoff = 1.0

    while True:
        logger.info("router.mqtt.connect", extra={"mqtt_url": settings.mqtt_url})
        try:
            mqtt_client = MQTTClient(settings.mqtt_url, "tars-router", enable_health=True)
            await mqtt_client.connect()
            
            if not mqtt_client.client:
                raise RuntimeError("MQTT client unavailable after connect")
                
            logger.info("router.mqtt.connected")
            publisher = AsyncioMQTTPublisher(mqtt_client.client)
            subscriber = AsyncioMQTTSubscriber(mqtt_client.client)
            subs = _build_subscriptions(settings, policy)

            def ctx_factory(_envelope: Envelope) -> Ctx:
                return Ctx(pub=publisher, policy=policy, logger=logger, metrics=metrics)

            dispatcher = Dispatcher(
                subscriber,
                subs,
                ctx_factory,
                logger=logger,
                queue_maxsize=settings.stream_settings.queue_maxsize,
                overflow_strategy=settings.stream_settings.queue_overflow,
                handler_timeout=settings.stream_settings.handler_timeout_sec,
            )
            ctx = Ctx(pub=publisher, policy=policy, logger=logger, metrics=metrics)
            await ctx.publish(
                "system.health.router", HealthPing(ok=True, event="ready"), qos=1, retain=True
            )
            backoff = 1.0
            try:
                await dispatcher.run()
            finally:
                await dispatcher.stop()
                await mqtt_client.shutdown()
        except Exception as exc:  
            logger.warning(
                "router.mqtt.disconnected", extra={"error": str(exc), "backoff": backoff}
            )
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
