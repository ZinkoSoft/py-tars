"""MQTT client for camera frame publishing."""

import base64
import logging
import time
from urllib.parse import urlparse

import orjson
import paho.mqtt.client as mqtt

logger = logging.getLogger("camera.mqtt")


class MQTTPublisher:
    """MQTT client for publishing frames and health status."""

    def __init__(self, url: str, frame_topic: str, health_topic: str):
        self.frame_topic = frame_topic
        self.health_topic = health_topic
        self.client = mqtt.Client()
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

        # Parse MQTT URL
        u = urlparse(url)
        self.host = u.hostname or "127.0.0.1"
        self.port = u.port or 1883
        if u.username and u.password:
            self.client.username_pw_set(u.username, u.password)

    def connect(self) -> None:
        """Connect to MQTT broker and start loop."""
        self.client.connect(self.host, self.port)
        self.client.loop_start()
        logger.info(f"MQTT client connecting to {self.host}:{self.port}")

    def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting MQTT: {e}")

    def publish_frame(
        self,
        jpeg_data: bytes,
        width: int,
        height: int,
        quality: int,
        mqtt_rate: int,
        backend: str | None,
        consecutive_failures: int,
    ) -> None:
        """Publish frame to MQTT (base64 encoded)."""
        frame_b64 = base64.b64encode(jpeg_data).decode("ascii")

        payload = {
            "frame": frame_b64,
            "timestamp": time.time(),
            "width": width,
            "height": height,
            "quality": quality,
            "mqtt_rate": mqtt_rate,
            "backend": backend,
            "consecutive_failures": consecutive_failures,
        }

        try:
            self.client.publish(self.frame_topic, orjson.dumps(payload), qos=0)
        except Exception as e:
            logger.error(f"Failed to publish frame: {e}")

    def publish_health(self, ok: bool, event: str = "") -> None:
        """Publish health status (retained)."""
        payload = {
            "ok": ok,
            "event": event or ("started" if ok else "error"),
            "timestamp": time.time(),
        }

        try:
            self.client.publish(self.health_topic, orjson.dumps(payload), qos=1, retain=True)
        except Exception as e:
            logger.error(f"Failed to publish health: {e}")

    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connect callback."""
        if rc == 0:
            logger.info("Connected to MQTT broker")
        else:
            logger.error(f"MQTT connection failed: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnect callback."""
        logger.warning(f"MQTT disconnected: {rc}")
