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
CAMERA_DEVICE_INDEX = int(os.getenv("CAMERA_DEVICE_INDEX", "0"))  # Camera device index (0, 1, 2, etc.)
CAMERA_WIDTH = int(os.getenv("CAMERA_WIDTH", "640"))
CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "480"))
CAMERA_FPS = int(os.getenv("CAMERA_FPS", "10"))
CAMERA_QUALITY = int(os.getenv("CAMERA_QUALITY", "80"))  # JPEG quality 1-100
CAMERA_ROTATION = int(os.getenv("CAMERA_ROTATION", "0"))  # 0, 90, 180, 270
CAMERA_TIMEOUT_MS = int(os.getenv("CAMERA_TIMEOUT_MS", "5000"))  # V4L2 capture timeout in ms
CAMERA_RETRY_ATTEMPTS = int(os.getenv("CAMERA_RETRY_ATTEMPTS", "3"))  # Retry attempts on capture failure
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
        self.backend = None  # Track which backend is being used
        self.consecutive_failures = 0  # Track consecutive capture failures
        self.last_successful_frame_time = None  # Track last successful frame

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
            logger.info(f"Camera service started: {CAMERA_WIDTH}x{CAMERA_HEIGHT} @ {CAMERA_FPS}fps, device {CAMERA_DEVICE_INDEX}, backend {self.backend}, HTTP on {HTTP_HOST}:{HTTP_PORT}")

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
        """Setup OpenCV camera capture with configurable device index and V4L2 backend"""
        try:
            # Use device index from config
            device_index = CAMERA_DEVICE_INDEX
            logger.info(f"Attempting to open camera device index: {device_index}")

            # Try with V4L2 backend first (Linux specific, more reliable)
            self.camera = cv2.VideoCapture(device_index, cv2.CAP_V4L2)
            if self.camera is not None and self.camera.isOpened():
                # Set camera properties
                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
                self.camera.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
                
                # Set timeout for V4L2 capture to avoid blocking
                self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize buffer to reduce latency
                
                # Verify settings were applied
                actual_width = self.camera.get(cv2.CAP_PROP_FRAME_WIDTH)
                actual_height = self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT)
                actual_fps = self.camera.get(cv2.CAP_PROP_FPS)
                
                self.backend = "opencv_v4l2"
                logger.info(f"Camera {device_index} opened with V4L2 backend: {actual_width}x{actual_height} @ {actual_fps}fps")
                return self.camera
            else:
                if self.camera is not None:
                    self.camera.release()
                self.camera = None
                
                # Fallback: try without specifying backend
                logger.warning(f"V4L2 backend failed for device {device_index}, trying default backend")
                self.camera = cv2.VideoCapture(device_index)
                if self.camera is not None and self.camera.isOpened():
                    # Set camera properties
                    self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
                    self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
                    self.camera.set(cv2.CAP_PROP_FPS, CAMERA_FPS)
                    self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    
                    # Verify settings were applied
                    actual_width = self.camera.get(cv2.CAP_PROP_FRAME_WIDTH)
                    actual_height = self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT)
                    actual_fps = self.camera.get(cv2.CAP_PROP_FPS)
                    
                    self.backend = "opencv_default"
                    logger.info(f"Camera {device_index} opened with default backend: {actual_width}x{actual_height} @ {actual_fps}fps")
                    return self.camera
                else:
                    if self.camera is not None:
                        self.camera.release()
                    self.camera = None
                    self.backend = None
                    
        except Exception as e:
            logger.error(f"Failed to setup camera device {device_index}: {e}")
            if self.camera is not None:
                try:
                    self.camera.release()
                except:
                    pass
            self.camera = None
            self.backend = None
        
        raise RuntimeError(f"No camera device found at index {device_index}")

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
        """Main capture and publish loop with robust error handling"""
        import io
        from PIL import Image

        frame_interval = 1.0 / CAMERA_FPS
        mqtt_frame_interval = CAMERA_FPS // CAMERA_MQTT_RATE if CAMERA_MQTT_RATE > 0 else CAMERA_FPS
        frame_counter = 0

        while self.running:
            try:
                start_time = time.time()

                # Capture frame with retry logic
                ret, frame = None, None
                for attempt in range(CAMERA_RETRY_ATTEMPTS):
                    try:
                        ret, frame = self.camera.read()
                        if ret and frame is not None:
                            # Reset failure counter on successful capture
                            self.consecutive_failures = 0
                            self.last_successful_frame_time = time.time()
                            break
                        else:
                            if attempt < CAMERA_RETRY_ATTEMPTS - 1:
                                logger.debug(f"Capture attempt {attempt + 1} failed, retrying...")
                                await asyncio.sleep(0.05)  # Brief pause before retry
                    except Exception as e:
                        logger.warning(f"Capture attempt {attempt + 1} exception: {e}")
                        if attempt < CAMERA_RETRY_ATTEMPTS - 1:
                            await asyncio.sleep(0.05)

                if not ret or frame is None:
                    self.consecutive_failures += 1
                    logger.warning(f"Failed to capture frame after {CAMERA_RETRY_ATTEMPTS} attempts (consecutive failures: {self.consecutive_failures})")
                    
                    # If we have too many consecutive failures, try to reconnect camera
                    if self.consecutive_failures >= 30:  # ~3 seconds at 10fps
                        logger.error("Too many consecutive capture failures, attempting camera reconnection...")
                        await self._reconnect_camera()
                        self.consecutive_failures = 0
                    
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
                        "mqtt_rate": CAMERA_MQTT_RATE,
                        "backend": self.backend,
                        "consecutive_failures": self.consecutive_failures
                    }

                    self.mqtt_client.publish(CAMERA_FRAME_TOPIC, orjson.dumps(payload), qos=0)
                    logger.debug(f"Published frame {frame_counter} to MQTT")

                self.frame_count += 1

                # Log frame rate every 100 frames (include failure info)
                if self.frame_count % 100 == 0:
                    actual_fps = 100 / (time.time() - (start_time - 99 * frame_interval))
                    logger.debug(f"Processed {self.frame_count} frames, ~{actual_fps:.1f} fps, backend: {self.backend}, failures: {self.consecutive_failures}")

                # Maintain frame rate
                elapsed = time.time() - start_time
                sleep_time = max(0, frame_interval - elapsed)
                await asyncio.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Error in capture loop: {e}")
                self._publish_health(False, str(e))
                await asyncio.sleep(1.0)

    async def _reconnect_camera(self):
        """Attempt to reconnect the camera after failures"""
        logger.info("Attempting camera reconnection...")
        try:
            if self.camera:
                self.camera.release()
                await asyncio.sleep(0.5)  # Give time for cleanup
            
            self.camera = self._setup_camera()
            logger.info(f"Camera reconnected successfully with backend: {self.backend}")
            self._publish_health(True, "reconnected")
        except Exception as e:
            logger.error(f"Camera reconnection failed: {e}")
            self._publish_health(False, f"reconnection_failed: {e}")

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