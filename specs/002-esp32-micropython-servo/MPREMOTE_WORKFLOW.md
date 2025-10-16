# mpremote-Only Workflow

**Feature**: 002-esp32-micropython-servo  
**Status**: Standardized on mpremote exclusively

## Overview

All ESP32 interactions use **`mpremote`** (MicroPython remote control) exclusively. No other tools (ampy, rshell, esptool for file operations, screen, picocom) are required for daily development.

## Why mpremote Only?

✅ **Single tool** for all ESP32 operations (file upload, REPL, execution)  
✅ **Official** MicroPython tool (actively maintained)  
✅ **Scriptable** - all operations can be automated  
✅ **Cross-platform** - works on Linux, macOS, Windows  
✅ **No device permissions** issues (handles serial access gracefully)  
✅ **Consistent** behavior across different ESP32 boards

## Installation

```bash
pip install mpremote
```

That's it. One tool, one command.

## Core Operations

### 1. Connect to REPL

```bash
mpremote connect /dev/ttyACM0
```

**Inside REPL**:
- `Ctrl+D` - Soft reboot
- `Ctrl+C` - Interrupt running code
- `Ctrl+X` - Exit mpremote

### 2. Upload Files

```bash
# Single file
mpremote connect /dev/ttyACM0 fs cp main.py :

# Multiple files
for f in *.py; do
    mpremote connect /dev/ttyACM0 fs cp "$f" :
done
```

**Using shell script** (recommended):
```bash
./upload.sh  # Handles all files automatically
```

### 3. Execute Code

```bash
# Run Python statement
mpremote connect /dev/ttyACM0 exec "print('Hello from ESP32')"

# Start main application
mpremote connect /dev/ttyACM0 exec "import main"

# Check memory
mpremote connect /dev/ttyACM0 exec "import gc; gc.collect(); print(gc.mem_free())"

# Soft reset
mpremote connect /dev/ttyACM0 exec "import machine; machine.reset()"
```

### 4. File Management

```bash
# List files
mpremote connect /dev/ttyACM0 fs ls

# Download file
mpremote connect /dev/ttyACM0 fs cp :main.py ./main_backup.py

# Delete file
mpremote connect /dev/ttyACM0 fs rm :old_file.py

# Check file size
mpremote connect /dev/ttyACM0 fs ls -l
```

### 5. Run Scripts

```bash
# Run script and return to REPL
mpremote connect /dev/ttyACM0 run test_i2c.py

# Run script and exit
mpremote connect /dev/ttyACM0 exec "$(cat test_i2c.py)"
```

## Shell Scripts Reference

All scripts in `firmware/esp32_test/` are mpremote-based:

### upload.sh
```bash
#!/bin/bash
# Uploads all firmware files using mpremote
# Usage: ./upload.sh
```

**Files uploaded**:
- `boot.py` - System initialization
- `main.py` - Entry point
- `pca9685.py` - I2C PWM driver
- `servo_controller.py` - Servo control
- `movement_presets.py` - Choreographies
- `web_server.py` - HTTP server
- `wifi_config.py` - WiFi credentials

### configure_wifi.sh
```bash
#!/bin/bash
# Interactive WiFi configuration
# Creates wifi_config.py and uploads to ESP32
# Usage: ./configure_wifi.sh
```

**Prompts for**:
- WiFi SSID
- WiFi password
- Access Point SSID (optional)
- Access Point password (optional)

### start_server.sh
```bash
#!/bin/bash
# Starts web server and monitors serial output
# Usage: ./start_server.sh
```

Equivalent to: `mpremote connect /dev/ttyACM0 exec "import main"`

### connect.sh
```bash
#!/bin/bash
# Opens REPL for interactive development
# Usage: ./connect.sh
```

Equivalent to: `mpremote connect /dev/ttyACM0`

### list_files.sh
```bash
#!/bin/bash
# Lists all files on ESP32
# Usage: ./list_files.sh
```

Equivalent to: `mpremote connect /dev/ttyACM0 fs ls`

### diagnose.sh
```bash
#!/bin/bash
# Uploads and runs I2C scanner
# Usage: ./diagnose.sh
```

**What it does**:
1. Uploads `i2c_scanner.py` to ESP32
2. Executes scanner
3. Displays detected I2C devices (should see 0x40 for PCA9685)

### clean.sh
```bash
#!/bin/bash
# Removes all firmware files from ESP32
# Usage: ./clean.sh
```

**Confirmation required**: Type `yes` to proceed.

## Common Workflows

### Fresh Deploy
```bash
cd firmware/esp32_test

# 1. Configure WiFi
./configure_wifi.sh

# 2. Upload firmware
./upload.sh

# 3. Start server
./start_server.sh
```

### Update Single File
```bash
# Edit file locally
vim servo_controller.py

# Upload changed file
mpremote connect /dev/ttyACM0 fs cp servo_controller.py :

# Restart ESP32
mpremote connect /dev/ttyACM0 exec "import machine; machine.reset()"
```

