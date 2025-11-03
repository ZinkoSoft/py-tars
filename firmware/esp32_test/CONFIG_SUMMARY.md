# Servo Configuration Summary

## ✨ New Feature: INI-Based Configuration

You can now adjust servo calibration settings **without re-uploading firmware**!

## Quick Usage

### 1. Edit Configuration File

The `servo_config.ini` file on the ESP32 contains all servo settings:

```ini
[servo_0]
min = 220
max = 360
neutral = 300
label = Main Legs Lift
reverse = False
```

### 2. Update and Reload

**Method 1: Edit locally and upload**
```bash
# Download from ESP32
mpremote connect /dev/ttyACM0 fs cp :servo_config.ini servo_config.ini

# Edit the file
nano servo_config.ini

# Upload back
./upload_config.sh

# Reload (no reboot needed!)
curl -X POST http://192.168.1.100/config/reload
```

**Method 2: Edit on ESP32 via REPL**
```python
# Connect via serial
mpremote connect /dev/ttyACM0

# Edit in Python
with open('servo_config.ini', 'r') as f:
    content = f.read()
    # ... modify content ...
    
with open('servo_config.ini', 'w') as f:
    f.write(modified_content)

# Reload
from servo_config import reload_config
reload_config()
```

## What You Can Change

- **min** - Minimum pulse width (servo fully retracted)
- **max** - Maximum pulse width (servo fully extended)
- **neutral** - Home/center position
- **reverse** - Flip servo direction (True/False)
- **label** - Human-readable name

## Workflow

1. **Test movements** using web interface individual servo controls
2. **Find optimal values** for min, max, neutral
3. **Update servo_config.ini** with tested values
4. **Upload and reload** - no firmware re-upload needed!
5. **Test presets** to verify movements

## Benefits

✅ **No firmware re-upload** - just edit INI file  
✅ **Quick iteration** - test and adjust in seconds  
✅ **Version control** - easy to backup/restore configs  
✅ **Hot reload** - apply changes without rebooting  
✅ **Text-based** - edit with any text editor  

## Files

- **`servo_config.ini`** - Configuration file (on ESP32)
- **`servo_config.py`** - Python module (loads INI automatically)
- **`upload_config.sh`** - Helper script to upload config
- **`CONFIG_GUIDE.md`** - Detailed calibration guide

## HTTP API

### Get Current Config
```bash
curl http://192.168.1.100/config
```

### Reload Config
```bash
curl -X POST http://192.168.1.100/config/reload
```

## Next Steps

Read **[CONFIG_GUIDE.md](CONFIG_GUIDE.md)** for:
- Detailed calibration procedures
- Pulse width conversion formulas
- Troubleshooting tips
- Example configurations
- Advanced scripting
