"""
Tests for movement MQTT contracts.

Validates all movement message models, enums, and validation functions.
"""

from __future__ import annotations

import json
import time

import pytest
from pydantic import ValidationError

from tars.contracts.v1.movement import (
    TOPIC_HEALTH_MOVEMENT_CONTROLLER,
    TOPIC_HEALTH_MOVEMENT_SERVICE,
    TOPIC_MOVEMENT_COMMAND,
    TOPIC_MOVEMENT_FRAME,
    TOPIC_MOVEMENT_STATE,
    TOPIC_MOVEMENT_STATUS,
    TOPIC_MOVEMENT_STOP,
    TOPIC_MOVEMENT_TEST,
    BaseMovementMessage,
    EmergencyStopCommand,
    MoveArmParams,
    MoveLegsParams,
    MovementAction,
    MovementCommand,
    MovementFrame,
    MovementState,
    MovementStateEvent,
    MovementStatusEvent,
    MovementStatusUpdate,
    TestMovementCommand,
    TestMovementRequest,
    validate_emergency_stop,
    validate_movement_command,
    validate_test_movement,
)


# ==============================================================================
# TOPIC CONSTANTS
# ==============================================================================


def test_topic_constants():
    """Test all topic constants are defined."""
    assert TOPIC_MOVEMENT_COMMAND == "movement/command"
    assert TOPIC_MOVEMENT_FRAME == "movement/frame"
    assert TOPIC_MOVEMENT_STATE == "movement/state"
    assert TOPIC_MOVEMENT_TEST == "movement/test"
    assert TOPIC_MOVEMENT_STOP == "movement/stop"
    assert TOPIC_MOVEMENT_STATUS == "movement/status"
    assert TOPIC_HEALTH_MOVEMENT_SERVICE == "system/health/movement"
    assert TOPIC_HEALTH_MOVEMENT_CONTROLLER == "system/health/movement-controller"


# ==============================================================================
# ENUMS
# ==============================================================================


def test_movement_action_enum():
    """Test MovementAction enum values."""
    assert MovementAction.RESET == "reset"
    assert MovementAction.DISABLE == "disable"
    assert MovementAction.STEP_FORWARD == "step_forward"
    assert MovementAction.STEP_BACKWARD == "step_backward"
    assert MovementAction.TURN_LEFT == "turn_left"
    assert MovementAction.TURN_RIGHT == "turn_right"
    assert MovementAction.BALANCE == "balance"
    assert MovementAction.LAUGH == "laugh"
    assert MovementAction.SWING_LEGS == "swing_legs"
    assert MovementAction.POSE == "pose"
    assert MovementAction.BOW == "bow"
    
    # Total count
    assert len(MovementAction) == 11


def test_test_movement_command_enum():
    """Test TestMovementCommand enum values."""
    # Basic
    assert TestMovementCommand.RESET == "reset"
    assert TestMovementCommand.STEP_FORWARD == "step_forward"
    assert TestMovementCommand.STEP_BACKWARD == "step_backward"
    assert TestMovementCommand.TURN_LEFT == "turn_left"
    assert TestMovementCommand.TURN_RIGHT == "turn_right"
    
    # Expressive
    assert TestMovementCommand.WAVE == "wave"
    assert TestMovementCommand.LAUGH == "laugh"
    assert TestMovementCommand.SWING_LEGS == "swing_legs"
    assert TestMovementCommand.PEZZ == "pezz"
    assert TestMovementCommand.PEZZ_DISPENSER == "pezz_dispenser"
    assert TestMovementCommand.NOW == "now"
    assert TestMovementCommand.BALANCE == "balance"
    assert TestMovementCommand.MIC_DROP == "mic_drop"
    assert TestMovementCommand.MONSTER == "monster"
    assert TestMovementCommand.POSE == "pose"
    assert TestMovementCommand.BOW == "bow"
    
    # Control
    assert TestMovementCommand.DISABLE == "disable"
    assert TestMovementCommand.STOP == "stop"
    
    # Manual
    assert TestMovementCommand.MOVE_LEGS == "move_legs"
    assert TestMovementCommand.MOVE_ARM == "move_arm"
    
    # Total count (5 basic + 11 expressive + 2 control + 2 manual = 20)
    assert len(TestMovementCommand) == 20


