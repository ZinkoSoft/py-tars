# HTTP API Contract

**Feature**: ESP32 MicroPython Servo Control System  
**Version**: 1.0  
**Base URL**: `http://<esp32-ip-address>`  
**Port**: 80

## Overview

RESTful HTTP API for controlling servos and managing the TARS robot. All endpoints use JSON for request/response bodies except the root endpoint which returns HTML.

## Authentication

None. This is a local network embedded device. Consider adding basic auth if deployed on untrusted networks.

## Common Response Structure

All JSON responses follow this structure:

```json
{
  "success": true,
  "message": "Operation description",
  "error": null,
  "server_timestamp": 1234567890.456,
  "latency_ms": 123.4
}
```

**Fields**:
- `success` (boolean): `true` if operation succeeded, `false` if error
- `message` (string): Human-readable description of result
- `error` (string | null): Error details if `success=false`, otherwise `null`
- `server_timestamp` (float): Unix timestamp when response sent
- `latency_ms` (float | null): Round-trip latency if client sent `timestamp` in request

## Endpoints

### GET /

**Description**: Returns HTML web interface for browser-based control.

**Response**: `text/html`

**Example**:
```http
GET / HTTP/1.1
Host: 192.168.1.100

HTTP/1.1 200 OK
Content-Type: text/html
Content-Length: 8192

<!DOCTYPE html>
<html>
  <head>...</head>
  <body>...</body>
</html>
```

---

### GET /status

**Description**: Returns current system status including WiFi, hardware, servo positions, and memory.

**Response**: `application/json`

**Response Body** (see `SystemStatus` in data-model.md):
```json
{
  "success": true,
  "message": "System status retrieved",
  "error": null,
  "server_timestamp": 1234567890.456,
  "data": {
    "wifi": {
      "connected": true,
      "ssid": "MyNetwork",
      "ip": "192.168.1.100",
      "signal": -45
    },
    "hardware": {
      "pca9685": {
        "detected": true,
        "address": 64,
        "frequency": 50
      },
      "i2c_bus": {
        "sda_pin": 8,
        "scl_pin": 9,
        "speed": 100000
      }
    },
    "servos": [
      {
        "channel": 0,
        "label": "Main Legs Lift",
        "position": 300,
        "target": null,
        "speed": 1.0,
        "state": "idle",
        "min_pulse": 200,
        "max_pulse": 500
      }
      // ... 8 more servos
    ],
    "emergency_stop": false,
    "memory": {
      "free": 180000,
      "total": 524288
    },
    "uptime": 123.45
  }
}
```

**Example**:
```http
GET /status HTTP/1.1
Host: 192.168.1.100

HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: 2048

{"success": true, "message": "System status retrieved", ...}
```

---

### POST /control

**Description**: Control servo movements (single, multiple, preset, speed adjustment).

**Request**: `application/json`

**Request Body** (see `ControlCommand` in data-model.md):

#### Command Type: "single"

Move a single servo to target position.

```json
{
  "type": "single",
  "channel": 0,
  "target": 350,
  "speed": 0.8,
  "timestamp": 1234567890.123
}
```

