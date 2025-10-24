# Servo Configuration Guide

## Overview

The TARS servo controller now supports **INI-based configuration** for easy calibration adjustments **without re-uploading firmware**. Simply edit `servo_config.ini` on the ESP32 filesystem and reload!

## Quick Start

### 1. Initial Setup

On first boot, the system automatically creates `servo_config.ini` with default values:

```ini
# TARS Servo Configuration
# Edit values and reboot ESP32 to apply changes
# No need to re-upload firmware!

[servo_0]
min = 220
max = 360
neutral = 300
label = Main Legs Lift
reverse = False

[servo_1]
min = 192
max = 408
neutral = 300
label = Left Leg Rotation
reverse = False

# ... (continues for all 9 servos)
```

### 2. Edit Configuration

**Option A: Via FTP/WebREPL**
1. Connect to ESP32 via FTP or WebREPL
2. Download `servo_config.ini`
3. Edit values in a text editor
4. Upload back to ESP32

**Option B: Via Serial/REPL**
```python
# Open the file for editing
with open('servo_config.ini', 'r') as f:
    content = f.read()
    print(content)

# Edit and save (example: change servo 0 max to 370)
with open('servo_config.ini', 'w') as f:
    f.write(content.replace('max = 360', 'max = 370'))
```

### 3. Apply Changes

**Option A: Reboot ESP32**
- Simplest method - config loads automatically on boot

**Option B: Reload via Web Interface**
1. Open `http://<ESP32_IP>/`
2. Navigate to Configuration section (if UI updated)
3. Click "Reload Configuration"

**Option C: Reload via HTTP API**
```bash
curl -X POST http://<ESP32_IP>/config/reload
```

**Option D: Reload via REPL**
```python
from servo_config import reload_config
reload_config()

# Re-initialize servos with new config
import uasyncio
uasyncio.run(controller.initialize_servos())
```

## Configuration Parameters

### Per-Servo Settings

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `min` | int | Minimum pulse width (12-bit PWM value) | `192` |
| `max` | int | Maximum pulse width (12-bit PWM value) | `408` |
| `neutral` | int | Neutral/home position | `300` |
| `label` | string | Human-readable name | `Left Leg Rotation` |
| `reverse` | bool | Reverse servo direction | `True` or `False` |

### Pulse Width Guide

PCA9685 uses 12-bit PWM (0-4095) at 50Hz:
- **1.0ms** = 204 (typical servo minimum)
- **1.5ms** = 307 (typical center)
- **2.0ms** = 409 (typical servo maximum)

**Formula**: `pwm_value = (pulse_ms * 1000 * 4096) / (1000000 / freq_hz)`
- At 50Hz: `pwm_value = pulse_us * 0.2048`

### Finding Your Values

1. **Start with safe defaults** (around 300 for neutral)
2. **Test incrementally** via web interface single servo control
3. **Record working values** that give full range without binding
4. **Update INI file** with tested values
5. **Set reverse flag** if servo moves opposite to expected direction

## Example: Calibrating a New Servo

Let's say you replace servo channel 3 (Right Shoulder) with a different model:

### Step 1: Test Range via Web Interface
```
Test min: Try values from 150-200 in increments of 10
Test max: Try values from 400-450 in increments of 10
Find neutral: Usually midpoint or mechanical center
```

### Step 2: Update servo_config.ini
```ini
[servo_3]
min = 180       # Found this gives full retraction
max = 420       # Found this gives full extension
neutral = 300   # Mechanical center
label = Right Shoulder
reverse = False # Set True if it moves backwards
```

### Step 3: Reload Configuration
```bash
curl -X POST http://192.168.1.100/config/reload
```

### Step 4: Test Presets
Run presets and verify movements look correct. Adjust if needed.

## Advanced: Scripted Calibration

Create a calibration script:

```python
# calibrate.py - Run on ESP32 via Thonny or ampy

import uasyncio as asyncio
from machine import I2C, Pin
from pca9685 import PCA9685
from servo_controller import ServoController

# Initialize hardware
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=100000)
pca = PCA9685(i2c)
pca.set_pwm_freq(50)
controller = ServoController(pca)

async def calibrate_servo(channel, test_values):
    """Test a range of values for a servo"""
    print(f"\nCalibrating channel {channel}...")
    
    for value in test_values:
        print(f"  Testing {value}... ", end='')
        await controller.move_servo_smooth(channel, value, speed=0.3)
        await asyncio.sleep(2)
        
        response = input("Good? (y/n/q): ")
        if response == 'y':
            print(f"  ✓ {value} is good")
        elif response == 'q':
            return
    
    print("Calibration complete!")

# Example: calibrate channel 3 from 150 to 450
asyncio.run(calibrate_servo(3, range(150, 451, 10)))
```

## API Reference

### GET /config
Returns current servo configuration as JSON.

**Response:**
```json
{
  "success": true,
  "config": {
    "0": {
      "min": 220,
      "max": 360,
      "neutral": 300,
      "label": "Main Legs Lift",
      "reverse": false
    },
    ...
  }
}
```

### POST /config/reload
Reloads configuration from `servo_config.ini` and re-initializes servos.

**Response:**
```json
{
  "success": true,
  "message": "Configuration reloaded from servo_config.ini and servos re-initialized"
}
```

## Troubleshooting

### Config file not loading
**Symptom**: Changes to INI file don't take effect
**Solutions**:
- Verify file is named exactly `servo_config.ini` (case-sensitive)
- Check file is in root directory of ESP32 filesystem
- Ensure file format is correct (use examples above)
- Check for syntax errors in INI file

### Servo moves opposite direction
**Solution**: Set `reverse = True` in INI file for that servo

### Servo doesn't reach full range
**Solution**: Adjust `min` and `max` values to extend range

### Servo binds at extremes
**Solution**: Reduce range by adjusting `min` and `max` values inward

### Changes work in REPL but not after reboot
**Solution**: Make sure you saved the INI file after editing

## File Management Tools

### Upload via ampy (from PC)
```bash
# Edit servo_config.ini on your PC, then upload:
ampy -p /dev/ttyUSB0 put servo_config.ini

# Verify upload:
ampy -p /dev/ttyUSB0 get servo_config.ini
```

### Upload via scripts (in repo)
```bash
# Use the provided upload script
./upload.sh servo_config.ini
```

### Edit via WebREPL
1. Connect to ESP32 WiFi or ensure it's on your network
2. Open WebREPL: http://micropython.org/webrepl/
3. Connect to `ws://<ESP32_IP>:8266`
4. Use file browser to download/upload `servo_config.ini`

## Best Practices

1. **Always backup** your working config before making changes
2. **Test changes incrementally** - adjust one servo at a time
3. **Document your changes** - add comments in the INI file
4. **Use version control** - keep configs for different servo models
5. **Emergency stop ready** - Have the web interface open during testing

## Example Configs

### Conservative (Safe) Config
Reduced range for gentle movements:
```ini
[servo_0]
min = 240
max = 340
neutral = 300
label = Main Legs Lift
reverse = False
```

### Extended (Full) Range Config
Maximum movement for experienced use:
```ini
[servo_0]
min = 200
max = 380
neutral = 290
label = Main Legs Lift
reverse = False
```

## Migration from Hardcoded Config

If you have custom values in `servo_config.py`, migrate them to INI:

1. Note your custom values from `servo_config.py`
2. Let the system create default `servo_config.ini` on first boot
3. Edit `servo_config.ini` with your custom values
4. Reload configuration
5. Test thoroughly

Your `servo_config.py` code remains unchanged - it automatically loads from INI when available!
