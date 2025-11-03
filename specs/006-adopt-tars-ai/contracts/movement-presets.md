# Movement Preset Contract

**Purpose**: Define the structure and validation rules for movement preset sequences

**Version**: 1.0.0  
**Date**: 2025-10-23

---

## Preset Structure

### Root Schema

```python
{
    "PRESET_NAME": PresetDefinition
}
```

### PresetDefinition

```python
{
    "steps": list[PresetStep]  # Ordered sequence of movement steps
}
```

### PresetStep

```python
{
    "targets": dict[int, int],   # Required: {channel: pulse_width}
    "speed": float,               # Required: Movement speed (0.1-1.0)
    "wait": float,                # Required: Delay after step (seconds, ≥0)
    "description": str            # Optional: Human-readable description
}
```

---

## Validation Rules

### Preset Name
- **Type**: String
- **Pattern**: `PRESET_[A-Z_]+` (uppercase with underscores)
- **Examples**: `PRESET_STEP_FORWARD`, `PRESET_TURN_LEFT`, `PRESET_WAVE_RIGHT`

### Targets Dictionary

**Schema**:
```python
targets: dict[int, int]
```

**Constraints**:
- **Keys** (channel): Integer in range 0-8
- **Values** (pulse_width): Integer within `SERVO_CALIBRATION[channel]` min/max range
- **Validation**: Must pass `validate_targets(targets)` from `servo_config.py`

**Example**:
```python
{
    0: 300,  # Main Legs Lift (neutral)
    1: 300,  # Left Leg Rotation (neutral)
    2: 300   # Right Leg Rotation (neutral)
}
```

### Speed

- **Type**: Float
- **Range**: 0.1 ≤ speed ≤ 1.0
- **Semantics**:
  - `0.1`: Slowest movement (18ms delay per step)
  - `1.0`: Fastest movement (2ms delay per step)
- **Validation**: Must pass `validate_speed(speed)`

### Wait

- **Type**: Float
- **Range**: wait ≥ 0.0
- **Units**: Seconds
- **Semantics**: Delay after movement completes before next step
- **Typical values**: 0.1-0.5 seconds

### Description

- **Type**: String (optional)
- **Purpose**: Human-readable explanation of movement step
- **Usage**: Logging, debugging, UI display

---

## Contract Examples

### Example 1: PRESET_STEP_FORWARD (Updated)

```python
"PRESET_STEP_FORWARD": {
    "steps": [
        {
            "targets": {0: 300, 1: 300, 2: 300},  # Neutral position
            "speed": 0.4,
            "wait": 0.2,
            "description": "Start from neutral"
        },
        {
            "targets": {0: 237, 1: 300, 2: 300},  # Lower legs (22%)
            "speed": 0.6,
            "wait": 0.2,
            "description": "Lower legs for weight shift"
        },
        {
            "targets": {0: 276, 1: 228, 2: 228},  # Shift weight (40% height, 17% rotation)
            "speed": 0.65,
            "wait": 0.2,
            "description": "Shift weight forward"
        },
        {
            "targets": {0: 339, 1: 300, 2: 300},  # Lift higher (85%)
            "speed": 0.8,
            "wait": 0.2,
            "description": "Lift legs to advance"
        },
        {
            "targets": {0: 300, 1: 300, 2: 300},  # Return to neutral
            "speed": 1.0,
            "wait": 0.5,
            "description": "Return to neutral position"
        }
    ]
}
```

**Calculation Note**: Percentage to pulse width conversion via `make_leg_targets(height_pct, left_pct, right_pct)`:
- 22% height → 237 pulse
- 40% height → 276 pulse
- 85% height → 339 pulse
- 17% rotation → 228 pulse

### Example 2: PRESET_NEUTRAL (Simple)

```python
"PRESET_NEUTRAL": {
    "steps": [
        {
            "targets": {0: 300, 1: 300, 2: 300, 3: 135, 4: 200, 5: 200, 6: 135, 7: 200, 8: 280},
            "speed": 0.5,
            "wait": 0.0,
            "description": "Move all servos to neutral/safe positions"
        }
    ]
}
```

---

## Validation Test Cases

### Test 1: Valid Preset

