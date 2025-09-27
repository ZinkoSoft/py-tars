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


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def load_settings() -> RouterSettings:
    defaults = RouterSettings()
    return RouterSettings(
        mqtt_url=os.getenv("MQTT_URL", defaults.mqtt_url),
        online_announce=_env_bool("ONLINE_ANNOUNCE", defaults.online_announce),
        online_text=os.getenv("ONLINE_ANNOUNCE_TEXT", defaults.online_text),
        topic_health_tts=os.getenv("TOPIC_HEALTH_TTS", defaults.topic_health_tts),
        topic_health_stt=os.getenv("TOPIC_HEALTH_STT", defaults.topic_health_stt),
    topic_health_router=os.getenv("TOPIC_HEALTH_ROUTER", defaults.topic_health_router),
        topic_stt_final=os.getenv("TOPIC_STT_FINAL", defaults.topic_stt_final),
        topic_tts_say=os.getenv("TOPIC_TTS_SAY", defaults.topic_tts_say),
        topic_llm_req=os.getenv("TOPIC_LLM_REQUEST", defaults.topic_llm_req),
        topic_llm_resp=os.getenv("TOPIC_LLM_RESPONSE", defaults.topic_llm_resp),
        topic_llm_stream=os.getenv("TOPIC_LLM_STREAM", defaults.topic_llm_stream),
        topic_llm_cancel=os.getenv("TOPIC_LLM_CANCEL", defaults.topic_llm_cancel),
        topic_wake_event=os.getenv("TOPIC_WAKE_EVENT", defaults.topic_wake_event),
        router_llm_tts_stream=_env_bool("ROUTER_LLM_TTS_STREAM", defaults.router_llm_tts_stream),
        stream_min_chars=_env_int("ROUTER_STREAM_MIN_CHARS", _env_int("STREAM_MIN_CHARS", defaults.stream_min_chars)),
        stream_max_chars=_env_int("ROUTER_STREAM_MAX_CHARS", _env_int("STREAM_MAX_CHARS", defaults.stream_max_chars)),
        stream_boundary_chars=os.getenv(
            "ROUTER_STREAM_BOUNDARY_CHARS",
            os.getenv("STREAM_BOUNDARY_CHARS", defaults.stream_boundary_chars),
        ),
        stream_boundary_only=_env_bool("ROUTER_STREAM_BOUNDARY_ONLY", defaults.stream_boundary_only),
        stream_hard_max_chars=_env_int("ROUTER_STREAM_HARD_MAX_CHARS", defaults.stream_hard_max_chars),
        wake_phrases_raw=os.getenv("ROUTER_WAKE_PHRASES", os.getenv("WAKE_PHRASES", defaults.wake_phrases_raw)),
        wake_window_sec=_env_float("ROUTER_WAKE_WINDOW_SEC", defaults.wake_window_sec),
        wake_ack_enabled=_env_bool("ROUTER_WAKE_ACK_ENABLED", defaults.wake_ack_enabled),
        wake_ack_text=os.getenv("ROUTER_WAKE_ACK_TEXT", defaults.wake_ack_text),
        wake_ack_choices_raw=os.getenv("ROUTER_WAKE_ACK_CHOICES", os.getenv("WAKE_ACK_CHOICES", defaults.wake_ack_choices_raw)),
        wake_ack_style=os.getenv("ROUTER_WAKE_ACK_STYLE", defaults.wake_ack_style),
        wake_reprompt_text=os.getenv("ROUTER_WAKE_REPROMPT_TEXT", defaults.wake_reprompt_text),
        wake_interrupt_text=os.getenv("ROUTER_WAKE_INTERRUPT_TEXT", defaults.wake_interrupt_text),
        wake_resume_text=os.getenv("ROUTER_WAKE_RESUME_TEXT", defaults.wake_resume_text),
        wake_cancel_text=os.getenv("ROUTER_WAKE_CANCEL_TEXT", defaults.wake_cancel_text),
        wake_timeout_text=os.getenv("ROUTER_WAKE_TIMEOUT_TEXT", defaults.wake_timeout_text),
        live_mode_default=_env_bool("ROUTER_LIVE_MODE_DEFAULT", defaults.live_mode_default),
        live_mode_enter_phrase=os.getenv("ROUTER_LIVE_MODE_ENTER_PHRASE", defaults.live_mode_enter_phrase),
        live_mode_exit_phrase=os.getenv("ROUTER_LIVE_MODE_EXIT_PHRASE", defaults.live_mode_exit_phrase),
        live_mode_enter_ack=os.getenv("ROUTER_LIVE_MODE_ENTER_ACK", defaults.live_mode_enter_ack),
        live_mode_exit_ack=os.getenv("ROUTER_LIVE_MODE_EXIT_ACK", defaults.live_mode_exit_ack),
        live_mode_active_hint=os.getenv("ROUTER_LIVE_MODE_ACTIVE_HINT", defaults.live_mode_active_hint),
        live_mode_inactive_hint=os.getenv("ROUTER_LIVE_MODE_INACTIVE_HINT", defaults.live_mode_inactive_hint),
    )


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
    settings = load_settings()
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
