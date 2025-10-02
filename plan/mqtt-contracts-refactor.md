# MQTT Contracts Refactor Plan

**Status**: Draft  
**Created**: 2025-10-02  
**Owner**: Movement Service Integration  
**Priority**: High

## Executive Summary

Refactor MQTT message handling across py-tars to use strongly-typed Pydantic v2 contracts. This plan addresses the dual-architecture movement system (frame-based `movement-service` + command-based ESP32 `tars_controller`), migrates shared contracts to `tars-core`, and establishes patterns for consistent message validation across all services.

## Problem Statement

### Current State Issues

1. **Duplicate Message Models**: Movement messages defined only in `apps/movement-service`, not shared with ESP32 firmware or other services
2. **Weak Typing on ESP32**: `tars_controller.py` uses dict-based JSON parsing without Pydantic validation
3. **Two Movement Architectures**: 
   - `movement-service`: Frame-based (host calculates frames, ESP32 applies pulse widths)
   - `tars_controller`: Command-based (ESP32 autonomously executes movement sequences)
4. **Topic Confusion**: Multiple movement topics with unclear boundaries (`movement/command`, `movement/frame`, `movement/test`, `movement/status`)
5. **No Contract Registry**: No single source of truth for all MQTT message shapes
6. **Inconsistent Validation**: Some services use Pydantic, others use raw dict parsing

### Impact

- Type safety violations lead to runtime errors
- No compile-time guarantees on message structure
- Difficult to evolve message formats without breaking changes
- Testing requires mocking raw JSON instead of typed objects

## Goals

### Primary Objectives

1. **Unified Contract Library**: All MQTT message contracts in `tars-core/contracts/v1/`
2. **Strict Typing**: All services use Pydantic models with `extra="forbid"`
3. **Architecture Clarity**: Clear separation between frame-based and command-based movement
4. **MicroPython Compatibility**: Validation patterns that work on ESP32 (subset of Pydantic)
5. **Backward Compatible**: Existing services continue to work during migration

### Success Criteria

- ✅ All movement contracts in `tars-core`
- ✅ `movement-service` imports contracts from `tars-core`
- ✅ ESP32 firmware has validation helpers for critical paths
- ✅ All MQTT topics documented with message shapes
- ✅ 100% test coverage for contract validation
- ✅ Zero breaking changes to existing message formats

## Current Architecture Analysis

### MQTT Topics Inventory

| Topic | Publisher | Subscriber | Message Type | Architecture |
|-------|-----------|------------|--------------|--------------|
| `movement/command` | External (future) | movement-service | MovementCommand | Frame-based |
| `movement/frame` | movement-service | ESP32 (future) | MovementFrame | Frame-based |
| `movement/state` | movement-service | External (future) | MovementState | Frame-based |
| `movement/test` | External/Router | ESP32 tars_controller | TestCommand (NEW) | Command-based |
| `movement/stop` | External/Router | ESP32 tars_controller | StopCommand (NEW) | Both |
| `movement/status` | ESP32 tars_controller | Router/UI | StatusEvent (NEW) | Command-based |
| `system/health/movement` | movement-service | Health monitor | HealthPing | Frame-based |
| `system/health/movement-controller` (NEW) | ESP32 | Health monitor | HealthPing | Command-based |

### Existing Contracts (apps/movement-service)

**models.py** (currently):
```python
class MovementAction(str, Enum):
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

class MovementCommand(BaseModel):
    id: str
    command: MovementAction
    params: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)

class MovementFrame(BaseModel):
    id: str
    seq: int
    total: int
    duration_ms: int
    hold_ms: int
    channels: dict[int, int]
    disable_after: bool = False
    done: bool = False

class MovementState(BaseModel):
    id: str
    event: str
    seq: int | None = None
    detail: str | None = None
    timestamp: float = Field(default_factory=time.time)
```

### ESP32 Command Format (tars_controller.py)

**Current format** (not typed):
```json
{
  "command": "wave",
  "speed": 0.8,
  "params": {
    "height_percent": 50,
    "left_percent": 50,
    "right_percent": 50
  }
}
```

