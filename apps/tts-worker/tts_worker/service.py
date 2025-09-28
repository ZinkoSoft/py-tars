from __future__ import annotations

import logging
from typing import Any, Optional
from urllib.parse import urlparse

import asyncio_mqtt as mqtt
import orjson as json
from asyncio_mqtt import MqttError
from pydantic import BaseModel, ValidationError

from .config import (
    MQTT_URL,
    TTS_AGGREGATE,
    TTS_AGGREGATE_DEBOUNCE_MS,
    TTS_AGGREGATE_SINGLE_WAV,
    TTS_PIPELINE,
    TTS_STREAMING,
)
from .piper_synth import set_player_observer, set_stop_checker

from tars.adapters.mqtt_asyncio import AsyncioMQTTPublisher  # type: ignore[import]
from tars.contracts.envelope import Envelope  # type: ignore[import]
from tars.contracts.registry import resolve_topic  # type: ignore[import]
from tars.contracts.v1 import (  # type: ignore[import]
    EVENT_TYPE_SAY,
    EVENT_TYPE_TTS_STATUS,
    HealthPing,
    TtsSay,
    TtsStatus,
)
from tars.domain.tts import (  # type: ignore[import]
    TTSCallbacks,
    TTSConfig,
    TTSDomainService,
    TTSControlMessage,
    StatusEvent,
)
from tars.runtime.publisher import publish_event  # type: ignore[import]


logger = logging.getLogger("tts-worker")
SOURCE_NAME = "tts"
STATUS_TOPIC = resolve_topic(EVENT_TYPE_TTS_STATUS)
SAY_TOPIC = resolve_topic(EVENT_TYPE_SAY)
CONTROL_TOPIC = "tts/control"
EVENT_TYPE_HEALTH_TTS = "system.health.tts"


def parse_mqtt(url: str) -> tuple[str, int, Optional[str], Optional[str]]:
    u = urlparse(url)
    return (u.hostname or "127.0.0.1", u.port or 1883, u.username, u.password)


class TTSService:
    def __init__(self, primary_synth: Any, *, wake_ack_synth: Any | None = None) -> None:
        self._publisher: AsyncioMQTTPublisher | None = None
        config = TTSConfig(
            streaming_enabled=bool(TTS_STREAMING),
            pipeline_enabled=bool(TTS_PIPELINE),
            aggregate_enabled=bool(TTS_AGGREGATE),
            aggregate_debounce_ms=int(TTS_AGGREGATE_DEBOUNCE_MS),
            aggregate_single_wav=bool(TTS_AGGREGATE_SINGLE_WAV),
        )
        self._domain = TTSDomainService(primary_synth, config, wake_synth=wake_ack_synth)
        set_player_observer(self._domain.on_player_spawn)
        set_stop_checker(self._domain.should_abort_playback)

    def _build_callbacks(self, client: mqtt.Client) -> TTSCallbacks:
        async def publish_status(
            event: StatusEvent,
            text: str,
            utt_id: Optional[str],
            reason: Optional[str],
            wake_ack: Optional[bool],
        ) -> None:
            await self._publish_status(
                client,
                event=event,
                text=text,
                utt_id=utt_id,
                reason=reason,
                wake_ack=wake_ack,
            )

        return TTSCallbacks(publish_status=publish_status)

    @staticmethod
    def _decode_event(
        payload: bytes,
        model: type[BaseModel],
        *,
        event_type: str | None = None,
    ) -> BaseModel | None:
        try:
            envelope = Envelope.model_validate_json(payload)
            raw = envelope.data
            if event_type and envelope.type != event_type:
                logger.debug(
                    "Envelope type mismatch: expected=%s actual=%s",
                    event_type,
                    envelope.type,
                )
        except ValidationError:
            try:
                raw = json.loads(payload)
            except json.JSONDecodeError as exc:
                logger.error("Failed to decode %s payload: %s", model.__name__, exc)
                return None

        try:
            return model.model_validate(raw)
        except ValidationError as exc:
            logger.error("Invalid %s payload: %s", model.__name__, exc)
            return None

    async def _publish_event(self, event_type: str, data: Any, *, qos: int = 1, retain: bool = False) -> str | None:
        publisher = self._publisher
        if publisher is None:
            logger.warning("MQTT publisher unavailable; dropping %s", event_type)
            return None
        try:
            return await publish_event(
                publisher,
                logger,
                event_type,
                data,
                qos=qos,
                retain=retain,
                source=SOURCE_NAME,
            )
        except Exception as exc:
            logger.error("Failed to publish %s: %s", event_type, exc)
            return None

    async def _publish_status(
        self,
        mqtt_client: mqtt.Client,
        *,
        event: StatusEvent,
        text: str,
        utt_id: Optional[str],
        reason: Optional[str] = None,
        log_level: int = logging.INFO,
        wake_ack: Optional[bool] = None,
    ) -> None:
        status = TtsStatus(
            event=event,
            text=text,
            utt_id=utt_id,
            reason=reason,
            wake_ack=wake_ack,
        )
        message_id = await self._publish_event(EVENT_TYPE_TTS_STATUS, status, qos=1)
        if message_id is None:
            envelope = Envelope.new(event_type=EVENT_TYPE_TTS_STATUS, data=status, source=SOURCE_NAME)
            await mqtt_client.publish(STATUS_TOPIC, envelope.model_dump_json().encode(), qos=1)
            message_id = envelope.id
        logger.log(
            log_level,
            "Published TTS %s status: message_id=%s",
            event,
            message_id,
        )

    async def run(self) -> None:
        host, port, username, password = parse_mqtt(MQTT_URL)
        logger.info("Connecting to MQTT %s:%s", host, port)
        try:
            async with mqtt.Client(hostname=host, port=port, username=username, password=password, client_id="tars-tts") as client:
                logger.info("Connected to MQTT %s:%s as tars-tts", host, port)
                self._publisher = AsyncioMQTTPublisher(client)
                await self._publish_event(EVENT_TYPE_HEALTH_TTS, HealthPing(ok=True, event="ready"), retain=True)
                await client.subscribe([(SAY_TOPIC, 0), (CONTROL_TOPIC, 0)])
                logger.info("Subscribed to %s and %s, ready to process messages", SAY_TOPIC, CONTROL_TOPIC)
                callbacks = self._build_callbacks(client)
                async with client.messages() as messages:
                    async for msg in messages:
                        try:
                            logger.info("Received message on %s", msg.topic)
                            if msg.topic.value == SAY_TOPIC:
                                say = self._decode_event(msg.payload, TtsSay, event_type=EVENT_TYPE_SAY)
                                if say is None:
                                    continue
                                await self._domain.handle_say(say, callbacks)
                            elif msg.topic.value == CONTROL_TOPIC:
                                try:
                                    data = json.loads(msg.payload)
                                except json.JSONDecodeError as exc:
                                    logger.warning("Invalid tts/control payload: %s", exc)
                                    continue
                                try:
                                    control = TTSControlMessage.from_dict(data)
                                except ValueError as exc:
                                    logger.warning("Invalid tts/control payload: %s", exc)
                                    continue
                                await self._domain.handle_control(control, callbacks)
                            else:
                                logger.debug("Ignoring unexpected topic %s", msg.topic)
                        except Exception as exc:
                            logger.error("Error processing message: %s", exc)
                            await self._publish_event(EVENT_TYPE_HEALTH_TTS, HealthPing(ok=False, err=str(exc)), retain=True)
        except MqttError as exc:
            logger.info("MQTT disconnected: %s; shutting down gracefully", exc)
        finally:
            self._publisher = None

