"""Tests for camera MQTT contracts."""

import pytest
from pydantic import ValidationError

from tars.contracts.v1.camera import (
    CameraCaptureRequest,
    CameraImageResponse,
    CameraStatusUpdate,
    TOPIC_CAMERA_CAPTURE,
    TOPIC_CAMERA_IMAGE,
)


class TestCameraTopicConstants:
    """Test camera topic constants are defined correctly."""
    
    def test_topic_constants_exist(self):
        """Test all topic constants are defined."""
        assert TOPIC_CAMERA_CAPTURE == "camera/capture"
        assert TOPIC_CAMERA_IMAGE == "camera/image"


class TestCameraCaptureRequest:
    """Test CameraCaptureRequest contract."""
    
    def test_valid_minimal_request(self):
        """Test valid request with minimal fields."""
        msg = CameraCaptureRequest()
        assert msg.format == "jpeg"  # Default
        assert msg.quality == 85  # Default
        assert msg.message_id is not None
        assert msg.request_id is not None
        assert msg.timestamp > 0
    
    def test_valid_full_request(self):
        """Test valid request with all fields."""
        msg = CameraCaptureRequest(
            format="png",
            quality=95,
            width=1920,
            height=1080,
            purpose="test_capture",
        )
        assert msg.format == "png"
        assert msg.quality == 95
        assert msg.width == 1920
        assert msg.height == 1080
        assert msg.purpose == "test_capture"
    
    def test_invalid_format(self):
        """Test invalid format raises ValidationError."""
        with pytest.raises(ValidationError) as exc:
            CameraCaptureRequest(format="gif")
        assert "format" in str(exc.value).lower()
    
    def test_invalid_quality_too_low(self):
        """Test quality < 1 raises ValidationError."""
        with pytest.raises(ValidationError) as exc:
            CameraCaptureRequest(quality=0)
        assert "quality" in str(exc.value).lower()
    
    def test_invalid_quality_too_high(self):
        """Test quality > 100 raises ValidationError."""
        with pytest.raises(ValidationError) as exc:
            CameraCaptureRequest(quality=101)
        assert "quality" in str(exc.value).lower()
    
    def test_invalid_width_zero(self):
        """Test width=0 raises ValidationError."""
        with pytest.raises(ValidationError) as exc:
            CameraCaptureRequest(width=0)
        assert "width" in str(exc.value).lower()
    
    def test_invalid_height_negative(self):
        """Test negative height raises ValidationError."""
        with pytest.raises(ValidationError) as exc:
            CameraCaptureRequest(height=-100)
        assert "height" in str(exc.value).lower()
    
    def test_extra_fields_forbidden(self):
        """Test extra fields are rejected."""
        with pytest.raises(ValidationError) as exc:
            CameraCaptureRequest(extra_field="invalid")
        assert "extra" in str(exc.value).lower()
    
    def test_json_serialization(self):
        """Test JSON serialization round-trip."""
        msg = CameraCaptureRequest(format="jpeg", quality=90)
        json_str = msg.model_dump_json()
        msg2 = CameraCaptureRequest.model_validate_json(json_str)
        assert msg.format == msg2.format
        assert msg.quality == msg2.quality
        assert msg.request_id == msg2.request_id