**Supported commands** (from handler.py):
- Basic: reset, step_forward, step_backward, turn_left, turn_right
- Expressive: wave, laugh, swing_legs, pezz, now, balance, mic_drop, monster, pose, bow
- Control: disable, stop
- Manual: move_legs, move_arm (with params)

## Proposed Architecture

### Contract Hierarchy

```
packages/tars-core/src/tars/contracts/v1/
├── __init__.py
├── health.py (existing)
├── movement.py (NEW - comprehensive movement contracts)
├── llm.py (existing)
├── stt.py (existing)
├── tts.py (existing)
├── memory.py (existing)
├── wake.py (existing)
└── mcp.py (existing)
```

### New movement.py Structure

```python
# packages/tars-core/src/tars/contracts/v1/movement.py

from __future__ import annotations
import uuid
import time
from enum import Enum
from pydantic import BaseModel, Field
from typing import Any, Literal

# ==============================================================================
# TOPICS (constants)
# ==============================================================================

TOPIC_MOVEMENT_COMMAND = "movement/command"      # Frame-based: external → service
TOPIC_MOVEMENT_FRAME = "movement/frame"          # Frame-based: service → ESP32
TOPIC_MOVEMENT_STATE = "movement/state"          # Frame-based: service → external
TOPIC_MOVEMENT_TEST = "movement/test"            # Command-based: external → ESP32
TOPIC_MOVEMENT_STOP = "movement/stop"            # Both: emergency stop
TOPIC_MOVEMENT_STATUS = "movement/status"        # Command-based: ESP32 → external
TOPIC_HEALTH_MOVEMENT_SERVICE = "system/health/movement"
TOPIC_HEALTH_MOVEMENT_CONTROLLER = "system/health/movement-controller"

# ==============================================================================
# ENUMS (shared vocabularies)
# ==============================================================================

class MovementAction(str, Enum):
    """Frame-based movement actions (movement-service)."""
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
    """Command-based movement commands (ESP32 tars_controller)."""
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
    """Status events published by ESP32."""
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
    """Base for all movement messages."""
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
    
    ESP32 autonomously executes movement sequences.
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
    
    Reports execution status from ESP32.
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
    """
    reason: str | None = None


# ==============================================================================
# MANUAL CONTROL PARAMETERS
# ==============================================================================

class MoveLegsParams(BaseModel):
    """Parameters for manual move_legs command."""
    height_percent: float = Field(ge=1, le=100)
    left_percent: float = Field(ge=1, le=100)
    right_percent: float = Field(ge=1, le=100)
    
    model_config = {"extra": "forbid"}


class MoveArmParams(BaseModel):
    """Parameters for manual move_arm command."""
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
    
    Raises:
        pydantic.ValidationError if invalid
    """
    return TestMovementRequest.model_validate(data)


def validate_movement_command(data: dict) -> MovementCommand:
    """
    Validate and parse movement/command message.
    
    Raises:
        pydantic.ValidationError if invalid
    """
    return MovementCommand.model_validate(data)
```

### MicroPython Compatibility Strategy

Since ESP32 can't run full Pydantic, we'll create lightweight validation helpers:

