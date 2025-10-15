# Movement Service

The movement service is a thin MQTT bridge that validates and forwards movement commands
to the ESP32 tars_controller. It consumes TestMovementRequest messages on `movement/test`,
validates them using Pydantic v2, and forwards them to the ESP32 which autonomously
executes movement sequences. Health status is emitted on `system/health/movement-service`.

## Architecture

**Command-based** (current):
- LLM/Router → `movement/test` → movement-service (validation) → ESP32 `movement/test` → autonomous execution
- ESP32 firmware (`tars_controller.py`) contains all movement sequence logic
- movement-service only validates and forwards commands

**NOT frame-based**: This service does NOT build PWM frames or calculate servo positions.
All movement logic is autonomously handled by the ESP32's MovementSequences class.

## Features

- ✅ Typed MQTT payloads using Pydantic v2 (TestMovementRequest contract)
- ✅ Command validation before forwarding to ESP32
- ✅ Asyncio/MQTT integration with QoS 1 publishing
- ✅ Health monitoring and reconnection backoff

## Configuration

Environment variables:

| Variable | Purpose | Default |
| --- | --- | --- |
| `MQTT_URL` | Broker connection string (`mqtt://user:pass@host:port`) | `mqtt://localhost:1883` |
| `MOVEMENT_TEST_TOPIC` | Movement command topic (bidirectional) | `movement/test` |
| `MOVEMENT_HEALTH_TOPIC` | Health heartbeat topic | `system/health/movement-service` |
| `MOVEMENT_PUBLISH_QOS` | MQTT QoS level for publishing | `1` |

## Running locally

```bash
python -m movement_service
```

The service will connect to the configured MQTT broker, publish a retained health
message, and start forwarding validated commands to the ESP32.

## ESP32 Firmware

The ESP32 runs `firmware/esp32/tars_controller.py` which:
- Subscribes to `movement/test` for TestMovementRequest messages
- Validates using `firmware/esp32/lib/validation.py`
- Executes movement sequences autonomously using the MovementSequences class
- Publishes status updates to `movement/status`

Valid commands (see `tars.contracts.v1.movement.TestMovementCommand`):
- Basic: `reset`, `step_forward`, `step_backward`, `turn_left`, `turn_right`
- Expressive: `wave`, `laugh`, `swing_legs`, `bow`, `pose`, `balance`, `mic_drop`
- Manual: `move_legs`, `move_arm` (with params)
- Control: `disable`, `stop`

Example command payload:
```json
{
  "command": "wave",
  "speed": 0.8,
  "request_id": "abc123"
}
```
