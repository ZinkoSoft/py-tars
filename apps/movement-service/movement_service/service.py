from __future__ import annotations

import asyncio
import logging
from typing import Iterable

import asyncio_mqtt as mqtt
from asyncio_mqtt import MqttError

from movement_service.calibration import MovementCalibration
from movement_service.config import MovementSettings
from movement_service.json import dumps, loads
from movement_service.models import MovementCommand, MovementFrame, MovementState
from movement_service.sequences import build_frames

_LOGGER = logging.getLogger("movement-service")


class MovementService:
    """Bridges movement commands to frame publications."""

    def __init__(self, settings: MovementSettings, calibration: MovementCalibration | None = None) -> None:
        self.settings = settings
        self.calibration = calibration or MovementCalibration()

    async def run(self) -> None:
        connect = self.settings.mqtt_connect_kwargs()
        backoff = 1.0
        while True:
            _LOGGER.info("movement.mqtt.connect", extra=connect)
            try:
                async with mqtt.Client(**connect) as client:
                    _LOGGER.info("movement.mqtt.connected")
                    await self._on_connect(client)
                    backoff = 1.0
                    await self._consume_commands(client)
            except MqttError as exc:
                _LOGGER.warning("movement.mqtt.disconnected", extra={"error": str(exc), "backoff": backoff})
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 8.0)
            except Exception as exc:  # pragma: no cover - safety net
                _LOGGER.exception("movement.run.error", exc_info=exc)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 8.0)

    async def _on_connect(self, client: mqtt.Client) -> None:
        await client.publish(
            self.settings.health_topic,
            dumps({"ok": True, "event": "ready"}),
            qos=self.settings.publish_qos,
            retain=True,
        )
        await client.subscribe(self.settings.command_topic, qos=self.settings.publish_qos)

    async def _consume_commands(self, client: mqtt.Client) -> None:
        async with client.messages() as messages:
            await client.subscribe(self.settings.command_topic, qos=self.settings.publish_qos)
            async for message in messages:
                if message.topic != self.settings.command_topic:
                    continue
                await self._handle_command(client, message.payload)

    async def _handle_command(self, client: mqtt.Client, payload: bytes) -> None:
        try:
            parsed = MovementCommand.model_validate(loads(payload))
        except Exception as exc:
            _LOGGER.warning("movement.command.invalid", extra={"error": str(exc)})
            await client.publish(
                self.settings.health_topic,
                dumps({"ok": False, "event": "invalid_command", "detail": str(exc)}),
                qos=self.settings.publish_qos,
                retain=False,
            )
            return

        _LOGGER.info("movement.command.received", extra={"id": str(parsed.id), "command": parsed.command.value})
        frames = list(build_frames(parsed, self.calibration))
        if not frames:
            _LOGGER.info("movement.command.noop", extra={"id": str(parsed.id)})
            return
        await self._publish_frames(client, frames)

    async def _publish_frames(self, client: mqtt.Client, frames: Iterable[MovementFrame]) -> None:
        last_frame: MovementFrame | None = None
        for frame in frames:
            last_frame = frame
            await client.publish(
                self.settings.frame_topic,
                dumps(frame.model_dump(mode="python")),
                qos=self.settings.publish_qos,
                retain=False,
            )
            await self._publish_state(client, MovementState(id=frame.id, event="frame", seq=frame.seq))
            await asyncio.sleep(self.settings.frame_backoff_ms / 1000)
        if last_frame is not None:
            await self._publish_state(
                client,
                MovementState(id=last_frame.id, event="completed", seq=last_frame.seq),
            )

    async def _publish_state(self, client: mqtt.Client, state: MovementState) -> None:
        await client.publish(
            self.settings.state_topic,
            dumps(state.model_dump(mode="python")),
            qos=0,
            retain=False,
        )