```python
# firmware/esp32/lib/validation.py (NEW)

"""
Lightweight validation helpers for MicroPython (ESP32).

Subset of Pydantic functionality that works on MicroPython.
For full validation, use tars-core contracts on the host.
"""

try:
    import ujson as json
except ImportError:
    import json


class ValidationError(Exception):
    """Validation failed."""
    pass


def validate_test_movement(data: dict) -> dict:
    """
    Validate movement/test command structure.
    
    Required fields:
    - command: str (one of valid commands)
    
    Optional fields:
    - speed: float (0.1-1.0, default 1.0)
    - params: dict (default {})
    - request_id: str
    - message_id: str
    - timestamp: float
    
    Returns:
        dict: Validated data with defaults applied
    
    Raises:
        ValidationError: If invalid
    """
    if not isinstance(data, dict):
        raise ValidationError("data must be dict")
    
    if "command" not in data:
        raise ValidationError("missing required field: command")
    
    command = data["command"]
    if not isinstance(command, str):
        raise ValidationError("command must be string")
    
    # Validate command is in supported list
    valid_commands = [
        "reset", "step_forward", "step_backward", "turn_left", "turn_right",
        "wave", "laugh", "swing_legs", "pezz", "pezz_dispenser",
        "now", "balance", "mic_drop", "monster", "pose", "bow",
        "disable", "stop", "move_legs", "move_arm"
    ]
    
    if command not in valid_commands:
        raise ValidationError(f"invalid command: {command}")
    
    # Apply defaults
    result = {
        "command": command,
        "speed": data.get("speed", 1.0),
        "params": data.get("params", {}),
    }
    
    # Validate speed
    speed = result["speed"]
    if not isinstance(speed, (int, float)):
        raise ValidationError("speed must be number")
    if speed < 0.1 or speed > 1.0:
        raise ValidationError("speed must be 0.1-1.0")
    
    # Validate params
    if not isinstance(result["params"], dict):
        raise ValidationError("params must be dict")
    
    # Pass through optional tracking fields
    if "request_id" in data:
        result["request_id"] = data["request_id"]
    if "message_id" in data:
        result["message_id"] = data["message_id"]
    if "timestamp" in data:
        result["timestamp"] = data["timestamp"]
    
    return result


def validate_emergency_stop(data: dict) -> dict:
    """
    Validate movement/stop command.
    
    All fields optional:
    - reason: str
    - message_id: str
    - timestamp: float
    
    Returns:
        dict: Validated data
    
    Raises:
        ValidationError: If invalid
    """
    if not isinstance(data, dict):
        raise ValidationError("data must be dict")
    
    result = {}
    
    if "reason" in data:
        if not isinstance(data["reason"], str):
            raise ValidationError("reason must be string")
        result["reason"] = data["reason"]
    
    if "message_id" in data:
        result["message_id"] = data["message_id"]
    if "timestamp" in data:
        result["timestamp"] = data["timestamp"]
    
    return result
```

## Implementation Plan

### Phase 1: Create tars-core Movement Contracts (Week 1)

**Tasks:**
1. ✅ Create `packages/tars-core/src/tars/contracts/v1/movement.py`
   - All enums (MovementAction, TestMovementCommand, MovementStatusEvent, MovementStateEvent)
   - All message models (MovementCommand, MovementFrame, MovementState, TestMovementRequest, MovementStatusUpdate, EmergencyStopCommand)
   - Manual control param models (MoveLegsParams, MoveArmParams)
   - Topic constants
   - Helper functions

2. ✅ Update `packages/tars-core/src/tars/contracts/v1/__init__.py`
   - Export all movement contracts

3. ✅ Add tests: `packages/tars-core/tests/test_movement_contracts.py`
   - Test all message validation (valid/invalid cases)
   - Test enum values
   - Test extra field rejection (`extra="forbid"`)
   - Test field constraints (speed 0.1-1.0, percentages 1-100)
   - Test JSON round-trip with orjson

4. ✅ Update `packages/tars-core/pyproject.toml`
   - Ensure orjson dependency

**Deliverables:**
- Comprehensive movement contracts in tars-core
- 100% test coverage for contract validation
- Documentation in docstrings

**Estimated Time**: 4-6 hours

### Phase 2: Update movement-service (Week 1)

**Tasks:**
1. ✅ Update `apps/movement-service/movement_service/models.py`
   - Import contracts from tars-core: `from tars.contracts.v1.movement import MovementCommand, MovementFrame, MovementState, MovementAction`
   - Remove local definitions
   - Keep this file if needed for service-specific models

2. ✅ Update `apps/movement-service/movement_service/service.py`
   - Import from tars-core contracts
   - Update message validation: use `MovementCommand.model_validate_json(payload)`
   - Add correlation IDs to published messages

3. ✅ Update `apps/movement-service/movement_service/config.py`
   - Import topic constants from tars-core
   - Use `TOPIC_MOVEMENT_COMMAND`, etc.

4. ✅ Update `apps/movement-service/movement_service/sequences.py`
   - Import MovementCommand, MovementFrame from tars-core

5. ✅ Update tests: `apps/movement-service/tests/test_models.py`
   - Import from tars-core
   - Test still pass

6. ✅ Update tests: `apps/movement-service/tests/test_sequences.py`
   - Import from tars-core
   - Test still pass