**Fields**:
- `type`: Must be `"single"`
- `channel` (integer): Servo channel (0-8)
- `target` (integer): Target pulse width (must be in servo's min/max range)
- `speed` (float, optional): Speed factor for this movement (0.1-1.0), defaults to global speed
- `timestamp` (float, optional): Client timestamp for latency tracking

**Response**:
```json
{
  "success": true,
  "message": "Servo 0 moving to 350",
  "error": null,
  "server_timestamp": 1234567890.456,
  "latency_ms": 333.0
}
```

**Errors**:
- `400 Bad Request`: Invalid channel, pulse width out of range, servo already moving
- `503 Service Unavailable`: Emergency stop active, low memory

---

#### Command Type: "multiple"

Move multiple servos simultaneously.

```json
{
  "type": "multiple",
  "targets": {
    "0": 350,
    "1": 400,
    "2": 200
  },
  "speed": 0.6,
  "timestamp": 1234567890.123
}
```

**Fields**:
- `type`: Must be `"multiple"`
- `targets` (object): Map of channel (string key) to target pulse width (integer)
- `speed` (float, optional): Speed factor for all movements (0.1-1.0)
- `timestamp` (float, optional): Client timestamp

**Response**:
```json
{
  "success": true,
  "message": "Moving 3 servos simultaneously",
  "error": null,
  "server_timestamp": 1234567890.456,
  "latency_ms": 333.0
}
```

**Errors**:
- `400 Bad Request`: Invalid targets, any servo already moving
- `503 Service Unavailable`: Emergency stop active

---

#### Command Type: "preset"

Execute a pre-programmed movement sequence.

```json
{
  "type": "preset",
  "preset": "step_forward",
  "timestamp": 1234567890.123
}
```

**Fields**:
- `type`: Must be `"preset"`
- `preset` (string): Preset name (see list below)
- `timestamp` (float, optional): Client timestamp

**Available Presets**:
- `"reset_positions"` - Reset to neutral stance
- `"step_forward"` - Walk forward one step
- `"step_backward"` - Walk backward one step
- `"turn_right"` - Turn 90° right
- `"turn_left"` - Turn 90° left
- `"right_hi"` - Wave right arm
- `"laugh"` - Bouncing motion
- `"swing_legs"` - Swing legs side to side
- `"balance"` - Balance on one foot
- `"mic_drop"` - Dramatic arm drop
- `"monster"` - Defensive posture with arms up
- `"pose"` - Strike a pose
- `"bow"` - Bow forward

**Response**:
```json
{
  "success": true,
  "message": "Preset 'step_forward' started",
  "error": null,
  "server_timestamp": 1234567890.456,
  "latency_ms": 333.0
}
```

**Errors**:
- `400 Bad Request`: Unknown preset name
- `409 Conflict`: Another sequence already running
- `503 Service Unavailable`: Emergency stop active

---

#### Command Type: "speed"

Update global speed factor for all subsequent movements.

```json
{
  "type": "speed",
  "speed": 0.5,
  "timestamp": 1234567890.123
}
```

**Fields**:
- `type`: Must be `"speed"`
- `speed` (float): New global speed factor (0.1-1.0)
- `timestamp` (float, optional): Client timestamp

**Response**:
```json
{
  "success": true,
  "message": "Global speed set to 0.5",
  "error": null,
  "server_timestamp": 1234567890.456,
  "latency_ms": 333.0
}
```

**Errors**:
- `400 Bad Request`: Speed out of range (0.1-1.0)

---

### POST /emergency

**Description**: Emergency stop all servos immediately. Cancels all active movements and disables all servos (PWM=0).

**Request**: No body required (or empty JSON `{}`)

**Request Body** (optional):
```json
{
  "timestamp": 1234567890.123
}
```

**Response**:
```json
{
  "success": true,
  "message": "Emergency stop activated - all servos disabled",
  "error": null,
  "server_timestamp": 1234567890.456,
  "latency_ms": 333.0
}
```

**Example**:
```http
POST /emergency HTTP/1.1
Host: 192.168.1.100
Content-Type: application/json
Content-Length: 2

{}

HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: 128

{"success": true, "message": "Emergency stop activated", ...}
```

**Notes**:
- Always succeeds (never returns error)
- Completes within 100ms (SC-004 requirement)
- Servos remain disabled until new movement command received

---

### POST /resume

**Description**: Re-initialize servos after emergency stop. Moves all servos to neutral positions.

**Request**: No body required (or empty JSON `{}`)

**Response**:
```json
{
  "success": true,
  "message": "Servos re-initialized to neutral positions",
  "error": null,
  "server_timestamp": 1234567890.456,
  "latency_ms": 333.0
}
```

**Example**:
```http
POST /resume HTTP/1.1
Host: 192.168.1.100
Content-Type: application/json
Content-Length: 2

{}

HTTP/1.1 200 OK
Content-Type: application/json

{"success": true, "message": "Servos re-initialized", ...}
```

---

## Error Responses

All errors follow this structure:

```json
{
  "success": false,
  "message": "Brief error description",
  "error": "Detailed error message with context",
  "server_timestamp": 1234567890.456,
  "latency_ms": 333.0
}
```

### HTTP Status Codes

| Code | Meaning | When Used |
|------|---------|-----------|
| 200 OK | Success | All successful operations |
| 400 Bad Request | Invalid input | Invalid JSON, out-of-range values, unknown command type |
| 404 Not Found | Unknown endpoint | Invalid URL path |
| 409 Conflict | Resource busy | Sequence already running, servo locked |
| 503 Service Unavailable | System unavailable | Emergency stop active, low memory, hardware error |

### Common Error Examples

**Invalid pulse width**:
```json
{
  "success": false,
  "message": "Invalid pulse width",
  "error": "Pulse width 700 exceeds maximum 600 for channel 0",
  "server_timestamp": 1234567890.456
}
```

**Sequence already running**:
```json
{
  "success": false,
  "message": "Cannot start preset",
  "error": "Movement sequence 'step_forward' is already running",
  "server_timestamp": 1234567890.456
}
```

**Emergency stop active**:
```json
{
  "success": false,
  "message": "System in emergency stop mode",
  "error": "Cannot execute movement commands while emergency stop active. Call /resume to re-initialize.",
  "server_timestamp": 1234567890.456
}
```

**Low memory**:
```json
{
  "success": false,
  "message": "Insufficient memory",
  "error": "Free memory (120000 bytes) below safe threshold (150000 bytes). Emergency stop recommended.",
  "server_timestamp": 1234567890.456
}
```

---

## Rate Limiting

No rate limiting implemented. Consider adding if misuse detected:
- Max 10 requests/second per client
- Max 5 concurrent connections total

---

## CORS Headers

Not implemented (not needed for same-origin web interface). If controlling from external web app, add:

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST
Access-Control-Allow-Headers: Content-Type
```

---

## WebSocket Support

Not implemented in v1.0. Future enhancement for real-time status streaming.

Proposed future endpoint: `ws://<ip>/ws` for bidirectional communication.

---

## Example Client Code (JavaScript)

```javascript
// Emergency stop
async function emergencyStop() {
  const response = await fetch('http://192.168.1.100/emergency', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({timestamp: Date.now() / 1000})
  });
  const result = await response.json();
  console.log(result.message);
  return result.success;
}

// Move single servo
async function moveServo(channel, target, speed = 1.0) {
  const response = await fetch('http://192.168.1.100/control', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      type: 'single',
      channel: channel,
      target: target,
      speed: speed,
      timestamp: Date.now() / 1000
    })
  });
  const result = await response.json();
  if (!result.success) {
    alert(`Error: ${result.error}`);
  }
  return result;
}

// Execute preset
async function executePreset(presetName) {
  const response = await fetch('http://192.168.1.100/control', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      type: 'preset',
      preset: presetName,
      timestamp: Date.now() / 1000
    })
  });
  const result = await response.json();
  return result;
}

// Get system status
async function getStatus() {
  const response = await fetch('http://192.168.1.100/status');
  const result = await response.json();
  return result.data;
}

// Set global speed
async function setSpeed(speedFactor) {
  const response = await fetch('http://192.168.1.100/control', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      type: 'speed',
      speed: speedFactor,
      timestamp: Date.now() / 1000
    })
  });
  return await response.json();
}
```

---

## Testing Checklist

### Manual Testing via cURL

```bash
# Get status
curl http://192.168.1.100/status

# Move single servo
curl -X POST http://192.168.1.100/control \
  -H "Content-Type: application/json" \
  -d '{"type":"single","channel":0,"target":350,"speed":0.8}'

# Execute preset
curl -X POST http://192.168.1.100/control \
  -H "Content-Type: application/json" \
  -d '{"type":"preset","preset":"step_forward"}'

# Emergency stop
curl -X POST http://192.168.1.100/emergency

# Resume
curl -X POST http://192.168.1.100/resume

# Set speed
curl -X POST http://192.168.1.100/control \
  -H "Content-Type: application/json" \
  -d '{"type":"speed","speed":0.5}'
```

### Contract Validation

- [ ] All endpoints return valid JSON (except `/` which returns HTML)
- [ ] Success responses have `success=true` and `message`
- [ ] Error responses have `success=false`, `message`, and `error`
- [ ] Status codes match documented values
- [ ] Latency tracking works when `timestamp` provided
- [ ] Invalid JSON returns 400 Bad Request
- [ ] Unknown endpoints return 404 Not Found
- [ ] Emergency stop completes within 100ms
- [ ] Concurrent requests don't crash server

---

## Version History

- **1.0** (2025-10-15): Initial API specification
