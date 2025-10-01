# Movement Service

The movement service translates high-level motion directives into low-level PWM
frames for the ESP32-based servo controller. It consumes directives on
`movement/command`, expands them into calibrated frames, and publishes the frames to
`movement/frame` for the MicroPython firmware (`servoctl.py`) to execute. Status
updates and health pings are emitted on `movement/state` and
`system/health/movement-service` respectively.

## Features

- ✅ Typed MQTT payloads using Pydantic v2
- ✅ Calibration-driven percent-to-PWM conversion
- ✅ Built-in scripts for reset, step forward/back, and turns
- ✅ Asyncio/MQTT integration with QoS 1 publishing

## Configuration

Environment variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `MQTT_URL` | Broker connection string (`mqtt://user:pass@host:port`) | `mqtt://localhost:1883` |
| `MOVEMENT_COMMAND_TOPIC` | High-level directive topic | `movement/command` |
| `MOVEMENT_FRAME_TOPIC` | Downstream frames topic | `movement/frame` |
| `MOVEMENT_STATE_TOPIC` | Service status topic | `movement/state` |
| `MOVEMENT_HEALTH_TOPIC` | Health heartbeat topic | `system/health/movement-service` |
| `MOVEMENT_CALIBRATION_PATH` | Optional path to JSON calibration override | none |

Servo calibration is loaded from `movement_service/calibration.py`. Custom values can
be provided via JSON at the path specified by `MOVEMENT_CALIBRATION_PATH`.

## Running locally

```bash
python -m movement_service
```

The service will connect to the configured MQTT broker, publish a retained health
message, and start replaying directives. See `tests/` for example directive payloads.

## Flashing the ESP32 firmware

1. Flash MicroPython (v1.22 or newer) onto the ESP32 using `esptool.py`.
2. Copy `firmware/esp32/servoctl.py` to the board:
	```bash
	ampy --port /dev/ttyUSB0 put firmware/esp32/servoctl.py servoctl.py
	```
3. (Optional) Upload a `movement_config.json` file that contains Wi-Fi and MQTT credentials.
	You can also set Wi-Fi from the on-device web portal after reboot.
4. Reset the board; it will connect to Wi-Fi (or expose the `TARS-Setup` portal if it
	needs credentials), subscribe to `movement/frame`, and publish health on
	`system/health/movement-esp32`. While connected you can visit the device in a browser
	to center its servos before running a move sequence.
5. Start `tars-movement-service` on your host to feed high-level directives.
