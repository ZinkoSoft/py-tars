from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Any, Optional

import orjson as json
from pydantic import BaseModel, ValidationError

from .config import (
    MQTT_URL,
    TTS_AGGREGATE,
    TTS_AGGREGATE_DEBOUNCE_MS,
    TTS_AGGREGATE_SINGLE_WAV,
    TTS_PIPELINE,
    TTS_STREAMING,
    TTS_WAKE_ACK_TEXTS,
    TTS_WAKE_CACHE_DIR,
    TTS_WAKE_CACHE_ENABLE,
    TTS_WAKE_CACHE_MAX,
)
from .piper_synth import set_player_observer, set_stop_checker

from tars.adapters.mqtt_client import MQTTClient  # type: ignore[import]
from tars.contracts.envelope import Envelope  # type: ignore[import]
from tars.contracts.v1 import (  # type: ignore[import]
    EVENT_TYPE_SAY,
    EVENT_TYPE_TTS_STATUS,
    TOPIC_TTS_CONTROL,
    TOPIC_TTS_SAY,
    TOPIC_TTS_STATUS,
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


logger = logging.getLogger("tts-worker")
SOURCE_NAME = "tts"
STATUS_TOPIC = TOPIC_TTS_STATUS
SAY_TOPIC = TOPIC_TTS_SAY
CONTROL_TOPIC = TOPIC_TTS_CONTROL
EVENT_TYPE_HEALTH_TTS = "system.health.tts"


class TTSService:
    def __init__(self, primary_synth: Any, *, wake_ack_synth: Any | None = None) -> None:
        self._mqtt_client: MQTTClient | None = None
        wake_cache_dir = None
        try:
            enabled = bool(int(TTS_WAKE_CACHE_ENABLE))
        except Exception:
            enabled = True
        if enabled:
            candidate = (TTS_WAKE_CACHE_DIR or "").strip()
            if candidate:
                wake_cache_dir = candidate
        try:
            wake_cache_max = max(1, int(TTS_WAKE_CACHE_MAX))
        except Exception:
            wake_cache_max = 16

        config = TTSConfig(
            streaming_enabled=bool(TTS_STREAMING),
            pipeline_enabled=bool(TTS_PIPELINE),
            aggregate_enabled=bool(TTS_AGGREGATE),
            aggregate_debounce_ms=int(TTS_AGGREGATE_DEBOUNCE_MS),
            aggregate_single_wav=bool(TTS_AGGREGATE_SINGLE_WAV),
            wake_cache_dir=wake_cache_dir,
            wake_cache_max_entries=wake_cache_max,
            wake_ack_preload_texts=tuple(TTS_WAKE_ACK_TEXTS),
        )
        self._domain = TTSDomainService(primary_synth, config, wake_synth=wake_ack_synth)
        set_player_observer(self._domain.on_player_spawn)
        set_stop_checker(self._domain.should_abort_playback)

    def _build_callbacks(self, mqtt_client: MQTTClient) -> TTSCallbacks:
        async def publish_status(
            event: StatusEvent,
            text: str,
            utt_id: Optional[str],
            reason: Optional[str],
            wake_ack: Optional[bool],
            system_announce: Optional[bool],
        ) -> None:
            await self._publish_status(
                mqtt_client,
                event=event,
                text=text,
                utt_id=utt_id,
                reason=reason,
                wake_ack=wake_ack,
                system_announce=system_announce,
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

    async def _publish_event(
        self, event_type: str, data: Any, *, qos: int = 1, retain: bool = False
    ) -> str:
        if self._mqtt_client is None:
            logger.warning("MQTT client unavailable; dropping %s", event_type)
            return ""
        try:
            from tars.contracts.registry import resolve_topic
            topic = resolve_topic(event_type)
            return await self._mqtt_client.publish_event(
                topic=topic,
                event_type=event_type,
                data=data.model_dump() if hasattr(data, "model_dump") else data,
                qos=qos,
                retain=retain,
            )
        except Exception as exc:
            logger.error("Failed to publish %s: %s", event_type, exc)
            return ""

    async def _publish_status(
        self,
        mqtt_client: MQTTClient,
        *,
        event: StatusEvent,
        text: str,
        utt_id: Optional[str],
        reason: Optional[str] = None,
        log_level: int = logging.INFO,
        wake_ack: Optional[bool] = None,
        system_announce: Optional[bool] = None,
    ) -> None:
        status = TtsStatus(
            event=event,
            text=text,
            utt_id=utt_id,
            reason=reason,
            wake_ack=wake_ack,
            system_announce=system_announce,
        )
        message_id = await self._publish_event(EVENT_TYPE_TTS_STATUS, status, qos=0)
        if message_id:
            logger.log(
                log_level,
                "Published TTS %s status: message_id=%s",
                event,
                message_id,
            )
        else:
            logger.warning("Failed to publish TTS %s status", event)

    async def run(self) -> None:
        logger.info("Connecting to MQTT %s", MQTT_URL)
        try:
            self._mqtt_client = MQTTClient(MQTT_URL, "tars-tts", enable_health=True)
            await self._mqtt_client.connect()
            
            logger.info("Connected to MQTT as tars-tts")
            await self._publish_event(
                EVENT_TYPE_HEALTH_TTS, HealthPing(ok=True, event="ready"), retain=True
            )
            
            # Set up subscriptions
            async def handle_say(payload: bytes) -> None:
                say = self._decode_event(payload, TtsSay, event_type=EVENT_TYPE_SAY)
                if say is None:
                    return
                callbacks = self._build_callbacks(self._mqtt_client)  # type: ignore
                await self._domain.handle_say(say, callbacks)
            
            async def handle_control(payload: bytes) -> None:
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError as exc:
                    logger.warning("Invalid tts/control payload: %s", exc)
                    return
                try:
                    control = TTSControlMessage.from_dict(data)
                except ValueError as exc:
                    logger.warning("Invalid tts/control payload: %s", exc)
                    return
                callbacks = self._build_callbacks(self._mqtt_client)  # type: ignore
                await self._domain.handle_control(control, callbacks)
            
            await self._mqtt_client.subscribe(SAY_TOPIC, handle_say, qos=1)
            await self._mqtt_client.subscribe(CONTROL_TOPIC, handle_control, qos=1)
            
            logger.info(
                "Subscribed to %s and %s, ready to process messages", SAY_TOPIC, CONTROL_TOPIC
            )
            
            # Preload wake cache
            logger.debug("Starting phrase cache preload task")
            preload_task: asyncio.Task[None] | None = None
            try:
                preload_task = asyncio.create_task(self._domain.preload_wake_cache())

                def _handle_preload_result(task: asyncio.Task[None]) -> None:
                    try:
                        task.result()
                    except asyncio.CancelledError:
                        logger.debug("Phrase cache preload cancelled")
                    except Exception as exc:  # pragma: no cover - defensive logging
                        logger.warning("Phrase cache preload failed", extra={"error": str(exc)})
                    else:
                        logger.info("Phrase cache preload complete")

                preload_task.add_done_callback(_handle_preload_result)

                # Keep service running
                await asyncio.Event().wait()
                
            finally:
                if preload_task is not None and not preload_task.done():
                    preload_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await preload_task
                await self._mqtt_client.shutdown()
        except Exception as exc:
            logger.info("MQTT disconnected: %s; shutting down gracefully", exc)
        finally:
            self._publisher = None