def test_movement_status_event_enum():
    """Test MovementStatusEvent enum values."""
    assert MovementStatusEvent.CONNECTED == "connected"
    assert MovementStatusEvent.DISCONNECTED == "disconnected"
    assert MovementStatusEvent.COMMAND_STARTED == "command_started"
    assert MovementStatusEvent.COMMAND_COMPLETED == "command_completed"
    assert MovementStatusEvent.COMMAND_FAILED == "command_failed"
    assert MovementStatusEvent.EMERGENCY_STOP == "emergency_stop"
    assert MovementStatusEvent.STOP_CLEARED == "stop_cleared"
    assert MovementStatusEvent.QUEUE_FULL == "queue_full"
    assert MovementStatusEvent.BATTERY_LOW == "battery_low"
    
    # Total count
    assert len(MovementStatusEvent) == 9


def test_movement_state_event_enum():
    """Test MovementStateEvent enum values."""
    assert MovementStateEvent.STARTED == "started"
    assert MovementStateEvent.FRAME_SENT == "frame_sent"
    assert MovementStateEvent.COMPLETED == "completed"
    assert MovementStateEvent.FAILED == "failed"
    assert MovementStateEvent.CANCELLED == "cancelled"
    
    # Total count
    assert len(MovementStateEvent) == 5


# ==============================================================================
# BASE MODEL
# ==============================================================================


def test_base_movement_message():
    """Test BaseMovementMessage auto-generates fields."""
    msg = BaseMovementMessage()
    
    # Auto-generated fields
    assert msg.message_id is not None
    assert len(msg.message_id) == 32  # UUID hex
    assert msg.timestamp > 0
    assert msg.timestamp <= time.time()


def test_base_movement_message_rejects_extra_fields():
    """Test extra fields are rejected (extra='forbid')."""
    with pytest.raises(ValidationError) as exc_info:
        BaseMovementMessage(extra_field="not allowed")
    
    assert "extra_field" in str(exc_info.value)


# ==============================================================================
# FRAME-BASED CONTRACTS
# ==============================================================================


def test_movement_command_valid():
    """Test valid MovementCommand creation."""
    cmd = MovementCommand(command=MovementAction.STEP_FORWARD)
    
    assert cmd.command == MovementAction.STEP_FORWARD
    assert cmd.params == {}
    assert len(cmd.id) == 32
    assert len(cmd.message_id) == 32
    assert cmd.timestamp > 0


def test_movement_command_with_params():
    """Test MovementCommand with params."""
    cmd = MovementCommand(
        command=MovementAction.BALANCE,
        params={"duration": 5.0}
    )
    
    assert cmd.params == {"duration": 5.0}


def test_movement_command_invalid_action():
    """Test MovementCommand rejects invalid action."""
    with pytest.raises(ValidationError):
        MovementCommand(command="invalid_action")


def test_movement_command_rejects_extra_fields():
    """Test MovementCommand rejects extra fields."""
    with pytest.raises(ValidationError) as exc_info:
        MovementCommand(
            command=MovementAction.RESET,
            extra="not allowed"
        )
    
    assert "extra" in str(exc_info.value)


def test_movement_frame_valid():
    """Test valid MovementFrame creation."""
    frame = MovementFrame(
        id="cmd123",
        seq=0,
        total=5,
        duration_ms=400,
        hold_ms=0,
        channels={0: 1500, 1: 1500, 2: 1500}
    )
    
    assert frame.id == "cmd123"
    assert frame.seq == 0
    assert frame.total == 5
    assert frame.duration_ms == 400
    assert frame.hold_ms == 0
    assert frame.channels == {0: 1500, 1: 1500, 2: 1500}
    assert frame.disable_after is False
    assert frame.done is False


def test_movement_frame_with_flags():
    """Test MovementFrame with disable_after and done flags."""
    frame = MovementFrame(
        id="cmd123",
        seq=4,
        total=5,
        duration_ms=400,
        hold_ms=200,
        channels={0: 1500},
        disable_after=True,
        done=True
    )
    
    assert frame.disable_after is True
    assert frame.done is True


