# TARS MCP Movement Server

MCP server providing movement and action control tools for TARS physical robot.

## Overview

This is a **pure MCP server** (no MQTT dependencies) that provides tools for the LLM to control the TARS robot's movements and actions. It returns structured data with `mqtt_publish` directives that the llm-worker publishes to MQTT topics consumed by the ESP32 firmware.

## Architecture

```
User: "Wave at me!"
  ↓
LLM Worker (decides to call tool)
  ↓
MCP Tool: wave(speed=0.8)
  ↓
Returns: {mqtt_publish: {topic: "movement/test", data: {command: "wave", speed: 0.8}}}
  ↓
LLM Worker publishes to MQTT
  ↓
ESP32 Firmware executes wave sequence
  ↓
Status updates: movement/status
```

## Tools Provided

### Movement Tools (Direct Robot Control)
- `move_forward(speed=0.8)` - Step forward one step
- `move_backward(speed=0.8)` - Step backward one step
- `turn_left(speed=0.8)` - Rotate left
- `turn_right(speed=0.8)` - Rotate right
- `stop_movement()` - Emergency stop (clears queue)

### Action Tools (Expressive/Non-Movement)
- `wave(speed=0.7)` - Wave gesture
- `laugh(speed=0.9)` - Bouncing motion
- `bow(speed=0.5)` - Bow forward
- `point(speed=0.7)` - Pointing gesture
- `pose(speed=0.6)` - Strike a pose
- `celebrate(speed=0.8)` - Victory celebration
- `balance(speed=0.6)` - Balancing animation
- `swing_legs(speed=0.6)` - Pendulum leg motion

## MQTT Contract

All tools return `mqtt_publish` directives that llm-worker publishes to:

**Topic**: `movement/test`

**Payload**:
```json
{
  "command": "wave",
  "speed": 0.8,
  "request_id": "llm-req-123"  // Optional correlation ID
}
```

**Stop Command**:

**Topic**: `movement/stop`

**Payload**: `{}`

## Installation

Automatically discovered and installed by mcp-bridge during Docker build:

```bash
cd ops
docker compose build llm --no-cache
```

## Development

```bash
cd packages/tars-mcp-movement

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Format
black tars_mcp_movement/
ruff check tars_mcp_movement/

# Type check
mypy tars_mcp_movement/
```

## Testing Manually

```bash
# Run the MCP server
python -m tars_mcp_movement

# In another terminal, use MCP inspector
npx @modelcontextprotocol/inspector python -m tars_mcp_movement
```

## Available Movement Sequences

Based on ESP32 firmware (`firmware/esp32/movements/sequences.py`):

**Basic Movements (5)**:
- `reset` - Return to neutral position
- `step_forward` - Walk forward one step
- `step_backward` - Walk backward one step
- `turn_left` - Rotate left
- `turn_right` - Rotate right

**Expressive Movements (10)**:
- `wave` - Wave with right arm
- `laugh` - Bouncing motion
- `swing_legs` - Pendulum leg motion
- `pezz` - Candy dispenser motion (10s hold)
- `now` - Pointing gesture
- `balance` - Balancing animation
- `mic_drop` - Dramatic mic drop
- `monster` - Defensive/threatening pose
- `pose` - Strike a pose
- `bow` - Bow forward

## Usage Example

When user says: **"Can you wave at me and then turn left?"**

LLM will call:
1. `wave(speed=0.8)`
2. `turn_left(speed=0.8)`

Each tool call returns `mqtt_publish` directive → llm-worker publishes → ESP32 executes → status updates flow back.

## Contract with ESP32 Firmware

**Command Topic**: `movement/test`

**Command Schema**:
```python
{
  "command": str,     # Movement name (wave, bow, etc.)
  "speed": float,     # 0.1-1.0 (optional, default 0.8)
  "request_id": str   # Optional correlation ID
}
```

**Status Topic**: `movement/status`

**Status Events**:
- `command_queued` - Command added to queue
- `command_started` - Execution started
- `command_completed` - Execution finished
- `command_error` - Validation/execution error
- `stopped` - Emergency stop triggered

**Stop Topic**: `movement/stop` (payload: `{}`)

## Design Principles

1. **Pure MCP Server** - No MQTT dependencies, just tool definitions
2. **Typed Returns** - All tools return structured dicts with `mqtt_publish` field
3. **LLM Decides Actions** - LLM chooses when to use expressive actions based on context
4. **Speed Control** - All movements accept speed parameter (0.1-1.0)
5. **Error Handling** - Validates speed ranges and command formats
6. **Correlation IDs** - Optional request_id for tracking multi-step operations

## Integration with llm-worker

The llm-worker's `ToolExecutor` class automatically:
1. Parses tool results for `mqtt_publish` field
2. Wraps in `tars.contracts.envelope.Envelope`
3. Publishes to MQTT with QoS 1
4. Logs publication events

See: `apps/llm-worker/llm_worker/handlers/tools.py`

## Future Enhancements

- [ ] Add duration parameter for longer actions
- [ ] Support for compound movements (sequences of commands)
- [ ] Real-time status callbacks via MQTT subscription
- [ ] Movement queue inspection/cancellation tools
- [ ] Servo-level control tools (advanced users)
- [ ] Safety boundaries and collision detection integration
