# Quickstart Guide: ESP32 MicroPython Servo Control System

**Feature**: 002-esp32-micropython-servo  
**Version**: 1.0  
**Date**: 2025-10-15

## Overview

This guide will help you set up, deploy, and test the ESP32 servo control system from scratch. Expected time: 30-45 minutes for first-time setup, 5-10 minutes for subsequent deploys.

## Prerequisites

### Hardware Requirements

- **ESP32-S3** development board with:
  - Minimum 4MB flash
  - 512KB SRAM
  - USB connection for programming/serial console
  - GPIO pins exposed for I2C (using GPIO 8=SDA, GPIO 9=SCL)
  
- **PCA9685** 16-channel PWM driver board:
  - I2C address: 0x40 (default) or configurable
  - External power supply (5-6V for servos)
  - I2C pullup resistors (usually built-in, 4.7kΩ)

- **9 Servos**:
  - Standard analog servos (50Hz PWM)
  - Connected to PCA9685 channels 0-8
  - External power supply (NOT powered from ESP32)

- **Power Supply**:
  - ESP32: 5V USB or 3.3V regulated
  - Servos: 5-6V, 3-5A capacity (depends on servo count and load)
  - PCA9685: Powered from servo supply or separate 5V

- **Wiring**:
  ```
  ESP32          PCA9685
  GPIO 8 (SDA) → SDA
  GPIO 9 (SCL) → SCL
  GND           → GND
  3.3V          → VCC (logic level)
  
  PCA9685        Servos (0-8)
  V+            ← External 5-6V supply (+)
  GND           ← External supply (-)
  PWM 0-8       → Servo signal wires
  ```

### Software Requirements

- **MicroPython firmware** v1.20+ for ESP32-S3
  - Download from: https://micropython.org/download/esp32s3/
  - Must include `uasyncio` module (included in standard builds)

- **mpremote** (official MicroPython tool - REQUIRED):
  - Install: `pip install mpremote`
  - Handles file upload, REPL access, and command execution
  - Single tool for all ESP32 interactions

- **Development machine**:
  - Python 3.x (for running shell scripts)
  - WiFi connection to same network as ESP32

### Network Requirements

