# Movement MQTT Contract Draft

## Topics

- `movement/command` (QoS 1)
  - Upstream directive addressed to the movement service from higher-level policies.
  - Payload: JSON encoded `MovementCommand`.
- `movement/frame` (QoS 1)
  - Downstream frames streamed to the ESP32 controller.
  - Payload: JSON encoded `MovementFrame`.
- `movement/state` (QoS 1, retained optional)
  - ESP32 controller publishes status/ack events.
  - Payload: JSON encoded `MovementState`.
- `system/health/movement` (QoS 1, retained)
  - Published by both movement service and ESP32 worker for health monitoring.

## Payloads

### MovementCommand

```json
{
  "id": "b5d2a0fe-dcaf-4cbb-8eda-a8628f2fde70",
  "command": "step_forward",
  "params": {
    "speed": 0.6
  },
  "timestamp": 1738291200.123
}
```

- `id`: UUID4 envelope identifier.
- `command`: One of `reset`, `step_forward`, `step_backward`, `turn_left`, `turn_right`, `laugh`, `bow`, `pose`, `balance`, `mic_drop`, `monster`, `now`, `pezz_dispenser`, `right_hi`, `swing_legs`.
- `params`: Optional command-specific parameters (e.g., `speed` in range 0.1-1.0).
- `timestamp`: Unix epoch seconds (float) when command was issued.

### MovementFrame

```json
{
  "id": "b5d2a0fe-dcaf-4cbb-8eda-a8628f2fde70",
  "seq": 0,
  "total": 24,
  "duration_ms": 400,
  "hold_ms": 150,
  "channels": {
    "0": 384,
    "1": 312,
    "2": 301,
    "3": 455,
    "4": 470,
    "5": 512,
    "6": 377,
    "7": 403,
    "8": 419
  },
  "disable_after": false
}
```

- `id`: Matches originating command id.
- `seq`: Zero-based sequence number.
- `total`: Total number of frames for this command.
- `duration_ms`: Transition duration to interpolate from the previous frame.
- `hold_ms`: Optional dwell time after reaching the target position.
- `channels`: Map of PWM channel index (`0-15`) to target pulse value (0-4095). Channels omitted are left untouched.
- `disable_after`: If `true`, ESP32 should cut PWM drive after `hold_ms` expires (used for idle).

### MovementState

```json
{
  "id": "b5d2a0fe-dcaf-4cbb-8eda-a8628f2fde70",
  "event": "completed",
  "seq": 24,
  "timestamp": 1738291200.823,
  "detail": null
}
```

- `event`: `accepted`, `started`, `frame_ack`, `completed`, or `error`.
- `seq`: Last processed frame when applicable.
- `detail`: Optional error message or diagnostics.

## Timing & QoS Rules

- Movement service publishes frames sequentially, awaiting an acknowledgement (`frame_ack` or `completed`) before advancing.
- ESP32 controller should watchdog frame gaps (>1.5× expected duration) and emit `error` events if timed out.
- All payloads must be encoded using `orjson` (service) or `ujson`/`json` (firmware) with forbidding extraneous keys.

## Calibration Handoff

- Host-side movement service remains responsible for percent-to-PWM conversion using calibrated ranges loaded from environment variables.
- ESP32 receives absolute PWM counts and never applies offsets.
- A separate retained topic `movement/calibration` can optionally be used later for runtime calibration pushes (not implemented yet).
