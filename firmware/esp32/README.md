# ESP32 Servo Firmware

This directory contains the MicroPython firmware that drives the TARS servo rig via
a PCA9685 controller. The firmware subscribes to MQTT `movement/frame` payloads
published by the host-side movement service, applies the PWM values, and reports
status back on `movement/state` and `system/health/movement-esp32`.

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

1. Clone this repository (or copy the `firmware/esp32` folder) and `cd` into it.
2. Copy `servoctl.py` to the board's filesystem:
   ```bash
   ampy --port /dev/ttyUSB0 put servoctl.py
   ```
   With `mpremote` the equivalent is:
   ```bash
   mpremote cp servoctl.py :servoctl.py
   ```
3. Create a `movement_config.json` file next to `servoctl.py` with your Wi-Fi and MQTT details (see below) and upload it to the board:
   ```bash
   ampy --port /dev/ttyUSB0 put movement_config.json
   ```
4. Reset the board. On boot, the firmware will:
  - Attempt to join the configured Wi-Fi network
  - Fall back to hosting a `TARS-Setup` access point with a web portal if Wi-Fi credentials are missing or invalid
  - Subscribe to `movement/frame`
  - Send a retained health payload on `system/health/movement-esp32`
  - Blink the optional status LED (if configured)

## Web-based Wi-Fi setup

If the firmware cannot connect to Wi-Fi it automatically enables an access point named
`TARS-Setup` (password optional, see `setup_portal` config). Connect to that network and
open `http://192.168.4.1/` to access the captive portal:

1. Enter your Wi-Fi SSID and password.
2. Submit the form to save the credentials to `movement_config.json`.
3. The board reboots and attempts to join the newly provided network.
4. Once the ESP32 is on your LAN, browse to `http://<esp32-ip>/` to reach the same portal
  where you can center individual servos or all channels before running live motions.

You can also trigger the portal by clearing the Wi-Fi credentials from
`movement_config.json` and resetting the board.

## Configuration file

The firmware reads `movement_config.json` at startup. All fields are optional—the
file overrides the defaults baked into `servoctl.py`. Example:

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
