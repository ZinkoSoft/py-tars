"""
Shared pytest fixtures for camera-service tests.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
async def mock_mqtt_client():
    """Mock MQTT client for testing."""
    client = AsyncMock()
    client.publish = AsyncMock()
    client.subscribe = AsyncMock()
    return client


@pytest.fixture
def mock_camera_device():
    """Mock camera device for testing."""
    camera = MagicMock()
    camera.isOpened.return_value = True
    camera.read.return_value = (True, None)  # Success, no frame data
    camera.release = MagicMock()
    return camera


@pytest.fixture
def camera_config():
    """Provide default camera configuration."""
    from camera_service.config import CameraConfig, HTTPConfig, MQTTConfig, ServiceConfig

    return ServiceConfig(
        enabled=True,
        camera=CameraConfig(
            device_index=0,
            width=640,
            height=480,
            fps=10,
            quality=80,
            rotation=0,
            timeout_ms=5000,
            retry_attempts=3,
            mqtt_rate=2,
        ),
        mqtt=MQTTConfig(
            url="mqtt://test:test@localhost:1883",
            frame_topic="camera/frame",
            health_topic="system/health/camera",
        ),
        http=HTTPConfig(
            host="0.0.0.0",
            port=8080,
        ),
        log_level="INFO",
    )


@pytest.fixture
def sample_jpeg_frame():
    """Provide sample JPEG frame data."""
    # Minimal valid JPEG header
    return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
