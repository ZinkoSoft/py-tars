# MCP Bridge

The **MCP Bridge** is a **build-time only** tool that discovers, installs, and configures MCP (Model Context Protocol) servers during Docker image builds. It generates a static configuration file (`mcp-servers.json`) that runtime services consume.

## 🎯 Purpose

**What MCP Bridge Does (Build-Time Only):**
1. **Discovers** MCP servers from multiple sources:
   - Local packages (`packages/tars-mcp-*`)
   - Extensions directory (`extensions/mcp-servers/*`)
   - External configuration (`ops/mcp/mcp.server.yml`)
2. **Installs** discovered Python packages (via pip)
3. **Generates** static configuration file (`mcp-servers.json`)
4. **Exits** with status code (0 = success, 1 = failure)

**What MCP Bridge Does NOT Do:**
- ❌ Does NOT run as a persistent service
- ❌ Does NOT connect to MCP servers
- ❌ Does NOT execute tool calls
- ❌ Does NOT use MQTT (no runtime communication)
- ❌ Does NOT exist in runtime images (uninstalled after build)

**Runtime Tool Execution:**
The **llm-worker** is responsible for:
- Reading generated `mcp-servers.json` configuration
- Connecting to MCP servers at runtime (stdio/SSE)
- Calling tools via MCP protocol
- Handling tool execution in response to LLM requests
- Publishing/subscribing to MQTT topics for tool calls

## 🏗️ Architecture

```
DOCKER BUILD TIME:
┌─────────────────────────────────────────────────┐
│  llm-worker.Dockerfile                          │
├─────────────────────────────────────────────────┤
│  1. Install mcp-bridge (temporary)              │
│  2. Copy workspace files                        │
│  3. RUN python -m mcp_bridge.main               │
│     ├─ Discover: Local + Extensions + External  │
│     ├─ Install: pip install packages            │
│     └─ Generate: mcp-servers.json               │
│  4. Copy config to /app/config/                 │
│  5. Uninstall mcp-bridge (cleanup)              │
└─────────────────────────────────────────────────┘
                    │
                    ▼
         mcp-servers.json (baked into image)
                    │
                    ▼
RUNTIME:
┌─────────────────────────────────────────────────┐
│  llm-worker Container                           │
├─────────────────────────────────────────────────┤
│  1. Read /app/config/mcp-servers.json           │
│  2. Connect to MCP servers (stdio/SSE)          │
│  3. Execute tools via MCP protocol              │
│  4. Handle MQTT tool call topics                │
└─────────────────────────────────────────────────┘
```

### Build-Time Flow (MCP Bridge - Runs During Docker Build)
1. **Discovery Phase**: Scan for MCP servers from all sources
2. **Installation Phase**: Install Python packages via pip (parallel)
3. **Configuration Phase**: Generate `mcp-servers.json` with metadata
4. **Exit**: Bridge terminates (exit code 0 if >= 50% install success)
5. **Cleanup**: Bridge uninstalled from final image

### Runtime Flow (LLM Worker - Reads Pre-Generated Config)
1. **Load Config**: Read `/app/config/mcp-servers.json`
2. **Connect**: Establish stdio/SSE connections to MCP servers
3. **Tool Execution**: Handle tool calls from LLM via MCP protocol
4. **MQTT Integration**: Publish/subscribe for tool requests/results

## 📋 Configuration

### MCP Server Discovery Sources

The MCP Bridge discovers servers from **three sources** (in order of precedence):

#### 1. **Local Packages** (Highest Priority)
Convention-based discovery from `packages/tars-mcp-*/`:
- Automatically detected if package follows naming convention
- Installed via `pip install -e <path>` (editable mode)
- Example structure:
  ```
  packages/tars-mcp-character/
  ├── pyproject.toml  # Must define mcp.server entry point
  ├── src/
  │   └── tars_mcp_character/
  │       └── server.py
  ```

#### 2. **Extensions Directory**
User-provided MCP servers in `extensions/mcp-servers/*/`:
- Each subdirectory is treated as a server
- Installed via `pip install -e <path>` (editable mode)
- Must contain `pyproject.toml` with MCP server entry point

#### 3. **External Configuration** (Lowest Priority)
Explicit server declarations in `ops/mcp/mcp.server.yml`:
```yaml
servers:
  - name: filesystem
    transport: stdio
    command: "npx"
    args: ["--yes", "@modelcontextprotocol/server-filesystem", "/workspace"]
    allowed_tools: ["read_file", "write_file", "list_dir"]
    package_name: "@modelcontextprotocol/server-filesystem"  # For npm packages

  - name: custom-api
    transport: stdio
    command: "python"
    args: ["-m", "my_mcp_server"]
    env:
      API_KEY: "${API_KEY}"  # Environment variable substitution supported
    allowed_tools: ["api_call", "fetch_data"]
    package_name: "my-mcp-server"  # For pip install
```

