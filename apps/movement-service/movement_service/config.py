from __future__ import annotations

import os
from urllib.parse import urlparse

from pydantic import BaseModel, Field


class MovementSettings(BaseModel):
    """Environment-driven configuration for the movement service."""

    mqtt_url: str = Field(default="mqtt://localhost:1883")
    command_topic: str = Field(default="movement/command")
    frame_topic: str = Field(default="movement/frame")
    state_topic: str = Field(default="movement/state")
    health_topic: str = Field(default="system/health/movement-service")
    calibration_path: str | None = Field(default=None)
    publish_qos: int = Field(default=1, ge=0, le=2)
    frame_backoff_ms: int = Field(default=40, ge=0, le=500)

    @classmethod
    def from_env(cls) -> "MovementSettings":
        data: dict[str, str | None] = {
            "mqtt_url": os.getenv("MQTT_URL"),
            "command_topic": os.getenv("MOVEMENT_COMMAND_TOPIC"),
            "frame_topic": os.getenv("MOVEMENT_FRAME_TOPIC"),
            "state_topic": os.getenv("MOVEMENT_STATE_TOPIC"),
            "health_topic": os.getenv("MOVEMENT_HEALTH_TOPIC"),
            "calibration_path": os.getenv("MOVEMENT_CALIBRATION_PATH"),
            "publish_qos": os.getenv("MOVEMENT_PUBLISH_QOS"),
            "frame_backoff_ms": os.getenv("MOVEMENT_FRAME_BACKOFF_MS"),
        }
        filtered = {k: v for k, v in data.items() if v is not None}
        return cls.model_validate(filtered)

    def mqtt_connect_kwargs(self) -> dict[str, str | int | None]:
        parsed = urlparse(self.mqtt_url)
        return {
            "hostname": parsed.hostname or "127.0.0.1",
            "port": parsed.port or 1883,
            "username": parsed.username,
            "password": parsed.password,
        }