class TestCameraImageResponse:
    """Test CameraImageResponse contract."""
    
    def test_valid_success_response(self):
        """Test valid successful response."""
        msg = CameraImageResponse(
            request_id="req-123",
            image_data="base64encodeddata",
            format="jpeg",
            width=1920,
            height=1080,
            size_bytes=204800,
        )
        assert msg.request_id == "req-123"
        assert msg.success is True
        assert msg.error is None
        assert msg.width == 1920
        assert msg.height == 1080
    
    def test_valid_failure_response(self):
        """Test valid failure response."""
        msg = CameraImageResponse(
            request_id="req-456",
            image_data="",
            format="jpeg",
            width=0,
            height=0,
            size_bytes=0,
            success=False,
            error="Camera unavailable",
        )
        assert msg.success is False
        assert msg.error == "Camera unavailable"
    
    def test_missing_required_request_id(self):
        """Test missing request_id raises ValidationError."""
        with pytest.raises(ValidationError) as exc:
            CameraImageResponse(
                image_data="data",
                format="jpeg",
                width=640,
                height=480,
                size_bytes=1000,
            )
        assert "request_id" in str(exc.value).lower()
    
    def test_invalid_format(self):
        """Test invalid format raises ValidationError."""
        with pytest.raises(ValidationError) as exc:
            CameraImageResponse(
                request_id="req-789",
                image_data="data",
                format="bmp",
                width=640,
                height=480,
                size_bytes=1000,
            )
        assert "format" in str(exc.value).lower()
    
    def test_invalid_size_negative(self):
        """Test negative size_bytes raises ValidationError."""
        with pytest.raises(ValidationError) as exc:
            CameraImageResponse(
                request_id="req-102",
                image_data="data",
                format="jpeg",
                width=640,
                height=480,
                size_bytes=-100,
            )
        assert "size_bytes" in str(exc.value).lower()
    
    def test_extra_fields_forbidden(self):
        """Test extra fields are rejected."""
        with pytest.raises(ValidationError) as exc:
            CameraImageResponse(
                request_id="req-103",
                image_data="data",
                format="jpeg",
                width=640,
                height=480,
                size_bytes=1000,
                extra_field="invalid",
            )
        assert "extra" in str(exc.value).lower()
    
    def test_json_serialization(self):
        """Test JSON serialization round-trip."""
        msg = CameraImageResponse(
            request_id="req-200",
            image_data="data",
            format="png",
            width=800,
            height=600,
            size_bytes=50000,
        )
        json_str = msg.model_dump_json()
        msg2 = CameraImageResponse.model_validate_json(json_str)
        assert msg.request_id == msg2.request_id
        assert msg.format == msg2.format
        assert msg.width == msg2.width


class TestCameraStatusUpdate:
    """Test CameraStatusUpdate contract."""
    
    def test_valid_status_ready(self):
        """Test valid camera ready status."""
        msg = CameraStatusUpdate(event="camera_ready")
        assert msg.event == "camera_ready"
        assert msg.request_id is None
        assert msg.detail is None
    
    def test_valid_status_capture_completed(self):
        """Test valid capture completed status."""
        msg = CameraStatusUpdate(
            event="capture_completed",
            request_id="req-300",
            detail="Captured 1920x1080 JPEG",
        )
        assert msg.event == "capture_completed"
        assert msg.request_id == "req-300"
        assert msg.detail is not None
    
    def test_invalid_event(self):
        """Test invalid event raises ValidationError."""
        with pytest.raises(ValidationError) as exc:
            CameraStatusUpdate(event="invalid_event")
        assert "event" in str(exc.value).lower()
    
    def test_extra_fields_forbidden(self):
        """Test extra fields are rejected."""
        with pytest.raises(ValidationError) as exc:
            CameraStatusUpdate(event="camera_ready", extra="invalid")
        assert "extra" in str(exc.value).lower()
    
    def test_json_serialization(self):
        """Test JSON serialization round-trip."""
        msg = CameraStatusUpdate(event="capture_started", request_id="req-400")
        json_str = msg.model_dump_json()
        msg2 = CameraStatusUpdate.model_validate_json(json_str)
        assert msg.event == msg2.event
        assert msg.request_id == msg2.request_id


class TestCameraIntegration:
    """Test integration scenarios."""
    
    def test_request_response_correlation(self):
        """Test request_id correlates request and response."""
        request = CameraCaptureRequest(format="jpeg", quality=85)
        
        # Simulate response with same request_id
        response = CameraImageResponse(
            request_id=request.request_id,
            image_data="base64data",
            format="jpeg",
            width=1920,
            height=1080,
            size_bytes=100000,
        )
        
        assert response.request_id == request.request_id
    
    def test_capture_flow_with_status(self):
        """Test complete capture flow with status updates."""
        # Request capture
        request = CameraCaptureRequest(purpose="test_flow")
        
        # Status: started
        status_started = CameraStatusUpdate(
            event="capture_started",
            request_id=request.request_id,
        )
        
        # Response: completed
        response = CameraImageResponse(
            request_id=request.request_id,
            image_data="data",
            format="jpeg",
            width=640,
            height=480,
            size_bytes=5000,
        )
        
        # Status: completed
        status_completed = CameraStatusUpdate(
            event="capture_completed",
            request_id=request.request_id,
            detail="Success",
        )
        
        # Verify correlation
        assert status_started.request_id == request.request_id
        assert response.request_id == request.request_id
        assert status_completed.request_id == request.request_id
