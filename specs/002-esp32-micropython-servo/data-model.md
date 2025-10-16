# Data Model: ESP32 MicroPython Servo Control System

**Feature**: 002-esp32-micropython-servo  
**Date**: 2025-10-15  
**Status**: Phase 1 Design

## Overview

This document defines the data structures, state management, and entity relationships for the ESP32 servo control system. Since MicroPython doesn't support Pydantic or dataclasses, all structures are documented as Python dictionaries with validation rules.

## Core Entities

### 1. ServoState

Represents the current state of a single servo channel.

**Structure**:
```python
{
    "channel": int,        # 0-8 (9 servos total)
    "label": str,          # Human-readable name (e.g., "Main Legs Lift")
    "position": int,       # Current PWM pulse width (0-600)
    "target": int | None,  # Target position if moving, None if idle
    "speed": float,        # Movement speed factor (0.1-1.0)
    "state": str,          # "idle" | "moving" | "disabled"
    "min_pulse": int,      # Minimum safe pulse width
    "max_pulse": int       # Maximum safe pulse width
}
```

**Validation Rules**:
- `channel`: Must be 0-8 (9 servos only)
- `position`: Must be in range `[min_pulse, max_pulse]`
- `target`: Must be in range `[min_pulse, max_pulse]` or `None`
- `speed`: Must be in range `[0.1, 1.0]`
- `state`: Must be one of `["idle", "moving", "disabled"]`
- `min_pulse`, `max_pulse`: Must be in range `[0, 600]`

**State Transitions**:
```
idle → moving:   When move command received
moving → idle:   When target position reached
* → disabled:    When emergency stop triggered
disabled → idle: When re-initialization requested
```

**Example**:
```python
servo_0_state = {
    "channel": 0,
    "label": "Main Legs Lift",
    "position": 300,
    "target": 400,
    "speed": 0.8,
    "state": "moving",
    "min_pulse": 200,
    "max_pulse": 500
}
```

---

### 2. MovementStep

Defines a single step in a choreographed movement sequence.

**Structure**:
```python
{
    "targets": dict[int, int],  # {channel: pulse_width} for servos to move
    "speed": float,             # Speed factor for this step (0.1-1.0)
    "delay_after": float        # Seconds to wait after step completes
}
```

**Validation Rules**:
- `targets`: Keys must be valid channels (0-8), values must be in servo's `[min_pulse, max_pulse]`
- `speed`: Must be in range `[0.1, 1.0]`
- `delay_after`: Must be >= 0.0, typically 0.1-2.0 seconds

**Example**:
```python
step_1 = {
    "targets": {
        0: 350,  # Main legs lift to 350
        1: 400,  # Left leg rotation to 400
        2: 200   # Right leg rotation to 200
    },
    "speed": 0.6,
    "delay_after": 0.2
}
```

---

### 3. MovementSequence

Defines a complete choreographed movement (preset).

**Structure**:
```python
{
    "name": str,              # Preset name (e.g., "step_forward")
    "display_name": str,      # Human-readable name (e.g., "Step Forward")
    "description": str,       # Brief description of movement
    "steps": list[MovementStep],  # Ordered list of movement steps
    "state": str,             # "ready" | "running" | "completed" | "aborted"
    "current_step": int       # Index of current step (0-based), -1 if not running
}
```

**Validation Rules**:
- `name`: Must match Python identifier rules (no spaces, starts with letter)
- `display_name`: Arbitrary string for UI display
- `steps`: Must contain at least 1 step
- `state`: Must be one of `["ready", "running", "completed", "aborted"]`
- `current_step`: Must be in range `[-1, len(steps)-1]`

**State Transitions**:
```
ready → running:     When sequence starts
running → completed: When all steps finish successfully
running → aborted:   When emergency stop or error occurs
completed → ready:   When reset for next execution
aborted → ready:     When reset after error
```

**Example**:
```python
step_forward_sequence = {
    "name": "step_forward",
    "display_name": "Step Forward",
    "description": "Robot takes one step forward",
    "steps": [
        {"targets": {0: 50, 1: 50, 2: 50}, "speed": 0.4, "delay_after": 0.2},
        {"targets": {0: 22, 1: 50, 2: 50}, "speed": 0.6, "delay_after": 0.2},
        {"targets": {0: 40, 1: 17, 2: 17}, "speed": 0.65, "delay_after": 0.2},
        {"targets": {0: 85, 1: 50, 2: 50}, "speed": 0.8, "delay_after": 0.2},
        {"targets": {0: 50, 1: 50, 2: 50}, "speed": 1.0, "delay_after": 0.5}
    ],
    "state": "ready",
    "current_step": -1
}
```

