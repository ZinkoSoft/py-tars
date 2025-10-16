# Servo Calibration Guide - TARS Servo Controller

Guide for calibrating and adjusting servo ranges for your specific hardware.

## Overview

Each servo has different physical characteristics and mounting positions. The calibration values in `servo_config.py` define the safe operating range for each servo to prevent mechanical damage.

## Calibration Format

In `servo_config.py`, each servo has these parameters:

```python
0: {
    "min": 220,        # Minimum pulse width (one extreme)
    "max": 350,        # Maximum pulse width (other extreme)
    "neutral": 300,    # Neutral/center position
    "label": "Main Legs Lift",
    "servo_type": "LDX-227"
}
```

## Pulse Width Explanation

Servos are controlled by pulse width modulation (PWM):
- Standard servos: 1ms (204) to 2ms (409) pulse width
- 1.5ms (307) is typically neutral/center
- PCA9685 uses 12-bit resolution (0-4095) at 50Hz

**Conversion**: 
- 1ms = 204 units
- 1.5ms = 307 units  
- 2ms = 409 units

**Formula**: `pulse_width_units = microseconds * 4.096`

## Default V2 Calibration

Current values from `config.ini` (MOVEMENT_VERSION = V2):

### Leg Servos (LDX-227 High-Torque)

| Channel | Function | Min | Max | Neutral | Range |
|---------|----------|-----|-----|---------|-------|
| 0 | Main Legs Lift | 220 | 350 | 300 | 130° |
| 1 | Left Leg Rotation | 192 | 408 | 300 | 216° |
| 2 | Right Leg Rotation | 192 | 408 | 300 | 216° |

