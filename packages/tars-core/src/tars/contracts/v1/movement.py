"""
Movement MQTT Contracts - Strongly-typed message models for movement control.

This module defines contracts for two movement architectures:

1. **Frame-based** (movement-service):
   - Host calculates servo pulse widths
   - Publishes frames to ESP32
   - Topics: movement/command → movement/frame → movement/state

2. **Command-based** (ESP32 tars_controller):
   - ESP32 autonomously executes movement sequences
   - Topics: movement/test → movement/status

All contracts use Pydantic v2 with strict validation (extra="forbid").
"""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ==============================================================================
# TOPICS (constants)
# ==============================================================================

TOPIC_MOVEMENT_COMMAND = "movement/command"  # Frame-based: external → service
TOPIC_MOVEMENT_FRAME = "movement/frame"  # Frame-based: service → ESP32
TOPIC_MOVEMENT_STATE = "movement/state"  # Frame-based: service → external
TOPIC_MOVEMENT_TEST = "movement/test"  # Command-based: external → ESP32
TOPIC_MOVEMENT_STOP = "movement/stop"  # Both: emergency stop
TOPIC_MOVEMENT_STATUS = "movement/status"  # Command-based: ESP32 → external
TOPIC_HEALTH_MOVEMENT_SERVICE = "system/health/movement"
TOPIC_HEALTH_MOVEMENT_CONTROLLER = "system/health/movement-controller"

# ==============================================================================
# ENUMS (shared vocabularies)
# ==============================================================================


class MovementAction(str, Enum):
    """
    Frame-based movement actions (movement-service).

    These commands are used by the frame-based architecture where the host
    calculates servo frame sequences and publishes them to ESP32.
    """

    RESET = "reset"
    DISABLE = "disable"
    STEP_FORWARD = "step_forward"
    STEP_BACKWARD = "step_backward"
    TURN_LEFT = "turn_left"
    TURN_RIGHT = "turn_right"
    BALANCE = "balance"
    LAUGH = "laugh"
    SWING_LEGS = "swing_legs"
    POSE = "pose"
    BOW = "bow"


class TestMovementCommand(str, Enum):
    """
    Command-based movement commands (ESP32 tars_controller).

    These commands are sent to ESP32 which autonomously executes
    the complete movement sequence.
    """

    # Basic movements
    RESET = "reset"
    STEP_FORWARD = "step_forward"
    STEP_BACKWARD = "step_backward"
    TURN_LEFT = "turn_left"
    TURN_RIGHT = "turn_right"

    # Expressive movements
    WAVE = "wave"
    LAUGH = "laugh"
    SWING_LEGS = "swing_legs"
    PEZZ = "pezz"
    PEZZ_DISPENSER = "pezz_dispenser"
    NOW = "now"
    BALANCE = "balance"
    MIC_DROP = "mic_drop"
    MONSTER = "monster"
    POSE = "pose"
    BOW = "bow"

    # Control
    DISABLE = "disable"
    STOP = "stop"

    # Manual control
    MOVE_LEGS = "move_legs"
    MOVE_ARM = "move_arm"


class MovementStatusEvent(str, Enum):
    """Status events published by ESP32 tars_controller."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    COMMAND_STARTED = "command_started"
    COMMAND_COMPLETED = "command_completed"
    COMMAND_FAILED = "command_failed"
    EMERGENCY_STOP = "emergency_stop"
    STOP_CLEARED = "stop_cleared"
    QUEUE_FULL = "queue_full"
    BATTERY_LOW = "battery_low"


class MovementStateEvent(str, Enum):
    """State events for frame-based architecture."""

    STARTED = "started"
    FRAME_SENT = "frame_sent"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ==============================================================================
# BASE MODELS
# ==============================================================================


class BaseMovementMessage(BaseModel):
    """
    Base for all movement messages.

    Provides common fields for correlation and tracing:
    - message_id: Unique identifier for this message
    - timestamp: Unix timestamp when message was created
    """

    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: float = Field(default_factory=time.time)

    model_config = {"extra": "forbid"}


# ==============================================================================
# FRAME-BASED ARCHITECTURE (movement-service)
# ==============================================================================


class MovementCommand(BaseMovementMessage):
    """
    Command for frame-based movement architecture.

    Published to: movement/command
    Consumed by: movement-service

    The service calculates frame sequences and publishes MovementFrame messages.

    Example:
        >>> cmd = MovementCommand(command=MovementAction.STEP_FORWARD)
        >>> cmd.id  # Auto-generated UUID
        >>> cmd.timestamp  # Auto-generated timestamp
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    command: MovementAction
    params: dict[str, Any] = Field(default_factory=dict)


class MovementFrame(BaseMovementMessage):
    """
    Frame for frame-based movement architecture.

    Published to: movement/frame
    Consumed by: ESP32 (future frame-based firmware)

    Contains pulse widths for servo channels calculated by movement-service.
    Frames are sequenced (seq/total) and linked to a MovementCommand via id.

    Example:
        >>> frame = MovementFrame(
        ...     id="cmd123",
        ...     seq=0,
        ...     total=5,
        ...     duration_ms=400,
        ...     hold_ms=0,
        ...     channels={0: 1500, 1: 1500, 2: 1500}
        ... )
    """

    id: str  # Links to MovementCommand.id
    seq: int
    total: int
    duration_ms: int
    hold_ms: int
    channels: dict[int, int]  # channel_num -> pulse_width_us
    disable_after: bool = False
    done: bool = False


