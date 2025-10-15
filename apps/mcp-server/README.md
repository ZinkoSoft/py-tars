# TARS MCP Server

**Model Context Protocol (MCP) server for TARS character and personality management.**

## Overview

This MCP server provides tools that allow TARS to dynamically adjust its own personality traits through Claude Desktop or other MCP clients. Changes are published to the `memory-worker` via MQTT, enabling real-time personality updates.

## Features

### MCP Tools

#### 1. `adjust_personality_trait`
Adjust a TARS personality trait value in real-time.

**Parameters:**
- `trait_name` (str): Name of the trait to adjust
- `new_value` (int): New value for the trait (0-100 scale)

**Valid Traits:**
- `honesty`, `humor`, `empathy`, `curiosity`, `confidence`, `formality`
- `sarcasm`, `adaptability`, `discipline`, `imagination`, `emotional_stability`
- `pragmatism`, `optimism`, `resourcefulness`, `cheerfulness`, `engagement`
- `respectfulness`, `verbosity`

**Example:**
```json
{
  "trait_name": "humor",
  "new_value": 75
}
```

**Response:**
```json
{
  "success": true,
  "trait": "humor",
  "new_value": 75,
  "message": "Trait 'humor' adjusted to 75%"
}
```

#### 2. `get_current_traits`
Query TARS's current personality trait values.

**Parameters:** None

**Response:**
```json
{
  "success": true,
  "message": "Trait query sent. Check character/current topic for latest values.",
  "note": "Actual values are maintained by memory-worker"
}
```

#### 3. `reset_all_traits`
Reset all personality traits to default values from `character.toml`.

**Parameters:** None

**Response:**
```json
{
  "success": true,
  "message": "All traits reset to default values from character.toml"
}
```

---

## MQTT Integration

### Published Topics

#### `character/update` (QoS 1)
Publishes trait updates and reset requests.

**Payload (Trait Update):**
```json
{
  "event_type": "character.update",
  "data": {
    "trait": "humor",
    "value": 75
  }
}
```

**Payload (Trait Reset):**
```json
{
  "event_type": "character.update",
  "data": {}
}
```

#### `character/get` (QoS 1)
Queries current character state from memory-worker.

**Payload:**
```json
{
  "event_type": "character.get",
  "data": {
    "section": "traits"
  }
}
```

### Subscribed Topics

This server does not subscribe to any topics (request-only).

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MQTT_URL` | `mqtt://tars:pass@mqtt:1883` | MQTT broker connection string |
| `TOPIC_CHARACTER_UPDATE` | `character/update` | Topic for trait updates |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Example `.env`
```bash
MQTT_URL=mqtt://tars:pass@localhost:1883
TOPIC_CHARACTER_UPDATE=character/update
LOG_LEVEL=INFO
```

---

## Installation

### From Source
```bash
cd apps/mcp-server
pip install -e ".[dev]"
```

### Development Setup
```bash
# Install dependencies
pip install -e ".[dev]"

# Run checks
make check
```

---

## Usage

### Stdio Transport (Claude Desktop)
```bash
tars-mcp-server stdio
```

### HTTP Transport
```bash
tars-mcp-server http --port 8080
```

### SSE Transport
```bash
tars-mcp-server sse
```

---

## Development

### Commands

```bash
# Format code
make fmt

# Lint and type check
make lint

# Run tests
make test

# Run all checks (CI gate)
make check

# Clean build artifacts
make clean

# Run server locally
make run
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=tars_mcp_server --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_tools.py
```

---

## Integration with Memory-Worker

The MCP server communicates with the `memory-worker` service via MQTT:

1. **Tool Call** → MCP Server receives tool request
2. **Validation** → Server validates trait name and value
3. **Envelope** → Wraps payload in `Envelope` with event type
4. **Publish** → Publishes to `character/update` (QoS 1)
5. **Memory-Worker** → Processes update and modifies character state
6. **Broadcast** → Memory-worker publishes to `system/character/current` (retained)

---

## Architecture

### FastMCP Framework

Uses [FastMCP](https://github.com/jlowin/fastmcp) for MCP server implementation:
- Automatic stdio/HTTP/SSE transport support
- Built-in CLI with `app.run()`
- Decorator-based tool registration (`@app.tool()`)

### Contracts

Uses typed contracts from `tars-core`:
- `CharacterTraitUpdate` - Trait change payload
- `CharacterResetTraits` - Reset request
- `CharacterGetRequest` - Query request
- `Envelope` - MQTT envelope wrapper

---

## Error Handling

All tools return structured error responses:

```json
{
  "success": false,
  "error": "Error message here"
}
```

**Common Errors:**
- Invalid trait value (not 0-100)
- Unknown trait name
- MQTT connection failure

---

## Dependencies

### Runtime
- `mcp[cli]>=1.2.0` - MCP SDK with FastMCP
- `pydantic>=2.7` - Data validation
- `orjson>=3.9` - Fast JSON serialization
- `python-dotenv>=1.0` - Environment variable management
- `asyncio-mqtt>=0.16.2` - Async MQTT client
- `tars-core>=0.1.0` - Shared contracts

### Development
- `pytest>=8.0` - Testing framework
- `pytest-asyncio>=0.23` - Async test support
- `pytest-cov>=4.1` - Coverage reporting
- `pytest-mock>=3.12` - Mocking utilities
- `ruff>=0.5` - Fast linter
- `black>=24.0` - Code formatter
- `mypy>=1.10` - Type checker
- `types-orjson>=3.9` - Type stubs

---

## License

MIT