---

### 4. SystemStatus

Global system state for monitoring and diagnostics.

**Structure**:
```python
{
    "wifi": {
        "connected": bool,
        "ssid": str | None,
        "ip": str | None,
        "signal": int        # RSSI in dBm
    },
    "hardware": {
        "pca9685": {
            "detected": bool,
            "address": int,  # I2C address (default 0x40)
            "frequency": int # PWM frequency in Hz (should be 50)
        },
        "i2c_bus": {
            "sda_pin": int,  # GPIO 8 (custom config)
            "scl_pin": int,  # GPIO 9 (custom config)
            "speed": int     # Hz (100000 or 400000)
        }
    },
    "servos": list[ServoState],  # 9 servo states
    "emergency_stop": bool,      # True if emergency stop active
    "memory": {
        "free": int,    # Free RAM in bytes
        "total": int    # Total RAM in bytes
    },
    "uptime": float     # Seconds since boot
}
```

**Validation Rules**:
- `wifi.ip`: Must be valid IPv4 string or `None`
- `wifi.signal`: Typical range -30 (excellent) to -90 (poor) dBm
- `hardware.pca9685.frequency`: Should be 50 for servos
- `servos`: Must contain exactly 9 `ServoState` objects
- `memory.free`: Must be <= `memory.total`
- `uptime`: Must be >= 0.0

**Example**:
```python
system_status = {
    "wifi": {
        "connected": True,
        "ssid": "MyNetwork",
        "ip": "192.168.1.100",
        "signal": -45
    },
    "hardware": {
        "pca9685": {
            "detected": True,
            "address": 0x40,
            "frequency": 50
        },
        "i2c_bus": {
            "sda_pin": 8,   # GPIO 8 (SDA)
            "scl_pin": 9,   # GPIO 9 (SCL)
            "speed": 100000
        }
    },
    "servos": [
        # ... 9 ServoState objects
    ],
    "emergency_stop": False,
    "memory": {
        "free": 180000,
        "total": 524288
    },
    "uptime": 123.45
}
```

---

### 5. ControlCommand

Incoming command from web interface to control servos.

**Structure**:
```python
{
    "type": str,              # "single" | "multiple" | "preset" | "emergency" | "speed"
    "channel": int | None,    # For type="single": which servo (0-8)
    "target": int | None,     # For type="single": target pulse width
    "targets": dict[int, int] | None,  # For type="multiple": {channel: target}
    "preset": str | None,     # For type="preset": preset name
    "speed": float | None,    # For type="speed" or movement commands
    "timestamp": float        # Client timestamp (for latency tracking)
}
```

**Command Types**:

1. **"single"**: Move one servo
   ```python
   {"type": "single", "channel": 0, "target": 350, "speed": 0.8, "timestamp": 1234567890.123}
   ```

2. **"multiple"**: Move multiple servos simultaneously
   ```python
   {"type": "multiple", "targets": {0: 350, 1: 400, 2: 200}, "speed": 0.6, "timestamp": 1234567890.123}
   ```

3. **"preset"**: Execute movement sequence
   ```python
   {"type": "preset", "preset": "step_forward", "timestamp": 1234567890.123}
   ```

4. **"emergency"**: Emergency stop all servos
   ```python
   {"type": "emergency", "timestamp": 1234567890.123}
   ```

5. **"speed"**: Update global speed setting
   ```python
   {"type": "speed", "speed": 0.5, "timestamp": 1234567890.123}
   ```

**Validation Rules**:
- `type`: Must be one of `["single", "multiple", "preset", "emergency", "speed"]`
- For `type="single"`: `channel` and `target` required
- For `type="multiple"`: `targets` required
- For `type="preset"`: `preset` required
- For `type="speed"`: `speed` required (0.1-1.0)
- `timestamp`: Optional but recommended for latency tracking

---

### 6. ControlResponse

Response from server after processing command.

**Structure**:
```python
{
    "success": bool,
    "message": str,
    "error": str | None,
    "server_timestamp": float,
    "latency_ms": float | None  # Round-trip latency if client timestamp provided
}
```

**Examples**:

Success:
```python
{
    "success": True,
    "message": "Servo 0 moving to 350",
    "error": None,
    "server_timestamp": 1234567890.456,
    "latency_ms": 123.4
}
```