def test_movement_state_valid():
    """Test valid MovementState creation."""
    state = MovementState(
        id="cmd123",
        event=MovementStateEvent.STARTED
    )
    
    assert state.id == "cmd123"
    assert state.event == MovementStateEvent.STARTED
    assert state.seq is None
    assert state.detail is None


def test_movement_state_with_details():
    """Test MovementState with seq and detail."""
    state = MovementState(
        id="cmd123",
        event=MovementStateEvent.FRAME_SENT,
        seq=0,
        detail="Frame 0/5 sent"
    )
    
    assert state.seq == 0
    assert state.detail == "Frame 0/5 sent"


# ==============================================================================
# COMMAND-BASED CONTRACTS
# ==============================================================================


def test_test_movement_request_valid():
    """Test valid TestMovementRequest creation."""
    req = TestMovementRequest(command=TestMovementCommand.WAVE)
    
    assert req.command == TestMovementCommand.WAVE
    assert req.speed == 1.0  # Default
    assert req.params == {}
    assert req.request_id is None


def test_test_movement_request_with_speed():
    """Test TestMovementRequest with custom speed."""
    req = TestMovementRequest(
        command=TestMovementCommand.WAVE,
        speed=0.8
    )
    
    assert req.speed == 0.8


def test_test_movement_request_speed_validation():
    """Test TestMovementRequest speed constraints."""
    # Too low
    with pytest.raises(ValidationError) as exc_info:
        TestMovementRequest(command=TestMovementCommand.WAVE, speed=0.05)
    assert "greater than or equal to 0.1" in str(exc_info.value)
    
    # Too high
    with pytest.raises(ValidationError) as exc_info:
        TestMovementRequest(command=TestMovementCommand.WAVE, speed=1.5)
    assert "less than or equal to 1" in str(exc_info.value)
    
    # Edge cases (valid)
    req_min = TestMovementRequest(command=TestMovementCommand.WAVE, speed=0.1)
    assert req_min.speed == 0.1
    
    req_max = TestMovementRequest(command=TestMovementCommand.WAVE, speed=1.0)
    assert req_max.speed == 1.0


def test_test_movement_request_with_request_id():
    """Test TestMovementRequest with request_id for correlation."""
    req = TestMovementRequest(
        command=TestMovementCommand.WAVE,
        speed=0.8,
        request_id="abc123"
    )
    
    assert req.request_id == "abc123"


def test_test_movement_request_with_params():
    """Test TestMovementRequest with params for manual commands."""
    req = TestMovementRequest(
        command=TestMovementCommand.MOVE_LEGS,
        params={
            "height_percent": 50,
            "left_percent": 50,
            "right_percent": 50
        }
    )
    
    assert req.params["height_percent"] == 50


def test_movement_status_update_valid():
    """Test valid MovementStatusUpdate creation."""
    status = MovementStatusUpdate(
        event=MovementStatusEvent.COMMAND_STARTED
    )
    
    assert status.event == MovementStatusEvent.COMMAND_STARTED
    assert status.command is None
    assert status.detail is None
    assert status.request_id is None


def test_movement_status_update_with_details():
    """Test MovementStatusUpdate with full details."""
    status = MovementStatusUpdate(
        event=MovementStatusEvent.COMMAND_COMPLETED,
        command="wave",
        detail="Completed successfully",
        request_id="abc123"
    )
    
    assert status.event == MovementStatusEvent.COMMAND_COMPLETED
    assert status.command == "wave"
    assert status.detail == "Completed successfully"
    assert status.request_id == "abc123"


def test_emergency_stop_command_valid():
    """Test valid EmergencyStopCommand creation."""
    stop = EmergencyStopCommand()
    
    assert stop.reason is None
    assert len(stop.message_id) == 32


def test_emergency_stop_command_with_reason():
    """Test EmergencyStopCommand with reason."""
    stop = EmergencyStopCommand(reason="user requested stop")
    
    assert stop.reason == "user requested stop"


# ==============================================================================
# MANUAL CONTROL PARAMETERS
# ==============================================================================


def test_move_legs_params_valid():
    """Test valid MoveLegsParams creation."""
    params = MoveLegsParams(
        height_percent=50,
        left_percent=50,
        right_percent=50
    )
    
    assert params.height_percent == 50
    assert params.left_percent == 50
    assert params.right_percent == 50


