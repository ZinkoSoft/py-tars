# Servo Command Specification

**Feature**: ESP32 MicroPython Servo Control System  
**Version**: 1.0  
**Date**: 2025-10-15

## Overview

This document specifies the internal servo control commands and data structures used by the `ServoController` class. These are the low-level operations that the HTTP API (`/control` endpoint) translates into.

## Servo Channel Mapping

The TARS robot has 9 servos connected to PCA9685 channels 0-8:

| Channel | Functional Name | Purpose | Min Pulse | Max Pulse | Neutral |
|---------|----------------|---------|-----------|-----------|---------|
| 0 | Main Legs Lift | Raises/lowers both legs (LDX-227) | 220 | 350 | 300 |
| 1 | Left Leg Rotation (Starboard) | Starboard drive servo (LDX-227) | 192 | 408 | 300 |
| 2 | Right Leg Rotation (Port) | Port drive servo (LDX-227) | 192 | 408 | 300 |
| 3 | Right Main Arm (Shoulder) | Right shoulder joint (MG996R) | 135 | 440 | 287 |
| 4 | Right Forearm (Elbow) | Right elbow joint (MG90S) | 200 | 380 | 290 |
| 5 | Right Hand (Wrist) | Right wrist/hand (MG90S) | 200 | 280 | 240 |
| 6 | Left Main Arm (Shoulder) | Left shoulder joint (MG996R) | 135 | 440 | 287 |
| 7 | Left Forearm (Elbow) | Left elbow joint (MG90S) | 200 | 380 | 290 |
| 8 | Left Hand (Wrist) | Left wrist/hand (MG90S) | 280 | 380 | 330 |

