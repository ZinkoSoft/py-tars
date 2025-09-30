#!/usr/bin/env python3
"""
Camera Service for TARS

Captures video from camera and provides MJPEG streaming over HTTP.
Publishes occasional frames to MQTT for monitoring/debugging.
Optimized for mobile robot use cases with configurable frame rates and quality.
"""

import sys
import os
# Add system dist-packages to path for libcamera BEFORE any imports that use it
sys.path.insert(0, '/usr/lib/python3/dist-packages')

import asyncio
import logging
import signal
import time
import threading
from typing import Optional

import orjson
import cv2
from flask import Flask, Response
import paho.mqtt.client as mqtt

# Configuration from environment
MQTT_URL = os.getenv("MQTT_URL", "mqtt://tars:pass@127.0.0.1:1883")
CAMERA_FRAME_TOPIC = os.getenv("CAMERA_FRAME_TOPIC", "camera/frame")
CAMERA_WIDTH = int(os.getenv("CAMERA_WIDTH", "640"))
CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "480"))
CAMERA_FPS = int(os.getenv("CAMERA_FPS", "10"))
CAMERA_QUALITY = int(os.getenv("CAMERA_QUALITY", "80"))  # JPEG quality 1-100
CAMERA_ROTATION = int(os.getenv("CAMERA_ROTATION", "0"))  # 0, 90, 180, 270
# MQTT rate limiting - publish to MQTT only every Nth frame to reduce noise
CAMERA_MQTT_RATE = int(os.getenv("CAMERA_MQTT_RATE", "2"))  # Publish to MQTT every 2 seconds worth of frames
# HTTP streaming configuration
HTTP_HOST = os.getenv("CAMERA_HTTP_HOST", "0.0.0.0")
HTTP_PORT = int(os.getenv("CAMERA_HTTP_PORT", "8080"))

# Health check topic
HEALTH_TOPIC = "system/health/camera"

logger = logging.getLogger("camera-service")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