class MovementState(BaseMovementMessage):
    """
    State update for frame-based movement architecture.

    Published to: movement/state
    Consumed by: External services (UI, monitoring)

    Reports progress of frame sequence execution.

    Example:
        >>> state = MovementState(
        ...     id="cmd123",
        ...     event=MovementStateEvent.FRAME_SENT,
        ...     seq=0
        ... )
    """

    id: str  # Links to MovementCommand.id
    event: MovementStateEvent
    seq: int | None = None
    detail: str | None = None


# ==============================================================================
# COMMAND-BASED ARCHITECTURE (ESP32 tars_controller)
# ==============================================================================


class TestMovementRequest(BaseMovementMessage):
    """
    Command for command-based movement architecture.

    Published to: movement/test
    Consumed by: ESP32 tars_controller

    ESP32 autonomously executes movement sequences. Speed controls
    execution speed (0.1 = slow, 1.0 = normal).

    Example:
        >>> req = TestMovementRequest(
        ...     command=TestMovementCommand.WAVE,
        ...     speed=0.8,
        ...     request_id="abc123"
        ... )
    """

    command: TestMovementCommand
    speed: float = Field(default=1.0, ge=0.1, le=1.0)
    params: dict[str, Any] = Field(default_factory=dict)

    # Optional: for tracking and correlation
    request_id: str | None = Field(default=None)


class MovementStatusUpdate(BaseMovementMessage):
    """
    Status update from ESP32 controller.

    Published to: movement/status
    Consumed by: Router, UI, monitoring services

    Reports execution status from ESP32 with correlation to original request.

    Example:
        >>> status = MovementStatusUpdate(
        ...     event=MovementStatusEvent.COMMAND_STARTED,
        ...     command="wave",
        ...     request_id="abc123"
        ... )
    """

    event: MovementStatusEvent
    command: str | None = None  # Which command triggered this status
    detail: str | None = None
    request_id: str | None = None  # Links to TestMovementRequest.request_id


class EmergencyStopCommand(BaseMovementMessage):
    """
    Emergency stop command.

    Published to: movement/stop
    Consumed by: ESP32 tars_controller, movement-service

    Immediately stops all movement and clears queues.

    Example:
        >>> stop = EmergencyStopCommand(reason="user requested stop")
    """

    reason: str | None = None


# ==============================================================================
# MANUAL CONTROL PARAMETERS
# ==============================================================================


class MoveLegsParams(BaseModel):
    """
    Parameters for manual move_legs command.

    All values are percentages (1-100) representing servo positions:
    - height_percent: 1=down, 100=up
    - left_percent: 1=back, 100=forward
    - right_percent: 1=back, 100=forward

    Example:
        >>> params = MoveLegsParams(
        ...     height_percent=50,
        ...     left_percent=50,
        ...     right_percent=50
        ... )
    """

    height_percent: float = Field(ge=1, le=100)
    left_percent: float = Field(ge=1, le=100)
    right_percent: float = Field(ge=1, le=100)

    model_config = {"extra": "forbid"}


class MoveArmParams(BaseModel):
    """
    Parameters for manual move_arm command.

    All values are percentages (1-100) representing servo positions.
    At least one arm joint must be specified.

    Right arm (port side):
    - port_main: Shoulder joint
    - port_forearm: Elbow joint
    - port_hand: Wrist/hand joint

    Left arm (starboard side):
    - star_main: Shoulder joint
    - star_forearm: Elbow joint
    - star_hand: Wrist/hand joint

    Example:
        >>> params = MoveArmParams(
        ...     port_main=50,
        ...     port_forearm=75,
        ...     star_main=50
        ... )
    """

    # Right arm (port)
    port_main: float | None = Field(default=None, ge=1, le=100)
    port_forearm: float | None = Field(default=None, ge=1, le=100)
    port_hand: float | None = Field(default=None, ge=1, le=100)

    # Left arm (star)
    star_main: float | None = Field(default=None, ge=1, le=100)
    star_forearm: float | None = Field(default=None, ge=1, le=100)
    star_hand: float | None = Field(default=None, ge=1, le=100)

    model_config = {"extra": "forbid"}


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


def validate_test_movement(data: dict) -> TestMovementRequest:
    """
    Validate and parse movement/test message.

    Args:
        data: Raw message data (dict)

    Returns:
        Validated TestMovementRequest instance

    Raises:
        pydantic.ValidationError: If message structure is invalid

    Example:
        >>> data = {"command": "wave", "speed": 0.8}
        >>> req = validate_test_movement(data)
        >>> req.command
        <TestMovementCommand.WAVE: 'wave'>
    """
    return TestMovementRequest.model_validate(data)


def validate_movement_command(data: dict) -> MovementCommand:
    """
    Validate and parse movement/command message.

    Args:
        data: Raw message data (dict)

    Returns:
        Validated MovementCommand instance

    Raises:
        pydantic.ValidationError: If message structure is invalid

    Example:
        >>> data = {"command": "step_forward"}
        >>> cmd = validate_movement_command(data)
        >>> cmd.command
        <MovementAction.STEP_FORWARD: 'step_forward'>
    """
    return MovementCommand.model_validate(data)


def validate_emergency_stop(data: dict) -> EmergencyStopCommand:
    """
    Validate and parse movement/stop message.

    Args:
        data: Raw message data (dict)

    Returns:
        Validated EmergencyStopCommand instance

    Raises:
        pydantic.ValidationError: If message structure is invalid

    Example:
        >>> data = {"reason": "user requested"}
        >>> stop = validate_emergency_stop(data)
        >>> stop.reason
        'user requested'
    """
    return EmergencyStopCommand.model_validate(data)