**Priority Rules:**
- If same server name appears in multiple sources, external config wins
- External config can override local/extension discovery
- Use external config for npm packages or custom commands

### Environment Variables

```bash
# Discovery configuration (used during Docker build)
WORKSPACE_ROOT=/tmp/workspace              # Root directory for discovery
MCP_LOCAL_PACKAGES_PATH=/tmp/workspace/packages  # Path to local packages
MCP_EXTENSIONS_PATH=/tmp/workspace/extensions/mcp-servers  # Extensions path
MCP_SERVERS_YAML=/tmp/workspace/ops/mcp/mcp.server.yml    # External config (optional)

# Output configuration
MCP_OUTPUT_DIR=/app/config           # Where to write mcp-servers.json
MCP_CONFIG_FILENAME=mcp-servers.json # Config filename (default: mcp-servers.json)

# Logging
LOG_LEVEL=INFO  # DEBUG for verbose output during build

# Note: No MQTT configuration - mcp-bridge does not use MQTT
```

## � Build Output

The MCP Bridge outputs structured logs during Docker build. No MQTT topics are used.

### Build Logs (stdout)

**Phase 1: Discovery**
```
2025-10-04 20:15:09 - mcp-bridge - INFO - Phase 1: MCP Server Discovery
2025-10-04 20:15:09 - mcp-bridge - INFO - Discovered 2 servers
2025-10-04 20:15:09 - mcp-bridge - INFO -   Local packages: 1
2025-10-04 20:15:09 - mcp-bridge - INFO -   Extensions: 0
2025-10-04 20:15:09 - mcp-bridge - INFO -   External config: 1
```

**Phase 2: Installation**
```
2025-10-04 20:15:10 - mcp-bridge - INFO - Phase 2: Package Installation
2025-10-04 20:15:10 - mcp-bridge - INFO - Installing 2 MCP server(s)...
2025-10-04 20:15:10 - mcp-bridge - INFO - ⏭️  tars-mcp-character already installed
2025-10-04 20:15:10 - mcp-bridge - INFO - Installation complete in 1.8s
2025-10-04 20:15:10 - mcp-bridge - INFO -   Success rate: 50.0%
```

**Phase 3: Configuration**
```
2025-10-04 20:15:10 - mcp-bridge - INFO - Phase 3: Configuration Generation
2025-10-04 20:15:10 - mcp-bridge - INFO - Generated configuration for 2 servers
2025-10-04 20:15:10 - mcp-bridge - INFO - Configuration written: /app/config/mcp-servers.json
2025-10-04 20:15:10 - mcp-bridge - INFO - File size: 1248 bytes
```

**Exit Status**
```
2025-10-04 20:15:10 - mcp-bridge - INFO - Build succeeded (>= 50% install success)
# Exit code: 0
```

### Runtime Topics (Handled by llm-worker)
These topics are **NOT** handled by mcp-bridge:
- ❌ `llm/tools/registry` - Tool registry (llm-worker publishes this)
- ❌ `llm/tool.call.request/#` - Tool execution requests (llm-worker handles)
- ❌ `llm/tool.call.result` - Tool results (llm-worker publishes)

## 🛠️ Adding MCP Servers

### Method 1: Local Package (Recommended for Python)

Create a new package following the convention:

```bash
# Create package structure
mkdir -p packages/tars-mcp-myserver/src/tars_mcp_myserver

# Create pyproject.toml
cat > packages/tars-mcp-myserver/pyproject.toml << 'EOF'
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "tars-mcp-myserver"
version = "0.1.0"
description = "My custom MCP server"
dependencies = ["mcp>=1.0.0"]

[project.entry-points."mcp.server"]
myserver = "tars_mcp_myserver.server:serve"
EOF

# Create server.py
cat > packages/tars-mcp-myserver/src/tars_mcp_myserver/server.py << 'EOF'
from mcp.server import Server

async def serve():
    server = Server("myserver")
    # Add your tools here
    return server
EOF
```

**Auto-discovery**: MCP Bridge will automatically find and install this package on next build.

### Method 2: Extension Directory

Place existing MCP server packages in `extensions/mcp-servers/`:

```bash
# Clone or copy external MCP server
cd extensions/mcp-servers/
git clone https://github.com/example/mcp-custom-server.git
```

