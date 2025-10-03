"""Camera service orchestration."""
import asyncio
import io
import logging
import time
from typing import Optional

from PIL import Image

from .capture import CameraCapture
from .config import ServiceConfig
from .mqtt_client import MQTTPublisher
from .streaming import StreamingServer


logger = logging.getLogger("camera.service")


class CameraService:
    """Orchestrates camera capture, MQTT publishing, and HTTP streaming."""

    def __init__(self, config: ServiceConfig):
        self.cfg = config
        self.running = False
        self.frame_count = 0
        
        # Components
        self.camera: Optional[CameraCapture] = None
        self.mqtt: Optional[MQTTPublisher] = None
        self.http: Optional[StreamingServer] = None

    async def start(self) -> None:
        """Initialize all components and start capture loop."""
        try:
            # Initialize MQTT
            self.mqtt = MQTTPublisher(
                self.cfg.mqtt.url,
                self.cfg.mqtt.frame_topic,
                self.cfg.mqtt.health_topic,
            )
            self.mqtt.connect()

            # Initialize camera
            self.camera = CameraCapture(
                self.cfg.camera.device_index,
                self.cfg.camera.width,
                self.cfg.camera.height,
                self.cfg.camera.fps,
            )
            self.camera.open()

            # Initialize HTTP streaming
            self.http = StreamingServer(
                self.cfg.http.host,
                self.cfg.http.port,
                self.cfg.camera.fps,
            )
            self.http.start()

            # Publish health
            self.mqtt.publish_health(True, "started")

            self.running = True
            logger.info(
                f"Camera service started: {self.cfg.camera.width}x{self.cfg.camera.height} "
                f"@ {self.cfg.camera.fps}fps, device {self.cfg.camera.device_index}, "
                f"backend {self.camera.backend}, HTTP on {self.cfg.http.host}:{self.cfg.http.port}"
            )

            # Run capture loop
            await self._capture_loop()

        except Exception as e:
            logger.error(f"Failed to start camera service: {e}")
            if self.mqtt:
                self.mqtt.publish_health(False, str(e))
            raise

    def stop(self) -> None:
        """Stop service and cleanup resources."""
        self.running = False

        if self.camera:
            self.camera.close()

        if self.mqtt:
            self.mqtt.publish_health(False, "stopped")
            self.mqtt.disconnect()

        logger.info("Camera service stopped")

    async def _capture_loop(self) -> None:
        """Main capture loop with frame processing and publishing."""
        frame_interval = 1.0 / self.cfg.camera.fps
        mqtt_frame_interval = (
            self.cfg.camera.fps // self.cfg.camera.mqtt_rate
            if self.cfg.camera.mqtt_rate > 0
            else self.cfg.camera.fps
        )
        frame_counter = 0

        while self.running:
            try:
                start_time = time.time()

                # Capture frame
                frame_rgb = self.camera.capture_frame(self.cfg.camera.retry_attempts)

                if frame_rgb is None:
                    logger.warning(
                        f"Failed to capture frame after {self.cfg.camera.retry_attempts} attempts "
                        f"(consecutive failures: {self.camera.consecutive_failures})"
                    )

                    # Reconnect if too many failures
                    if self.camera.needs_reconnect(threshold=30):
                        logger.error("Too many failures, reconnecting camera...")
                        await self._reconnect_camera()

                    await asyncio.sleep(0.1)
                    continue

                # Convert to JPEG
                jpeg_data = self._encode_jpeg(frame_rgb, self.cfg.camera.quality)

                # Update HTTP stream
                self.http.update_frame(jpeg_data)

                frame_counter += 1

                # Publish to MQTT at reduced rate
                if frame_counter % mqtt_frame_interval == 0:
                    self.mqtt.publish_frame(
                        jpeg_data,
                        self.cfg.camera.width,
                        self.cfg.camera.height,
                        self.cfg.camera.quality,
                        self.cfg.camera.mqtt_rate,
                        self.camera.backend,
                        self.camera.consecutive_failures,
                    )
                    logger.debug(f"Published frame {frame_counter} to MQTT")

                self.frame_count += 1

                # Log stats every 100 frames
                if self.frame_count % 100 == 0:
                    actual_fps = 100 / (time.time() - (start_time - 99 * frame_interval))
                    logger.debug(
                        f"Processed {self.frame_count} frames, ~{actual_fps:.1f} fps, "
                        f"backend: {self.camera.backend}, failures: {self.camera.consecutive_failures}"
                    )

                # Maintain frame rate
                elapsed = time.time() - start_time
                sleep_time = max(0, frame_interval - elapsed)
                await asyncio.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Error in capture loop: {e}")
                self.mqtt.publish_health(False, str(e))
                await asyncio.sleep(1.0)

    def _encode_jpeg(self, frame_rgb, quality: int) -> bytes:
        """Encode RGB frame as JPEG bytes."""
        img = Image.fromarray(frame_rgb)
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=quality, optimize=True)
        return buffer.getvalue()

    async def _reconnect_camera(self) -> None:
        """Attempt camera reconnection after failures."""
        logger.info("Attempting camera reconnection...")
        try:
            self.camera.close()
            await asyncio.sleep(0.5)  # Cleanup pause

            self.camera.open()
            logger.info(f"Camera reconnected with backend: {self.camera.backend}")
            self.mqtt.publish_health(True, "reconnected")
        except Exception as e:
            logger.error(f"Camera reconnection failed: {e}")
            self.mqtt.publish_health(False, f"reconnection_failed: {e}")
