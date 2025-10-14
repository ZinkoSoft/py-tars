"""Unit tests for movement-service models (command-based architecture)."""

from __future__ import annotations

import pytest

from movement_service.models import (
    EmergencyStopCommand,
    MovementStatusUpdate,
    TestMovementCommand,
    TestMovementRequest,
)


@pytest.mark.unit
def test_test_movement_request_defaults() -> None:
    """Test TestMovementRequest with default values."""
    request = TestMovementRequest(command=TestMovementCommand.WAVE)
    assert request.command == TestMovementCommand.WAVE
    assert request.speed == 1.0
    assert request.params == {}
    assert request.request_id is None
    assert request.message_id is not None
    assert request.timestamp > 0


@pytest.mark.unit
def test_test_movement_request_with_speed() -> None:
    """Test TestMovementRequest with custom speed."""
    request = TestMovementRequest(command=TestMovementCommand.LAUGH, speed=0.5)
    assert request.command == TestMovementCommand.LAUGH
    assert request.speed == 0.5


@pytest.mark.unit
def test_test_movement_request_with_params() -> None:
    """Test TestMovementRequest with params."""
    params = {"height_percent": 50.0, "left_percent": 75.0, "right_percent": 25.0}
    request = TestMovementRequest(command=TestMovementCommand.MOVE_LEGS, params=params)
    assert request.params == params


@pytest.mark.unit
def test_test_movement_request_roundtrip() -> None:
    """Test TestMovementRequest serialization roundtrip."""
    request = TestMovementRequest(command=TestMovementCommand.STEP_FORWARD, speed=0.8, request_id="test-123")
    data = request.model_dump()
    parsed = TestMovementRequest.model_validate(data)
    assert parsed.command == request.command
    assert parsed.speed == request.speed
    assert parsed.request_id == request.request_id


@pytest.mark.unit
def test_test_movement_request_speed_validation() -> None:
    """Test TestMovementRequest speed validation."""
    with pytest.raises(ValueError, match="speed"):
        TestMovementRequest(command=TestMovementCommand.WAVE, speed=1.5)  # Too high
    with pytest.raises(ValueError, match="speed"):
        TestMovementRequest(command=TestMovementCommand.WAVE, speed=0.05)  # Too low


@pytest.mark.unit
def test_movement_status_update() -> None:
    """Test MovementStatusUpdate creation."""
    status = MovementStatusUpdate(event="command_started", command="wave", request_id="test-123")
    assert status.event == "command_started"
    assert status.command == "wave"
    assert status.request_id == "test-123"
    assert status.message_id is not None


@pytest.mark.unit
def test_emergency_stop_command() -> None:
    """Test EmergencyStopCommand creation."""
    stop = EmergencyStopCommand(reason="test stop")
    assert stop.reason == "test stop"
    assert stop.message_id is not None


@pytest.mark.unit
def test_emergency_stop_command_no_reason() -> None:
    """Test EmergencyStopCommand without reason."""
    stop = EmergencyStopCommand()
    assert stop.reason is None