**Note**: LDX-227 servos have ±108° range from neutral (wider than MG996R's ±80°)

### Right Arm (MG996R Shoulder, MG90S Forearm/Hand)

| Channel | Function | Servo Type | Min | Max | Neutral | Range |
|---------|----------|------------|-----|-----|---------|-------|
| 3 | Right Shoulder | MG996R | 135 | 440 | 287 | 305° |
| 4 | Right Elbow | MG90S | 200 | 380 | 290 | 180° |
| 5 | Right Hand | MG90S | 200 | 280 | 240 | 80° |

**Critical**: Channel 5 max is 280 (not 380) to prevent hand mechanism binding.

### Left Arm (MG996R Shoulder, MG90S Forearm/Hand)

| Channel | Function | Servo Type | Min | Max | Neutral | Range |
|---------|----------|------------|-----|-----|---------|-------|
| 6 | Left Shoulder | MG996R | 135 | 440 | 287 | 305° |
| 7 | Left Elbow | MG90S | 200 | 380 | 290 | 180° |
| 8 | Left Hand | MG90S | 280 | 380 | 330 | 100° |

**Note**: Left arm values are NOT inverted in calibration. The inversion is handled by the mechanical mounting.

## Calibration Procedure

### Safety First

⚠️ **Important**:
1. Start with conservative ranges
2. Test at slow speed
3. Listen for strain/grinding
4. Monitor for overheating
5. Keep emergency stop ready

### Step 1: Find Neutral Position

1. **Upload files**:
   ```bash
   ./upload.sh
   ```

2. **Connect to REPL**:
   ```bash
   ./connect.sh
   ```

3. **Initialize PCA9685**:
   ```python
   import machine
   from pca9685 import PCA9685
   
   i2c = machine.I2C(0, scl=machine.Pin(9), sda=machine.Pin(8))
   pca = PCA9685(i2c)
   pca.set_pwm_freq(50)
   ```

4. **Find neutral (typically 300-307)**:
   ```python
   channel = 0  # Test channel 0
   
   # Try center value
   pca.set_pwm(channel, 0, 300)
   
   # Adjust until servo is mechanically centered
   pca.set_pwm(channel, 0, 305)
   pca.set_pwm(channel, 0, 310)
   # etc.
   ```

5. **Record neutral value**

### Step 2: Find Minimum Position

1. **Start from neutral**:
   ```python
   pca.set_pwm(channel, 0, 300)  # Your neutral
   ```

2. **Decrease slowly**:
   ```python
   # Decrease by 10 units at a time
   pca.set_pwm(channel, 0, 290)
   pca.set_pwm(channel, 0, 280)
   pca.set_pwm(channel, 0, 270)
   # Continue...
   ```

3. **Stop when**:
   - Servo reaches mechanical limit
   - You hear strain/grinding
   - Servo arm hits physical obstruction

4. **Back off 10-20 units** for safety margin:
   ```python
   # If limit was at 200, use 220 as min
   min_value = 220
   ```

5. **Record minimum value**

### Step 3: Find Maximum Position

1. **Start from neutral**:
   ```python
   pca.set_pwm(channel, 0, 300)  # Your neutral
   ```

2. **Increase slowly**:
   ```python
   # Increase by 10 units at a time
   pca.set_pwm(channel, 0, 310)
   pca.set_pwm(channel, 0, 320)
   pca.set_pwm(channel, 0, 330)
   # Continue...
   ```

3. **Stop when reaching limit** (same criteria as minimum)

4. **Back off 10-20 units** for safety

5. **Record maximum value**

### Step 4: Update Configuration

1. **Edit `servo_config.py`**:
   ```python
   SERVO_CALIBRATION = {
       0: {
           "min": 220,     # Your measured min
           "max": 350,     # Your measured max
           "neutral": 300, # Your measured neutral
           "label": "Main Legs Lift",
           "servo_type": "LDX-227"
       },
       # ... rest of servos
   }
   ```

2. **Upload updated config**:
   ```bash
   mpremote connect /dev/ttyACM0 fs cp servo_config.py :
   ```

3. **Test**:
   ```bash
   ./test_servos.sh
   ```

### Step 5: Verify All Servos

Repeat Steps 1-4 for all 9 servos.

## Quick Calibration Tool

Use this script in REPL to find ranges quickly:

```python
import machine
import time
from pca9685 import PCA9685

i2c = machine.I2C(0, scl=machine.Pin(9), sda=machine.Pin(8))
pca = PCA9685(i2c)
pca.set_pwm_freq(50)

def calibrate_servo(channel, start=150, end=450, step=10, delay=0.5):
    """
    Sweep servo through range to find limits
    
    Args:
        channel: Servo channel (0-8)
        start: Starting pulse width
        end: Ending pulse width
        step: Step size
        delay: Delay between steps (seconds)
    """
    print(f"Calibrating channel {channel}")
    print("Watch servo and press Ctrl+C when it hits limit")
    print("")
    
    try:
        for pulse in range(start, end + step, step):
            pca.set_pwm(channel, 0, pulse)
            print(f"Pulse: {pulse}", end="\r")
            time.sleep(delay)
    except KeyboardInterrupt:
        print(f"\nStopped at pulse: {pulse}")
        print(f"Consider using {pulse - 20} as limit (with safety margin)")
    
    # Return to neutral
    pca.set_pwm(channel, 0, 300)

# Example: Calibrate channel 0
calibrate_servo(0)
```

## Tips and Best Practices

### 1. Conservative Ranges

Start with narrower ranges than you think you need:
- Easier to expand than repair damaged servos
- Prevents mechanical stress
- Extends servo lifespan

### 2. Safety Margins

Always leave 10-20 units margin from physical limits:
```python
"min": physical_limit + 20,  # Add margin
"max": physical_limit - 20,  # Subtract margin
```

### 3. Test Incrementally

When expanding range:
1. Increase by 10 units
2. Upload and test
3. Check for issues
4. Repeat if safe

### 4. Different Servo Types

Different servo models have different ranges:
- **LDX-227**: Wide range (±108° typical)
- **MG996R**: Standard range (±80° typical)
- **MG90S**: Standard range (±80° typical)

### 5. Mirrored Servos

Left/right arm servos may need:
- Same min/max values
- Opposite movement directions
- Handled in mechanical mounting, not calibration

### 6. Document Changes

Keep notes of calibration changes:
```python
# Channel 5 calibration notes:
# - Original max was 380
# - Reduced to 280 due to hand binding
# - Date: 2025-10-15
```

## Common Calibration Issues

### Servo Buzzing at Neutral

**Problem**: Servo makes noise at neutral position

**Solution**: Adjust neutral value:
```python
"neutral": 305,  # Try values around 300-310
```

### Limited Range

**Problem**: Servo doesn't reach expected range

**Solution**:
1. Check servo type (different models have different ranges)
2. Verify mechanical mounting allows full range
3. Ensure servo isn't binding

### Asymmetric Range

**Problem**: Range is larger on one side

**Solution**: Normal for some servos/mounting:
```python
"min": 200,
"neutral": 320,  # Not centered
"max": 400,
```

### Hand Servos (5, 8) Special Cases

**Channel 5** (Right Hand):
- Max is 280, not 380
- Prevents over-extension
- Do not increase without testing

**Channel 8** (Left Hand):
- Range is 280-380
- Different from channel 5 due to mounting
- Inverted orientation

## Validation Testing

After calibration, run validation:

```bash
./test_servos.sh
```

Checks:
- All servos reach min position
- All servos reach max position
- No mechanical binding
- Smooth motion throughout range

## Troubleshooting Calibration

### Servo Goes Wrong Direction

Not a calibration issue - check:
1. Servo connected to correct channel
2. Mechanical mounting orientation
3. Preset movement logic

### Servo Exceeds Limits

Update validation in `servo_config.py`:
```python
def validate_pulse_width(channel, pulse):
    # Validation automatically uses your calibrated min/max
    pass
```

### Web Interface Shows Wrong Range

Update both:
1. `servo_config.py` - SERVO_CALIBRATION
2. `web_server.py` - HTML servo definitions (if hardcoded)

## Advanced Calibration

### Fine-Tuning Offsets

For precise alignment, add offset system:

```python
SERVO_OFFSETS = {
    0: 0,    # No offset
    1: +5,   # Shift right by 5
    2: -3,   # Shift left by 3
    # ...
}

# Apply in servo_controller.py:
target_with_offset = target + SERVO_OFFSETS[channel]
```

### Speed-Based Calibration

Different speeds may need different ranges:
- Fast movements: Narrower range
- Slow movements: Can use full range

### Load-Based Calibration

Heavier loads may reduce effective range:
- Test with actual payload
- Reduce range if servo struggles

## Calibration Checklist

Before finalizing calibration:

- [ ] All 9 servos tested individually
- [ ] Neutral positions don't cause strain
- [ ] Min/max have safety margins (10-20 units)
- [ ] No mechanical binding throughout range
- [ ] Test servos.sh completes without issues
- [ ] Preset movements work without hitting limits
- [ ] Documentation updated with any changes
- [ ] Backup old calibration values (just in case)

## Reference Values

If you need to start over, here are safe conservative values:

```python
# Conservative calibration (narrow ranges)
SERVO_CALIBRATION = {
    0: {"min": 250, "max": 320, "neutral": 285},
    1: {"min": 250, "max": 350, "neutral": 300},
    2: {"min": 250, "max": 350, "neutral": 300},
    3: {"min": 200, "max": 400, "neutral": 300},
    4: {"min": 250, "max": 350, "neutral": 300},
    5: {"min": 230, "max": 270, "neutral": 250},
    6: {"min": 200, "max": 400, "neutral": 300},
    7: {"min": 250, "max": 350, "neutral": 300},
    8: {"min": 300, "max": 360, "neutral": 330},
}
```

These can be gradually expanded after testing.

## Support

If you encounter issues during calibration:
1. See TROUBLESHOOTING.md
2. Document exact symptoms
3. Record values that cause problems
4. Revert to last known good calibration
5. Test incrementally

Remember: **Safety first!** Better to have limited range than damaged servos.
