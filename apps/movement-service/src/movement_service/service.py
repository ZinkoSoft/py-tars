from __future__ import annotations

import asyncio
import logging

import asyncio_mqtt as mqtt
from asyncio_mqtt import MqttError

from movement_service.config import MovementSettings
from movement_service.json import dumps, loads
from movement_service.models import TestMovementRequest

_LOGGER = logging.getLogger("movement-service")


class MovementService:
    """
    Movement service that forwards commands to ESP32 tars_controller.

    Architecture:
      1. Subscribe to movement/test topic (commands from LLM/Router)
      2. Validate TestMovementRequest messages (Pydantic v2)
      3. Forward valid commands to ESP32's movement/test topic
      4. ESP32 autonomously executes movement sequences

    Note: This service does NOT build servo frames. ESP32 firmware
    (tars_controller.py) contains MovementSequences that autonomously
    execute all movement logic. This service only validates and forwards.
    """

    def __init__(self, settings: MovementSettings) -> None:
        self.settings = settings

    async def run(self) -> None:
        """Run the movement service with reconnection backoff."""
        connect = self.settings.mqtt_connect_kwargs()
        backoff = 1.0
        while True:
            _LOGGER.info("movement.mqtt.connect", extra=connect)
            try:
                async with mqtt.Client(**connect) as client:  # type: ignore[arg-type]
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
        """Publish health and subscribe to test topic on connect."""
        await client.publish(
            self.settings.health_topic,
            dumps({"ok": True, "event": "ready"}),
            qos=self.settings.publish_qos,
            retain=True,
        )
        await client.subscribe(self.settings.test_topic, qos=self.settings.publish_qos)
        _LOGGER.info("movement.subscribed", extra={"topic": self.settings.test_topic})

    async def _consume_commands(self, client: mqtt.Client) -> None:
        """Consume and handle test commands."""
        async with client.messages() as messages:
            await client.subscribe(self.settings.test_topic, qos=self.settings.publish_qos)
            async for message in messages:
                if str(message.topic) != self.settings.test_topic:
                    continue
                if not isinstance(message.payload, bytes):
                    _LOGGER.warning("movement.payload.invalid_type", extra={"type": type(message.payload).__name__})
                    continue
                await self._handle_test_command(client, message.payload)

    async def _handle_test_command(self, client: mqtt.Client, payload: bytes) -> None:
        """
        Validate and forward test command to ESP32.

        Flow:
          1. Parse + validate TestMovementRequest (Pydantic v2)
          2. Forward to ESP32's movement/test topic (ESP32 executes autonomously)
        """
        try:
            parsed = TestMovementRequest.model_validate(loads(payload))
        except Exception as exc:
            _LOGGER.warning("movement.command.invalid", extra={"error": str(exc)})
            await client.publish(
                self.settings.health_topic,
                dumps({"ok": False, "event": "invalid_command", "detail": str(exc)}),
                qos=self.settings.publish_qos,
                retain=False,
            )
            return

        _LOGGER.info(
            "movement.command.forwarding",
            extra={
                "command": parsed.command.value,
                "speed": parsed.speed,
                "request_id": parsed.request_id,
            },
        )

        # Forward to ESP32 (ESP32 publishes status updates to movement/status)
        payload_out = dumps(parsed.model_dump(mode="python"))
        await client.publish(self.settings.test_topic, payload_out, qos=self.settings.publish_qos)