**Auto-discovery**: MCP Bridge will install all servers in this directory.

### Method 3: External Configuration (For npm/non-Python)

Add to `ops/mcp/mcp.server.yml`:

```yaml
servers:
  - name: filesystem
    transport: stdio
    command: "npx"
    args: ["--yes", "@modelcontextprotocol/server-filesystem", "/workspace"]
    allowed_tools: ["read_file", "write_file", "list_dir"]
    package_name: "@modelcontextprotocol/server-filesystem"  # npm package

  - name: my-custom-server
    transport: stdio
    command: "python"
    args: ["-m", "my_mcp_server"]
    env:
      API_KEY: "${API_KEY}"
    allowed_tools: ["tool1", "tool2"]
    package_name: "my-mcp-server"  # pip package
```

### Rebuild to Apply Changes

```bash
# Rebuild llm-worker image (mcp-bridge runs during build)
cd ops
docker compose build llm --no-cache

# Verify config was generated
docker run --rm tars/llm:dev cat /app/config/mcp-servers.json | jq .

# Deploy updated image
docker compose up -d llm
```

## 📝 Generated Configuration Format

MCP Bridge generates `mcp-servers.json` for llm-worker to consume at runtime:

```json
{
  "version": 1,
  "servers": [
    {
      "name": "tars-mcp-character",
      "source": "local_package",
      "transport": "stdio",
      "command": "python",
      "args": ["-m", "tars_mcp_character.server"],
      "env": {},
      "allowed_tools": null,
      "package_name": "tars-mcp-character",
      "installed": true,
      "install_path": "/workspace/packages/tars-mcp-character"
    },
    {
      "name": "filesystem",
      "source": "external_config",
      "transport": "stdio",
      "command": "npx",
      "args": ["--yes", "@modelcontextprotocol/server-filesystem", "/workspace"],
      "env": {},
      "allowed_tools": ["read_file", "write_file", "list_dir"],
      "package_name": "@modelcontextprotocol/server-filesystem",
      "installed": false,
      "install_path": null
    }
  ],
  "generated_at": "2025-10-04T12:34:56Z",
  "discovery_summary": {
    "total_servers": 2,
    "sources": {
      "local": 1,
      "external": 1
    }
  },
  "installation_summary": {
    "total_servers": 2,
    "installed": 0,
    "already_installed": 1,
    "failed": 1,
    "skipped": 0,
    "success_rate": 0.5,
    "duration_sec": 1.8
  }
}
```

**Usage by llm-worker:**
- Reads this file at startup
- Connects to each server via stdio/HTTP
- Queries tools via `session.list_tools()`
- Converts to OpenAI function specs for LLM
- Handles tool execution via MCP protocol

## 🧪 Testing

### Test Docker Build Integration

```bash
# Run comprehensive build test
bash apps/mcp-bridge/test-docker-integration.sh

# This will:
# 1. Build llm-worker image with mcp-bridge
# 2. Verify mcp-servers.json exists in image
# 3. Validate JSON structure
# 4. Check mcp-bridge is uninstalled from runtime
# 5. Verify MCP servers are installed
```

### Verify Generated Configuration

```bash
# Check generated config file
cat config/mcp-servers.json | jq .

# Verify servers are listed
jq '.servers[] | {name, source, installed}' config/mcp-servers.json
```

### Test Discovery Locally

```bash
# Run discovery without installation
cd apps/mcp-bridge
python -c "
from mcp_bridge.discovery import ServerDiscoveryService
import asyncio

async def test():
    service = ServerDiscoveryService()
    servers = await service.discover_all_servers()
    for s in servers:
        print(f'{s.name}: {s.source} - {s.transport}')

asyncio.run(test())
"
```

### Test Full Pipeline

```bash
# Run complete build pipeline
cd apps/mcp-bridge
python -m mcp_bridge.main

# Check exit code (should be 0)
echo $?

# Verify config file was created
ls -lh config/mcp-servers.json
```

## 🔧 Development

### Local Development

```bash
# Install dependencies
pip install -e .

# Run discovery + installation + config generation
export MCP_USE_DISCOVERY=true
export MCP_LOCAL_PACKAGES_PATH=/workspace/packages
export MCP_OUTPUT_DIR=/workspace/config
python -m mcp_bridge.main

# Run tests
pytest tests/ -v
```

### Docker Integration

The MCP Bridge runs during llm-worker Docker build:

**File**: `docker/specialized/llm-worker.Dockerfile`

