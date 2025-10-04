# TARS MCP Server Extensions

This directory is for **user-created MCP servers** that extend TARS functionality beyond the built-in capabilities.

## What Goes Here?

- ✅ Weather APIs
- ✅ Calendar integrations
- ✅ Home automation tools
- ✅ Custom business logic
- ✅ Third-party service integrations
- ❌ Core TARS functionality (those go in `packages/tars-mcp-*/`)

## Creating a Custom MCP Server

### 1. Create Directory Structure

```bash
cd extensions/mcp-servers
mkdir my-server
cd my-server
```

### 2. Create `pyproject.toml`

```toml
[project]
name = "my-mcp-server"
version = "0.1.0"
description = "My custom MCP server for TARS"
dependencies = [
    "mcp[cli]>=1.2.0",
]

[project.scripts]
my-mcp-server = "my_mcp_server.__main__:main"
```

### 3. Create Server Code

`my_mcp_server/__init__.py`:
```python
"""My custom MCP server."""
```

`my_mcp_server/__main__.py`:
```python
"""Entry point."""
from .server import app

def main():
    app.run()

if __name__ == "__main__":
    main()
```

`my_mcp_server/server.py`:
```python
"""Server implementation."""
from mcp.server.fastmcp import FastMCP

app = FastMCP("My Server")

@app.tool()
def my_tool(arg: str) -> str:
    """My custom tool."""
    return f"Processed: {arg}"
```

### 4. Test Locally

```bash
pip install -e .
python -m my_mcp_server
```

### 5. Add to Configuration

Edit `ops/mcp/mcp.server.yml`:

```yaml
servers:
  # ... existing servers ...
  
  - name: my-server
    transport: stdio
    command: "python"
    args: ["-m", "my_mcp_server"]
    env:
      MY_API_KEY: "${MY_API_KEY}"  # Optional environment variables
```

### 6. Rebuild mcp-bridge

```bash
cd ops
docker compose build mcp-bridge
docker compose up -d mcp-bridge
```

## Example: Weather MCP Server

See `packages/tars-mcp-character/` for a complete working example of an MCP server integrated with TARS.

For a simpler standalone example:

<details>
<summary>Click to expand weather server example</summary>

`extensions/mcp-servers/weather/pyproject.toml`:
```toml
[project]
name = "weather-mcp"
version = "0.1.0"
dependencies = ["mcp[cli]>=1.2.0", "requests"]

[project.scripts]
weather-mcp = "weather_mcp.__main__:main"
```

`extensions/mcp-servers/weather/weather_mcp/server.py`:
```python
from mcp.server.fastmcp import FastMCP
import requests

app = FastMCP("Weather Service")

@app.tool()
def get_weather(city: str) -> dict:
    """Get current weather for a city."""
    # Call weather API
    response = requests.get(f"https://api.weather.com/v1/current?city={city}")
    return response.json()
```

Configuration:
```yaml
- name: weather
  transport: stdio
  command: "python"
  args: ["-m", "weather_mcp"]
  env:
    WEATHER_API_KEY: "${WEATHER_API_KEY}"
```

</details>

## Lifecycle Management

Your servers will:
- **Spawn on-demand** when TARS needs to call a tool
- **Idle timeout** after 5 minutes of inactivity (configurable)
- **Auto-restart** if they crash

See `plan/mcp-server-setup.md` for details on lifecycle management.

## Tips

1. **Keep it simple** - One server per service/API
2. **Use environment variables** for API keys and configuration
3. **Add error handling** - MCP servers should handle failures gracefully
4. **Test independently** - Run `python -m your_server` before integrating
5. **Document your tools** - Clear docstrings help TARS use them correctly

## Git Ignore

This directory is gitignored (except this README). Your custom servers won't be committed to the TARS repository, keeping your customizations separate.

## Sharing Your Server

If you create a useful MCP server, consider:
1. Publishing it as a separate git repository
2. Sharing on GitHub with topic `tars-mcp-server`
3. Submitting a PR to add it to the TARS community extensions list

## Troubleshooting

**Server not showing up in tool registry?**
- Check `ops/mcp/mcp.server.yml` syntax
- Ensure server is installed: `pip list | grep my-server`
- Check mcp-bridge logs: `docker logs tars-mcp-bridge`

**Server crashes on startup?**
- Run directly: `python -m my_mcp_server`
- Check for import errors
- Verify dependencies are installed

**Tools not being called?**
- Check tool names match between server and mcp.server.yml allowlist
- Verify tool docstrings are clear (LLM uses them to decide when to call)
- Check llm-worker logs for tool call attempts

## Resources

- [MCP Python SDK Documentation](https://github.com/modelcontextprotocol/python-sdk)
- [FastMCP Examples](https://github.com/modelcontextprotocol/python-sdk/tree/main/examples)
- [TARS MCP Architecture](../../plan/mcp-server-setup.md)
