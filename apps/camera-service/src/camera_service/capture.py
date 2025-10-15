"""Camera capture and frame processing."""

import logging
import time

import cv2

logger = logging.getLogger("camera.capture")


class CameraCapture:
    """Handles OpenCV camera initialization and frame capture."""

    def __init__(self, device_index: int, width: int, height: int, fps: int):
        self.device_index = device_index
        self.width = width
        self.height = height
        self.fps = fps
        self.camera: cv2.VideoCapture | None = None
        self.backend: str | None = None
        self.consecutive_failures = 0
        self.last_successful_frame_time: float | None = None

    def open(self) -> None:
        """Open camera with V4L2 backend, fallback to default."""
        try:
            logger.info(f"Opening camera device index: {self.device_index}")

            # Try V4L2 backend first (Linux, more reliable)
            self.camera = cv2.VideoCapture(self.device_index, cv2.CAP_V4L2)
            if self.camera and self.camera.isOpened():
                self._configure_camera("opencv_v4l2")
                return

            # Fallback to default backend
            if self.camera:
                self.camera.release()

            logger.warning(f"V4L2 failed for device {self.device_index}, trying default backend")
            self.camera = cv2.VideoCapture(self.device_index)
            if self.camera and self.camera.isOpened():
                self._configure_camera("opencv_default")
                return

            raise RuntimeError(f"Failed to open camera device {self.device_index}")

        except Exception as e:
            self._cleanup()
            raise RuntimeError(f"Camera initialization failed: {e}") from e

    def _configure_camera(self, backend: str) -> None:
        """Configure camera properties and verify settings."""
        if not self.camera:
            return

        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.camera.set(cv2.CAP_PROP_FPS, self.fps)
        self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize latency

        # Verify applied settings
        actual_width = self.camera.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_height = self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT)
        actual_fps = self.camera.get(cv2.CAP_PROP_FPS)

        self.backend = backend
        logger.info(
            f"Camera {self.device_index} opened with {backend}: "
            f"{actual_width}x{actual_height} @ {actual_fps}fps"
        )

    def capture_frame(self, max_retries: int = 3) -> bytes | None:
        """
        Capture a single frame and return as RGB numpy array.

        Returns None on failure after retries.
        """
        if not self.camera:
            return None

        for attempt in range(max_retries):
            try:
                ret, frame = self.camera.read()
                if ret and frame is not None:
                    self.consecutive_failures = 0
                    self.last_successful_frame_time = time.time()
                    # Convert BGR to RGB
                    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                logger.debug(f"Capture attempt {attempt + 1}/{max_retries} failed")
                time.sleep(0.05)  # Brief pause before retry

            except Exception as e:
                logger.warning(f"Capture attempt {attempt + 1} exception: {e}")
                time.sleep(0.05)

        self.consecutive_failures += 1
        return None

    def needs_reconnect(self, threshold: int = 30) -> bool:
        """Check if consecutive failures exceed threshold (requires reconnect)."""
        return self.consecutive_failures >= threshold

    def close(self) -> None:
        """Release camera resources."""
        self._cleanup()

    def _cleanup(self) -> None:
        """Internal cleanup helper."""
        if self.camera:
            try:
                self.camera.release()
            except Exception as e:
                logger.error(f"Error releasing camera: {e}")
            self.camera = None
        self.backend = None