### Debug Session
```bash
# Connect to REPL
./connect.sh

# Test components interactively
>>> import machine
>>> i2c = machine.I2C(0, scl=machine.Pin(9), sda=machine.Pin(8))
>>> i2c.scan()
[64]  # 0x40 detected

>>> from pca9685 import PCA9685
>>> pca = PCA9685(i2c)
>>> pca.set_pwm(0, 0, 300)  # Test servo 0
```

### Check System Status
```bash
# Memory usage
mpremote connect /dev/ttyACM0 exec "import gc; gc.collect(); print('Free:', gc.mem_free())"

# WiFi status
mpremote connect /dev/ttyACM0 exec "import network; wlan=network.WLAN(network.STA_IF); print(wlan.ifconfig() if wlan.isconnected() else 'Not connected')"

# I2C devices
mpremote connect /dev/ttyACM0 exec "import machine; i2c=machine.I2C(0, scl=machine.Pin(9), sda=machine.Pin(8)); print('I2C:', i2c.scan())"
```

### Quick Restart
```bash
# Soft reset
mpremote connect /dev/ttyACM0 exec "import machine; machine.reset()"

# Or use shell script
./start_server.sh
```

## Device Detection

mpremote automatically finds ESP32 if only one is connected:

```bash
# Auto-detect device
mpremote connect auto fs ls

# Explicit device (recommended for scripts)
mpremote connect /dev/ttyACM0 fs ls
```

**Common device paths**:
- Linux: `/dev/ttyACM0` or `/dev/ttyUSB0`
- macOS: `/dev/cu.usbserial-*` or `/dev/cu.usbmodem*`
- Windows: `COM3` or similar

## Troubleshooting

### Permission Denied
```bash
# Add user to dialout group (Linux)
sudo usermod -a -G dialout $USER
# Log out and log back in

# Or temporary fix
sudo chmod 666 /dev/ttyACM0
```

### Device Not Found
```bash
# List available serial devices
ls /dev/tty* | grep -E 'ACM|USB'

# Check dmesg for connection
dmesg | tail -20
```

### Connection Refused
```bash
# Another process may be using the port
# Check for other mpremote/screen/minicom instances
ps aux | grep -E 'mpremote|screen|minicom|picocom'

# Kill blocking process
killall mpremote
```

### Upload Fails Mid-Transfer
```bash
# Reconnect and retry
mpremote connect /dev/ttyACM0 exec "import machine; machine.reset()"
sleep 2
./upload.sh
```

### REPL Not Responding
```bash
# Force interrupt with Ctrl+C
# Then soft reset with Ctrl+D
# Exit with Ctrl+X and reconnect
```

## Advanced: Custom mpremote Commands

### One-Liner System Info
```bash
mpremote connect /dev/ttyACM0 exec "
import sys, machine, gc
gc.collect()
print('MicroPython:', sys.version)
print('CPU Freq:', machine.freq(), 'Hz')
print('Free Memory:', gc.mem_free(), 'bytes')
"
```

### Batch Upload with Verification
```bash
for f in *.py; do
    echo "Uploading $f..."
    mpremote connect /dev/ttyACM0 fs cp "$f" : && \
    mpremote connect /dev/ttyACM0 exec "print('$f uploaded OK')" || \
    echo "FAILED: $f"
done
```

### Live Log Monitoring
```bash
# Start server and keep connection open
mpremote connect /dev/ttyACM0 exec "import main" &
sleep 2
mpremote connect /dev/ttyACM0  # Reconnect for logs
```

## Benefits Summary

| Feature | mpremote | ampy | rshell | screen |
|---------|----------|------|--------|--------|
| File upload | ✅ | ✅ | ✅ | ❌ |
| REPL access | ✅ | ❌ | ✅ | ✅ |
| Execute code | ✅ | ❌ | ❌ | ❌ |
| Auto-reconnect | ✅ | ❌ | ❌ | ❌ |
| Scriptable | ✅ | ⚠️ | ⚠️ | ❌ |
| Official tool | ✅ | ❌ | ❌ | N/A |
| Active development | ✅ | ❌ | ⚠️ | N/A |

**Conclusion**: mpremote handles all use cases with a single, well-maintained tool.

## References

- **Official docs**: https://docs.micropython.org/en/latest/reference/mpremote.html
- **GitHub**: https://github.com/micropython/micropython/tree/master/tools/mpremote
- **PyPI**: https://pypi.org/project/mpremote/

## Implementation Status

✅ All shell scripts converted to mpremote  
✅ Documentation updated (quickstart.md)  
✅ Quickstart references actual scripts  
✅ No ampy/rshell/screen dependencies  
✅ Cross-platform compatible  

**Ready for implementation**: All tooling standardized on mpremote.
