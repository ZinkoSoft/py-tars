# tars-mcp-movement Quick Start

## ✅ Installation Complete

The `tars-mcp-movement` package has been successfully created and installed in your workspace!

**Status**:
- ✅ Package created at `packages/tars-mcp-movement/`
- ✅ Installed in venv with dev dependencies
- ✅ All 22 tests passing
- ✅ MCP server runs successfully
- ✅ Ready for Docker integration

## What You Can Do Now

### 1. Test Locally

```bash
# Activate venv
source /home/james/git/py-tars/.venv/bin/activate

# Run tests
cd packages/tars-mcp-movement
pytest tests/ -v

# Run the MCP server
python -m tars_mcp_movement
```

### 2. Deploy to Docker

```bash
cd ops

# Rebuild llm-worker (auto-discovers tars-mcp-movement)
docker compose build llm --no-cache

# Check that it was discovered
docker compose build llm --no-cache 2>&1 | grep "tars-mcp-movement"

# Start the stack
docker compose up -d

# Verify tools are loaded
docker compose logs llm | grep "tools from"
# Expected: "Loaded X tools from 2 servers"
```

### 3. Test End-to-End

**Terminal 1** - Monitor movement commands:
```bash
mosquitto_sub -h localhost -t 'movement/test' -v
```

**Terminal 2** - Monitor status updates:
```bash
mosquitto_sub -h localhost -t 'movement/status' -v
```

**Terminal 3** - Send LLM request:
```bash
# Simple wave
mosquitto_pub -h localhost -t 'llm/request' -m '{
  "id": "test-001",
  "text": "Wave at me",
  "stream": false
}' -q 1

# Movement command
mosquitto_pub -h localhost -t 'llm/request' -m '{
  "id": "test-002", 
  "text": "Move forward and then turn left",
  "stream": false
}' -q 1

# Contextual action (LLM decides)
mosquitto_pub -h localhost -t 'llm/request' -m '{
  "id": "test-003",
  "text": "Hi TARS! How are you doing today?",
  "stream": false
}' -q 1
```

**Expected Flow**:
1. LLM receives request
2. Calls appropriate MCP tools
3. Tools return `mqtt_publish` directives
4. llm-worker publishes to `movement/test`
5. ESP32 executes movement
6. Status updates appear on `movement/status`

## Available Tools

### Movement (5 tools)
- `move_forward(speed=0.8)` - Step forward
- `move_backward(speed=0.8)` - Step backward
- `turn_left(speed=0.8)` - Rotate left
- `turn_right(speed=0.8)` - Rotate right
- `stop_movement()` - Emergency stop

### Actions (8 tools)
- `wave(speed=0.7)` - Wave gesture
- `laugh(speed=0.9)` - Bouncing motion
- `bow(speed=0.5)` - Bow forward
- `point(speed=0.7)` - Pointing gesture
- `pose(speed=0.6)` - Strike a pose
- `celebrate(speed=0.8)` - Victory motion
- `swing_legs(speed=0.6)` - Playful leg swing
- `reset_position(speed=0.8)` - Return to neutral

## File Structure

```
packages/tars-mcp-movement/
├── README.md                   # Full documentation
├── pyproject.toml              # Package config
├── Makefile                    # Dev commands
├── pytest.ini                  # Test config
├── tars_mcp_movement/
│   ├── __init__.py            # Package init
│   ├── __main__.py            # CLI entry
│   └── server.py              # 13 MCP tools
└── tests/
    ├── conftest.py            # Test fixtures
    ├── test_tools.py          # Tool tests (19 tests)
    └── test_integration.py    # Integration tests (3 tests)
```

## Development Commands

```bash
cd packages/tars-mcp-movement

# Run tests
make test

# Format code
make fmt

# Lint code
make lint

# Run all checks (fmt + lint + test)
make check
```

## Integration Points

### Updated Files

1. **`apps/llm-worker/llm_worker/mcp_client.py`**
   - Added `"tars-movement"` to command map
   - Maps to `python -m tars_mcp_movement`

2. **Auto-discovered by mcp-bridge**
   - Follows `packages/tars-mcp-*` naming convention
   - Will be installed during Docker build
   - Added to `/app/config/mcp-servers.json`

3. **Compatible with ESP32 firmware**
   - Uses existing `movement/test` topic
   - Maps to existing movement sequences
   - No firmware changes needed

## Documentation

- **Full Integration Guide**: `/home/james/git/py-tars/docs/MCP_MOVEMENT_INTEGRATION.md`
- **Package README**: `packages/tars-mcp-movement/README.md`
- **ESP32 Movements**: `firmware/esp32/movements/sequences.py`
- **MCP Bridge Docs**: `apps/mcp-bridge/README.md`

## Next Steps

1. ✅ **Done**: Package created and tested
2. 📦 **Next**: Deploy to Docker (`docker compose build llm`)
3. 🤖 **Then**: Test with ESP32 hardware
4. 🎯 **Finally**: Test natural language interactions

## Example Interactions

**User**: "Wave at me"
- LLM calls: `wave(speed=0.7)`
- ESP32 executes wave sequence
- TARS waves with right arm

**User**: "Move forward and turn left"
- LLM calls: `move_forward(speed=0.8)`, `turn_left(speed=0.8)`
- ESP32 executes step forward, then rotate left
- TARS moves as requested

**User**: "Hi TARS!"
- LLM responds: "Hello! *waves*"
- LLM calls: `wave(speed=0.7)` (contextual decision)
- TARS waves while greeting

**User**: "You're awesome!"
- LLM responds: "Thank you! *strikes a pose*"
- LLM calls: `pose(speed=0.6)` (contextual decision)
- TARS poses with confidence

## Troubleshooting

**Tests fail**:
```bash
# Check pytest is using venv
which pytest
# Should show: /home/james/git/py-tars/.venv/bin/pytest

# Or use venv explicitly
/home/james/git/py-tars/.venv/bin/pytest tests/ -v
```

**MCP server won't start**:
```bash
# Check dependencies
/home/james/git/py-tars/.venv/bin/pip list | grep mcp

# Try running directly
/home/james/git/py-tars/.venv/bin/python -m tars_mcp_movement
```

**Docker build issues**:
```bash
# Clean build
docker compose build llm --no-cache --pull

# Check if package exists
ls -la packages/tars-mcp-movement/

# Verify pyproject.toml
cat packages/tars-mcp-movement/pyproject.toml
```

## Success Criteria

✅ All 22 tests pass  
✅ MCP server starts without errors  
✅ Docker build discovers package  
✅ llm-worker loads movement tools  
✅ MQTT messages flow correctly  
✅ ESP32 executes movements  

---

**Status**: Ready for deployment! 🚀

The LLM can now control TARS movements and decide contextually when to use expressive actions.
