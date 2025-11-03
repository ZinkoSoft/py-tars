# Phase 1: Data Model

**Feature**: Adopt TARS AI Movement System Updates  
**Date**: 2025-10-23

## Entity Overview

This feature does not introduce new entities but enhances existing ones with additional state tracking and error handling capabilities.

---

## Entity: ServoController (Enhanced)

**Purpose**: Manages coordinated multi-servo movements with async control, position tracking, and I2C error recovery

**Location**: `firmware/esp32_test/servo_controller.py`

### Attributes

| Attribute | Type | Description | Validation |
|-----------|------|-------------|------------|
| `pca9685` | PCA9685 | Hardware PWM controller instance | Required, must be initialized |
| `positions` | list[int] | Current PWM positions for all 9 servos (0-4095) | Length=9, values in SERVO_CALIBRATION range |
| `locks` | list[asyncio.Lock] | Per-channel locks for thread-safe access | Length=9, one per servo |
| `emergency_stop` | bool | Emergency stop flag to cancel movements | Default False |
| `global_speed` | float | Global speed multiplier (0.1-1.0) | Range 0.1-1.0 |
| `active_sequence` | str \| None | Name of currently executing preset (None if idle) | Used to prevent concurrent execution |
| `i2c_lock` | asyncio.Lock | **NEW**: Global I2C bus lock for retry operations | Shared across all channels |
| `MAX_RETRIES` | int | **NEW**: Maximum I2C retry attempts | Constant = 3 |

### State Transitions

```
Idle → Executing → Idle
  ↓       ↓         ↑
  ↓   Emergency → Disabled
  ↓       ↓
  └─> Error → Retry (up to MAX_RETRIES) → Success/Failure
```

**State Descriptions**:
- **Idle**: `active_sequence = None`, no movements executing
- **Executing**: `active_sequence = <preset_name>`, movement in progress
- **Emergency**: `emergency_stop = True`, all servos disabled
- **Error**: I2C communication failure, entering retry loop
- **Retry**: Waiting 50ms before retry attempt
- **Disabled**: All servos PWM=0 (floating state)

### Enhanced Methods

#### `move_servo_smooth(channel, target, speed)` - ENHANCED

**Changes**:
- Add `async with self.i2c_lock` around PCA9685 operations
- Update `self.positions[channel]` during movement (not just at end)
- Add retry logic with 50ms delays on OSError
- Add defensive errno checking (errno 121 detection)

**Signature**:
```python
async def move_servo_smooth(self, channel: int, target: int, speed: float = None) -> None
```

**New Behavior**:
```python
async with self.locks[channel]:  # Existing per-channel lock
    async with self.i2c_lock:    # NEW: Global I2C lock
        for attempt in range(MAX_RETRIES):
            try:
                self.pca9685.set_pwm(channel, 0, position)
                self.positions[channel] = position  # Update each step
                break
            except OSError as e:
                # Retry with 50ms delay
```

#### `initialize_servos()` - ENHANCED

**Changes**:
- Wrap all PCA9685 operations with retry logic
- Set all 16 channels to 0 initially (not just 9 active channels)
- Add errno 121 specific error detection

**New Behavior**:
```python
def initialize_servos(self):
    # Set all 16 channels to 0 (floating state)
    for channel in range(16):
        self._set_pwm_with_retry(channel, 0)
    
    # Initialize 9 active servos to safe positions
    for channel in range(9):
        # existing logic with retry
```

#### `_set_pwm_with_retry(channel, pulse)` - NEW METHOD

**Purpose**: Centralize I2C retry logic for all PWM operations

**Signature**:
```python
async def _set_pwm_with_retry(self, channel: int, pulse: int) -> bool
```

**Implementation**:
```python
async def _set_pwm_with_retry(self, channel, pulse):
    """Set PWM with automatic retry on I2C errors"""
    async with self.i2c_lock:
        for attempt in range(self.MAX_RETRIES):
            try:
                self.pca9685.set_pwm(channel, 0, pulse)
                return True
            except OSError as e:
                is_remote_io = (hasattr(e, 'errno') and e.errno == 121) or \
                               "Remote I/O" in str(e)
                
                if is_remote_io and attempt < self.MAX_RETRIES - 1:
                    print(f"I2C retry {attempt+1}/{self.MAX_RETRIES} on ch{channel}")
                    await asyncio.sleep(0.05)  # 50ms delay
                    continue
                else:
                    print(f"I2C error on ch{channel}: {e}")
                    return False
    return False
```

**Returns**: `True` if successful, `False` if all retries exhausted

---

## Entity: MovementPreset (Updated)

**Purpose**: Defines coordinated servo movement sequences

**Location**: `firmware/esp32_test/movement_presets.py`

### Structure

```python
{
    "PRESET_NAME": {
        "steps": [
            {
                "targets": {channel: pulse_width, ...},
                "speed": float,
                "wait": float,  # seconds
                "description": str
            },
            ...
        ]
    }
}
```

### Updated Preset: PRESET_STEP_FORWARD

**Changes**: Updated percentage values and timing for smoother gait

**Before**:
```python
"PRESET_STEP_FORWARD": {
    "steps": [
        # Original sequence (different percentages)
    ]
}
```

