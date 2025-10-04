# TARS MCP Server Extensions

This directory is for **local user-created MCP servers** that extend TARS functionality beyond the built-in capabilities.

> ⚠️ **Local Extensions Only**: This directory is `.gitignore`d - your custom servers stay on your machine and won't be committed to the repository. This keeps your personal integrations, API keys, and custom logic private.

## 🚀 How It Works (Automatic Discovery)

When you rebuild the `mcp-bridge` Docker image:

1. **mcp-bridge** scans `extensions/mcp-servers/` at **build time**
2. Discovers all MCP server packages (any folder with `pyproject.toml` + `mcp` dependency)
3. Installs them via `pip install -e .`
4. Generates `mcp-servers.json` configuration
5. **llm-worker** receives this config and automatically discovers your tools
6. Your tools become available to TARS with **zero manual registration**

**You just create a package here → rebuild → TARS knows about it!**

## What Can You Build?

- ✅ Weather APIs (OpenWeather, Weather.com, etc.)
- ✅ Calendar integrations (Google Calendar, Outlook)
- ✅ Home automation (Home Assistant, Philips Hue)
- ✅ File operations (upload, search, organize)
- ✅ Web search and scraping
- ✅ Database queries
- ✅ Custom business logic
- ✅ Third-party service integrations
- ❌ Core TARS functionality (those go in `packages/tars-mcp-*/` for project-wide features)

## 📦 Creating Your First MCP Server

### Prerequisites

- Basic Python knowledge
- Understanding of the functionality you want to add
- API keys for any external services (optional)

### Step 1: Create Directory Structure

```bash
cd extensions/mcp-servers
mkdir my-server
cd my-server
```

**Important**: Each MCP server must be a **proper Python package** with:
- A folder matching your package name (with underscores: `my_mcp_server/`)
- A `pyproject.toml` file at the root
- An `__init__.py` file in the package folder
- A `__main__.py` for the entry point

### Step 2: Create `pyproject.toml`

```toml
[project]
name = "my-mcp-server"
version = "0.1.0"
description = "My custom MCP server for TARS"
dependencies = [
    "mcp[cli]>=1.2.0",
    # Add other dependencies here (requests, etc.)
]

[project.scripts]
my-mcp-server = "my_mcp_server.__main__:main"
```

**Key Requirements**:
- **Must** have `mcp[cli]>=1.2.0` as a dependency (this triggers auto-discovery)
- Package name uses hyphens (`my-mcp-server`)
- Module name uses underscores (`my_mcp_server`)
- Entry point script must be defined

### Step 3: Create Server Code

`my_mcp_server/__init__.py`:
```python
"""My custom MCP server."""
__version__ = "0.1.0"
```

`my_mcp_server/__main__.py`:
```python
"""Entry point for stdio transport."""
from .server import app

def main():
    """Run server via stdio (used by mcp-bridge)."""
    app.run()

if __name__ == "__main__":
    main()
```

`my_mcp_server/server.py`:
```python
"""Server implementation with tools."""
from mcp.server.fastmcp import FastMCP

app = FastMCP("My Server")

@app.tool()
def my_tool(arg: str) -> str:
    """My custom tool.
    
    This docstring is important! The LLM uses it to understand
    when and how to call your tool.
    
    Args:
        arg: A string to process
        
    Returns:
        The processed result
    """
    return f"Processed: {arg}"

@app.tool()
def another_tool(count: int) -> dict:
    """Demonstrate returning structured data.
    
    Args:
        count: Number of items to generate
        
    Returns:
        A dictionary with results
    """
    return {
        "items": [f"item_{i}" for i in range(count)],
        "total": count
    }
```

**Tool Guidelines**:
- Write **clear docstrings** - the LLM reads them to decide when to call your tool
- Use **type hints** - helps with validation and auto-generated schemas
- Return **simple types** - strings, dicts, lists (avoid complex objects)
- Handle **errors gracefully** - return error messages as strings, don't crash

### Step 4: Test Locally (Optional but Recommended)

Before integrating with TARS, test your server independently:

```bash
# From extensions/mcp-servers/my-server/
pip install -e .

# Run the server (it will start in stdio mode)
python -m my_mcp_server

# In another terminal, you can test with MCP inspector:
npx @modelcontextprotocol/inspector python -m my_mcp_server
```

### Step 5: Add stdio Configuration

**Automatic Discovery**: mcp-bridge will automatically find your package, but you need to configure **how to run it** via stdio.

Edit `ops/mcp/mcp.server.yml`:

