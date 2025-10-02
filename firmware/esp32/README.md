# ESP32 Servo Firmware

This directory contains the MicroPython firmware that drives the TARS servo rig via
a PCA9685 controller.

## 🎉 Phase 4-5 Complete!

**Status**: ✅ All movement modules implemented and integrated  
**Total Code**: 3,733 lines (Phase 3 + Phase 4-5)  
**Tests**: 38/38 passing (100%)  
**Documentation**: See [PHASE_4_5_COMPLETE.md](./PHASE_4_5_COMPLETE.md) for full details

**What's New:**
- ✅ WiFi/MQTT infrastructure (Phase 3)
- ✅ Percentage-based servo API (1-100 scale)
- ✅ 15 TARS-AI movement sequences (basic + expressive)
- ✅ Asyncio parallel servo control
- ✅ Command queue with emergency stop
- ✅ Full integration into `tars_controller.py`

**Next Step**: Hardware deployment and servo calibration (see below)

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

### Quick Setup (Recommended) 🚀

Use the **automated setup script** to flash your ESP32 in one command:

```bash
cd firmware/esp32
./setup.sh
```

The script will automatically:
- ✅ Check for required tools (`esptool`, `mpremote`)
- ✅ Detect connected ESP32 devices
- ✅ Read MQTT credentials from `../../.env` (MQTT_USER, MQTT_PASS, MQTT_PORT)
- ✅ Auto-detect your host IP address
- ✅ **Scan for available WiFi networks** (or manual entry, or skip for portal setup)
- ✅ Generate complete `movement_config.json` with all required fields
- ✅ Auto-download MicroPython firmware if needed
- ✅ Guide through manual bootloader mode if needed (hold BOOT, press RESET)
- ✅ Upload `lib/`, `movements/`, `tars_controller.py`, `main.py`, and `movement_config.json` to ESP32
- ✅ Verify application is running with LED status check

### LED Status Indicators 🚦

The ESP32 uses an onboard RGB LED (GPIO 48) to indicate system status:

- 🔵 **Cyan (Solid)** - System booting
- 🔴 **Red (Breathing)** - No WiFi / Setup portal active (connect to `TARS-Setup`)
- 🟡 **Yellow (Blinking)** - MQTT connection error (check broker/credentials)
- 🟢 **Green (Solid)** - Fully connected and running ✓

See [LED_STATUS.md](./LED_STATUS.md) for detailed troubleshooting.

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

The firmware reads `movement_config.json` at startup. All fields are optional—the
file provides configuration for WiFi, MQTT, and hardware settings. Example:

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
    "scl": 22,
    "sda": 21
  },
  "topics": {
    "frame": "movement/frame",
    "state": "movement/state",
    "health": "system/health/movement-esp32"
  },
  "frame_timeout_ms": 2500,
  "status_led": 2,
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
  }
}
```

Key fields:

- `wifi`: SSID/password for the access point the ESP32 should join.
- `mqtt`: Connection parameters for the broker. Keepalive defaults to 30 seconds.
- `pca9685`: I²C pinout and frequency. Update `address` if your board uses a
  different bus address.
- `topics`: MQTT topics matching the movement-service contract.
- `frame_timeout_ms`: When exceeded without a new frame, the firmware publishes a
  timeout error.
- `status_led`: Optional GPIO pin that toggles every loop iteration for a quick
  heartbeat indicator.
- `setup_portal`: Access point and timeout settings for the onboarding Wi-Fi portal.
- `servo_channel_count`: Number of active PCA9685 channels (used by the centering UI).
- `default_center_pulse`: PWM count applied when a channel lacks a specific calibration.
- `servo_centers`: Optional per-channel PWM overrides used by the centering controls.

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

## Health and troubleshooting

- Watch the broker for `system/health/movement-esp32`. `{"ok": true}` indicates the
  firmware is healthy and subscribed.
- Frame acknowledgements are published on `movement/state` with `event:"frame_ack"`.
- If Wi-Fi authentication fails, the firmware re-enables the setup portal so you can
  update credentials without reflashing.
- Use the on-device portal to center servos before playbacks; if nothing moves, ensure
  the PCA9685 is powered and the channel count matches your wiring.
- Use `mpremote repl` for interactive debugging on the board. The firmware exposes
  a `main()` entry point if you need to re-run the controller manually.

Once the board reports `ready`, start the host-side `movement_service` to stream
servo frames.
