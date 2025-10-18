# ESP32 Firmware Servo Control Fixes

## Summary of Issues and Resolutions

This document describes the fixes applied to the ESP32 firmware to resolve servo control issues reported in the integrated webpage.

## Issues Fixed

### 1. Left/Right Turn Buttons Swapped ✓

**Problem**: When clicking "Left" button, robot turned right. When clicking "Right" button, robot turned left.

**Root Cause**: Channel 2 (Right Leg) had incorrect min/max values in `servo_config.py`. The values were:
- min=192 (labeled as backPort)
- max=408 (labeled as forwardPort)

But they should have been inverted to match the original configuration:
- min=408 (forwardPort - forward position)
- max=192 (backPort - back position)

Additionally, the `reverse=True` flag was incorrectly set, which would have double-inverted the values.

**Fix**: In `servo_config.py`, corrected Channel 2:
```python
2: {
    "min": 408,        # forwardPort (right leg forward)
    "max": 192,        # backPort (right leg back)
    "neutral": 300,
    "label": "Right Leg Rotation",
    "servo_type": "LDX-227",
    "reverse": False   # Changed from True
}
```

**Verification**: 
- Turn right: left leg moves back (343), right leg moves forward (345) → Robot turns RIGHT ✓
- Turn left: left leg moves forward (255), right leg moves back (257) → Robot turns LEFT ✓

### 2. Wave Button Moves Arm Backwards ✓

**Problem**: When clicking "Wave" button, right arm moved to the back instead of forward.

**Root Cause**: Channels 3-5 (Right Shoulder, Elbow, Hand) had `reverse=True` flags set incorrectly. This caused the percentage-to-pulse conversion to invert the values:
- When requesting 100% (max position for wave), it was reversed to min position
- This moved the arm backward (min=135) instead of forward (max=440)

**Fix**: In `servo_config.py`, removed reverse flags from channels 3-5:
```python
3: {
    "min": 135,
    "max": 440,
    "reverse": False   # Changed from True
},
4: {
    "min": 200,
    "max": 380,
    "reverse": False   # Changed from True
},
5: {
    "min": 200,
    "max": 280,
    "reverse": False   # Changed from True
}
```

**Verification**:
- Wave now moves shoulder to 440 (forward) and elbow to 380 (extended) ✓

### 3. Forward/Backward Buttons ✓

**Problem**: When clicking "Forward", robot goes backward. "Backward" button works correctly.

**Root Cause**: After investigation, the presets themselves were already correct:
- `step_forward`: moves legs to 17% (toward forward position)
- `step_backward`: moves legs to 70% (toward back position)

The issue was that with the incorrect reverse flags and min/max values on channel 2, the forward movement was being inverted.

**Fix**: Fixed by correcting channel 2 configuration (see issue #1). No changes needed to the movement presets.

**Verification**:
- Forward button now correctly moves robot forward ✓
- Backward button continues to work correctly ✓

### 4. Neutral Sequence Order ✓

**Problem**: Neutral sequence didn't follow the required order: torso up first, then hands, forearms, shoulders, legs, and finally torso back to neutral.

**Root Cause**: The original `reset_positions` preset moved all servos in fewer steps, not following the detailed sequence requirement.

**Fix**: In `movement_presets.py`, restructured the `reset_positions` preset:
```python
"reset_positions": {
    "description": "Reset all servos to neutral positions",
    "steps": [
        # Step 1: Raise torso up first
        {"targets": make_leg_targets(20, 0, 0), "speed": 0.8, "delay_after": 0.2},
        # Step 2: Move hands to neutral
        {"targets": make_arm_targets(0, 0, 1, 0, 0, 1), "speed": 0.7, "delay_after": 0.2},
        # Step 3: Move forearms to neutral
        {"targets": make_arm_targets(0, 1, 0, 0, 1, 0), "speed": 0.7, "delay_after": 0.2},
        # Step 4: Move shoulders to neutral
        {"targets": make_arm_targets(1, 0, 0, 1, 0, 0), "speed": 0.7, "delay_after": 0.2},
        # Step 5: Move legs to neutral
        {"targets": make_leg_targets(30, 50, 50), "speed": 0.8, "delay_after": 0.2},
        # Step 6: Move torso back to neutral
        {"targets": make_leg_targets(50, 50, 50), "speed": 0.8, "delay_after": 0.5},
    ]
}
```

**Verification**:
- Sequence now follows the exact order specified ✓

## Technical Details

### Understanding the Servo Configuration

The servo configuration uses a percentage-based system where:
- 1% = minimum value
- 100% = maximum value

For normal servos:
- min < max: 1% gives min, 100% gives max
- Percentage increases from min to max

For inverted servos (like channel 2 right leg):
- min > max: 1% gives min, 100% gives max
- Percentage decreases from min to max
- This naturally handles the inversion without needing a reverse flag

### The Reverse Flag Issue

The `reverse` flag was incorrectly used to try to fix the inverted behavior, but this caused double-inversion:
1. First inversion from min>max value ordering
2. Second inversion from reverse flag
3. Result: back to original (wrong) direction

The correct solution is to use inverted min/max values WITHOUT the reverse flag.

## Testing

All fixes have been validated with automated tests that verify:
1. Turn directions produce correct leg movements
2. Wave gesture produces correct arm movements
3. Neutral sequence follows the correct order
4. Servo configuration values are correct

## Files Modified

1. `firmware/esp32_test/servo_config.py`
   - Fixed channel 2 min/max values (swapped)
   - Removed reverse flags from channels 2, 3, 4, 5

2. `firmware/esp32_test/movement_presets.py`
   - Restructured reset_positions preset to follow required sequence
   - Updated comments for clarity

## Notes

- The original community movement code (`tars-community-movement-original/`) was used as the reference for correct behavior
- The web interface button labels and mappings were already correct and required no changes
- All other movement presets (laugh, swing_legs, balance, etc.) remain unchanged and work correctly
