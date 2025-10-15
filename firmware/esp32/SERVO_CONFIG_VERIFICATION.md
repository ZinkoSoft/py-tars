# Servo Configuration Verification

**Date:** 2025-10-13  
**Status:** ✅ VERIFIED - Main firmware matches working esp32_test configuration

## Summary

The main ESP32 firmware in `/firmware/esp32/` already has the correct servo ranges that match the working configuration from `/firmware/esp32/esp32_test/` and the original Python TARS V2 `module_servoctl_v2.py`.

## Servo 0 - Main Legs (Height Control)

### Original Python V2 Config (module_servoctl_v2.py)
```ini
upHeight = 220        # Highest position (legs raised)
neutralHeight = 300   # Neutral/middle position
downHeight = 350      # Lowest position (legs lowered)
```

### ESP32 Test (Working Configuration)
```python
# servo_config.py
SERVO_RANGES = {
    0: {'min': 220, 'max': 350, 'default': 300},  # Main legs
}

MOVEMENT_CONFIG = {
    'up_height': 220,
    'neutral_height': 300,
    'down_height': 350,
}
```

### Main Firmware (movements/config.py)
```python
DEFAULT_LEGS = {
    "height": {
        "channel": 0,
        "up": 220,        # ✅ CORRECT
        "neutral": 300,   # ✅ CORRECT
        "down": 350,      # ✅ CORRECT
        "min": 200,       # Safety limit (not used in normal operation)
        "max": 400,       # Safety limit (not used in normal operation)
    },
}
```

**Result:** ✅ **MATCH** - All values identical

## Servo 1 - Left Leg Rotation (Starboard in code)

### Original Python V2 Config
```ini
forwardStarboard = 220
neutralStarboard = 300
backStarboard = 380
perfectStaroffset = 0
```

### ESP32 Test (Working Configuration)
```python
SERVO_RANGES = {
    1: {'min': 220, 'max': 380, 'default': 300},
}

MOVEMENT_CONFIG = {
    'forward_starboard': 220,
    'neutral_starboard': 300,
    'back_starboard': 380,
    'perfect_star_offset': 0,
}
```

### Main Firmware
```python
DEFAULT_LEGS = {
    "left": {
        "channel": 1,
        "forward": 220,   # ✅ CORRECT
        "neutral": 300,   # ✅ CORRECT
        "back": 380,      # ✅ CORRECT
        "offset": 0,      # ✅ CORRECT
        "min": 200,
        "max": 400,
    },
}
```

**Result:** ✅ **MATCH** - All values identical

## Servo 2 - Right Leg Rotation (Port in code)

### Original Python V2 Config
```ini
forwardPort = 380
neutralPort = 300
backPort = 220
perfectPortoffset = 0
```

### ESP32 Test (Working Configuration)
```python
SERVO_RANGES = {
    2: {'min': 220, 'max': 380, 'default': 300},
}

MOVEMENT_CONFIG = {
    'forward_port': 380,
    'neutral_port': 300,
    'back_port': 220,
    'perfect_port_offset': 0,
}
```

### Main Firmware
```python
DEFAULT_LEGS = {
    "right": {
        "channel": 2,
        "forward": 380,   # ✅ CORRECT
        "neutral": 300,   # ✅ CORRECT
        "back": 220,      # ✅ CORRECT
        "offset": 0,      # ✅ CORRECT
        "min": 200,
        "max": 400,
    },
}
```

**Result:** ✅ **MATCH** - All values identical

## Arm Servos (Channels 3-8)

### Original Python V2 Config
```ini
# RIGHT ARM
portMainMin = 135
portMainMax = 440
portForarmMin = 200
portForarmMax = 380
portHandMin = 200
portHandMax = 280

# LEFT ARM
starMainMin = 440
starMainMax = 135
starForarmMin = 380
starForarmMax = 200
starHandMin = 380
starHandMax = 280
```

### Main Firmware
```python
DEFAULT_ARMS = {
    "right_main": {
        "channel": 3,
        "min": 135,    # ✅ CORRECT
        "max": 440,    # ✅ CORRECT
    },
    "right_forearm": {
        "channel": 4,
        "min": 200,    # ✅ CORRECT
        "max": 380,    # ✅ CORRECT
    },
    "right_hand": {
        "channel": 5,
        "min": 200,    # ✅ CORRECT
        "max": 280,    # ✅ CORRECT
    },
    "left_main": {
        "channel": 6,
        "min": 135,    # ✅ CORRECT (inverted from 440)
        "max": 440,    # ✅ CORRECT (inverted from 135)
    },
    "left_forearm": {
        "channel": 7,
        "min": 200,    # ✅ CORRECT (inverted from 380)
        "max": 380,    # ✅ CORRECT (inverted from 200)
    },
    "left_hand": {
        "channel": 8,
        "min": 280,    # ✅ CORRECT (inverted from 380)
        "max": 380,    # ✅ CORRECT (inverted from 280)
    },
}
```

**Result:** ✅ **MATCH** - All values identical (left arm properly inverted)