```python
preset = {
    "PRESET_TEST": {
        "steps": [
            {
                "targets": {0: 300, 1: 250, 2: 350},
                "speed": 0.5,
                "wait": 0.1,
                "description": "Test movement"
            }
        ]
    }
}
# Should: PASS
```

### Test 2: Invalid Channel

```python
preset = {
    "PRESET_INVALID": {
        "steps": [
            {
                "targets": {10: 300},  # Channel 10 doesn't exist
                "speed": 0.5,
                "wait": 0.1
            }
        ]
    }
}
# Should: FAIL - ValueError("Invalid channel 10. Must be 0-8.")
```

### Test 3: Pulse Width Out of Range

```python
preset = {
    "PRESET_INVALID": {
        "steps": [
            {
                "targets": {0: 500},  # Out of range for channel 0 (max 360)
                "speed": 0.5,
                "wait": 0.1
            }
        ]
    }
}
# Should: FAIL - ValueError("Pulse width 500 out of range for channel 0")
```

### Test 4: Invalid Speed

```python
preset = {
    "PRESET_INVALID": {
        "steps": [
            {
                "targets": {0: 300},
                "speed": 1.5,  # > 1.0
                "wait": 0.1
            }
        ]
    }
}
# Should: FAIL - ValueError("Speed 1.5 out of range. Must be 0.1-1.0")
```

### Test 5: Negative Wait

```python
preset = {
    "PRESET_INVALID": {
        "steps": [
            {
                "targets": {0: 300},
                "speed": 0.5,
                "wait": -0.1  # Negative
            }
        ]
    }
}
# Should: FAIL - ValueError("Wait time must be ≥0")
```

---

## Integration with ServoController

### Loading Presets

```python
from movement_presets import MOVEMENT_PRESETS

servo_controller = ServoController(pca9685)
await servo_controller.execute_preset("PRESET_STEP_FORWARD", MOVEMENT_PRESETS)
```

### Execution Flow

```
1. Validate preset exists in dictionary
2. Check active_sequence is None (not already running)
3. For each step:
   a. Validate targets with validate_targets()
   b. Validate speed with validate_speed()
   c. Call move_multiple(targets, speed)
   d. Wait for completion
   e. Sleep for wait duration
4. Disable all servos (floating state)
5. Clear active_sequence
```

### Error Handling

```python
try:
    await servo_controller.execute_preset("PRESET_NAME", MOVEMENT_PRESETS)
except ValueError as e:
    # Invalid preset name or validation failure
    print(f"Preset error: {e}")
except RuntimeError as e:
    # Another sequence already running
    print(f"Busy: {e}")
except Exception as e:
    # I2C errors, emergency stop, etc.
    print(f"Execution error: {e}")
```

---

## Contract Versioning

**Version**: 1.0.0

**Breaking Changes** (require major version bump):
- Change to `targets` dictionary structure
- Change to required fields in PresetStep
- Change to validation rules (stricter constraints)

**Non-Breaking Changes** (minor/patch):
- Add new optional fields to PresetStep
- Add new presets to dictionary
- Update existing preset values (if semantics unchanged)

---

## Reference Data

### SERVO_CALIBRATION Ranges (for validation)

| Channel | Label | Min | Max | Neutral |
|---------|-------|-----|-----|---------|
| 0 | Main Legs Lift | 220 | 360 | 300 |
| 1 | Left Leg Rotation | 192 | 408 | 300 |
| 2 | Right Leg Rotation | 192 | 408 | 300 |
| 3 | Right Shoulder | 135 | 440 | 135 |
| 4 | Right Elbow | 200 | 380 | 200 |
| 5 | Right Hand | 200 | 280 | 200 |
| 6 | Left Shoulder | 135 | 440 | 135 |
| 7 | Left Elbow | 200 | 380 | 200 |
| 8 | Left Hand | 280 | 380 | 280 |

---

## Compliance Checklist

For each movement preset, verify:

- [ ] Preset name follows `PRESET_[A-Z_]+` pattern
- [ ] All steps have required fields: `targets`, `speed`, `wait`
- [ ] All target channels are in range 0-8
- [ ] All target pulse widths within SERVO_CALIBRATION min/max
- [ ] All speed values in range 0.1-1.0
- [ ] All wait values ≥ 0
- [ ] Optional description is string if present
- [ ] Preset can be executed without errors
- [ ] Movement completes smoothly (visual inspection on hardware)