7. ✅ Update `apps/movement-service/pyproject.toml`
   - Add dependency: `tars-core = {path = "../../packages/tars-core", develop = true}`

**Deliverables:**
- movement-service uses tars-core contracts
- No breaking changes to MQTT message formats
- All tests pass

**Estimated Time**: 3-4 hours

### Phase 3: Add ESP32 Validation Helpers (Week 2)

**Tasks:**
1. ✅ Create `firmware/esp32/lib/validation.py`
   - Lightweight validation for movement/test messages
   - Lightweight validation for movement/stop messages
   - ValidationError exception class
   - Self-tests (run on import)

2. ✅ Update `firmware/esp32/movements/handler.py`
   - Import validation helpers: `from lib.validation import validate_test_movement, ValidationError`
   - Replace `parse_command()` logic with `validate_test_movement()`
   - Add try/except around validation
   - Publish validation errors to movement/status

3. ✅ Update `firmware/esp32/tars_controller.py`
   - Import validation helpers
   - Add validation to movement/test handler
   - Add validation to movement/stop handler

4. ✅ Add tests: `firmware/esp32/tests/test_validation.py`
   - Test valid commands
   - Test invalid commands (missing fields, wrong types, out-of-range values)
   - Test defaults applied

**Deliverables:**
- ESP32 has type-safe message parsing
- Validation errors logged and published
- Tests prove correctness

**Estimated Time**: 3-4 hours

### Phase 4: Add movement/status Publishing (Week 2)

**Tasks:**
1. ✅ Update `firmware/esp32/movements/handler.py`
   - Add `_publish_status()` method
   - Publish status on command start/complete/fail
   - Publish status on emergency stop/clear

2. ✅ Update `firmware/esp32/tars_controller.py`
   - Subscribe to movement/status for health monitoring
   - Add status event handlers

3. ✅ Create status message builder: `firmware/esp32/lib/status.py`
   - `build_status_message(event, command, detail, request_id)` helper
   - Ensures consistent structure matching tars-core contract

**Deliverables:**
- ESP32 publishes typed status events
- Status events match tars-core MovementStatusUpdate contract
- Can be consumed by Router/UI/monitoring

**Estimated Time**: 2-3 hours

### Phase 5: Update Router Integration (Week 2)

**Tasks:**
1. ✅ Update `apps/router/main.py`
   - Import from tars-core: `from tars.contracts.v1.movement import TestMovementRequest, TestMovementCommand`
   - Add movement command rules (if needed)
   - Subscribe to movement/status for feedback

2. ✅ Add movement intent detection (if needed)
   - "make TARS wave" → publish to movement/test
   - "stop moving" → publish to movement/stop

**Deliverables:**
- Router can trigger movement commands via MQTT
- Router receives status updates
- Natural language → movement commands

**Estimated Time**: 2-3 hours

### Phase 6: Documentation & Testing (Week 3)

**Tasks:**
1. ✅ Create `docs/mqtt-contracts.md`
   - Document all MQTT topics
   - Document message shapes
   - Document which services publish/subscribe
   - Document both architectures (frame-based vs command-based)

2. ✅ Update `.github/copilot-instructions.md`
   - Add section on MQTT contracts
   - Reference tars-core as source of truth
   - Add validation patterns

3. ✅ Create integration tests
   - Test movement-service → MQTT → contract validation
   - Test Router → MQTT → ESP32 contract validation
   - Test error handling (malformed messages)

4. ✅ Update README files
   - `apps/movement-service/README.md`
   - `firmware/esp32/README.md` (or .claude/ARCHITECTURE.md)
   - `packages/tars-core/README.md`

**Deliverables:**
- Comprehensive documentation
- Integration tests prove correctness
- Team knows how to use contracts

**Estimated Time**: 4-6 hours

## Migration Strategy

### Backward Compatibility

All message formats remain unchanged during migration:
- Existing `movement/command`, `movement/frame`, `movement/state` continue to work
- New `movement/test`, `movement/stop`, `movement/status` are additive
- movement-service can run side-by-side with ESP32 firmware

### Rollout Plan