- 2.4GHz WiFi network (ESP32 doesn't support 5GHz)
- WPA2 security
- DHCP enabled (for IP address assignment)
- No firewall rules blocking port 80

---

## Step 1: Flash MicroPython Firmware

### 1.1 Download Firmware

```bash
cd ~/Downloads
wget https://micropython.org/resources/firmware/esp32s3-20231005-v1.21.0.bin
```

### 1.2 Erase Flash (First Time Only)

```bash
# Install esptool if not already installed
pip install esptool

# Find your device port
ls /dev/tty*  # Look for /dev/ttyUSB0 or /dev/ttyACM0

# Erase flash
esptool.py --port /dev/ttyUSB0 erase_flash
```

### 1.3 Flash MicroPython

```bash
esptool.py --chip esp32s3 \
  --port /dev/ttyUSB0 \
  write_flash -z 0x0 esp32s3-20231005-v1.21.0.bin
```

**Expected output**:
```
Hash of data verified.
Leaving...
Hard resetting via RTS pin...
```

### 1.4 Verify Installation

```bash
# Connect to REPL using mpremote
mpremote connect /dev/ttyUSB0

# You should see MicroPython REPL:
# >>> 
```

Press Ctrl+D to reboot. You should see boot messages and MicroPython version.
Press Ctrl+X to exit mpremote.

---

## Step 2: Configure WiFi

### 2.1 Set WiFi Credentials

```bash
cd firmware/esp32_test

# Run configuration script
./configure_wifi.sh
```

**You'll be prompted for**:
- SSID (network name)
- Password

**What it does**:
- Creates `wifi_config.py` with credentials as Python constants:
  ```python
  SSID = "YourNetwork"
  PASSWORD = "YourPassword"
  ```

### 2.2 Test WiFi Connection (Optional)

Connect to serial console and test manually:

```python
>>> import network
>>> wlan = network.WLAN(network.STA_IF)
>>> wlan.active(True)
>>> wlan.connect('YourSSID', 'YourPassword')
>>> wlan.isconnected()
True
>>> wlan.ifconfig()
('192.168.1.100', '255.255.255.0', '192.168.1.1', '8.8.8.8')
```

Note the IP address (192.168.1.100 in this example).

---

## Step 3: Upload Firmware Files

### 3.1 Verify I2C Bus (Recommended)

Before uploading main code, verify PCA9685 is detected:

```bash
# Run diagnostics (uploads and runs i2c_scanner automatically)
./diagnose.sh
```

**Expected output**:
```
========================================
I2C Diagnostics - TARS Servo Controller
========================================
✓ Scanner uploaded
Running scan...
========================================
I2C devices found at: 0x40 (64)
========================================
```

If no devices found:
- Check wiring: GPIO 8 (SDA), GPIO 9 (SCL), GND
- Verify PCA9685 has power
- Check I2C pullup resistors (usually on PCA9685 board)

### 3.2 Upload Application Files

```bash
# Upload all firmware files using mpremote
./upload.sh
```

**This uploads**:
- `boot.py` - System initialization
- `main.py` - Entry point
- `wifi_config.py` - WiFi credentials
- `pca9685.py` - I2C PWM driver
- `servo_controller.py` - Servo control logic
- `movement_presets.py` - Preset choreographies
- `web_server.py` - Async HTTP server

**Expected output**:
```
========================================
TARS Servo Controller - ESP32 Upload
========================================
Device: /dev/ttyACM0

Uploading files...

  [pca9685.py] ... ✓ OK
  [servo_config.py] ... ✓ OK
  [servo_controller.py] ... ✓ OK
  [wifi_config.py] ... ✓ OK
  [web_interface.py] ... ✓ OK
  [boot.py] ... ✓ OK
  [main.py] ... ✓ OK

========================================
✓ All files uploaded successfully!
========================================
```

### 3.3 List Files on ESP32

```bash
# List all files on ESP32 filesystem using mpremote
./list_files.sh
```

**Expected output**:
```
========================================
ESP32 File System
========================================

ls :
         231 boot.py
        1456 main.py
         189 wifi_config.py
        2345 pca9685.py
servo_controller.py
movement_presets.py
web_server.py
```

---

## Step 4: Start the System

### 4.1 Start Web Server

**Option 1: Using shell script (recommended)**
```bash
# Start web server and monitor serial output
./start_server.sh
```

**Option 2: Manual mpremote command**
```bash
# Start web server
mpremote connect /dev/ttyACM0 exec "import main"
```

**Option 3: From REPL**
```bash
# Connect to REPL
./connect.sh

# Start server manually
>>> import main
```

### 4.2 Watch Boot Sequence

**Expected serial output**:
```
==================================================
ESP32 Booting - TARS Servo Controller
CPU Freq: 240MHz
Free Memory: 180000 bytes
==================================================

Initializing I2C...
I2C initialized: SDA=8, SCL=9, freq=100000Hz

Initializing PCA9685...
PCA9685 detected at address 0x40
PWM frequency set to 50Hz

Connecting to WiFi: YourNetwork...
Connected! IP: 192.168.1.100
Web interface: http://192.168.1.100

Starting web server on port 80...
Web server running!

Initializing servos to neutral positions...
Servo initialization complete
System ready
```

**If errors occur**:
- **"I2C device not found"**: Check PCA9685 wiring and power
- **"WiFi connection timeout"**: Verify SSID/password in wifi_config.py
- **"Out of memory"**: Firmware may be too large for available RAM (try reducing HTML size)

### 4.3 Note the IP Address

The IP address is displayed in the serial console:
```
Web interface: http://192.168.1.100
```

Save this IP address for accessing the web interface.

---

## Step 5: Access Web Interface

### 5.1 Open in Browser

Navigate to the displayed IP address:
```
http://192.168.1.100
```

**Expected interface**:
- Red emergency stop button (top-right corner)
- System status panel (WiFi, hardware, memory)
- 9 servo control sliders (one per channel)
- Global speed slider
- 13 preset movement buttons

### 5.2 Test System Status

Click "Refresh Status" button (or it updates automatically if implemented).

**Expected status display**:
```
WiFi: Connected to YourNetwork (192.168.1.100)
Signal: -45 dBm

Hardware: PCA9685 detected at 0x40, PWM 50Hz
I2C: SDA=21, SCL=22, 100kHz

Servos: 9 active, all idle
Emergency Stop: Inactive

Memory: 180000 / 524288 bytes free
Uptime: 123.4 seconds
```

---

## Step 6: Test Servo Control

### 6.1 Test Single Servo

**Safety first**: Ensure servos have room to move without obstruction.

1. Click on servo 0 (Main Legs Lift) slider
2. Move slider from 300 (neutral) to 400
3. Observe servo moving smoothly upward
4. Move slider back to 300
5. Observe servo returning to neutral

**Expected behavior**:
- Smooth gradual movement (not instant jump)
- Movement speed matches global speed setting
- Servo stops at target position
- Status updates show current position

### 6.2 Test Speed Control

1. Set global speed to 0.1 (slowest)
2. Move servo 0 from 300 to 400
3. Observe very slow movement (~18 seconds)
4. Set global speed to 1.0 (fastest)
5. Move servo 0 from 400 to 300
6. Observe fast movement (~2 seconds)

### 6.3 Test Emergency Stop

1. Start a servo movement (e.g., servo 0 to 500)
2. While moving, click red STOP button
3. Observe:
   - Servo stops immediately (within 100ms)
   - Button turns red/highlighted
   - Status shows "Emergency Stop: Active"
   - All servos go to floating state (no torque)

4. Click "Resume" button
5. Observe:
   - Servos re-initialize to neutral positions
   - Emergency stop status clears
   - System ready for new commands

---

## Step 7: Test Preset Movements

### 7.1 Reset to Neutral

1. Click "Reset Positions" button
2. Observe all servos moving to neutral stance:
   - Legs at 50% height
   - Legs centered rotation
   - Arms at minimum positions
3. Wait for completion
4. Verify servos disabled (no holding torque)

### 7.2 Test Walking Presets

**Step Forward**:
1. Click "Step Forward" button
2. Observe choreographed sequence:
   - Legs lower
   - Legs rotate forward
   - Legs lift high
   - Return to neutral
3. Total duration: ~2-3 seconds

**Step Backward**:
1. Click "Step Backward" button
2. Observe reverse walking motion

**Turn Right**:
1. Click "Turn Right" button
2. Observe turning motion with leg rotation

### 7.3 Test Arm Presets

**Greet (Right Hi)**:
1. Click "Greet" button
2. Observe:
   - Robot lifts right side
   - Right arm raises
   - Hand waves 3 times
   - Arm lowers
   - Return to neutral

**Mic Drop**:
1. Click "Mic Drop" button
2. Observe:
   - Right arm raises
   - Holds position (dramatic pause)
   - Hand drops
   - Return to neutral

### 7.4 Test All Presets

Run through all 13 presets:
- [ ] Reset Positions
- [ ] Step Forward
- [ ] Step Backward
- [ ] Turn Right
- [ ] Turn Left
- [ ] Greet
- [ ] Laugh
- [ ] Swing Legs
- [ ] Balance
- [ ] Mic Drop
- [ ] Defensive Posture
- [ ] Pose
- [ ] Bow

**Expected results**:
- All sequences complete successfully
- No servo binding or mechanical issues
- Smooth coordinated movements
- Servos disable after completion

---

## Step 8: Advanced Testing

### 8.1 Test Multiple Servos

Using cURL or web interface's manual mode:

```bash
curl -X POST http://192.168.1.100/control \
  -H "Content-Type: application/json" \
  -d '{
    "type": "multiple",
    "targets": {"0": 350, "1": 400, "2": 200},
    "speed": 0.6
  }'
```

**Expected result**: All 3 servos move simultaneously to their targets.

### 8.2 Test Concurrent Access

1. Open web interface in two browser windows
2. In window 1: Start preset "Step Forward"
3. In window 2: Immediately try to start "Turn Right"
4. Expected: Window 2 shows error "Sequence already running"
5. Wait for window 1 sequence to complete
6. Window 2 can now start "Turn Right" successfully

### 8.3 Test Error Handling

**Invalid pulse width**:
```bash
curl -X POST http://192.168.1.100/control \
  -H "Content-Type: application/json" \
  -d '{"type": "single", "channel": 0, "target": 700, "speed": 1.0}'
```

**Expected response**:
```json
{
  "success": false,
  "message": "Invalid pulse width",
  "error": "Pulse width 700 exceeds maximum 600 for channel 0"
}
```

**Invalid channel**:
```bash
curl -X POST http://192.168.1.100/control \
  -H "Content-Type: application/json" \
  -d '{"type": "single", "channel": 10, "target": 300, "speed": 1.0}'
```

**Expected response**:
```json
{
  "success": false,
  "message": "Invalid channel",
  "error": "Channel 10 invalid. Must be 0-8."
}
```

---

## Step 9: Performance Validation

### 9.1 Measure Latency

**Boot time**:
```bash
# Reboot ESP32 and time from reset to "System ready" message
# Expected: <10 seconds (SC-001)
```

**Command latency**:
```bash
time curl -X POST http://192.168.1.100/control \
  -H "Content-Type: application/json" \
  -d '{"type": "single", "channel": 0, "target": 350, "speed": 1.0}'

# Expected: <200ms (SC-003)
```

**Emergency stop latency**:
1. Start long movement (servo 0: 200 → 500 at speed=0.1)
2. Immediately click emergency stop
3. Measure time from click to servo stop
4. Expected: <100ms (SC-004)

### 9.2 Test Parallel Execution

```bash
# Move 6 servos simultaneously
curl -X POST http://192.168.1.100/control \
  -H "Content-Type: application/json" \
  -d '{
    "type": "multiple",
    "targets": {
      "0": 350, "1": 400, "2": 200,
      "3": 300, "4": 300, "5": 300
    },
    "speed": 0.5
  }'
```

**Verify**:
- All 6 servos move simultaneously (not sequentially)
- Web server remains responsive during movement
- Memory doesn't exhaust
- Expected: SC-005 (6+ concurrent movements)

### 9.3 Test Long-Running Stability

**30-Minute Stress Test**:
```bash
# Create a script to run presets continuously
for i in {1..100}; do
  curl -X POST http://192.168.1.100/control \
    -H "Content-Type: application/json" \
    -d '{"type": "preset", "preset": "step_forward"}'
  sleep 5
done
```

**Monitor**:
- Serial console for memory warnings
- Web interface remains accessible
- No crashes or reboots
- Expected: SC-009 (30+ minutes stable operation)

---

## Troubleshooting

### Issue: "I2C device not found"

**Symptoms**: PCA9685 not detected during boot

**Solutions**:
1. Check wiring:
   ```
   ESP32 GPIO 8 → PCA9685 SDA
   ESP32 GPIO 9 → PCA9685 SCL
   ESP32 GND    → PCA9685 GND
   ```
2. Verify PCA9685 has power (3.3V or 5V to VCC)
3. Check I2C address (default 0x40):
   ```python
   >>> import machine
   >>> i2c = machine.I2C(0, scl=machine.Pin(9), sda=machine.Pin(8))
   >>> i2c.scan()
   [64]  # Should see 64 (0x40 in decimal)
   ```
4. Try different GPIO pins if defaults don't work

---

### Issue: "WiFi connection timeout"

**Symptoms**: ESP32 can't connect to WiFi

**Solutions**:
1. Verify SSID and password in `wifi_config.py`
2. Check WiFi network is 2.4GHz (not 5GHz)
3. Move ESP32 closer to router
4. Check router allows new device connections
5. Try setting static IP:
   ```python
   wlan.ifconfig(('192.168.1.100', '255.255.255.0', '192.168.1.1', '8.8.8.8'))
   ```

---

### Issue: "Out of memory"

**Symptoms**: MemoryError during boot or operation

**Solutions**:
1. Check free memory:
   ```python
   >>> import gc
   >>> gc.collect()
   >>> gc.mem_free()
   180000  # Should be >150KB
   ```
2. Reduce HTML interface size (compress, remove comments)
3. Limit concurrent servo movements (reduce from 6 to 3)
4. Add more frequent `gc.collect()` calls
5. Check for memory leaks (free memory should not decrease over time)

---

### Issue: Servo binding or mechanical issues

**Symptoms**: Servo won't move, makes noise, or gets hot

**Solutions**:
1. Check mechanical obstructions
2. Verify pulse width within safe range (not exceeding min/max)
3. Ensure servo has adequate power supply (3-5A for 9 servos)
4. Test servo individually with known-good pulse widths
5. Adjust calibration values if needed:
   ```python
   # In servo_controller.py
   SERVO_CALIBRATION[0]['min'] = 250  # Increase min if binding
   SERVO_CALIBRATION[0]['max'] = 450  # Decrease max if binding
   ```

---

### Issue: Web interface not loading

**Symptoms**: Browser shows "Connection refused" or times out

**Solutions**:
1. Verify ESP32 is on same network:
   ```bash
   ping 192.168.1.100
   ```
2. Check firewall not blocking port 80
3. Try accessing from serial console:
   ```python
   >>> import socket
   >>> s = socket.socket()
   >>> s.bind(('', 80))
   >>> # If error, port 80 may be in use
   ```
4. Check server is running:
   ```
   # In serial console, should see:
   Web server running on port 80
   ```
5. Try different browser or disable browser extensions

---

### Issue: Emergency stop not working

**Symptoms**: Servos don't stop immediately when button clicked

**Solutions**:
1. Verify emergency stop endpoint:
   ```bash
   curl -X POST http://192.168.1.100/emergency
   ```
2. Check serial console for errors
3. Verify `emergency_stop` flag is checked in movement loops
4. Ensure asyncio tasks are cancellable (not blocked in synchronous code)
5. Test with simple movement first (not complex preset)

---

## Maintenance

### Daily Checks

- [ ] WiFi connection stable
- [ ] Servo movements smooth
- [ ] Web interface responsive
- [ ] No memory warnings in serial console

### Weekly Checks

- [ ] Free memory >200KB
- [ ] All presets still work
- [ ] Emergency stop tested
- [ ] Servo calibration still accurate

### Monthly Checks

- [ ] Update MicroPython firmware if new version available
- [ ] Check servo mechanical condition (gears, wires)
- [ ] Verify power supply output voltage
- [ ] Test 30-minute stability run

---

## Development Workflow

### Making Changes

1. **Edit files locally**: `firmware/esp32_test/*.py`
2. **Upload changes**: `./upload.sh <filename.py>`
3. **Reboot ESP32**: Ctrl+D in serial console or press reset button
4. **Test changes**: Via web interface or serial console
5. **Monitor logs**: Watch serial console for errors

### Adding New Presets

1. Edit `movement_presets.py`
2. Add new preset definition:
   ```python
   PRESETS['my_new_move'] = {
       'name': 'my_new_move',
       'display_name': 'My New Move',
       'description': 'Does something cool',
       'steps': [
           {'targets': {0: 350}, 'speed': 0.8, 'delay_after': 0.2},
           # ... more steps
       ]
   }
   ```
3. Upload: `./upload.sh movement_presets.py`
4. Reboot ESP32
5. Test from web interface

### Adjusting Calibration

1. Test servos manually to find safe min/max values
2. Edit `servo_controller.py` `SERVO_CALIBRATION` dict
3. Upload: `./upload.sh servo_controller.py`
4. Reboot ESP32
5. Verify new ranges work correctly

---

## Quick Reference

### Shell Scripts (All use mpremote)

All scripts in `firmware/esp32_test/` use `mpremote` exclusively:

```bash
# Upload all firmware files
./upload.sh

# Configure WiFi credentials
./configure_wifi.sh

# Start web server
./start_server.sh

# Connect to REPL
./connect.sh

# List files on ESP32
./list_files.sh

# Run I2C diagnostics
./diagnose.sh

# Clean all files from ESP32
./clean.sh
```

### Direct mpremote Commands

```bash
# Connect to REPL
mpremote connect /dev/ttyACM0

# Upload single file
mpremote connect /dev/ttyACM0 fs cp main.py :

# Download file from ESP32
mpremote connect /dev/ttyACM0 fs cp :main.py ./main_backup.py

# List files
mpremote connect /dev/ttyACM0 fs ls

# Remove file
mpremote connect /dev/ttyACM0 fs rm :old_file.py

# Execute Python code
mpremote connect /dev/ttyACM0 exec "import machine; print(machine.freq())"

# Run script and return to REPL
mpremote connect /dev/ttyACM0 run test_script.py

# Soft reset
mpremote connect /dev/ttyACM0 exec "import machine; machine.reset()"
```

### Serial Console Commands

```python
# Reboot
import machine
machine.reset()

# Check memory
import gc
gc.collect()
gc.mem_free()

# Test WiFi
import network
wlan = network.WLAN(network.STA_IF)
wlan.isconnected()
wlan.ifconfig()

# Scan I2C
import machine
i2c = machine.I2C(0, scl=machine.Pin(9), sda=machine.Pin(8))
i2c.scan()

# Manual servo control
from pca9685 import PCA9685
import machine
i2c = machine.I2C(0, scl=machine.Pin(9), sda=machine.Pin(8))
pca = PCA9685(i2c)
pca.set_pwm_freq(50)
pca.set_pwm(0, 0, 300)  # Channel 0, pulse width 300
```

### API Testing Commands

```bash
# Get status
curl http://192.168.1.100/status | jq

# Move servo
curl -X POST http://192.168.1.100/control \
  -H "Content-Type: application/json" \
  -d '{"type":"single","channel":0,"target":350,"speed":0.8}'

# Run preset
curl -X POST http://192.168.1.100/control \
  -H "Content-Type: application/json" \
  -d '{"type":"preset","preset":"step_forward"}'

# Emergency stop
curl -X POST http://192.168.1.100/emergency

# Set speed
curl -X POST http://192.168.1.100/control \
  -H "Content-Type: application/json" \
  -d '{"type":"speed","speed":0.5}'
```

---

## Next Steps

After completing this quickstart:

1. **Calibrate servos**: Fine-tune min/max values for your specific hardware
2. **Create custom presets**: Add new movement sequences for your use case
3. **Enhance web interface**: Add features like sequence recording, real-time position display
4. **Add authentication**: Implement basic auth if deploying on untrusted network
5. **Integrate with main TARS system**: Connect ESP32 to MQTT for remote control (future enhancement)

---

## Support

If you encounter issues not covered in this guide:

1. Check serial console for error messages
2. Review data-model.md and contracts documentation
3. Test with minimal setup (single servo, simple movements)
4. Check hardware connections and power supply
5. Verify MicroPython firmware version matches requirements

---

**Version**: 1.0 | **Last Updated**: 2025-10-15
