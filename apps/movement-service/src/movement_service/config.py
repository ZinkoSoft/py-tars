from __future__ import annotations

import os
from urllib.parse import urlparse

from pydantic import BaseModel, Field
from tars.contracts.v1.movement import (
    TOPIC_HEALTH_MOVEMENT_SERVICE,
    TOPIC_MOVEMENT_TEST,
)


class MovementSettings(BaseModel):
    """Environment-driven configuration for the movement service (command-based)."""

    mqtt_url: str = Field(default="mqtt://localhost:1883")
    test_topic: str = Field(default=TOPIC_MOVEMENT_TEST)
    health_topic: str = Field(default=TOPIC_HEALTH_MOVEMENT_SERVICE)
    publish_qos: int = Field(default=1, ge=0, le=2)

    @classmethod
    def from_env(cls) -> MovementSettings:
        data: dict[str, str | None] = {
            "mqtt_url": os.getenv("MQTT_URL"),
            "test_topic": os.getenv("MOVEMENT_TEST_TOPIC"),
            "health_topic": os.getenv("MOVEMENT_HEALTH_TOPIC"),
            "publish_qos": os.getenv("MOVEMENT_PUBLISH_QOS"),
        }
        filtered = {k: v for k, v in data.items() if v is not None}
        return cls.model_validate(filtered)

    def mqtt_connect_kwargs(self) -> dict[str, str | int | None]:
        """Return MQTT connection kwargs for asyncio-mqtt.Client."""
        parsed = urlparse(self.mqtt_url)
        kwargs: dict[str, str | int | None] = {
            "hostname": parsed.hostname or "127.0.0.1",
            "port": parsed.port or 1883,
        }
        if parsed.username:
            kwargs["username"] = parsed.username
        if parsed.password:
            kwargs["password"] = parsed.password
        return kwargs