def test_move_legs_params_validation():
    """Test MoveLegsParams percentage constraints."""
    # Too low
    with pytest.raises(ValidationError):
        MoveLegsParams(height_percent=0, left_percent=50, right_percent=50)
    
    # Too high
    with pytest.raises(ValidationError):
        MoveLegsParams(height_percent=101, left_percent=50, right_percent=50)
    
    # Edge cases (valid)
    params_min = MoveLegsParams(height_percent=1, left_percent=1, right_percent=1)
    assert params_min.height_percent == 1
    
    params_max = MoveLegsParams(height_percent=100, left_percent=100, right_percent=100)
    assert params_max.height_percent == 100


def test_move_arm_params_valid():
    """Test valid MoveArmParams creation."""
    params = MoveArmParams(
        port_main=50,
        port_forearm=75,
        star_main=50
    )
    
    assert params.port_main == 50
    assert params.port_forearm == 75
    assert params.star_main == 50
    assert params.port_hand is None
    assert params.star_forearm is None
    assert params.star_hand is None


def test_move_arm_params_validation():
    """Test MoveArmParams percentage constraints."""
    # Too low
    with pytest.raises(ValidationError):
        MoveArmParams(port_main=0)
    
    # Too high
    with pytest.raises(ValidationError):
        MoveArmParams(port_main=101)
    
    # Edge cases (valid)
    params_min = MoveArmParams(port_main=1)
    assert params_min.port_main == 1
    
    params_max = MoveArmParams(star_hand=100)
    assert params_max.star_hand == 100


def test_move_arm_params_all_fields():
    """Test MoveArmParams with all fields."""
    params = MoveArmParams(
        port_main=50,
        port_forearm=60,
        port_hand=70,
        star_main=40,
        star_forearm=30,
        star_hand=20
    )
    
    assert params.port_main == 50
    assert params.port_forearm == 60
    assert params.port_hand == 70
    assert params.star_main == 40
    assert params.star_forearm == 30
    assert params.star_hand == 20


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


def test_validate_test_movement():
    """Test validate_test_movement helper."""
    data = {"command": "wave", "speed": 0.8}
    req = validate_test_movement(data)
    
    assert isinstance(req, TestMovementRequest)
    assert req.command == TestMovementCommand.WAVE
    assert req.speed == 0.8


def test_validate_test_movement_invalid():
    """Test validate_test_movement rejects invalid data."""
    with pytest.raises(ValidationError):
        validate_test_movement({"command": "invalid"})
    
    with pytest.raises(ValidationError):
        validate_test_movement({"speed": 0.8})  # Missing command


def test_validate_movement_command():
    """Test validate_movement_command helper."""
    data = {"command": "step_forward"}
    cmd = validate_movement_command(data)
    
    assert isinstance(cmd, MovementCommand)
    assert cmd.command == MovementAction.STEP_FORWARD


def test_validate_movement_command_invalid():
    """Test validate_movement_command rejects invalid data."""
    with pytest.raises(ValidationError):
        validate_movement_command({"command": "invalid"})
    
    with pytest.raises(ValidationError):
        validate_movement_command({})  # Missing command


def test_validate_emergency_stop():
    """Test validate_emergency_stop helper."""
    data = {"reason": "user requested"}
    stop = validate_emergency_stop(data)
    
    assert isinstance(stop, EmergencyStopCommand)
    assert stop.reason == "user requested"


def test_validate_emergency_stop_empty():
    """Test validate_emergency_stop with empty data."""
    data = {}
    stop = validate_emergency_stop(data)
    
    assert isinstance(stop, EmergencyStopCommand)
    assert stop.reason is None


# ==============================================================================
# JSON SERIALIZATION (orjson compatibility)
# ==============================================================================


def test_json_serialization_test_movement_request():
    """Test TestMovementRequest JSON round-trip."""
    req = TestMovementRequest(
        command=TestMovementCommand.WAVE,
        speed=0.8,
        request_id="abc123"
    )
    
    # Serialize to JSON
    json_str = req.model_dump_json()
    data = json.loads(json_str)
    
    # Deserialize back
    req2 = TestMovementRequest.model_validate(data)
    
    assert req2.command == req.command
    assert req2.speed == req.speed
    assert req2.request_id == req.request_id


