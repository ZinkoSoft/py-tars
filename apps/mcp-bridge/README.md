# MCP Bridge

The **MCP Bridge** service enables TARS to use external tools through the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). It acts as a bridge between MCP-compatible tool servers and the LLM worker, allowing TARS to perform actions like reading/writing files, making API calls, and executing custom tools.

## 🏗️ Architecture

```
[MCP Servers] ←→ MCP Bridge ←→ MQTT ←→ LLM Worker
     ↓              ↓              ↓           ↓
  Filesystem      Tool Registry   Tool Calls   Tool Results
  APIs           → MQTT          → MQTT       → MQTT
  Databases       Publishing      Execution    Integration
```

The MCP Bridge:
1. **Discovers Tools** - Connects to configured MCP servers and enumerates available tools
2. **Publishes Registry** - Sends tool specifications to `llm/tools/registry` topic
3. **Executes Calls** - Receives tool execution requests from `llm/tool.call.request/#`
4. **Returns Results** - Publishes results to `llm/tool.call.result`

## 📋 Configuration

### MCP Server Configuration

Configure MCP servers in `ops/mcp/mcp.server.yml`:

```yaml
servers:
  - name: filesystem
    transport: stdio
    command: "mcp-filesystem"
    args: ["--root", "/home/user/work"]
    tools_allowlist: ["read_file", "write_file", "list_dir"]

  - name: weather
    transport: stdio
    command: "mcp-weather-api"
    env:
      API_KEY: "your-weather-api-key"
    tools_allowlist: ["get_weather", "get_forecast"]

timeouts:
  connect_ms: 5000
  tool_call_ms: 30000
```

### Environment Variables

```bash
# MQTT connection
MQTT_HOST=127.0.0.1
MQTT_PORT=1883
MQTT_USER=tars
MQTT_PASS=your_password

# MCP configuration
MCP_SERVERS_YAML=/config/mcp.server.yml

# Logging
LOG_LEVEL=INFO
```

## 🔌 MQTT Topics

### Published Topics
- **`llm/tools/registry`** - Tool registry (retained)
- **`llm/tool.call.result`** - Tool execution results
- **`system/health/mcp-bridge`** - Health status (retained)

### Subscribed Topics
- **`llm/tool.call.request/#`** - Tool execution requests

## 🛠️ Adding MCP Servers

### 1. Install MCP Server

```bash
# Example: Install filesystem MCP server
npm install -g @modelcontextprotocol/server-filesystem

# Or build from source
git clone https://github.com/modelcontextprotocol/server-filesystem
cd server-filesystem && npm install && npm run build
```

### 2. Configure Server

Add to `ops/mcp/mcp.server.yml`:

```yaml
servers:
  - name: my-custom-server
    transport: stdio
    command: "my-mcp-server"
    args: ["--config", "/path/to/config.json"]
    env:
      API_KEY: "your-api-key"
    tools_allowlist: ["tool1", "tool2"]  # Optional: restrict tools
```

### 3. Restart MCP Bridge

```bash
docker compose restart mcp-bridge
```

## 📝 Tool Specification Format

Tools are converted to OpenAI-compatible function specifications:

```json
{
  "type": "function",
  "function": {
    "name": "mcp:filesystem:read_file",
    "description": "Read contents of a file",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string",
          "description": "Path to the file to read"
        }
      },
      "required": ["path"]
    }
  }
}
```

## 🧪 Testing

### Monitor Tool Registry

```bash
# Watch for tool registry updates
mosquitto_sub -h 127.0.0.1 -p 1883 -u tars -P change_me -t 'llm/tools/registry' -v
```

### Monitor Tool Calls

```bash
# Watch tool execution
mosquitto_sub -h 127.0.0.1 -p 1883 -u tars -P change_me -t 'llm/tool.call.+' -v
```

### Test Tool Execution

```bash
# Manual tool call (replace with actual tool name and args)
mosquitto_pub -h 127.0.0.1 -p 1883 -u tars -P change_me -t 'llm/tool.call.request/test-123' \
  -m '{
    "call_id": "test-123",
    "name": "mcp:filesystem:read_file",
    "arguments": {"path": "/etc/hostname"}
  }'
```

### Health Check

```bash
# Check MCP bridge health
mosquitto_sub -h 127.0.0.1 -p 1883 -u tars -P change_me -t 'system/health/mcp-bridge' -v
```

## 🔧 Development

### Local Development

```bash
# Install dependencies
pip install -e .

# Run locally
export MQTT_HOST=127.0.0.1
export MCP_SERVERS_YAML=/path/to/mcp.server.yml
python -m mcp_bridge.main
```

### Docker Development

```bash
# Build and run
docker compose -f ops/compose.yml build mcp-bridge
docker compose -f ops/compose.yml up mcp-bridge
```

### Adding New Transports

Currently supports `stdio` transport. To add new transports:

1. Add transport handler in `mcp_bridge/transports/`
2. Update server configuration schema
3. Register transport in main connection logic

## 🚨 Troubleshooting

### Common Issues

**MCP Server Won't Start**
- Check command path and arguments
- Verify environment variables
- Check server logs: `docker compose logs mcp-bridge`

**Tools Not Appearing in Registry**
- Verify `tools_allowlist` configuration
- Check MCP server tool enumeration
- Ensure server starts successfully

**Tool Calls Failing**
- Check tool arguments match schema
- Verify MCP server is running
- Check timeouts in configuration

**MQTT Connection Issues**
- Verify MQTT credentials
- Check network connectivity
- Ensure MQTT broker is running

### Debug Logging

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
docker compose restart mcp-bridge
```

## 📚 Examples

### Filesystem Tools

```yaml
servers:
  - name: filesystem
    transport: stdio
    command: "mcp-filesystem"
    args: ["--root", "/workspace"]
    tools_allowlist: ["read_file", "write_file", "list_dir"]
```

### API Tools

```yaml
servers:
  - name: github
    transport: stdio
    command: "mcp-github"
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"
    tools_allowlist: ["search_issues", "create_issue"]
```

### Custom Tools

```yaml
servers:
  - name: calculator
    transport: stdio
    command: "python"
    args: ["/path/to/calculator_server.py"]
    tools_allowlist: ["calculate", "solve_equation"]
```

## 🔗 Related Components

- **LLM Worker** - Consumes tool registry and makes tool calls
- **TARS Core** - Shared contracts and MQTT utilities
- **MCP Servers** - External tool providers (filesystem, APIs, etc.)

## 📄 License

This service is part of the TARS project. See main project license for details.