```yaml
servers:
  # ... existing servers (tars-character, etc.) ...
  
  - name: my-server               # Unique name for this server
    transport: stdio               # Always use stdio for local servers
    command: "python"              # Command to run
    args: ["-m", "my_mcp_server"]  # Module to execute
    env:                           # Optional environment variables
      MY_API_KEY: "${MY_API_KEY}"
```

**Environment Variables**:
- Reference from your `.env` file using `${VAR_NAME}` syntax
- Secrets stay in `.env`, not committed to git
- Server receives them at runtime

### Step 6: Rebuild and Deploy

```bash
cd ops

# Rebuild mcp-bridge (this triggers discovery and installation)
docker compose build mcp-bridge

# Rebuild llm-worker (receives the generated config)
docker compose build llm-worker

# Restart services
docker compose up -d mcp-bridge llm-worker
```

**What happens during build**:
1. `mcp-bridge` Dockerfile copies `extensions/mcp-servers/` → `/tmp/workspace/extensions/`
2. Runs discovery: finds your `my-server` package (has `mcp` dependency)
3. Installs it: `pip install -e /tmp/workspace/extensions/mcp-servers/my-server`
4. Generates config: Creates `mcp-servers.json` with server metadata + tool schemas
5. Copies config → `llm-worker` image at `/app/config/mcp-servers.json`
6. **llm-worker** reads this config at runtime and knows about your tools!

### Step 7: Verify It Works

```bash
# Check mcp-bridge found your server
docker logs tars-mcp-bridge 2>&1 | grep "my-server"

# Should see:
# - "Discovered server: my-server"
# - "Installed: my-mcp-server"
# - "Tools discovered: my_tool, another_tool"

# Test by asking TARS to use your tool
# (via voice, UI, or publish to llm/request topic)
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

## 🔄 How MCP Servers Run (stdio Transport)

Your MCP servers run as **stdio subprocesses** managed by **mcp-bridge**:

1. **Build Time** (when you run `docker compose build`):
   - mcp-bridge discovers and installs your packages
   - Generates tool schemas and configuration
   - Configuration baked into llm-worker image

2. **Runtime** (when containers are running):
   - mcp-bridge starts **one stdio subprocess per server** (e.g., `python -m my_mcp_server`)
   - Each server communicates via **stdin/stdout** (JSON-RPC over stdio)
   - When LLM wants to call a tool:
     - llm-worker publishes `llm/tools/call` to MQTT
     - mcp-bridge receives request and calls your server via stdio
     - Your tool executes and returns result
     - mcp-bridge publishes result back to llm-worker via MQTT
   - Subprocesses stay alive during mcp-bridge lifetime
   - If a server crashes, mcp-bridge handles the error gracefully

**Key Points**:
- No HTTP servers needed
- No ports to expose
- Simple process isolation
- Automatic cleanup on shutdown

## 💡 Best Practices

1. **Keep it simple** - One server per service/API domain
2. **Use environment variables** for API keys and secrets (via `.env`)
3. **Add error handling** - Return error strings instead of crashing
4. **Test independently** - Run `python -m your_server` before Docker integration
5. **Document your tools** - Clear docstrings help the LLM understand when to call them
6. **Type everything** - Use type hints for automatic schema generation
7. **Keep tools focused** - Small, single-purpose tools work better than large multi-function ones
8. **Return simple data** - Strings, dicts, lists - avoid complex objects or binary data

## 🔒 Privacy & Git

**This directory is `.gitignore`d** - your custom servers are **local only**:

✅ **Stays Private**:
- Your custom code and integrations
- API keys in `.env`
- Personal automation logic
- Business-specific tools

❌ **Not Committed**:
- No risk of accidentally committing secrets
- Your customizations don't affect upstream TARS repo
- Each developer can have their own local extensions

**Exception**: Only this `README.md` is tracked in git for documentation.

## 🌐 Sharing Your Server (Optional)

Created something useful? You can share it:

1. **Extract to separate repo**:
   ```bash
   # Move your extension to a standalone repo
   mkdir ~/my-mcp-servers
   cp -r extensions/mcp-servers/my-server ~/my-mcp-servers/
   cd ~/my-mcp-servers
   git init
   ```

2. **Publish on GitHub** with topic `tars-mcp-server`

3. **Usage by others**:
   ```bash
   # Users clone your repo into their extensions/
   cd extensions/mcp-servers
   git clone https://github.com/you/my-mcp-server
   cd ../../ops
   docker compose build mcp-bridge llm-worker
   ```

4. **Consider submitting** to a community extensions list (if one exists)

## 🐛 Troubleshooting

### Server not discovered during build?

**Check mcp-bridge build logs**:
```bash
docker compose build mcp-bridge 2>&1 | grep -A5 "my-server"
```

**Common issues**:
- ❌ Missing `mcp[cli]>=1.2.0` in `pyproject.toml` dependencies
- ❌ No `pyproject.toml` file in server directory
- ❌ Package name mismatch (file: `my_server` vs config: `my-server`)
- ❌ Syntax errors in `pyproject.toml`

**Fix**: Ensure your `pyproject.toml` has `mcp` dependency and proper structure

### Server not in tool registry?

**Verify mcp-bridge discovered it**:
```bash
docker logs tars-mcp-bridge | grep "Discovered server"
```

**Check mcp.server.yml**:
- Server name matches the one in `mcp.server.yml`
- Command and args are correct
- No YAML syntax errors

**Rebuild both images**:
```bash
cd ops
docker compose build mcp-bridge llm-worker
docker compose up -d
```

### Server crashes on startup?

**Test locally first**:
```bash
cd extensions/mcp-servers/my-server
pip install -e .
python -m my_mcp_server
```

**Common issues**:
- ❌ Import errors (missing dependencies)
- ❌ Module naming mismatch
- ❌ Missing `__main__.py` file
- ❌ Environment variables not set

**Check container logs**:
```bash
docker logs tars-mcp-bridge 2>&1 | grep -A10 "my-server"
```

### Tools not being called by TARS?

**Check llm-worker sees the tools**:
```bash
docker logs tars-llm-worker | grep "Loaded.*tools from registry"
```

**Common issues**:
- ❌ Tool docstrings are unclear (LLM doesn't understand when to use them)
- ❌ Tool names are too generic or confusing
- ❌ Tool parameters are too complex
- ❌ LLM wasn't asked to do something that needs your tool

**Improve tool discoverability**:
```python
@app.tool()
def get_weather(city: str, units: str = "metric") -> dict:
    """Get current weather conditions for a specific city.
    
    Use this when the user asks about weather, temperature, or
    current conditions in any location.
    
    Args:
        city: Name of the city (e.g., "London", "New York")
        units: Temperature units - "metric" for Celsius, "imperial" for Fahrenheit
        
    Returns:
        dict with temperature, conditions, humidity, etc.
    """
    # Implementation...
