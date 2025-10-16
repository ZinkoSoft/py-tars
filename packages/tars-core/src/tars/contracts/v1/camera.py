"""Camera service MQTT contracts."""

from __future__ import annotations

import time
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, Field, ConfigDict

# Event types (legacy - prefer topic constants)
EVENT_TYPE_CAMERA_CAPTURE = "camera.capture"
EVENT_TYPE_CAMERA_IMAGE = "camera.image"

# MQTT Topic constants
TOPIC_CAMERA_CAPTURE = "camera/capture"
TOPIC_CAMERA_IMAGE = "camera/image"
TOPIC_CAMERA_FRAME = "camera/frame"


class BaseCameraMessage(BaseModel):
    """Base for all camera messages."""
    model_config = ConfigDict(extra="forbid")
    
    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: float = Field(default_factory=time.time)


class CameraCaptureRequest(BaseCameraMessage):
    """
    Request to capture an image from the camera.
    
    Published to: camera/capture
    Consumed by: camera-service
    """
    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    
    # Capture parameters
    format: Literal["jpeg", "png", "raw"] = "jpeg"
    quality: int = Field(default=85, ge=1, le=100, description="JPEG quality (1-100)")
    width: Optional[int] = Field(default=None, ge=1, description="Desired width in pixels")
    height: Optional[int] = Field(default=None, ge=1, description="Desired height in pixels")
    
    # Optional metadata
    purpose: Optional[str] = Field(default=None, description="Purpose of capture (for logging)")


class CameraImageResponse(BaseCameraMessage):
    """
    Response containing captured image data.
    
    Published to: camera/image
    Consumed by: MCP bridge, other services
    """
    request_id: str  # Links to CameraCaptureRequest
    
    # Image data
    image_data: str = Field(description="Base64-encoded image data")
    format: Literal["jpeg", "png", "raw"]
    width: int = Field(ge=0, description="Actual width in pixels (0 if failed)")
    height: int = Field(ge=0, description="Actual height in pixels (0 if failed)")
    size_bytes: int = Field(ge=0, description="Size of image data in bytes")
    
    # Status
    success: bool = True
    error: Optional[str] = Field(default=None, description="Error message if capture failed")
    
    # Optional metadata
    purpose: Optional[str] = None
    capture_timestamp: float = Field(default_factory=time.time)


class CameraStatusUpdate(BaseCameraMessage):
    """
    Status update from camera service.
    
    Published to: camera/status (if needed)
    Consumed by: Monitoring services
    """
    event: Literal[
        "camera_ready",
        "camera_unavailable",
        "capture_started",
        "capture_completed",
        "capture_failed",
    ]
    request_id: Optional[str] = None
    detail: Optional[str] = None


class CameraFrame(BaseCameraMessage):
    """
    Real-time camera frame for visualization/streaming.
    
    Published to: camera/frame
    Consumed by: UI services, visualization
    """
    frame_data: str = Field(description="Base64-encoded frame data")
    format: Literal["jpeg", "png"] = "jpeg"
    width: int = Field(ge=1, description="Frame width in pixels")
    height: int = Field(ge=1, description="Frame height in pixels")
    frame_number: int = Field(ge=0, description="Sequential frame number")
    fps: Optional[float] = Field(default=None, ge=0, description="Frames per second")