Error:
```python
{
    "success": False,
    "message": "Invalid pulse width",
    "error": "Pulse width 700 exceeds maximum 600 for channel 0",
    "server_timestamp": 1234567890.456,
    "latency_ms": 123.4
}
```

---

## State Management

### Global State Variables

The servo controller maintains these global state variables:

```python
# servo_controller.py module-level state

class ServoController:
    def __init__(self, pca9685):
        self.pca = pca9685
        
        # Servo position tracking (current PWM values)
        self.positions = [300, 300, 300, 135, 200, 200, 440, 380, 380]
        
        # Async locks (one per servo to prevent concurrent movements)
        self.locks = [asyncio.Lock() for _ in range(9)]
        
        # Emergency stop flag
        self.emergency_stop = False
        
        # Global speed factor (affects all movements)
        self.global_speed = 1.0
        
        # Active movement sequence (None if idle)
        self.active_sequence = None
```

### Concurrency Control

**Servo-Level Locking**:
- Each servo has an `asyncio.Lock` to ensure only one movement task can control it at a time
- Attempting to move a servo while it's already moving will wait for lock (or timeout)

**Emergency Stop**:
- Sets `emergency_stop = True` flag
- All active movement tasks check this flag periodically
- When detected, tasks raise `asyncio.CancelledError` and stop immediately
- After all tasks cancelled, all servos set to PWM=0 (disabled/floating)

**Sequence Execution**:
- Only one preset sequence can run at a time
- `active_sequence` tracks running sequence (or `None` if idle)
- New sequence requests rejected if `active_sequence is not None`

---

## Calibration Data

Servo calibration constants (from original config.ini V2 configuration):

```python
# IMPORTANT: These are V2 calibration values from config.ini [SERVO] section
# MOVEMENT_VERSION = V2
SERVO_CALIBRATION = {
    # Leg servos (channels 0-2)
    0: {  # Main Legs Lift (servo 0)
        "label": "Main Legs Lift",
        "min": 220,   # upHeight (upper limit)
        "max": 350,   # downHeight (lower limit - CAUTION)
        "neutral": 300  # neutralHeight
    },
    1: {  # Left Leg Rotation (servo 1) - LDX-227 servo
        "label": "Left Leg Rotation (Starboard)", 
        "min": 192,   # forwardStarboard (V2: -108 from neutral for LDX-227)
        "max": 408,   # backStarboard (V2: +108 from neutral for LDX-227)
        "neutral": 300  # neutralStarboard
    },
    2: {  # Right Leg Rotation (servo 2) - LDX-227 servo
        "label": "Right Leg Rotation (Port)",
        "min": 192,   # backPort (V2: -108 from neutral for LDX-227)
        "max": 408,   # forwardPort (V2: +108 from neutral for LDX-227)
        "neutral": 300  # neutralPort
    },
    # Right Arm servos (channels 3-5)
    3: {  # Right Shoulder - MG996R
        "label": "Right Main Arm (Shoulder)", 
        "min": 135,   # portMainMin
        "max": 440,   # portMainMax
        "neutral": 287  # midpoint (avoid strain)
    },
    4: {  # Right Elbow - MG90S
        "label": "Right Forearm (Elbow)", 
        "min": 200,   # portForarmMin
        "max": 380,   # portForarmMax
        "neutral": 290  # midpoint
    },
    5: {  # Right Wrist/Hand - MG90S
        "label": "Right Hand (Wrist)", 
        "min": 200,   # portHandMin
        "max": 280,   # portHandMax (note: 280 not 380!)
        "neutral": 240  # midpoint
    },
    # Left Arm servos (channels 6-8) - INVERTED min/max from right arm!
    6: {  # Left Shoulder - MG996R
        "label": "Left Main Arm (Shoulder)", 
        "min": 135,   # starMainMax (inverted)
        "max": 440,   # starMainMin (inverted)
        "neutral": 287  # midpoint
    },
    7: {  # Left Elbow - MG90S
        "label": "Left Forearm (Elbow)", 
        "min": 200,   # starForarmMax (inverted)
        "max": 380,   # starForarmMin (inverted)
        "neutral": 290  # midpoint
    },
    8: {  # Left Wrist/Hand - MG90S
        "label": "Left Hand (Wrist)", 
        "min": 280,   # starHandMax (inverted)
        "max": 380,   # starHandMin (inverted)
        "neutral": 330  # midpoint
    }
}
```

