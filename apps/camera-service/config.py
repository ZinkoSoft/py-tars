"""Camera service configuration from environment variables."""
import os
from dataclasses import dataclass


@dataclass
class CameraConfig:
    """Camera hardware and capture settings."""
    device_index: int
    width: int
    height: int
    fps: int
    quality: int  # JPEG quality 1-100
    rotation: int  # 0, 90, 180, 270
    timeout_ms: int  # V4L2 capture timeout
    retry_attempts: int
    mqtt_rate: int  # Publish every N frames


@dataclass
class MQTTConfig:
    """MQTT connection settings."""
    url: str
    frame_topic: str
    health_topic: str


@dataclass
class HTTPConfig:
    """HTTP streaming server settings."""
    host: str
    port: int


@dataclass
class ServiceConfig:
    """Complete camera service configuration."""
    enabled: bool
    camera: CameraConfig
    mqtt: MQTTConfig
    http: HTTPConfig
    log_level: str


def load_config() -> ServiceConfig:
    """Load configuration from environment variables."""
    camera = CameraConfig(
        device_index=int(os.getenv("CAMERA_DEVICE_INDEX", "0")),
        width=int(os.getenv("CAMERA_WIDTH", "640")),
        height=int(os.getenv("CAMERA_HEIGHT", "480")),
        fps=int(os.getenv("CAMERA_FPS", "10")),
        quality=int(os.getenv("CAMERA_QUALITY", "80")),
        rotation=int(os.getenv("CAMERA_ROTATION", "0")),
        timeout_ms=int(os.getenv("CAMERA_TIMEOUT_MS", "5000")),
        retry_attempts=int(os.getenv("CAMERA_RETRY_ATTEMPTS", "3")),
        mqtt_rate=int(os.getenv("CAMERA_MQTT_RATE", "2")),
    )

    mqtt = MQTTConfig(
        url=os.getenv("MQTT_URL", "mqtt://tars:pass@127.0.0.1:1883"),
        frame_topic=os.getenv("CAMERA_FRAME_TOPIC", "camera/frame"),
        health_topic="system/health/camera",
    )

    http = HTTPConfig(
        host=os.getenv("CAMERA_HTTP_HOST", "0.0.0.0"),
        port=int(os.getenv("CAMERA_HTTP_PORT", "8080")),
    )

    return ServiceConfig(
        enabled=os.getenv("CAMERA_ENABLED", "1").lower() in ("1", "true", "yes", "on"),
        camera=camera,
        mqtt=mqtt,
        http=http,
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