class CameraService:
    def __init__(self):
        self.mqtt_client: Optional[mqtt.Client] = None
        self.camera: Optional[cv2.VideoCapture] = None
        self.flask_app: Optional[Flask] = None
        self.running = False
        self.frame_count = 0
        self.latest_frame = None
        self.frame_lock = threading.Lock()

    async def start(self):
        """Initialize camera, MQTT, and HTTP server, then start streaming"""
        try:
            # Initialize MQTT
            self.mqtt_client = self._setup_mqtt()
            host, port, username, password = self._parse_mqtt_url(MQTT_URL)
            if username and password:
                self.mqtt_client.username_pw_set(username, password)
            self.mqtt_client.connect(host, port)
            self.mqtt_client.loop_start()

            # Initialize camera
            self.camera = self._setup_camera()

            # Initialize Flask app
            self.flask_app = self._setup_flask()

            # Publish health status
            self._publish_health(True)

            self.running = True
            logger.info(f"Camera service started: {CAMERA_WIDTH}x{CAMERA_HEIGHT} @ {CAMERA_FPS}fps, HTTP on {HTTP_HOST}:{HTTP_PORT}")

            # Start HTTP server in background thread
            http_thread = threading.Thread(target=self._run_flask, daemon=True)
            http_thread.start()

            # Start capture loop
            await self._capture_loop()

        except Exception as e:
            logger.error(f"Failed to start camera service: {e}")
            self._publish_health(False, str(e))
            raise

    def stop(self):
        """Stop camera and cleanup"""
        self.running = False

        if self.camera:
            try:
                self.camera.release()
            except Exception as e:
                logger.error(f"Error stopping camera: {e}")

        if self.mqtt_client:
            try:
                self._publish_health(False, "stopped")
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception as e:
                logger.error(f"Error stopping MQTT: {e}")

        logger.info("Camera service stopped")

    def _setup_mqtt(self) -> mqtt.Client:
        """Setup MQTT client"""
        client = mqtt.Client()
        client.on_connect = self._on_mqtt_connect
        client.on_disconnect = self._on_mqtt_disconnect
        return client

    def _parse_mqtt_url(self, url: str) -> tuple:
        """Parse MQTT URL into host, port, username, password"""
        from urllib.parse import urlparse
        u = urlparse(url)
        return u.hostname or "127.0.0.1", u.port or 1883, u.username, u.password

    def _setup_camera(self):
        """Setup OpenCV camera capture"""
        # Try different camera indices
        for camera_index in [0, 1, 2]:
            try:
                cap = cv2.VideoCapture(camera_index)
                if cap.isOpened():
                    # Set camera properties
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
                    cap.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
                    
                    # Verify settings were applied
                    actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                    actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                    actual_fps = cap.get(cv2.CAP_PROP_FPS)
                    
                    logger.info(f"Camera {camera_index}: {actual_width}x{actual_height} @ {actual_fps}fps")
                    return cap
                else:
                    cap.release()
            except Exception as e:
                logger.warning(f"Failed to open camera {camera_index}: {e}")
                continue
        
        raise RuntimeError("No camera device found or accessible")

    def _setup_flask(self) -> Flask:
        """Setup Flask app for MJPEG streaming"""
        app = Flask(__name__)

        @app.route('/stream')
        def stream():
            """MJPEG stream endpoint"""
            return Response(
                self._generate_frames(),
                mimetype='multipart/x-mixed-replace; boundary=frame'
            )

        @app.route('/snapshot')
        def snapshot():
            """Single frame snapshot"""
            with self.frame_lock:
                if self.latest_frame:
                    return Response(self.latest_frame, mimetype='image/jpeg')
                else:
                    return Response("No frame available", status=503)

        return app

    def _run_flask(self):
        """Run Flask app in background thread"""
        try:
            self.flask_app.run(host=HTTP_HOST, port=HTTP_PORT, threaded=True)
        except Exception as e:
            logger.error(f"Flask server error: {e}")

    def _generate_frames(self):
        """Generator for MJPEG stream"""
        while self.running:
            with self.frame_lock:
                if self.latest_frame:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n'
                           b'\r\n' +
                           self.latest_frame + b'\r\n')
            time.sleep(1.0 / CAMERA_FPS)  # Throttle to target FPS

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT connect callback"""
        if rc == 0:
            logger.info("Connected to MQTT broker")
        else:
            logger.error(f"MQTT connection failed: {rc}")

    def _on_mqtt_disconnect(self, client, userdata, rc):
        """MQTT disconnect callback"""
        logger.warning(f"MQTT disconnected: {rc}")

    def _publish_health(self, ok: bool, error: str = ""):
        """Publish health status"""
        if not self.mqtt_client:
            return

        payload = {
            "ok": ok,
            "event": error or ("started" if ok else "error"),
            "timestamp": time.time()
        }

        try:
            self.mqtt_client.publish(HEALTH_TOPIC, orjson.dumps(payload), qos=1, retain=True)
        except Exception as e:
            logger.error(f"Failed to publish health: {e}")

    async def _capture_loop(self):
        """Main capture and publish loop"""
        import io
        from PIL import Image

        frame_interval = 1.0 / CAMERA_FPS
        mqtt_frame_interval = CAMERA_FPS // CAMERA_MQTT_RATE if CAMERA_MQTT_RATE > 0 else CAMERA_FPS
        frame_counter = 0

        while self.running:
            try:
                start_time = time.time()

                # Capture frame
                ret, frame = self.camera.read()
                if not ret:
                    logger.warning("Failed to capture frame")
                    await asyncio.sleep(0.1)
                    continue

                # Convert BGR to RGB
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Convert to JPEG
                img = Image.fromarray(frame)
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=CAMERA_QUALITY, optimize=True)
                jpeg_data = buffer.getvalue()

                # Store latest frame for HTTP streaming
                with self.frame_lock:
                    self.latest_frame = jpeg_data

                frame_counter += 1

                # Publish to MQTT at reduced rate to avoid noise
                if frame_counter % mqtt_frame_interval == 0:
                    # Encode as base64 for MQTT transport (only for occasional frames)
                    import base64
                    frame_b64 = base64.b64encode(jpeg_data).decode('ascii')

                    # Publish frame to MQTT (low frequency for monitoring/debugging)
                    payload = {
                        "frame": frame_b64,
                        "timestamp": time.time(),
                        "width": CAMERA_WIDTH,
                        "height": CAMERA_HEIGHT,
                        "quality": CAMERA_QUALITY,
                        "mqtt_rate": CAMERA_MQTT_RATE
                    }

                    self.mqtt_client.publish(CAMERA_FRAME_TOPIC, orjson.dumps(payload), qos=0)
                    logger.debug(f"Published frame {frame_counter} to MQTT")

                # TODO: Send high-frequency frames via WebSocket endpoint
                # For now, we'll implement MJPEG over HTTP as a simpler alternative

                self.frame_count += 1

                # Log frame rate every 100 frames
                if self.frame_count % 100 == 0:
                    actual_fps = 100 / (time.time() - (start_time - 99 * frame_interval))
                    logger.info(f"Processed {self.frame_count} frames, ~{actual_fps:.1f} fps, MQTT rate: {CAMERA_MQTT_RATE} fps")

                # Maintain frame rate
                elapsed = time.time() - start_time
                sleep_time = max(0, frame_interval - elapsed)
                await asyncio.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Error in capture loop: {e}")
                self._publish_health(False, str(e))
                await asyncio.sleep(1.0)

async def main():
    """Main entry point"""
    service = CameraService()

    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        service.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        await service.start()
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()

if __name__ == "__main__":
    asyncio.run(main())