**Critical Notes**:
- **V2 Configuration**: These values come from `config.ini` with `MOVEMENT_VERSION = V2`
- **Channel 0 (Main Legs)**: Min=upHeight (220), Max=downHeight (350) - inverted because down is higher PWM value. **Using LDX-227 servo**.
- **Channels 1-2 (Leg Rotation)**: **Using LDX-227 servos** with ±108 from neutral (300). Range: 192-408 (wider than MG996R's ±80 range of 220-380).
- **Channels 3, 6 (Shoulder Joints)**: MG996R servos (high-torque for main arm joints)
- **Channels 4-5, 7-8 (Forearm/Hand)**: MG90S servos (lighter weight for extremities)
- **Channels 6-8 (Left Arm)**: **INVERTED** min/max from right arm (starMain/Forarm/Hand V2 variables have swapped values)
- **Channel 5 Hand**: Max is 280 (not 380 like channel 4) - prevent over-extension of hand mechanism
- **Neutral positions**: Use midpoint between min/max to avoid startup strain on servos
- May need fine-tuning for specific hardware installation

**Servo Type Summary**:
- **Legs (0-2)**: LDX-227 (high torque, wide rotation)
- **Shoulders (3, 6)**: MG996R (high torque)
- **Forearms/Hands (4-5, 7-8)**: MG90S (lightweight, precise)

---

## Data Flow Diagrams

### 1. Single Servo Movement Flow

```
User clicks slider → Browser sends POST /control
                     {"type": "single", "channel": 0, "target": 350}
                     ↓
Web Server receives request → Validates command
                     ↓
ServoController.move_servo_smooth(0, 350, speed=0.8)
                     ↓
Acquire lock[0] → Check emergency_stop flag
                     ↓
Loop: current position → target position
      - Set PWM via PCA9685
      - Update positions[0]
      - Sleep 20ms * (1 - speed)
      - Check emergency_stop each iteration
                     ↓
Release lock[0] → Return success
                     ↓
Send response to browser: {"success": true, "message": "..."}
```

### 2. Preset Sequence Flow

```
User clicks "Step Forward" button → Browser sends POST /control
                                    {"type": "preset", "preset": "step_forward"}
                                    ↓
Web Server validates preset exists → Check active_sequence is None
                                    ↓
Set active_sequence = "step_forward" → Execute sequence
                                    ↓
For each step in sequence:
    1. Create async task for each servo in step.targets
    2. await asyncio.gather(*tasks) → Parallel movement
    3. Wait step.delay_after seconds
    4. Check emergency_stop flag
                                    ↓
All steps complete → Disable servos → Set active_sequence = None
                                    ↓
Send response: {"success": true, "message": "Sequence completed"}
```

### 3. Emergency Stop Flow

```
User clicks red STOP button → Browser sends POST /emergency
                             ↓
Set emergency_stop = True → Wait 100ms for tasks to cancel
                             ↓
All movement tasks detect flag → Raise CancelledError → Exit
                             ↓
Set all servos PWM = 0 (disabled) → Set emergency_stop = False
                             ↓
Send response: {"success": true, "message": "Emergency stop activated"}
```

---

## Memory Considerations

### Estimated Memory Usage

| Component | Estimated Size | Notes |
|-----------|---------------|-------|
| ServoState (1 servo) | ~200 bytes | Dict with 8 fields |
| SystemStatus | ~2 KB | Includes 9 ServoStates + WiFi/hardware info |
| MovementSequence | ~500 bytes | Varies by number of steps |
| HTML Interface | ~8 KB | Embedded as string constant |
| PCA9685 Driver | ~1 KB | Minimal driver code |
| ServoController | ~2 KB | State + locks |
| Web Server | ~3 KB | Request/response handling |
| **Total** | **~20 KB** | Core application code + data |

### Memory Management Strategy

1. **Pre-allocate buffers**: Use fixed-size buffers for HTTP requests/responses
2. **Garbage collection**: Call `gc.collect()` after each web request and sequence completion
3. **Avoid dynamic allocation in loops**: Re-use position arrays, don't create new lists/dicts in servo movement loops
4. **Monitor free memory**: Log `gc.mem_free()` on status requests to detect leaks

### Memory Safety Limits

- **Minimum free RAM**: 150 KB (emergency stop should work even under memory pressure)
- **Warning threshold**: 200 KB free (log warning if below)
- **Comfortable operating**: 250-300 KB free (typical steady state)

If free memory drops below 150 KB:
1. Reject new movement commands
2. Return error: "Low memory, emergency stop recommended"
3. Log to serial console

---

## Phase 1 Complete

All data structures, state management, and entity relationships defined. Ready to proceed to contracts (HTTP API schemas).