1. **Week 1**: Deploy tars-core contracts, update movement-service
2. **Week 2**: Add ESP32 validation, add status publishing
3. **Week 3**: Update Router, add integration tests, finalize docs

### Rollback Strategy

If issues arise:
- Revert `apps/movement-service` to local models (simple PR revert)
- ESP32 validation is non-breaking (just removes validation layer)
- tars-core contracts don't affect existing services until imported

## Testing Strategy

### Unit Tests

- **tars-core**: Test all contract models (valid/invalid cases)
- **movement-service**: Test service logic with mocked contracts
- **ESP32**: Test validation helpers with CPython (before deploying to hardware)

### Integration Tests

- **MQTT Round-Trip**: Publish typed message → validate received message matches
- **Error Handling**: Publish malformed message → verify error handling
- **Cross-Service**: Router → ESP32 → Status → UI

### Hardware Tests

- Deploy to ESP32, send movement/test commands
- Verify movement executes correctly
- Verify status events published
- Verify emergency stop works

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking changes to existing messages | HIGH | Keep all formats unchanged; add new contracts alongside |
| MicroPython validation too heavy | MEDIUM | Keep validation minimal; validation is opt-in |
| Performance impact on ESP32 | LOW | Validation is fast dict checks; benchmarked before deploy |
| Import cycles in tars-core | MEDIUM | Keep contracts pure (no cross-imports); only Pydantic deps |
| Movement-service already used in prod | LOW | User confirmed not in prod; free to modify |

## Success Metrics

- ✅ 100% of movement MQTT messages have Pydantic models in tars-core
- ✅ Zero breaking changes to existing message formats
- ✅ All unit tests pass (tars-core, movement-service, ESP32 validation)
- ✅ Integration test proves Router → ESP32 → Status works end-to-end
- ✅ Documentation complete for all MQTT topics
- ✅ Team uses contracts for all new MQTT messages

## Future Enhancements

### Phase 7: Extend to Other Services (Future)

Apply same pattern to other MQTT topics:
- STT contracts (already in tars-core, audit for completeness)
- TTS contracts (already in tars-core, audit for completeness)
- LLM contracts (already in tars-core, audit for completeness)
- Memory contracts (already in tars-core, audit for completeness)
- Wake contracts (already in tars-core, audit for completeness)

### Phase 8: Contract Registry (Future)

Create runtime contract registry:
```python
# tars-core/contracts/registry.py
from tars.contracts.v1 import movement, health, llm

TOPIC_TO_CONTRACT = {
    "movement/test": movement.TestMovementRequest,
    "movement/stop": movement.EmergencyStopCommand,
    "movement/status": movement.MovementStatusUpdate,
    "system/health/*": health.HealthPing,
    # ... etc
}

def validate_message(topic: str, payload: bytes):
    contract = TOPIC_TO_CONTRACT.get(topic)
    if contract:
        return contract.model_validate_json(payload)
    return None  # Unknown topic
```

### Phase 9: OpenAPI/AsyncAPI Spec Generation (Future)

Generate API docs from Pydantic models:
- AsyncAPI spec for all MQTT topics
- Swagger UI for exploration
- Client SDK generation (TypeScript for UI)

## Appendix A: Example Message Flows

### Flow 1: Command-Based Movement (Router → ESP32)

```
1. Router receives "make TARS wave"
2. Router publishes to movement/test:
   {
     "command": "wave",
     "speed": 0.8,
     "request_id": "abc123",
     "message_id": "xyz789",
     "timestamp": 1696281234.5
   }
3. ESP32 validates message with validate_test_movement()
4. ESP32 queues command
5. ESP32 publishes to movement/status:
   {
     "event": "command_started",
     "command": "wave",
     "request_id": "abc123",
     "message_id": "def456",
     "timestamp": 1696281234.6
   }
6. ESP32 executes wave sequence
7. ESP32 publishes to movement/status:
   {
     "event": "command_completed",
     "command": "wave",
     "request_id": "abc123",
     "message_id": "ghi789",
     "timestamp": 1696281238.2
   }
```

### Flow 2: Emergency Stop