**Notes (V2 Configuration)**:
- **Pulse widths** are in PCA9685 units (0-4095 range), constrained to 0-600 for servo safety
- **MOVEMENT_VERSION = V2** from config.ini (V1 values are deprecated)
- **Channel 0**: Min=upHeight (220), Max=downHeight (350) - raising legs goes to lower PWM value. **LDX-227 servo**.
- **Channels 1-2**: **LDX-227 servos** with ±108 range from neutral (300). Min=192, Max=408 (wider than MG996R's ±80 range).
- **Channels 3, 6 (Shoulders)**: **MG996R servos** (high torque for shoulder joints)
- **Channels 4-5, 7-8 (Forearms/Hands)**: **MG90S servos** (lightweight for extremities)
- **Channel 5 (Right Hand)**: Max is 280 (not 380) to prevent over-extension of hand mechanism
- **Channel 8 (Left Hand)**: Inverted range (280-380) compared to right hand (200-280)
- **Min/Max values** are mechanical limits - exceeding these may cause servo binding or damage
- **Neutral positions** are calculated midpoints to avoid startup strain

**Servo Type Distribution**:
- **LDX-227** (3x): Channels 0-2 (legs) - High torque, wide rotation
- **MG996R** (2x): Channels 3, 6 (shoulders) - High torque for heavy lifting
- **MG90S** (4x): Channels 4-5, 7-8 (forearms/hands) - Lightweight, precise control

**Notes**:
- Pulse widths are in PCA9685 units (0-4095 range), constrained to 0-600 for servo safety
- Min/Max values are mechanical limits - exceeding these may cause servo binding or damage
- Neutral positions are safe starting points for initialization

---

## Core Commands

### 1. Move Single Servo

**Function**: `async move_servo_smooth(channel, target, speed)`

**Description**: Move a single servo from its current position to a target position with smooth interpolation.

**Parameters**:
- `channel` (int): Servo channel (0-8)
- `target` (int): Target pulse width (must be in range [min_pulse, max_pulse] for this servo)
- `speed` (float): Speed factor (0.1=slow, 1.0=fast). Affects delay between incremental steps.

**Behavior**:
1. Acquire lock for `channel` (wait if another movement is in progress)
2. Get current position from `positions[channel]`
3. Calculate step direction: `+1` if moving up, `-1` if moving down
4. Loop from current to target in increments of 1:
   - Check `emergency_stop` flag (raise `CancelledError` if true)
   - Set PWM via `pca9685.set_pwm(channel, 0, position)`
   - Update `positions[channel] = position`
   - Sleep `0.02 * (1.0 - speed)` seconds (20ms at speed=1.0, 200ms at speed=0.1)
5. Release lock

**Returns**: None (async function completes when movement finishes)

**Raises**:
- `ValueError`: If `channel` invalid (not 0-8) or `target` out of range
- `asyncio.CancelledError`: If emergency stop activated during movement
- `RuntimeError`: If lock acquisition times out (another task holding lock too long)

**Example**:
```python
# Move servo 0 (Main Legs Lift) to position 400 at 80% speed
await servo_controller.move_servo_smooth(0, 400, 0.8)
```

**Timing**:
- For 100-unit movement at speed=1.0: 100 * 20ms = 2 seconds
- For 100-unit movement at speed=0.5: 100 * 40ms = 4 seconds
- For 100-unit movement at speed=0.1: 100 * 180ms = 18 seconds

---

### 2. Move Multiple Servos

**Function**: `async move_multiple(targets, speed)`

**Description**: Move multiple servos simultaneously (in parallel) to their respective targets.

**Parameters**:
- `targets` (dict): Map of `{channel: target_pulse}` for servos to move
- `speed` (float): Speed factor applied to all servos (0.1-1.0)

**Behavior**:
1. Create async task for each `(channel, target)` pair in `targets`
2. Each task calls `move_servo_smooth(channel, target, speed)`
3. Use `asyncio.gather(*tasks, return_exceptions=True)` to run all tasks in parallel
4. Wait for all tasks to complete or cancel

**Returns**: None (async function completes when all movements finish)

**Raises**:
- `ValueError`: If any channel invalid or target out of range
- `asyncio.CancelledError`: If emergency stop activated (propagates from child tasks)

**Example**:
```python
# Move 3 servos simultaneously
await servo_controller.move_multiple({
    0: 350,  # Main legs lift
    1: 400,  # Left leg rotation
    2: 200   # Right leg rotation
}, speed=0.6)
```

**Notes**:
- Servos with different travel distances will complete at different times
- Each servo acquires its own lock independently
- If one servo is already moving (lock held), its task will wait for lock

---

### 3. Emergency Stop

**Function**: `async emergency_stop_all()`

**Description**: Immediately disable all servos by setting PWM to 0 (floating state). Cancels all active movement tasks.

**Parameters**: None

**Behavior**:
1. Set `emergency_stop = True` flag
2. Wait 100ms for active movement tasks to detect flag and cancel
3. Set all servos (channels 0-15) to PWM=0: `pca9685.set_pwm(ch, 0, 0)`
4. Set `emergency_stop = False` flag

**Returns**: None

**Raises**: Never raises (always succeeds)

**Example**:
```python
await servo_controller.emergency_stop_all()
```

**Timing**: Completes within 100ms (SC-004 requirement)

**Notes**:
- Movement tasks check `emergency_stop` flag every iteration (every 20ms)
- Setting PWM=0 causes servo to go into floating state (no torque)
- Does NOT update `positions` array (positions remain at last known values)
- After emergency stop, servos can be re-commanded to move again

---

### 4. Disable All Servos

**Function**: `disable_all_servos()`

**Description**: Set all servos to floating state (PWM=0) without cancelling tasks. Used at end of sequences.

**Parameters**: None

**Behavior**:
1. Loop through all 16 channels
2. Set each to PWM=0: `pca9685.set_pwm(ch, 0, 0)`
3. No task cancellation (unlike emergency stop)

**Returns**: None

**Example**:
```python
servo_controller.disable_all_servos()
```

**Notes**:
- Synchronous function (not async)
- Does not set `emergency_stop` flag
- Used after preset sequences complete to reduce holding torque

---

### 5. Reset to Neutral Positions

**Function**: `async reset_positions(speed)`

**Description**: Move all servos to their neutral (safe) positions.

**Parameters**:
- `speed` (float): Speed factor for movement (0.1-1.0)

**Behavior**:
1. Get neutral position for each servo from `SERVO_CALIBRATION`
2. Call `move_multiple({0: neutral0, 1: neutral1, ...}, speed)`
3. Wait for all movements to complete
4. Optionally disable servos after reaching neutral

**Returns**: None

**Example**:
```python
await servo_controller.reset_positions(speed=0.4)
```

**Notes**:
- Neutral positions: [300, 300, 300, 200, 200, 200, 200, 200, 200]
- Used during initialization and as part of some preset sequences

---

## Preset Movement Sequences

Presets are defined as lists of `MovementStep` (see data-model.md). Each step specifies:
- `targets`: Which servos to move and to what positions
- `speed`: Speed factor for this step
- `delay_after`: How long to wait after step completes before next step

### Execution Flow

**Function**: `async execute_preset(preset_name)`

**Parameters**:
- `preset_name` (str): Name of preset to execute (e.g., "step_forward")

**Behavior**:
```python
async def execute_preset(self, preset_name):
    if self.active_sequence is not None:
        raise RuntimeError(f"Sequence '{self.active_sequence}' already running")
    
    preset = PRESETS.get(preset_name)
    if preset is None:
        raise ValueError(f"Unknown preset: {preset_name}")
    
    self.active_sequence = preset_name
    
    try:
        for step in preset['steps']:
            # Move servos in parallel
            await self.move_multiple(step['targets'], step['speed'])
            
            # Wait before next step
            await asyncio.sleep(step['delay_after'])
            
            # Check if emergency stop activated
            if self.emergency_stop:
                raise asyncio.CancelledError("Emergency stop during preset")
        
        # Sequence complete - disable servos
        self.disable_all_servos()
        
    finally:
        self.active_sequence = None
```

**Returns**: None

**Raises**:
- `ValueError`: If `preset_name` unknown
- `RuntimeError`: If another sequence already running
- `asyncio.CancelledError`: If emergency stop activated during execution

---

## Preset Definitions

All presets are defined in `movement_presets.py` as dictionaries. Here are the 13 required presets:

### 1. reset_positions

**Description**: Move to neutral stance (safe starting position)

**Steps**:
1. Lift legs to 20% height at speed 0.2
2. Move legs to 30% height, center rotation at speed 0.2
3. Move to 50% height (neutral) at speed 0.2
4. Move arms to minimum positions at speed 0.3
5. Disable all servos

**Total Duration**: ~3-4 seconds

---

### 2. step_forward

**Description**: Walk forward one step

**Steps**:
1. Neutral stance (50% height, center rotation)
2. Lower to 22% height
3. Rotate both legs forward (port 17%, starboard 17%), lift to 40%
4. Raise to 85% height
5. Return to neutral (50% height, center rotation)
6. Disable servos

**Total Duration**: ~2-3 seconds

---

### 3. step_backward

**Description**: Walk backward one step

**Steps**:
1. Neutral stance
2. Lower to 28% height, legs at 0% rotation
3. Legs to 35% height, rotation to 70%
4. Legs to 55% height, rotation to 40%
5. Return to neutral
6. Disable servos

**Total Duration**: ~2-3 seconds

---

### 4. turn_right

**Description**: Turn 90 degrees to the right

**Steps**:
1. Neutral stance
2. Lift to 100% height, legs at 0% rotation
3. Legs at 0% height, port 70%, starboard 30%
4. Legs to 50% height, keep rotation
5. Legs at 0% height, center rotation
6. Return to neutral
7. Disable servos

**Total Duration**: ~3-4 seconds

---

### 5. turn_left

**Description**: Turn 90 degrees to the left (mirror of turn_right)

**Steps**: Similar to `turn_right` but with port/starboard swapped

**Total Duration**: ~3-4 seconds

---

### 6. right_hi (Greet)

**Description**: Wave right arm

**Steps**:
1. Neutral stance
2. Lift to 80% height, starboard leg 70% rotation
3. Lower to 50% height
4. Right arm: main 100%, forearm up
5. Wave: forearm 50% → 100% → 50% → 100% (repeat 3x)
6. Lower right arm
7. Return to neutral
8. Disable servos

**Total Duration**: ~5-6 seconds

---

### 7. laugh

**Description**: Bouncing motion (rapid up/down)

**Steps**: Alternate between 50% height and 1% height rapidly (5 cycles)

**Total Duration**: ~2 seconds

---

### 8. swing_legs

**Description**: Swing legs side to side

**Steps**:
1. Lift to 100% height
2. Alternate: legs 20%/80% → 80%/20% (3 cycles)
3. Center legs
4. Return to neutral
5. Disable servos

**Total Duration**: ~3-4 seconds

---

### 9. balance

**Description**: Balance on one foot with wobbling

**Steps**:
1. Lift to 30% height
2. Wobble: legs 60% → 40% → 60% → 40% (3 cycles)
3. Return to neutral
4. Disable servos

**Total Duration**: ~4-5 seconds

---

### 10. mic_drop

**Description**: Dramatic arm drop gesture

**Steps**:
1. Lift to 80% height, starboard leg 100% rotation
2. Right arm: main 60%, forearm 50%
3. Right arm: forearm 70%
4. Wait 1 second
5. Right arm: hand 100% (drop)
6. Wait 2 seconds
7. Lower arm
8. Return to neutral
9. Disable servos

**Total Duration**: ~6-7 seconds

---

### 11. monster (Defensive Posture)

**Description**: Arms up in defensive position

**Steps**:
1. Lift to 80% height, legs 70% rotation
2. Lower to 50% height
3. Both arms: main 100%, forearm 100%, hands 100%
4. Wave hands: 50% → 100% (repeat 2x)
5. Lower arms
6. Return to neutral
7. Disable servos

**Total Duration**: ~5-6 seconds

---

### 12. pose

**Description**: Strike a pose and hold

**Steps**:
1. Neutral stance
2. Lower to 30% height, legs 40% rotation
3. Lift to 100% height, legs 30% rotation
4. Hold for 3 seconds
5. Reverse movements
6. Return to neutral
7. Disable servos

**Total Duration**: ~8-9 seconds

---

### 13. bow

**Description**: Bow forward

**Steps**:
1. Neutral stance
2. Lower to 15% height
3. Legs 70% rotation (lean forward)
4. Lift to 60% height
5. Raise to 95% height, legs 65% rotation
6. Hold for 3 seconds
7. Lower to 15% height
8. Return to neutral
9. Disable servos

**Total Duration**: ~8-9 seconds

---

## Validation Rules

### Input Validation

All servo commands must validate:

```python
def validate_channel(channel):
    """Ensure channel is valid (0-8 for 9 servos)"""
    if not isinstance(channel, int) or channel < 0 or channel > 8:
        raise ValueError(f"Invalid channel {channel}. Must be 0-8.")

def validate_pulse_width(channel, pulse):
    """Ensure pulse width is in safe range for this servo"""
    cal = SERVO_CALIBRATION[channel]
    if pulse < cal['min'] or pulse > cal['max']:
        raise ValueError(
            f"Pulse {pulse} out of range [{cal['min']}, {cal['max']}] "
            f"for channel {channel} ({cal['label']})"
        )

def validate_speed(speed):
    """Ensure speed factor is in valid range"""
    if not isinstance(speed, (int, float)) or speed < 0.1 or speed > 1.0:
        raise ValueError(f"Speed {speed} out of range [0.1, 1.0]")

def validate_targets(targets):
    """Validate multiple servo targets"""
    if not isinstance(targets, dict):
        raise TypeError("Targets must be a dictionary")
    
    for channel, pulse in targets.items():
        validate_channel(int(channel))
        validate_pulse_width(int(channel), pulse)
```

### State Validation

Before executing commands:

```python
def check_emergency_stop():
    """Verify emergency stop not active"""
    if self.emergency_stop:
        raise RuntimeError(
            "Cannot execute movement: emergency stop active. "
            "Call /resume to re-initialize."
        )

def check_memory():
    """Verify sufficient free memory"""
    free = gc.mem_free()
    if free < 150000:  # 150KB threshold
        raise RuntimeError(
            f"Insufficient memory ({free} bytes free). "
            f"Emergency stop recommended."
        )

def check_sequence_lock():
    """Verify no sequence already running"""
    if self.active_sequence is not None:
        raise RuntimeError(
            f"Cannot start preset: sequence '{self.active_sequence}' "
            f"is already running."
        )
```

---

## Error Handling

### Common Errors

1. **Invalid Channel**: Channel not in range 0-8
   ```python
   ValueError: Invalid channel 10. Must be 0-8.
   ```

2. **Pulse Width Out of Range**: Target exceeds min/max for servo
   ```python
   ValueError: Pulse 700 out of range [200, 600] for channel 0 (Main Legs Lift)
   ```

3. **Servo Locked**: Another task is moving the same servo
   ```python
   RuntimeError: Servo 0 is currently moving. Wait for completion or cancel.
   ```

4. **Sequence Running**: Cannot start preset while another runs
   ```python
   RuntimeError: Cannot start preset: sequence 'step_forward' is already running.
   ```

5. **Emergency Stop**: Movement blocked by emergency stop
   ```python
   RuntimeError: Cannot execute movement: emergency stop active.
   ```

6. **Low Memory**: Insufficient RAM to create async tasks
   ```python
   RuntimeError: Insufficient memory (120000 bytes free). Emergency stop recommended.
   ```

### Recovery Procedures

| Error | Recovery |
|-------|----------|
| Invalid input | Return 400 error to client, log error |
| Servo locked | Wait with timeout (5s), then return 409 Conflict |
| Sequence running | Return 409 Conflict to client |
| Emergency stop | Return 503 Service Unavailable, client must call /resume |
| Low memory | Call gc.collect(), if still low return 503 |
| I2C failure | Retry 3x with 100ms delay, if fails return 503 and log |

---

## Performance Characteristics

### Timing

| Operation | Expected Duration | Notes |
|-----------|------------------|-------|
| Single servo move (100 units, speed=1.0) | 2.0s | 100 * 20ms |
| Single servo move (100 units, speed=0.1) | 18.0s | 100 * 180ms |
| Emergency stop | <100ms | SC-004 requirement |
| Move 9 servos (100 units each, parallel) | 2.0s | All finish simultaneously |
| Preset sequence (average) | 3-6s | Varies by complexity |
| HTTP request → servo starts moving | <200ms | SC-003 requirement |

### Resource Usage

| Resource | Usage | Notes |
|----------|-------|-------|
| RAM per servo task | ~2 KB | Includes stack + coroutine |
| RAM for 6 concurrent tasks | ~15 KB | SC-005 requirement |
| CPU per servo movement | <5% | Mostly sleeping, minimal compute |
| I2C bandwidth | <10 KB/s | PWM updates are infrequent |

---

## Testing Checklist

### Unit Tests (Manual)

- [ ] Move single servo to min, neutral, max positions
- [ ] Verify smooth movement (no visible steps at speed=0.1)
- [ ] Move multiple servos simultaneously (verify parallel execution)
- [ ] Emergency stop during single servo movement
- [ ] Emergency stop during preset sequence
- [ ] Execute all 13 presets successfully
- [ ] Attempt invalid channel (expect ValueError)
- [ ] Attempt out-of-range pulse width (expect ValueError)
- [ ] Start preset while another running (expect RuntimeError)
- [ ] Speed variations (0.1, 0.5, 1.0) produce visible differences

### Integration Tests (Manual)

- [ ] Web interface can control all servos
- [ ] Emergency stop button works from web interface
- [ ] Preset buttons execute correct sequences
- [ ] System status shows current servo positions
- [ ] Speed slider affects subsequent movements
- [ ] System recovers after emergency stop
- [ ] Multiple browser clients don't crash server

---

## Version History

- **1.0** (2025-10-15): Initial servo command specification