```dockerfile
# Install mcp-bridge (temporarily)
COPY apps/mcp-bridge /tmp/mcp-bridge
RUN pip install --no-cache-dir /tmp/mcp-bridge

# Copy workspace for discovery
COPY packages /tmp/workspace/packages
COPY extensions/mcp-servers /tmp/workspace/extensions/mcp-servers
COPY ops/mcp/mcp.server.yml /tmp/workspace/ops/mcp/mcp.server.yml

# Run mcp-bridge (ONE-SHOT build-time operation)
RUN mkdir -p /app/config && \
    cd /tmp/workspace && \
    WORKSPACE_ROOT=/tmp/workspace \
    MCP_OUTPUT_DIR=/tmp/workspace/config \
    python -m mcp_bridge.main

# Copy generated config to runtime location
RUN cp /tmp/workspace/config/mcp-servers.json /app/config/mcp-servers.json

# Clean up (mcp-bridge not needed at runtime)
RUN pip uninstall -y tars-mcp-bridge && \
    rm -rf /tmp/mcp-bridge /tmp/workspace

# Verify config was generated
RUN test -f /app/config/mcp-servers.json || \
    (echo "ERROR: mcp-servers.json not generated!" && exit 1)

# Install llm-worker
COPY apps/llm-worker /tmp/llm-worker
RUN pip install /tmp/llm-worker

CMD ["python", "-m", "llm_worker"]
```

**Key Points**:
- mcp-bridge installs, runs, generates config, then is **uninstalled**
- Config is **baked into the image** at `/app/config/mcp-servers.json`
- llm-worker reads this static config at runtime

### Adding New Discovery Sources

To add a new discovery source:

1. Create new discovery class in `mcp_bridge/discovery/`
2. Implement `DiscoverySource` protocol
3. Register in `ServerDiscoveryService`
4. Add configuration options

### Testing Discovery Sources

```bash
# Test local package discovery
pytest tests/test_local_discovery.py -v

# Test external config discovery
pytest tests/test_discovery_integration.py -v

# Test with real packages
pytest tests/test_real_discovery.py -v
```

## 🚨 Troubleshooting

### Common Issues

**No Servers Discovered**
- Check `MCP_LOCAL_PACKAGES_PATH` and `MCP_EXTENSIONS_PATH` environment variables
- Verify package naming convention: `tars-mcp-*` or placed in extensions directory
- Ensure `pyproject.toml` exists with MCP entry point
- Check logs: `python -m mcp_bridge.main` (debug mode)

**Installation Failures**
- Check package `pyproject.toml` is valid
- Verify pip can install package: `pip install -e <path>`
- Check `MCP_PIP_TIMEOUT_SEC` if timing out
- Review installation logs in MQTT topic `system/health/mcp-bridge/installation`

**Config File Not Generated**
- Check `MCP_OUTPUT_DIR` exists and is writable
- Verify at least one server was discovered
- Check exit code: should be 0 for success
- Review logs for errors during config generation

**Package Already Installed Issues**
- Set `MCP_SKIP_ALREADY_INSTALLED=false` to force reinstall
- Manually uninstall: `pip uninstall <package-name>`
- Clear pip cache: `pip cache purge`

**External Config Not Loading**
- Verify YAML syntax: `yamllint ops/mcp/mcp.server.yml`
- Check environment variable substitution: `${VAR}` format
- Ensure `MCP_SERVERS_YAML` points to correct file
- Validate required fields: `name`, `transport`, `command`

### Debug Logging

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
python -m mcp_bridge.main
```

### Manual Testing

```bash
# Test discovery only
python -c "
from mcp_bridge.discovery import ServerDiscoveryService
import asyncio
import logging
logging.basicConfig(level=logging.DEBUG)

async def test():
    service = ServerDiscoveryService()
    servers = await service.discover_all_servers()
    print(f'Discovered {len(servers)} servers')
    for s in servers:
        print(f'  - {s.name} ({s.source}): {s.transport}')

asyncio.run(test())
"

# Test installation only
python -c "
from mcp_bridge.installation import InstallationService
from mcp_bridge.discovery import ServerDiscoveryService
import asyncio
import logging
logging.basicConfig(level=logging.DEBUG)

async def test():
    # Discover
    disc_service = ServerDiscoveryService()
    servers = await disc_service.discover_all_servers()
    
    # Install
    inst_service = InstallationService()
    summary = await inst_service.install_all(servers)
    print(f'Installed: {summary.installed}/{summary.total_servers}')
    print(f'Success rate: {summary.success_rate:.1%}')