def test_json_serialization_movement_command():
    """Test MovementCommand JSON round-trip."""
    cmd = MovementCommand(
        command=MovementAction.STEP_FORWARD,
        params={"test": "value"}
    )
    
    json_str = cmd.model_dump_json()
    data = json.loads(json_str)
    
    cmd2 = MovementCommand.model_validate(data)
    
    assert cmd2.command == cmd.command
    assert cmd2.params == cmd.params
    assert cmd2.id == cmd.id


def test_json_serialization_movement_frame():
    """Test MovementFrame JSON round-trip."""
    frame = MovementFrame(
        id="cmd123",
        seq=0,
        total=5,
        duration_ms=400,
        hold_ms=0,
        channels={0: 1500, 1: 1500, 2: 1500}
    )
    
    json_str = frame.model_dump_json()
    data = json.loads(json_str)
    
    frame2 = MovementFrame.model_validate(data)
    
    assert frame2.id == frame.id
    assert frame2.seq == frame.seq
    assert frame2.channels == frame.channels


def test_json_serialization_movement_status_update():
    """Test MovementStatusUpdate JSON round-trip."""
    status = MovementStatusUpdate(
        event=MovementStatusEvent.COMMAND_COMPLETED,
        command="wave",
        request_id="abc123"
    )
    
    json_str = status.model_dump_json()
    data = json.loads(json_str)
    
    status2 = MovementStatusUpdate.model_validate(data)
    
    assert status2.event == status.event
    assert status2.command == status.command
    assert status2.request_id == status.request_id


# ==============================================================================
# INTEGRATION SCENARIOS
# ==============================================================================


def test_command_based_flow():
    """Test command-based movement flow (Router → ESP32 → Status)."""
    # 1. Router creates request
    req = TestMovementRequest(
        command=TestMovementCommand.WAVE,
        speed=0.8,
        request_id="flow123"
    )
    
    # 2. ESP32 receives and validates
    json_data = json.loads(req.model_dump_json())
    validated_req = validate_test_movement(json_data)
    assert validated_req.request_id == "flow123"
    
    # 3. ESP32 publishes start status
    status_start = MovementStatusUpdate(
        event=MovementStatusEvent.COMMAND_STARTED,
        command=str(validated_req.command.value),
        request_id=validated_req.request_id
    )
    
    # 4. ESP32 publishes completion status
    status_complete = MovementStatusUpdate(
        event=MovementStatusEvent.COMMAND_COMPLETED,
        command=str(validated_req.command.value),
        request_id=validated_req.request_id
    )
    
    # Verify correlation
    assert status_start.request_id == status_complete.request_id == "flow123"
    assert status_start.command == status_complete.command == "wave"


def test_frame_based_flow():
    """Test frame-based movement flow (Command → Service → Frames)."""
    # 1. External service creates command
    cmd = MovementCommand(command=MovementAction.STEP_FORWARD)
    
    # 2. movement-service calculates frames
    frames = [
        MovementFrame(
            id=cmd.id,
            seq=i,
            total=3,
            duration_ms=400,
            hold_ms=0,
            channels={0: 1500, 1: 1500, 2: 1500},
            done=(i == 2)
        )
        for i in range(3)
    ]
    
    # 3. movement-service publishes states
    states = [
        MovementState(
            id=cmd.id,
            event=MovementStateEvent.FRAME_SENT,
            seq=i
        )
        for i in range(3)
    ]
    
    # Verify correlation
    assert all(f.id == cmd.id for f in frames)
    assert all(s.id == cmd.id for s in states)
    assert frames[-1].done is True


def test_emergency_stop_flow():
    """Test emergency stop flow."""
    # 1. User triggers stop
    stop = EmergencyStopCommand(reason="user requested stop")
    
    # 2. ESP32 receives and validates
    json_data = json.loads(stop.model_dump_json())
    validated_stop = validate_emergency_stop(json_data)
    assert validated_stop.reason == "user requested stop"
    
    # 3. ESP32 publishes emergency stop status
    status = MovementStatusUpdate(
        event=MovementStatusEvent.EMERGENCY_STOP,
        detail=validated_stop.reason
    )
    
    assert status.event == MovementStatusEvent.EMERGENCY_STOP
    assert status.detail == "user requested stop"
