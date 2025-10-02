# ESP32 Servo Firmware

This directory contains the MicroPython firmware that drives the TARS servo rig via
a PCA9685 controller with full autonomous movement capabilities.

## 🎉 MQTT Contracts Refactor Complete!

**Status**: ✅ Production-ready autonomous robot controller  
**Architecture**: Event-driven MQTT command processing with async movement execution  
**Hardware**: ESP32-S3 with PCA9685 PWM controller (16 channels)

**What's Working:**
- ✅ Autonomous boot and WiFi/MQTT connection
- ✅ MQTT command reception on `movement/test` and `movement/stop`
- ✅ Command validation with typed schemas (lib/validation.py)
- ✅ Status publishing to `movement/status` with full lifecycle tracking
- ✅ 15 TARS-AI movement sequences (wave, bow, laugh, reset, etc.)
- ✅ Health monitoring optimized (5-minute intervals)
- ✅ Non-blocking event loop with reliable message processing
- ✅ LED status indicators for connection state
- ✅ Development workflow with easy REPL access

**Next Step**: Hardware calibration and servo tuning (see below)

## Prerequisites

- ESP32 development board with access to the PCA9685 servo driver
- MicroPython v1.22 (or newer) flashed to the ESP32
- TCP-accessible MQTT broker matching the movement-service configuration
- Tools for interacting with the board filesystem, e.g. [`ampy`](https://github.com/scientifichackers/ampy) or [`mpremote`](https://docs.micropython.org/en/latest/reference/mpremote.html)

## Flash MicroPython

1. Download the latest ESP32 MicroPython firmware (`.bin`) from the official [MicroPython downloads](https://micropython.org/download/esp32/) page.
2. Put the board into bootloader mode (typically by holding **BOOT** and tapping **EN/RST**).
3. Erase the flash (optional but recommended):
   ```bash
   esptool.py --chip esp32 --port /dev/ttyUSB0 erase_flash
   ```
4. Write the firmware image:
   ```bash
   esptool.py --chip esp32 --port /dev/ttyUSB0 --baud 460800 \
     write_flash -z 0x1000 esp32-20240222-v1.22.2.bin
   ```

Adjust the port and image name for your setup.

## Deploy the servo firmware

### 🚀 Quick Setup (Initial Flash)

Use the **automated setup script** for first-time ESP32 setup:

```bash
cd firmware/esp32
./setup.sh
```

**What `setup.sh` does:**

1. **Tool Validation**
   - Checks for `esptool` and `mpremote` (install with `pip install esptool mpremote`)
   - Adds `~/.local/bin` to PATH if needed

2. **Device Detection**
   - Scans for connected ESP32 devices on `/dev/ttyUSB*` and `/dev/ttyACM*`
   - Checks dialout group permissions (Linux)
   - Prompts for manual device selection if multiple found

3. **Configuration Generation**
   - Reads MQTT credentials from `../../.env` (MQTT_USER, MQTT_PASS, MQTT_PORT)
   - Auto-detects your host IP address for MQTT broker connection
   - Offers WiFi setup options:
     - **Scan for networks** - Lists available WiFi SSIDs to choose from
     - **Manual entry** - Type SSID/password directly
     - **Skip setup** - Leave blank for web portal configuration later
   - Generates complete `movement_config.json` with:
     - WiFi credentials (ssid, password)
     - MQTT settings (host, port, username, password, client_id)
     - PCA9685 I²C configuration (address, frequency, SCL/SDA pins)
     - MQTT topics (test, stop, status, frame, state, health)
     - **Servo configuration** (legs and arms channels, ranges, neutral positions)
     - Frame timeout, LED status pin, setup portal config
   - Creates `main.py` with proper async event loop initialization

4. **Firmware Flashing**
   - Auto-downloads latest MicroPython ESP32-S3 firmware if not found
   - Caches firmware in `/tmp/` for reuse
   - Guides through bootloader mode if needed:
     - Hold **BOOT** button
     - Press **RESET** button
     - Release both buttons
   - Erases flash and writes MicroPython firmware
   - Waits for device to reconnect

5. **File Upload**
   - Uploads complete firmware structure:
     - `lib/` - WiFi manager, MQTT client, LED status, validation, config utilities
     - `movements/` - Servo config, controller, sequences, command handler
     - `tars_controller.py` - Main autonomous controller
     - `main.py` - Boot script with async event loop
     - `movement_config.json` - Generated configuration
   - Shows progress for each directory/file

6. **Verification**
   - Checks if LED is active (indicates running application)
   - Displays connection summary (WiFi SSID, MQTT host, device path)
   - Provides next steps and troubleshooting tips

**First-time setup takes ~2-3 minutes** including firmware download and flash.

### 🔧 Development Workflow

For **iterative development** after initial setup, use the development workflow script:

```bash
cd firmware/esp32
./esp32_dev.sh
```

**What `esp32_dev.sh` provides:**

Interactive menu with 7 options:

1. **Flash all files to ESP32** - Full upload of firmware structure
   - Use when multiple files changed
   - Uploads lib/, movements/, tars_controller.py, main.py, config

2. **Quick update (tars_controller.py only)** - Fast iteration
   - Uploads just the main controller file
   - Saves time during development (5 seconds vs 30 seconds)

3. **Connect to REPL (program running)** - Monitor logs
   - Connects to ESP32 serial console
   - See real-time MQTT messages, movement logs, errors
   - Press CTRL+C to stop program and get interactive REPL
   - Press CTRL+D to soft reset (restart)
   - Press CTRL+X to disconnect

4. **Stop and enter REPL (interactive mode)** - Debug mode
   - Stops the running program
   - Gives interactive Python prompt
   - Test functions manually: `await controller.wave()`
   - Import modules and experiment

5. **Soft reset (restart program)** - Quick reboot
   - Like pressing the reset button
   - Runs main.py automatically
   - No need to disconnect/reconnect

6. **Flash + restart (full deployment)** - Production deploy
   - Uploads everything and restarts
   - Optionally connects to REPL to view logs

7. **Exit** - Closes the script

**Why use `esp32_dev.sh` instead of `mpremote exec`?**
- ✅ No REPL blocking - can connect while program runs
- ✅ Interactive menu - no need to remember commands
- ✅ Quick iterations - update one file in 5 seconds
- ✅ Automatic device detection and error handling

**Typical development cycle:**
```bash
# Edit tars_controller.py
vim tars_controller.py

# Quick update
./esp32_dev.sh
# Choose: 2 (Quick update)

# Connect to see logs
./esp32_dev.sh
# Choose: 3 (Connect to REPL)
# Watch logs, press CTRL+C then CTRL+X to exit

# Send test command from another terminal
mosquitto_pub -h localhost -t 'movement/test' -m '{"command":"wave","speed":0.8}' -q 1
```

### LED Status Indicators 🚦

The ESP32 uses an onboard RGB LED (GPIO 48) to indicate system status:

- � **Yellow** - System booting / initializing
- � **Cyan** - WiFi connected, MQTT connecting
- 🟢 **Green** - Fully connected and operational ✓
- �🔴 **Red (Breathing)** - WiFi disconnected / Setup portal active
- � **Orange (Blinking)** - MQTT connection error
- 🔴 **Red (Solid)** - Emergency stop activated
- � **Blue (Flash)** - MQTT message published (visual feedback)

**Troubleshooting:**
- **Red breathing**: Connect to `TARS-Setup` WiFi and visit `http://192.168.4.1/`
- **Orange blinking**: Check MQTT broker is running and credentials are correct
- **No LED**: Power issue or wrong GPIO pin in config

### WiFi Configuration Options

The script offers three ways to configure WiFi:

1. **Scan for networks** - Automatically detects available WiFi networks and lets you select from a list
2. **Manual entry** - Type in the SSID manually
3. **Skip setup** - Leave WiFi blank and configure later via the ESP32's web portal
   - ESP32 will create a `TARS-Setup` WiFi network
   - Connect and visit `http://192.168.4.1/` to configure

**Prerequisites:**
```bash
pip install esptool mpremote
```

**MicroPython Firmware:**
The script will automatically download the latest ESP32-S3 MicroPython firmware if not found locally. The firmware is cached in `/tmp/` for reuse. You can also manually download it from:
- https://micropython.org/download/ESP32_GENERIC_S3/
- Place the `.bin` file in this directory to use your own version

### Manual Setup

1. Clone this repository (or copy the `firmware/esp32` folder) and `cd` into it.
2. Copy the modular structure to the board's filesystem:
   ```bash
   # Using mpremote (recommended)
   mpremote fs cp -r lib/ :lib/
   mpremote fs cp -r movements/ :movements/
   mpremote fs cp tars_controller.py :tars_controller.py
   mpremote fs cp main.py :main.py
   ```
3. Create a `movement_config.json` file with your Wi-Fi and MQTT details (see below) and upload it to the board:
   ```bash
   mpremote fs cp movement_config.json :movement_config.json
   ```
4. Reset the board. On boot, the firmware will:
  - Attempt to join the configured Wi-Fi network
  - Connect to MQTT broker and subscribe to `movement/test` and `movement/stop`
  - Execute movement sequences autonomously
  - Send a retained health payload on `system/health/movement`
  - Show connection status via LED indicators

## WiFi Configuration

**Note**: The new `tars_controller.py` architecture focuses on autonomous movement sequences.
WiFi setup is handled via `setup.sh` (recommended) or manual `movement_config.json` editing.

If you need WiFi credentials, use the `setup.sh` script which has built-in WiFi scanning:
```bash
./setup.sh
```

Alternatively, manually edit `movement_config.json`:
```json
{
  "wifi": {
    "ssid": "YourNetwork",
    "password": "YourPassword"
  },
  ...
}
```

For the old web-based setup portal, see `servoctl.py` (legacy architecture).

## Configuration file

The firmware reads `movement_config.json` at startup. Generated by `setup.sh`, this
file provides configuration for WiFi, MQTT, hardware, and servo definitions. Example:

```json
{
  "wifi": {
    "ssid": "MyRoboticsLab",
    "password": "super-secure-pass"
  },
  "mqtt": {
    "host": "192.168.1.50",
    "port": 1883,
    "username": "tars",
    "password": "broker-secret",
    "client_id": "tars-esp32",
    "keepalive": 30
  },
  "pca9685": {
    "address": 64,
    "frequency": 50,
    "scl": 20,
    "sda": 21
  },
  "topics": {
    "frame": "movement/frame",
    "state": "movement/state",
    "health": "system/health/movement-esp32",
    "test": "movement/test",
    "stop": "movement/stop",
    "status": "movement/status"
  },
  "frame_timeout_ms": 2500,
  "status_led": 48,
  "setup_portal": {
    "ssid": "TARS-Setup",
    "password": null,
    "port": 80,
    "timeout_s": 300
  },
  "servo_channel_count": 12,
  "default_center_pulse": 305,
  "servo_centers": {
    "0": 302,
    "1": 310
  },
  "servos": {
    "legs": {
      "height": {
        "channel": 0,
        "up": 220,
        "neutral": 300,
        "down": 350,
        "min": 200,
        "max": 400
      },
      "left": {
        "channel": 1,
        "forward": 220,
        "neutral": 300,
        "back": 380,
        "offset": 0,
        "min": 200,
        "max": 400
      },
      "right": {
        "channel": 2,
        "forward": 380,
        "neutral": 300,
        "back": 220,
        "offset": 0,
        "min": 200,
        "max": 400
      }
    },
    "arms": {
      "right": {
        "main": {
          "channel": 3,
          "min": 135,
          "max": 440,
          "neutral": 287
        },
        "forearm": {
          "channel": 4,
          "min": 200,
          "max": 380,
          "neutral": 290
        },
        "hand": {
          "channel": 5,
          "min": 200,
          "max": 280,
          "neutral": 240
        }
      },
      "left": {
        "main": {
          "channel": 6,
          "min": 135,
          "max": 440,
          "neutral": 287
        },
        "forearm": {
          "channel": 7,
          "min": 200,
          "max": 380,
          "neutral": 290
        },
        "hand": {
          "channel": 8,
          "min": 280,
          "max": 380,
          "neutral": 330
        }
      }
    }
  }
}
```

### Key Configuration Sections:

**Network & Communication:**
- `wifi`: SSID/password for the access point the ESP32 should join
- `mqtt`: Broker connection parameters (host, port, credentials, client_id, keepalive)
- `topics`: MQTT topics for command/status/health messages (matches movement contracts)

**Hardware:**
- `pca9685`: I²C configuration (address, frequency, SCL/SDA pins)
  - Standard address is 64 (0x40)
  - Frequency 50Hz for servos
  - SCL=20, SDA=21 for ESP32-S3
- `status_led`: RGB LED GPIO pin (48 for ESP32-S3 onboard LED)

**Behavior:**
- `frame_timeout_ms`: Timeout for frame-based control (2500ms default)
- `setup_portal`: Fallback WiFi AP settings when connection fails

**Servo Configuration (NEW):**
- `servos.legs`: 3 leg servos (height, left, right) with position definitions
  - `up`/`down` for height
  - `forward`/`back` for left/right legs
  - `neutral` for rest position
  - `min`/`max` for safety limits
- `servos.arms`: 6 arm servos (right and left, each with main/forearm/hand)
  - `min`/`max` ranges for each joint
  - `neutral` for rest position
  - Channels 3-8 for the 6 arm servos

**Servo Calibration:**
- `servo_centers`: Per-channel pulse width overrides for centering
- `default_center_pulse`: Fallback pulse width (305 for MG996R servos)

**Adjusting Servo Ranges:**
Edit `movement_config.json` directly or regenerate with `./setup.sh`:
```json
"servos": {
  "arms": {
    "right": {
      "main": {
        "channel": 3,
        "min": 150,      // Adjust based on your servo
        "max": 450,      // Adjust based on your servo
        "neutral": 300   // Center position
      }
    }
  }
}
```

Upload updated config:
```bash
./esp32_dev.sh
# Choose: 1 (Flash all files)
# Or manually:
mpremote connect /dev/ttyACM0 fs cp movement_config.json :movement_config.json
mpremote connect /dev/ttyACM0 reset
```

## Troubleshooting

### No serial devices found (Ubuntu/Linux)

**1. Add user to dialout group** (required for serial port access):
```bash
sudo usermod -a -G dialout $USER
# Log out and back in for changes to take effect
```

**2. Check if device is detected**:
```bash
ls /dev/ttyUSB* /dev/ttyACM*
# Expected output: /dev/ttyUSB0 or /dev/ttyACM0
```

**3. Verify USB connection**:
```bash
lsusb
# Look for: "CP210x", "CH340", "FTDI", or "Silicon Labs"
```

**4. Check dmesg for device detection**:
```bash
sudo dmesg | tail -20
# Should show: "USB Serial device" or "cp210x" when you plug in the ESP32
```

**Expected device paths:**
- **Linux (Ubuntu)**: `/dev/ttyUSB0` or `/dev/ttyACM0`
- **macOS**: `/dev/cu.usbmodem*` or `/dev/tty.usbserial-*`

### Common ESP32 USB chips
- **CP210x** (Silicon Labs) - Most common, usually works out-of-box on Linux
- **CH340** - Common on clone boards, usually works on Ubuntu 18.04+
- **FTDI** - Less common, usually works out-of-box

### Still not working?
- Try a different USB cable (must support data, not just power)
- Try a different USB port
- Reboot after adding user to dialout group
- Check if ESP32 LED is on (indicates power)

## Testing Movement Commands

Once the ESP32 boots and connects, test the movement system:

### Monitor Status Messages

```bash
# Watch status lifecycle (command_started, command_completed, etc.)
mosquitto_sub -h localhost -t 'movement/status' -v
```

### Send Movement Commands

```bash
# Basic movements
mosquitto_pub -h localhost -t 'movement/test' -m '{"command":"wave","speed":0.8}' -q 1
mosquitto_pub -h localhost -t 'movement/test' -m '{"command":"bow","speed":0.7}' -q 1
mosquitto_pub -h localhost -t 'movement/test' -m '{"command":"reset","speed":0.5}' -q 1

# With request tracking
mosquitto_pub -h localhost -t 'movement/test' -m '{"command":"laugh","speed":1.0,"request_id":"test-123"}' -q 1

# Emergency stop (clears queue)
mosquitto_pub -h localhost -t 'movement/stop' -m '{}' -q 1
```

### Available Movement Sequences

**Basic Movements (5):**
- `reset` - Return to neutral position
- `step_forward` - Walk forward one step
- `step_backward` - Walk backward one step
- `turn_left` - Rotate left
- `turn_right` - Rotate right

**Expressive Movements (10):**
- `wave` - Wave with right arm
- `laugh` - Bouncing motion
- `swing_legs` - Pendulum leg motion
- `pezz` / `pezz_dispenser` - Candy dispenser motion (10s hold)
- `now` - Pointing gesture
- `balance` - Balancing animation
- `mic_drop` - Dramatic mic drop
- `monster` - Defensive/threatening pose
- `pose` - Strike a pose
- `bow` - Bow forward

### Expected Status Messages

```json
// Command queued
{"message_id": "esp32_12345", "event": "command_queued", "command": "wave", "queue_size": 1}

// Command started
{"message_id": "esp32_12346", "event": "command_started", "command": "wave", "timestamp": 12}

// Command completed
{"message_id": "esp32_15789", "event": "command_completed", "command": "wave", "timestamp": 15}

// With request tracking
{"message_id": "esp32_20123", "event": "command_completed", "command": "bow", "request_id": "test-123", "timestamp": 20}
```

## Health Monitoring & Troubleshooting

### Health Messages

Watch for health status (published every 5 minutes):
```bash
mosquitto_sub -h localhost -t 'system/health/movement-esp32' -v
```

Expected: `{"ok": true, "event": "periodic_health_check"}`

### State Messages

Monitor general state events:
```bash
mosquitto_sub -h localhost -t 'movement/state' -v
```

Events:
- `ready` - Firmware online and subscribed
- `command_queued` - Command added to queue
- `command_error` - Validation or execution error
- `stopped` - Emergency stop triggered
- `shutdown` - Graceful shutdown

### Common Issues

**No movement when commands sent:**
1. Check PCA9685 is powered (5-6V external power required)
2. Verify servo channels match config (0-8 for legs + arms)
3. Check servo wiring to PCA9685 channels
4. Monitor ESP32 serial output: `./esp32_dev.sh` → option 3

**"MQTT received" but no execution:**
1. Check validation errors in serial logs
2. Verify command format matches schema
3. Check movement handler queue isn't stopped

**WiFi connection fails:**
1. Check WiFi credentials in `movement_config.json`
2. Verify WiFi network is 2.4GHz (ESP32 doesn't support 5GHz)
3. Connect to `TARS-Setup` AP and reconfigure via web portal

**MQTT connection fails:**
1. Verify MQTT broker is running: `docker compose -f ops/compose.yml ps`
2. Check broker credentials match `.env` file
3. Ensure host IP is correct in `movement_config.json`

**REPL not accessible:**
1. Stop `mpremote exec` session (CTRL+C)
2. Use `./esp32_dev.sh` option 3 for proper REPL access
3. Check device permissions: `ls -l /dev/ttyACM0`

### Interactive Debugging

Connect to REPL while program runs:
```bash
./esp32_dev.sh
# Choose: 3 (Connect to REPL)
```

You'll see real-time logs:
```
MQTT received: movement/test
Queued: wave (queue size: 1)
Executing: wave (speed=0.8, request_id=None)
Waving...
✓ Wave complete
```

Press CTRL+C to stop and get interactive prompt:
```python
>>> import tars_controller
>>> # Test functions manually
>>> # Press CTRL+D to restart
```

### Performance Optimization

Current optimizations:
- ✅ Health publishing: Once per 5 minutes (reduced from 20/sec)
- ✅ Frame timeout logging: Once per timeout event (not spammed)
- ✅ MQTT message processing: Non-blocking with socket timeout (1ms)
- ✅ Event loop: 50ms sleep for task switching

Monitor CPU usage via serial logs - should be minimal during idle.
