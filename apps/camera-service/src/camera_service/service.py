"""Camera service orchestration."""

import asyncio
import base64
import io
import logging
import time

from PIL import Image
from tars.adapters.mqtt_client import MQTTClient  # type: ignore[import]
from tars.contracts.v1.camera import CameraFrame  # type: ignore[import]

from .capture import CameraCapture
from .config import ServiceConfig
from .streaming import StreamingServer

logger = logging.getLogger("camera.service")


class CameraService:
    """Orchestrates camera capture, MQTT publishing, and HTTP streaming."""

    def __init__(self, config: ServiceConfig):
        self.cfg = config
        self.running = False
        self.frame_count = 0

        # Components
        self.camera: CameraCapture | None = None
        self.mqtt: MQTTClient | None = None
        self.http: StreamingServer | None = None

    async def start(self) -> None:
        """Initialize all components with automatic MQTT reconnection."""
        backoff = 1.0
        max_backoff = 30.0
        
        # Initialize camera and HTTP once (outside reconnection loop)
        try:
            self.camera = CameraCapture(
                self.cfg.camera.device_index,
                self.cfg.camera.width,
                self.cfg.camera.height,
                self.cfg.camera.fps,
            )
            self.camera.open()

            self.http = StreamingServer(
                self.cfg.http.host,
                self.cfg.http.port,
                self.cfg.camera.fps,
            )
            self.http.start()
            
            logger.info(
                f"Camera hardware initialized: {self.cfg.camera.width}x{self.cfg.camera.height} "
                f"@ {self.cfg.camera.fps}fps, device {self.cfg.camera.device_index}, "
                f"backend {self.camera.backend}, HTTP on {self.cfg.http.host}:{self.cfg.http.port}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize camera hardware: {e}")
            raise
        
        # MQTT reconnection loop
        while self.running or not self.running:  # Run until explicitly stopped
            try:
                # Initialize MQTT
                self.mqtt = MQTTClient(
                    self.cfg.mqtt.url,
                    client_id="tars-camera",
                    enable_health=True,
                    enable_heartbeat=True,
                )
                await self.mqtt.connect()

                # Centralized client handles health automatically on connect
                logger.info("Camera service MQTT connected - health published automatically")

                self.running = True
                
                # Reset backoff on successful connection
                backoff = 1.0

                # Run capture loop and wait for disconnect
                capture_task = asyncio.create_task(self._capture_loop())
                disconnect_task = asyncio.create_task(self.mqtt.wait_for_disconnect())
                
                # Wait for either task to complete
                done, pending = await asyncio.wait(
                    [capture_task, disconnect_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Cancel pending task
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                
                # Re-raise exception from completed task if any
                for task in done:
                    if not task.cancelled():
                        task.result()  # This will raise if there was an exception

            except asyncio.CancelledError:
                logger.info("Camera service shutdown requested")
                raise
            except Exception as e:
                logger.warning(f"Camera MQTT disconnected: {e}; reconnecting in {backoff:.1f}s...")
            finally:
                if self.mqtt:
                    await self.mqtt.shutdown()
                    self.mqtt = None
            
            # Exponential backoff before reconnect
            if self.running:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, max_backoff)
            else:
                break

    async def stop(self) -> None:
        """Stop service and cleanup resources."""
        self.running = False

        if self.camera:
            self.camera.close()

        if self.mqtt:
            await self.mqtt.shutdown()

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
                    await self._publish_frame(
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
                # Centralized client will handle health publishing on errors
                await asyncio.sleep(1.0)

    async def _publish_frame(
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

        frame = CameraFrame(
            frame_data=frame_b64,
            format="jpeg",
            width=width,
            height=height,
            frame_number=self.frame_count,
            fps=mqtt_rate if mqtt_rate > 0 else None,
        )

        try:
            await self.mqtt.publish_event(
                topic=self.cfg.mqtt.frame_topic,
                event_type="camera.frame",
                data=frame,
                qos=0,
            )
        except Exception as e:
            logger.error(f"Failed to publish frame: {e}")

    def _encode_jpeg(self, frame_rgb, quality: int) -> bytes:
        """Encode RGB frame as JPEG bytes."""
        img = Image.fromarray(frame_rgb)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        return buffer.getvalue()

    async def _reconnect_camera(self) -> None:
        """Attempt camera reconnection after failures."""
        logger.info("Attempting camera reconnection...")
        try:
            self.camera.close()
            await asyncio.sleep(0.5)  # Cleanup pause

            self.camera.open()
            logger.info(f"Camera reconnected with backend: {self.camera.backend}")
            # Centralized client will handle health updates automatically
        except Exception as e:
            logger.error(f"Camera reconnection failed: {e}")
            # Errors will be reflected in health status automatically
