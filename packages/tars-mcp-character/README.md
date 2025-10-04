# TARS Character Management MCP Server

MCP server for managing TARS personality traits dynamically.

## Tools

- **adjust_personality_trait(trait_name, new_value)** - Modify a personality trait (0-100 scale)
- **get_current_traits()** - Query current trait values
- **reset_all_traits()** - Reset all traits to defaults from character.toml

## Usage

### As stdio subprocess (in mcp-bridge):
```yaml
# ops/mcp/mcp.server.yml
servers:
  - name: tars-character
    transport: stdio
    command: "python"
    args: ["-m", "tars_mcp_character"]
```

### Direct execution (for testing):
```bash
python -m tars_mcp_character
```

## Development

```bash
cd packages/tars-mcp-character

# Install in editable mode
pip install -e .

# Install with dev dependencies (includes pytest)
pip install -e ".[dev]"

# Test locally
python -m tars_mcp_character
```

## Testing

```bash
# Run all unit tests
make test

# Run tests with coverage
make test-cov

# Run integration tests (requires MQTT broker)
make test-integration

# Run specific test file
pytest tests/test_tools.py -v

# Run specific test function
pytest tests/test_tools.py::TestAdjustPersonalityTrait::test_adjust_trait_valid_value -v
```

**Test Categories:**

- **Unit Tests** (`tests/test_tools.py`): Fast, isolated tests with mocked dependencies
- **Integration Tests** (`tests/test_integration.py`): Full MCP protocol tests (requires MQTT broker)

**Running Integration Tests:**

Integration tests require a running MQTT broker:

```bash
cd /path/to/py-tars/ops
docker compose up -d mqtt

# Then run integration tests
cd /path/to/py-tars/packages/tars-mcp-character
make test-integration
```

## Dependencies

- `mcp[cli]>=1.2.0` - MCP SDK with FastMCP
- `tars-core` - TARS contracts and MQTT utilities
- `asyncio-mqtt` - MQTT client
- `orjson` - Fast JSON serialization
