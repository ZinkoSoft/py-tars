"""MJPEG HTTP streaming server."""

import logging
import threading
import time

from flask import Flask, Response

logger = logging.getLogger("camera.http")


class StreamingServer:
    """Flask-based MJPEG streaming server."""

    def __init__(self, host: str, port: int, fps: int):
        self.host = host
        self.port = port
        self.fps = fps
        self.latest_frame: bytes | None = None
        self.frame_lock = threading.Lock()
        self.flask_app = self._create_app()
        self.server_thread: threading.Thread | None = None

    def _create_app(self) -> Flask:
        """Create Flask application with routes."""
        app = Flask(__name__)

        @app.route("/stream")
        def stream():
            """MJPEG stream endpoint."""
            return Response(
                self._generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame"
            )

        @app.route("/snapshot")
        def snapshot():
            """Single frame snapshot endpoint."""
            with self.frame_lock:
                if self.latest_frame:
                    return Response(self.latest_frame, mimetype="image/jpeg")
                return Response("No frame available", status=503)

        return app

    def _generate_frames(self):
        """Generator for MJPEG stream."""
        while True:
            with self.frame_lock:
                if self.latest_frame:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"\r\n" + self.latest_frame + b"\r\n"
                    )
            time.sleep(1.0 / self.fps)  # Throttle to target FPS

    def update_frame(self, jpeg_data: bytes) -> None:
        """Update the latest frame for streaming."""
        with self.frame_lock:
            self.latest_frame = jpeg_data

    def start(self) -> None:
        """Start HTTP server in background thread."""
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        logger.info(f"HTTP streaming server started on {self.host}:{self.port}")

    def _run_server(self) -> None:
        """Run Flask server (called in background thread)."""
        try:
            self.flask_app.run(
                host=self.host, port=self.port, threaded=True, debug=False, use_reloader=False
            )
        except Exception as e:
            logger.error(f"HTTP server error: {e}")