asyncio.run(test())
"
```

## 📚 Examples

### Example 1: Local Python Package

```
packages/tars-mcp-calculator/
├── pyproject.toml
└── src/
    └── tars_mcp_calculator/
        ├── __init__.py
        └── server.py
```

**pyproject.toml:**
```toml
[project]
name = "tars-mcp-calculator"
version = "0.1.0"
dependencies = ["mcp>=1.0.0"]

[project.entry-points."mcp.server"]
calculator = "tars_mcp_calculator.server:serve"
```

**Result:** Auto-discovered, installed via pip, added to mcp-servers.json

### Example 2: Extension from GitHub

```bash
cd extensions/mcp-servers/
git clone https://github.com/example/awesome-mcp-server.git
```

**Result:** Auto-discovered, installed editable, added to mcp-servers.json

### Example 3: External npm Package

**ops/mcp/mcp.server.yml:**
```yaml
servers:
  - name: filesystem
    transport: stdio
    command: "npx"
    args: ["--yes", "@modelcontextprotocol/server-filesystem", "/workspace"]
    allowed_tools: ["read_file", "write_file", "list_dir"]
    package_name: "@modelcontextprotocol/server-filesystem"
```

**Result:** Not installed (npm package), command preserved in mcp-servers.json for runtime

### Example 4: Mixed Sources

**Discovery finds:**
1. `packages/tars-mcp-character/` → installed, stdio command generated
2. `extensions/mcp-servers/custom-api/` → installed, stdio command generated  
3. `ops/mcp/mcp.server.yml` → filesystem server (npm) → command preserved

**Generated mcp-servers.json:**
```json
{
  "servers": [
    {
      "name": "tars-mcp-character",
      "source": "local_package",
      "installed": true,
      "command": "python",
      "args": ["-m", "tars_mcp_character.server"]
    },
    {
      "name": "custom-api", 
      "source": "extension",
      "installed": true,
      "command": "python",
      "args": ["-m", "custom_api.server"]
    },
    {
      "name": "filesystem",
      "source": "external_config",
      "installed": false,
      "command": "npx",
      "args": ["--yes", "@modelcontextprotocol/server-filesystem", "/workspace"]
    }
  ]
}
```

## � Workflow Summary

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP BRIDGE (Build-Time)                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. DISCOVERY                                               │
│     ├─ Scan packages/tars-mcp-*/                            │
│     ├─ Scan extensions/mcp-servers/*/                       │
│     └─ Parse ops/mcp/mcp.server.yml                         │
│                                                             │
│  2. INSTALLATION                                            │
│     ├─ pip install -e <local packages>                      │
│     ├─ pip install -e <extensions>                          │
│     └─ pip install <external packages> (if package_name)    │
│                                                             │
│  3. CONFIGURATION GENERATION                                │
│     └─ Write config/mcp-servers.json                        │
│                                                             │
│  4. HEALTH REPORTING                                        │
│     ├─ Publish system/health/mcp-bridge/discovery           │
│     ├─ Publish system/health/mcp-bridge/installation        │
│     └─ Publish system/health/mcp-bridge/config              │
│                                                             │
│  5. EXIT (code 0 if successful)                             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │ mcp-servers.json    │
                  │ (Generated Config)  │
                  └─────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   LLM WORKER (Runtime)                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. LOAD CONFIG                                             │
│     └─ Read mcp-servers.json                                │
│                                                             │
│  2. CONNECT TO SERVERS                                      │
│     ├─ stdio: spawn process, stdio_client()                 │
│     └─ http: HTTP client connection                         │
│                                                             │
│  3. DISCOVER TOOLS                                          │
│     └─ session.list_tools() for each server                 │
│                                                             │
│  4. BUILD TOOL REGISTRY                                     │
│     └─ Convert to OpenAI function specs                     │
│                                                             │
│  5. PUBLISH REGISTRY                                        │
│     └─ MQTT: llm/tools/registry (retained)                  │
│                                                             │
│  6. HANDLE TOOL CALLS                                       │
│     ├─ Subscribe: llm/tool.call.request/#                   │
│     ├─ Execute: session.call_tool()                         │
│     └─ Publish: llm/tool.call.result                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## �🔗 Related Components

- **LLM Worker** - Consumes generated config, connects to MCP servers at runtime, handles tool execution
- **TARS Core** - Shared contracts and MQTT utilities
- **Local Packages** - `packages/tars-mcp-*/` - Convention-based MCP servers
- **Extensions** - `extensions/mcp-servers/*/` - User-provided MCP servers
- **External Config** - `ops/mcp/mcp.server.yml` - Explicit server declarations

## 📄 License

This service is part of the TARS project. See main project license for details.