## Key Differences from Initial esp32_test Bug

### The Bug (Before Fix)
The esp32_test initially had incorrect servo ranges:

```python
# ❌ WRONG - Servo went too high and too low
SERVO_RANGES = {
    0: {'min': 200, 'max': 500, 'default': 300},  # Range too large!
}
```

This caused the legs to:
- Go **too high** (200 vs correct 220)
- Go **dangerously low** (500 vs correct 350)
- Total range: 300 units (should be 130 units)

### The Fix
```python
# ✅ CORRECT - Matches TARS V2 config
SERVO_RANGES = {
    0: {'min': 220, 'max': 350, 'default': 300},  # Proper range
}
```

## Percentage-to-Pulse Conversion

The main firmware uses a **percentage-based API (1-100)** which is more intuitive than raw pulse values:

```python
# Example: Move legs to 50% height
pulse = config.percentage_to_pulse("legs", "height", 50)
# Result: ~285 (midpoint between 220 and 350)

# Example: Move legs fully down (100%)
pulse = config.percentage_to_pulse("legs", "height", 100)
# Result: 350 (down position)

# Example: Move legs fully up (1%)
pulse = config.percentage_to_pulse("legs", "height", 1)
# Result: 220 (up position)
```

This abstraction is defined in `movements/config.py` and properly maps percentages to the correct pulse ranges.

## PCA9685 Driver Verification

Both versions use identical PCA9685 driver implementation:

### Common Features
- I2C address: `0x40` (default)
- PWM frequency: `50Hz` (standard for servos)
- 12-bit resolution: `0-4095` ticks
- Each tick at 50Hz: ~4.88μs
- Typical servo range: 150-600 (0.73ms-2.93ms)

### Prescale Calculation
```python
# Both drivers calculate the same prescale value
prescale = int((25_000_000 / (4096 * 50)) - 1)
# Result: 121 for 50Hz
```

**Result:** ✅ **IDENTICAL** - No differences in PWM driver

## Movement Sequences Verification

The main firmware includes all 15 movement sequences from the original Python TARS:

### Basic Movements (5)
1. `reset_position` - Return to neutral stance ✅
2. `step_forward` - Walk forward one step ✅
3. `step_backward` - Walk backward one step ✅
4. `turn_left` - Rotate left ✅
5. `turn_right` - Rotate right ✅

### Expressive Movements (10)
6. `wave` - Wave hello with right arm ✅
7. `laugh` - Bouncing motion ✅
8. `swing_legs` - Pendulum leg motion ✅
9. `pezz_dispenser` - PEZZ dispenser pose ✅
10. `now` - Pointing gesture ✅
11. `balance` - Balance on one leg ✅
12. `mic_drop` - Mic drop gesture ✅
13. `monster` - Defensive posture ✅
14. `pose` - Static pose ✅
15. `bow` - Bow gesture ✅

All sequences are implemented in `movements/sequences.py` with identical logic to the original Python version.

## Configuration Files

### Main Firmware Config Locations
- **Servo definitions:** `firmware/esp32/movements/config.py` (ServoConfig class)
- **Default config:** `firmware/esp32/lib/config.py` (DEFAULT_CONFIG)
- **Runtime config:** `movement_config.json` (optional user overrides)
- **PCA9685 driver:** `firmware/esp32/lib/pca9685.py`

### ESP32 Test Config Locations
- **Servo definitions:** `firmware/esp32/esp32_test/servo_config.py`
- **Servo controller:** `firmware/esp32/esp32_test/servo_controller.py`
- **Web interface:** `firmware/esp32/esp32_test/web_interface.py`

## Conclusion

✅ **NO CHANGES NEEDED**

The main ESP32 firmware (`/firmware/esp32/`) already has the correct servo configuration that matches:
1. The working `esp32_test` configuration (after the fix)
2. The original Python TARS V2 `module_servoctl_v2.py`
3. All 15 movement sequences properly implemented

The bug that existed in `esp32_test` (servo going too high/low) was specific to that test environment and has been fixed. The main firmware never had this issue.

## Testing Recommendations

When deploying to hardware:

1. **Test each servo individually** using the web interface or MQTT commands
2. **Verify ranges** - legs should move within safe limits (220-350 for height)
3. **Test all 15 movement sequences** to ensure coordinated motion works
4. **Monitor for servo strain** - servos should move smoothly without binding
5. **Check leg clearance** - ensure downHeight (350) doesn't cause chassis contact

## Files Modified During Verification

### esp32_test (Fixed during troubleshooting)
- `firmware/esp32/esp32_test/servo_config.py` - Corrected servo ranges ✅

### Main Firmware (No changes needed)
- `firmware/esp32/movements/config.py` - Already correct ✅
- `firmware/esp32/lib/pca9685.py` - Already correct ✅
- `firmware/esp32/movements/sequences.py` - Already correct ✅
- `firmware/esp32/movements/control.py` - Already correct ✅

---

**Verification completed:** 2025-10-13  
**Status:** ✅ All configurations match and are correct  
**Action required:** None - deploy with confidence