```

### Server runs but returns errors?

**Check environment variables**:
```bash
# In your .env file
MY_API_KEY=your_actual_key_here
```

**Verify they're passed to mcp-bridge**:
```yaml
# ops/mcp/mcp.server.yml
servers:
  - name: my-server
    env:
      MY_API_KEY: "${MY_API_KEY}"  # References .env
```

**Add error handling in your tool**:
```python
@app.tool()
def my_tool(arg: str) -> str:
    """My tool with error handling."""
    try:
        # Your logic here
        return "Success!"
    except Exception as e:
        return f"Error: {str(e)}"  # Return error as string, don't crash
```

## 📚 Resources

**TARS Documentation**:
- [TARS MCP Architecture](../../plan/mcp-server-setup.md) - Complete architecture docs
- [mcp-bridge README](../../apps/mcp-bridge/README.md) - Build-time discovery details
- [Example: tars-mcp-character](../../packages/tars-mcp-character/) - Built-in character management server

**MCP Protocol**:
- [MCP Python SDK Documentation](https://github.com/modelcontextprotocol/python-sdk)
- [FastMCP Examples](https://github.com/modelcontextprotocol/python-sdk/tree/main/examples)
- [MCP Specification](https://spec.modelcontextprotocol.io/)

**Python Packaging**:
- [pyproject.toml Guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)

## 🎯 Quick Reference

**Minimum viable MCP server**:
```
my-server/
├── pyproject.toml          # Must have mcp[cli]>=1.2.0
├── my_mcp_server/
│   ├── __init__.py         # Empty or with __version__
│   ├── __main__.py         # Entry point with app.run()
│   └── server.py           # FastMCP app with @app.tool() decorators
```

**Discovery requirements**:
1. ✅ Located in `extensions/mcp-servers/`
2. ✅ Has `pyproject.toml` with `mcp[cli]>=1.2.0` dependency
3. ✅ Has entry point defined in `[project.scripts]`
4. ✅ Configured in `ops/mcp/mcp.server.yml` with stdio transport

**Build command** (after adding/modifying servers):
```bash
cd ops
docker compose build mcp-bridge llm-worker
docker compose up -d
```

---

**Happy building! 🚀** Your local TARS extensions stay private and automatically integrate with the LLM.