**After**:
```python
"PRESET_STEP_FORWARD": {
    "steps": [
        {
            "targets": make_leg_targets(50, 50, 50),  # Neutral
            "speed": 0.4,
            "wait": 0.2,
            "description": "Start from neutral"
        },
        {
            "targets": make_leg_targets(22, 50, 50),  # Lower (was 28)
            "speed": 0.6,
            "wait": 0.2,
            "description": "Lower legs"
        },
        {
            "targets": make_leg_targets(40, 17, 17),  # Shift weight (NEW combo)
            "speed": 0.65,
            "wait": 0.2,
            "description": "Shift weight forward"
        },
        {
            "targets": make_leg_targets(85, 50, 50),  # Lift higher (was 55)
            "speed": 0.8,
            "wait": 0.2,
            "description": "Lift legs"
        },
        {
            "targets": make_leg_targets(50, 50, 50),  # Return to neutral
            "speed": 1.0,
            "wait": 0.5,  # Longer pause (was 0.2)
            "description": "Return to neutral"
        }
    ]
}
```

**Validation Rules**:
- All target pulse widths must be within SERVO_CALIBRATION min/max
- Speed values must be 0.1-1.0
- Wait values must be ≥0

---

## Entity: I2CErrorState (Conceptual)

**Purpose**: Tracks retry attempts and error recovery state

**Lifetime**: Per I2C operation (not persisted)

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `attempt` | int | Current retry attempt (0-2) |
| `channel` | int | Servo channel being operated on |
| `operation` | str | Operation type ("set_pwm", "init") |
| `last_error` | OSError | Last exception encountered |
| `is_remote_io` | bool | Whether error is errno 121 |

### State Machine

```
[Attempt 0] → Try I2C → Success → Done
     ↓
   Error → Is Remote I/O? → Yes → Wait 50ms → [Attempt 1]
     ↓                  ↓
     No                 No → Fail
     ↓
   Fail
```

**Retry Conditions**:
- Error is OSError
- Error is errno 121 (Remote I/O) OR contains "Remote I/O" in message
- Attempt count < MAX_RETRIES

**Termination Conditions**:
- Success (return True)
- Max retries exhausted (return False)
- Non-retriable error (return False)

---

## Relationships

```
ServoController (1) ──manages──> (9) ServoChannels
       │
       ├──executes──> (N) MovementPresets
       │
       ├──tracks──> (9) PositionStates
       │
       └──handles──> (N) I2CErrorStates (transient)

MovementPreset (1) ──contains──> (N) PresetSteps
       │
       └──references──> SERVO_CALIBRATION (static config)
```

---

## Data Invariants

### Servo Positions
- `len(self.positions) == 9` (always)
- `SERVO_CALIBRATION[ch]["min"] ≤ self.positions[ch] ≤ SERVO_CALIBRATION[ch]["max"]`
- Updated atomically within lock context

### Lock State
- Per-channel locks prevent concurrent updates to same servo
- Global I2C lock prevents concurrent hardware access
- Lock acquisition order: channel lock → i2c lock (prevent deadlock)

### Active Sequence
- `self.active_sequence != None` ⟹ preset executing
- Only one preset can execute at a time
- Set in `try` block, cleared in `finally` block (guaranteed cleanup)

### Emergency Stop
- `self.emergency_stop == True` ⟹ all movements cancelled
- Reset to False after emergency procedure completes
- Checked at start of every movement loop iteration

---

## Validation Functions (from servo_config.py)

These validation functions ensure data integrity:

```python
validate_channel(channel: int) -> bool
    # Ensures channel in range 0-8

validate_pulse_width(channel: int, pulse: int) -> bool
    # Ensures pulse within SERVO_CALIBRATION[channel] min/max

validate_speed(speed: float) -> bool
    # Ensures speed in range 0.1-1.0

validate_targets(targets: dict) -> bool
    # Validates entire movement target dictionary
```

All validation functions raise `ValueError` on invalid input.

---

## Migration Notes

### Backward Compatibility

✅ **Preserves**: All existing ServoController public API  
✅ **Preserves**: Movement preset structure  
✅ **Preserves**: Servo calibration data  
⚠️ **Changes**: Internal implementation (retry logic, position tracking)  
⚠️ **Changes**: PRESET_STEP_FORWARD sequence values (visual change in movement)

### Testing Implications

**Contract Tests** (can be automated):
- Validate movement preset structure
- Verify target pulse widths within calibration ranges
- Check speed/wait values are valid

**Integration Tests** (require hardware):
- Verify I2C retry recovery with loose wiring
- Validate position tracking accuracy across movements
- Confirm step_forward executes smoothly with new sequence
- Test concurrent move_legs + move_arm operations

---

## Error Handling Model

### Error Categories

| Error Type | Retry? | Action |
|------------|--------|--------|
| errno 121 (Remote I/O) | Yes (3×) | Log retry, wait 50ms, retry |
| Other OSError | No | Log error, return False |
| ValueError (invalid input) | No | Raise immediately |
| CancelledError (emergency stop) | No | Propagate cancellation |

### Error Recovery Flow

```
I2C Operation → OSError
    ↓
Check errno 121?
    ↓ Yes                    ↓ No
Attempt < MAX_RETRIES?   Log & return False
    ↓ Yes      ↓ No
Wait 50ms    Log & return False
    ↓
Retry operation
```

---

## Performance Characteristics

**Expected Behavior**:
- **Normal operation**: Single I2C write per step (~2-5ms)
- **Transient error**: 3 retries × 50ms = ~150ms max recovery time
- **Position updates**: Minimal overhead (int assignment per step)
- **Lock contention**: Rare (movements are sequential within channel)

**Memory Impact**:
- New `i2c_lock`: ~20 bytes (asyncio.Lock object)
- No additional position storage (reuses existing list)
- No new globals or large data structures
