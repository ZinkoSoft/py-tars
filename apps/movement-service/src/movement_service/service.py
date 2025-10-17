from __future__ import annotations

import asyncio
import logging

from tars.adapters.mqtt_client import MQTTClient  # type: ignore[import]

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
        self.mqtt_client: MQTTClient | None = None

    async def run(self) -> None:
        """Run the movement service with reconnection backoff."""
        backoff = 1.0
        while True:
            _LOGGER.info("movement.mqtt.connect", extra={"mqtt_url": self.settings.mqtt_url})
            try:
                self.mqtt_client = MQTTClient(
                    self.settings.mqtt_url,
                    "tars-movement",
                    enable_health=True,
                )
                await self.mqtt_client.connect()
                _LOGGER.info("movement.mqtt.connected")
                
                await self._on_connect()
                backoff = 1.0
                await asyncio.Event().wait()  # Keep running
            except Exception as exc:
                _LOGGER.warning("movement.mqtt.disconnected", extra={"error": str(exc), "backoff": backoff})
                if self.mqtt_client:
                    await self.mqtt_client.shutdown()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 8.0)

    async def _on_connect(self) -> None:
        """Publish health and subscribe to test topic on connect."""
        assert self.mqtt_client is not None
        await self.mqtt_client.publish_health(ok=True, event="ready")
        await self.mqtt_client.subscribe(
            self.settings.test_topic,
            self._handle_test_command,
            qos=self.settings.publish_qos
        )
        _LOGGER.info("movement.subscribed", extra={"topic": self.settings.test_topic})

    async def _handle_test_command(self, payload: bytes) -> None:
        """
        Validate and forward test command to ESP32.

        Flow:
          1. Parse + validate TestMovementRequest (Pydantic v2)
          2. Forward to ESP32's movement/test topic (ESP32 executes autonomously)
        """
        assert self.mqtt_client is not None
        try:
            parsed = TestMovementRequest.model_validate(loads(payload))
        except Exception as exc:
            _LOGGER.warning("movement.command.invalid", extra={"error": str(exc)})
            await self.mqtt_client.publish_health(
                ok=False, event="invalid_command", err=str(exc)
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
        await self.mqtt_client.publish(
            self.settings.test_topic,
            payload_out,
            qos=self.settings.publish_qos
        )
