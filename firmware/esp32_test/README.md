# TARS Servo Controller - ESP32 MicroPython Firmware

Complete servo control system for ESP32-S3 with PCA9685 PWM driver.

## Quick Start

### 1. Prerequisites

- ESP32-S3 with MicroPython v1.20+ installed
- mpremote installed: `pip install mpremote`
- PCA9685 connected via I2C (SDA=GPIO8, SCL=GPIO9)
- 9 servos connected to PCA9685 channels 0-8

### 2. Configure WiFi

```bash
./configure_wifi.sh
```

This will prompt for your WiFi credentials and create `wifi_config.py`.

### 3. Upload Firmware

```bash
./upload.sh
```

Uploads all required Python files to the ESP32.

### 4. Start the System

```bash
./start_server.sh
```

This connects to the ESP32 serial console and starts the main program. The web interface URL will be displayed.

### 5. Access Web Interface

Open your browser to `http://<ESP32-IP>/` to control servos.

## Files

### Core Modules

- **`boot.py`** - Runs on ESP32 boot, initializes system
- **`main.py`** - Main entry point, starts web server
- **`pca9685.py`** - I2C PWM driver for PCA9685
- **`servo_config.py`** - Servo calibration and validation
- **`servo_controller.py`** - Async servo movement control
- **`wifi_manager.py`** - WiFi connection with retry logic
- **`web_server.py`** - Async HTTP server with embedded HTML interface
- **`movement_presets.py`** - 13 preset movement sequences

### Configuration

- **`wifi_config.py`** - WiFi credentials (created by configure_wifi.sh)

### Utility Scripts

- **`upload.sh`** - Upload all files to ESP32
- **`configure_wifi.sh`** - Configure WiFi credentials
- **`start_server.sh`** - Connect to serial console and start system
- **`diagnose.sh`** - Run system diagnostics
- **`test_servos.sh`** - Test all servos (min/neutral/max)
- **`status.sh`** - Display system status
- **`list_files.sh`** - List files on ESP32
- **`clean.sh`** - Remove files from ESP32
- **`connect.sh`** - Connect to REPL

## Common Commands

### Upload specific file

```bash
mpremote connect /dev/ttyACM0 fs cp <filename.py> :
```

### Run diagnostics

```bash
./diagnose.sh
```

### Test all servos

```bash
./test_servos.sh
```

### Check system status

```bash
./status.sh
```

### Connect to REPL

```bash
./connect.sh
```

or

```bash
mpremote connect /dev/ttyACM0
```

### Restart system

In REPL:
```python
import machine
machine.reset()
```

Or soft reset:
```
Ctrl+D
```

## Web Interface Features

- **Individual Servo Control** - Control each of 9 servos independently
- **Speed Control** - Adjust movement speed (0.1 = slow, 1.0 = fast)
- **Preset Movements** - 13 preset sequences (walk, turn, wave, etc.)
- **Emergency Stop** - Immediately disable all servos
- **System Status** - View WiFi, memory, and servo information

## Preset Movements

1. **Reset** - All servos to neutral position
2. **Step Forward** - Walk forward one step
3. **Step Backward** - Walk backward one step
4. **Turn Right** - Turn 90° right
5. **Turn Left** - Turn 90° left
6. **Wave/Greet** - Right arm wave
7. **Laugh** - Bouncing motion
8. **Swing Legs** - Side-to-side swinging
9. **Balance** - Balance on legs
10. **Mic Drop** - Dramatic arm drop
11. **Monster** - Defensive posture
12. **Pose** - Strike a pose
13. **Bow** - Bow forward

## Servo Mapping

| Channel | Function | Servo Type | Range |
|---------|----------|------------|-------|
| 0 | Main Legs Lift | LDX-227 | 220-350 |
| 1 | Left Leg Rotation | LDX-227 | 192-408 |
| 2 | Right Leg Rotation | LDX-227 | 192-408 |
| 3 | Right Shoulder | MG996R | 135-440 |
| 4 | Right Elbow | MG90S | 200-380 |
| 5 | Right Hand | MG90S | 200-280 |
| 6 | Left Shoulder | MG996R | 135-440 |
| 7 | Left Elbow | MG90S | 200-380 |
| 8 | Left Hand | MG90S | 280-380 |

## Troubleshooting

### PCA9685 not detected

```bash
./diagnose.sh
```

Check:
- PCA9685 is powered
- I2C wiring: SDA=GPIO8, SCL=GPIO9
- I2C address is 0x40

### WiFi connection failed

```bash
./configure_wifi.sh
```

Check:
- Network is 2.4GHz (ESP32 doesn't support 5GHz)
- WPA2 security
- Correct SSID and password

### Memory errors

Check memory status:
```bash
./status.sh
```

If low memory:
1. Reduce number of concurrent movements
2. Avoid long-running sequences
3. Restart ESP32: `machine.reset()`

### Servo not moving

1. Check calibration in `servo_config.py`
2. Test individual servo with `test_servos.sh`
3. Verify servo power supply (5-6V, adequate current)
4. Check PCA9685 connections

### Upload failed

Check:
- USB cable connected
- Correct device: `/dev/ttyACM0` or `/dev/ttyUSB0`
- Device permissions: `sudo chmod 666 /dev/ttyACM0`
- mpremote installed: `pip install mpremote`

## Development

### Testing changes

1. Edit file locally
2. Upload: `mpremote connect /dev/ttyACM0 fs cp <file.py> :`
3. Restart: `Ctrl+D` in REPL or `machine.reset()`

### Viewing logs

```bash
./start_server.sh
```

or

```bash
mpremote connect /dev/ttyACM0
```

### Memory management

The system automatically calls `gc.collect()` after:
- Each HTTP request
- Each preset sequence
- On errors

### Adding new presets

Edit `movement_presets.py` and add to `PRESETS` dictionary:

```python
"my_preset": {
    "description": "My custom movement",
    "steps": [
        {"targets": make_leg_targets(50, 50, 50), "speed": 0.8, "delay_after": 0.2},
        # Add more steps...
    ]
}
```

## Safety

⚠️ **IMPORTANT**:

1. Always test new movements at slow speed first
2. Emergency stop button is available in web interface
3. Never exceed calibrated min/max values
4. External power supply required for servos (NOT from ESP32)
5. Servo binding or unusual noise = STOP IMMEDIATELY

## API Endpoints

- `GET /` - Web interface (HTML)
- `POST /control` - Send servo commands
- `GET /status` - Get system status
- `POST /emergency` - Emergency stop
- `POST /resume` - Resume after emergency stop

## License

Part of the TARS project. See repository root for license information.