```
1. User says "stop"
2. Router publishes to movement/stop:
   {
     "reason": "user requested stop",
     "message_id": "stop123",
     "timestamp": 1696281240.0
   }
3. ESP32 validates with validate_emergency_stop()
4. ESP32 executes emergency_stop()
5. ESP32 publishes to movement/status:
   {
     "event": "emergency_stop",
     "detail": "user requested stop",
     "message_id": "stop456",
     "timestamp": 1696281240.1
   }
```

### Flow 3: Frame-Based Movement (Future)

```
1. External service publishes to movement/command:
   {
     "id": "cmd123",
     "command": "step_forward",
     "params": {},
     "message_id": "msg123",
     "timestamp": 1696281250.0
   }
2. movement-service validates with MovementCommand.model_validate_json()
3. movement-service calculates frames
4. movement-service publishes to movement/frame (multiple):
   {
     "id": "cmd123",
     "seq": 0,
     "total": 5,
     "duration_ms": 400,
     "hold_ms": 0,
     "channels": {0: 1500, 1: 1500, 2: 1500},
     "disable_after": false,
     "done": false,
     "message_id": "frame0",
     "timestamp": 1696281250.1
   }
5. movement-service publishes to movement/state:
   {
     "id": "cmd123",
     "event": "frame_sent",
     "seq": 0,
     "message_id": "state0",
     "timestamp": 1696281250.1
   }
6. Repeat for all frames
7. Final state:
   {
     "id": "cmd123",
     "event": "completed",
     "seq": 4,
     "message_id": "state_done",
     "timestamp": 1696281253.0
   }
```

## Appendix B: File Checklist

### New Files
- ✅ `packages/tars-core/src/tars/contracts/v1/movement.py`
- ✅ `packages/tars-core/tests/test_movement_contracts.py`
- ✅ `firmware/esp32/lib/validation.py`
- ✅ `firmware/esp32/lib/status.py`
- ✅ `firmware/esp32/tests/test_validation.py`
- ✅ `docs/mqtt-contracts.md`
- ✅ `plan/mqtt-contracts-refactor.md` (this file)

### Modified Files
- ✅ `packages/tars-core/src/tars/contracts/v1/__init__.py`
- ✅ `packages/tars-core/pyproject.toml`
- ✅ `apps/movement-service/movement_service/models.py`
- ✅ `apps/movement-service/movement_service/service.py`
- ✅ `apps/movement-service/movement_service/config.py`
- ✅ `apps/movement-service/movement_service/sequences.py`
- ✅ `apps/movement-service/tests/test_models.py`
- ✅ `apps/movement-service/tests/test_sequences.py`
- ✅ `apps/movement-service/pyproject.toml`
- ✅ `firmware/esp32/movements/handler.py`
- ✅ `firmware/esp32/tars_controller.py`
- ✅ `apps/router/main.py` (optional)
- ✅ `.github/copilot-instructions.md`
- ✅ `apps/movement-service/README.md`
- ✅ `firmware/esp32/.claude/ARCHITECTURE.md`
- ✅ `packages/tars-core/README.md`

## Appendix C: Validation Examples

### Python (tars-core) Validation

```python
from tars.contracts.v1.movement import TestMovementRequest

# Valid
msg = TestMovementRequest(command="wave", speed=0.8)
assert msg.command == "wave"
assert msg.speed == 0.8

# Invalid - speed out of range
try:
    msg = TestMovementRequest(command="wave", speed=1.5)
except ValidationError as e:
    print(e)  # speed must be <= 1.0

# Invalid - extra field
try:
    TestMovementRequest(command="wave", extra_field="oops")
except ValidationError as e:
    print(e)  # Extra inputs not permitted
```

### MicroPython (ESP32) Validation

```python
from lib.validation import validate_test_movement, ValidationError

# Valid
data = {"command": "wave", "speed": 0.8}
validated = validate_test_movement(data)
assert validated["command"] == "wave"
assert validated["speed"] == 0.8

# Invalid - missing command
try:
    validate_test_movement({"speed": 0.8})
except ValidationError as e:
    print(e)  # missing required field: command

# Invalid - speed out of range
try:
    validate_test_movement({"command": "wave", "speed": 1.5})
except ValidationError as e:
    print(e)  # speed must be 0.1-1.0
```

---

**End of Plan**
