# llm-worker

A pluggable LLM microservice for TARS with streaming support, tool calling, RAG integration, and character persona management. Subscribes to `llm/request`, optionally performs RAG via `memory-worker`, calls a configured LLM provider, and publishes responses via `llm/response` or `llm/stream`.

**Status**: Production-ready with handler-based architecture following SOLID principles.

## Features

- ✅ **Streaming & Non-Streaming**: Configurable LLM response streaming with sentence boundary detection
- ✅ **Tool Calling**: Direct MCP (Model Context Protocol) integration for function calling
- ✅ **RAG Integration**: Non-blocking memory retrieval with correlation IDs
- ✅ **Character Personas**: Dynamic character/persona management with system prompt generation
- ✅ **TTS Integration**: Optional streaming to TTS worker with sentence chunking
- ✅ **OpenAI Responses API**: Auto-detection for newer ChatGPT models (gpt-4.1, gpt-5, etc.)
- ✅ **Handler Architecture**: Clean separation of concerns (routing, requests, character, tools, RAG)

## Architecture

**Handler-based design** following SOLID principles:

- **`MessageRouter`**: Routes MQTT messages to appropriate handlers based on topic
- **`RequestHandler`**: Complete LLM request processing pipeline (streaming, tool calling, RAG)
- **`CharacterManager`**: Character/persona management with system prompt generation
- **`ToolExecutor`**: MCP tool execution and registry management
- **`RAGHandler`**: Non-blocking memory queries with correlation IDs

**Main service** (`LLMService`) is only ~190 lines, handling initialization and MQTT lifecycle.

## Environment Variables

### Core Settings
- `MQTT_URL` - MQTT broker URL (e.g., `mqtt://user:pass@127.0.0.1:1883`)
- `LLM_PROVIDER` - Provider name (currently: `openai`)
- `LLM_MODEL` - Model name (e.g., `gpt-4o`, `gpt-4-turbo`)
- `LLM_MAX_TOKENS` - Max tokens per response (default: `4096`)
- `LLM_TEMPERATURE` - Sampling temperature (default: `0.7`)
- `LLM_TOP_P` - Nucleus sampling (default: `1.0`)
- `LOG_LEVEL` - Logging level (default: `INFO`)

### OpenAI Provider
- `OPENAI_API_KEY` - OpenAI API key (required)
- `OPENAI_BASE_URL` - Optional base URL for OpenAI-compatible APIs
- `OPENAI_RESPONSES_MODELS` - Comma-separated list of models using Responses API (supports `*` wildcards)
  - Default: `gpt-4.1*,gpt-4o-mini*,gpt-5*,gpt-5-mini,gpt-5-nano`

### RAG Integration
- `RAG_ENABLED` - Enable RAG retrieval (default: `false`)
- `RAG_TOP_K` - Number of documents to retrieve (default: `5`)
- `RAG_PROMPT_TEMPLATE` - Template for injecting RAG context into prompts

#### Tool Calling (MCP)
- `TOOL_CALLING_ENABLED` - Enable tool calling (default: `false`)
- `TOPIC_TOOLS_REGISTRY` - Topic for tool registry updates (default: `tools/registry`)
- `TOPIC_TOOL_CALL_REQUEST` - Topic for tool call requests (default: `tools/call/request`)
- `TOPIC_TOOL_CALL_RESULT` - Topic for tool call results (default: `tools/call/result`)

**MCP Server Configuration**: Tools are registered via `tools/registry` topic and executed via stdio subprocess transport. Each tool server must be a standalone Python module that can be invoked as `python -m <module_name>`.

### Streaming & TTS
- `LLM_TTS_STREAM` - Forward LLM stream to TTS (default: `false`)
- `STREAM_MIN_CHARS` - Min chars before flushing to TTS (default: `50`)
- `STREAM_MAX_CHARS` - Max chars before forced flush (default: `200`)
- `STREAM_BOUNDARY_CHARS` - Sentence boundary chars (default: `.!?`)

### Topics
- `TOPIC_LLM_REQUEST` - Incoming LLM requests (default: `llm/request`)
- `TOPIC_LLM_RESPONSE` - Non-streaming responses (default: `llm/response`)
- `TOPIC_LLM_STREAM` - Streaming deltas (default: `llm/stream`)
- `TOPIC_LLM_CANCEL` - Cancel streaming requests (default: `llm/cancel`)
- `TOPIC_HEALTH` - Health status (retained) (default: `system/health/llm`)
- `TOPIC_MEMORY_QUERY` - RAG queries to memory-worker (default: `memory/query`)
- `TOPIC_MEMORY_RESULTS` - RAG results from memory-worker (default: `memory/results`)
- `TOPIC_CHARACTER_CURRENT` - Current character snapshot (retained) (default: `system/character/current`)
- `TOPIC_CHARACTER_RESULT` - Character update results (default: `character/result`)
- `TOPIC_CHARACTER_GET` - Request character snapshot (default: `character/get`)
- `TOPIC_TTS_SAY` - TTS output topic (default: `tts/say`)

## MQTT Contracts

All payloads use **Envelope** wrapper with correlation IDs for request-response patterns.

### Input: `llm/request`
```json
{
  "id": "req-123",
  "text": "What is the weather?",
  "stream": true,
  "use_rag": true,
  "rag_k": 5,
  "system": "Optional system prompt override",
  "params": {
    "model": "gpt-4o",
    "temperature": 0.7,
    "max_tokens": 2048
  }
}
```

### Output: `llm/response` (non-streaming)
```json
{
  "id": "req-123",
  "reply": "The weather is sunny today.",
  "provider": "openai",
  "model": "gpt-4o",
  "tokens": {
    "prompt": 15,
    "completion": 8,
    "total": 23
  }
}
```

### Output: `llm/stream` (streaming)
```json
{
  "id": "req-123",
  "seq": 0,
  "delta": "The weather",
  "done": false
}
```

### Input: `character/result` (character updates)
```json
{
  "envelope": "full|section|partial",
  "data": {
    "name": "TARS",
    "systemprompt": "You are TARS...",
    "traits": { "humor": "90%", "honesty": "100%" },
    "description": "Tactical Assistant Robot System"
  }
}
```

### Input: `tools/registry` (MCP tools)
```json
{
  "tools": [
    {
      "name": "get_weather",
      "description": "Get current weather",
      "parameters": { "type": "object", "properties": {...} }
    }
  ]
}
```

## Handler Details

### MessageRouter
Routes incoming MQTT messages to appropriate handlers:
- `character/current` → `CharacterManager.update_from_current()`
- `character/result` → `CharacterManager.update()` (with envelope support)
- `tools/registry` → `ToolExecutor.load_tools()`
- `memory/results` → `RAGHandler.handle_results()`
- `tools/call/result` → `ToolExecutor.handle_tool_result()`
- `llm/request` → `RequestHandler.process_request()`

### RequestHandler
Processes LLM requests end-to-end:
1. Decode request (with Envelope support)
2. Extract parameters (model, temp, etc.)
3. Optional RAG query (non-blocking with correlation IDs)
4. Build system prompt from character persona
5. Call LLM provider (streaming or non-streaming)
6. Handle tool calls (execute via MCP, follow-up response)
7. Publish response/stream with sentence boundary detection
8. Optional TTS forwarding with chunking

### CharacterManager
Manages character personas:
- `get_name()` - Get current character name
- `update_from_current(data)` - Update from full snapshot (character/current)
- `update_section(key, value)` - Update single section
- `merge_update(data)` - Partial update merge
- `build_system_prompt(base?)` - Generate system prompt from traits/description

### ToolExecutor
Handles MCP tool execution:
- `load_tools(payload)` - Load tools from registry
- `execute_tool(name, args)` - Execute tool via MCP client
- `handle_tool_result(payload)` - Process tool results (legacy compat)

### RAGHandler
Non-blocking RAG queries:
- `query(client, prompt, top_k, correlation_id)` - Publish query with correlation ID
- `handle_results(payload)` - Resolve pending query futures
- Uses `asyncio.Future` for immediate response (no polling)
- 5-second timeout prevents indefinite blocking

## OpenAI Responses API

When targeting newer ChatGPT family models (e.g., `gpt-4.1`, `gpt-4o-mini`, `gpt-5`, `gpt-5-mini`, `gpt-5-nano`), the worker automatically switches to OpenAI's Responses API for compatibility.

Configure via `OPENAI_RESPONSES_MODELS` (supports wildcards):
```bash
export OPENAI_RESPONSES_MODELS="gpt-4.1*,gpt-5*,custom-model"
```

## Run (Local)

Create a venv, install requirements, export environment variables:

```bash
cd apps/llm-worker
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export MQTT_URL="mqtt://user:pass@127.0.0.1:1883"
export OPENAI_API_KEY="sk-..."
export RAG_ENABLED=true
export TOOL_CALLING_ENABLED=true
export LLM_TTS_STREAM=true

python -m llm_worker
```

## Run (Docker)

See `ops/compose.yml` for full stack deployment with MQTT broker, memory-worker, and TTS-worker.

```bash
cd ops
docker compose up llm-worker
```

## Development

**Run tests**:
```bash
cd apps/llm-worker
pytest tests/
```

**Code quality**:
```bash
make fmt   # Format with ruff + black
make lint  # Lint with ruff + mypy
make test  # Run tests with coverage
make check # All of the above (CI gate)
```

## Async Patterns

Following py-tars async best practices:
- **CPU-bound work**: All CPU-intensive operations use `asyncio.to_thread()` (none currently in LLM worker)
- **Correlation IDs**: RAG and tool calls use correlation IDs with `asyncio.Future` (no polling)
- **Timeouts**: All external calls have timeouts (5s for RAG, 30s for tools)
- **Cancellation**: Proper `CancelledError` propagation
- **No blocking**: Event loop never blocks >50ms

## MCP Client Implementation

### Overview
The LLM worker integrates with MCP (Model Context Protocol) servers via **stdio subprocess transport**. Each tool call spawns a dedicated subprocess, executes the tool via JSON-RPC, and returns the result.

### Architecture
- **MCP Client**: `llm_worker/mcp_client.py` - Direct stdio transport implementation
- **Tool Executor**: `llm_worker/handlers/tools.py` - Tool registry and execution orchestration
- **Transport**: Stdio subprocess with `StdioServerParameters`
- **Protocol**: JSON-RPC 2.0 over stdin/stdout

### Critical Implementation Detail: Async Context Manager

**The Fix**: `ClientSession` MUST be used as an async context manager for proper protocol lifecycle:

```python
from mcp import StdioServerParameters, ClientSession, stdio_client

async def execute_tool(server_name: str, command: str, args: list, tool_name: str, arguments: dict):
    """Execute MCP tool via stdio subprocess."""
    server_params = StdioServerParameters(command=command, args=args)
    
    # ✅ CORRECT: Nested async context managers
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize the MCP session (establishes protocol version, capabilities)
            await session.initialize()
            
            # Execute the tool call
            result = await session.call_tool(tool_name, arguments)
            
            # Extract content from result
            if hasattr(result, 'content') and result.content:
                return result.content[0].text if result.content else "{}"
            return "{}"
```

**Why This Matters**:
- Without the async context manager, `session.initialize()` hangs indefinitely
- Context manager handles proper protocol handshake and cleanup
- Ensures stdio streams are properly flushed and closed

**What We Tried (and failed)**:
- ❌ Direct `ClientSession(read, write)` without context manager → hung at initialize
- ❌ Manual session lifecycle management → protocol errors
- ❌ Polling for results → never received responses

### Tool Registry Format

Tools are registered via `tools/registry` MQTT topic:

```json
{
  "tools": [
    {
      "name": "adjust_personality_trait",
      "description": "Adjust TARS personality trait value",
      "parameters": {
        "type": "object",
        "properties": {
          "trait_name": {"type": "string", "description": "Trait to adjust"},
          "new_value": {"type": "integer", "minimum": 0, "maximum": 100}
        },
        "required": ["trait_name", "new_value"]
      },
      "mcp_server": "tars_mcp_character",
      "mcp_command": "python",
      "mcp_args": ["-m", "tars_mcp_character"]
    }
  ]
}
```

### Tool Execution Flow

1. **LLM detects tool call** in response (via function calling)
2. **ToolExecutor.execute_tool()** invoked with tool name + arguments
3. **MCPClient._execute_with_stdio()** spawns subprocess:
   - Command: `python -m tars_mcp_character`
   - Protocol: JSON-RPC over stdin/stdout
4. **Session initialization**: Protocol version negotiation + capability exchange
5. **Tool execution**: `session.call_tool(name, args)` via JSON-RPC
6. **Result extraction**: Parse content from MCP response
7. **MQTT publish**: Extract `mqtt_publish` directives and publish to MQTT
8. **Follow-up response**: LLM generates final response with tool results in context

### MCP Server Requirements

For a tool server to work with this client:

1. **Standalone module**: Must be runnable as `python -m <module_name>`
2. **Pure MCP protocol**: Server should NOT have MQTT dependencies (client handles publishing)
3. **JSON-RPC stdio**: Read from stdin, write to stdout
4. **Proper initialization**: Respond to `initialize` method with protocol version
5. **Tool metadata**: Return structured results with optional `mqtt_publish` directives

Example minimal MCP server:
```python
from mcp.server.fastmcp import FastMCP

app = FastMCP("My Tool Server")

@app.tool()
def my_tool(param: str) -> dict:
    return {
        "success": True,
        "result": f"Processed: {param}",
        "mqtt_publish": {
            "topic": "my/topic",
            "data": {"param": param}
        }
    }
```

### Debugging MCP Issues

**Test server manually** (stdin/stdout):
```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | python -m your_mcp_server
```

**Expected response**:
```json
{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"...","version":"..."}}}
```

**Common issues**:
- Server hangs → Check for blocking I/O or missing async context manager
- Protocol errors → Verify JSON-RPC 2.0 compliance
- Import errors → Ensure server has no conflicting async event loops (e.g., asyncio-mqtt)

### Package Requirements

The MCP client requires the full CLI package:
```toml
dependencies = ["mcp[cli]>=1.16.0"]
```

The `[cli]` extra includes stdio transport dependencies that are NOT in the base `mcp` package.

## SOLID Compliance

✅ **Single Responsibility**: Each handler owns one domain  
✅ **Open/Closed**: Easy to add handlers without modifying existing code  
✅ **Liskov Substitution**: Handlers implement clean protocols  
✅ **Interface Segregation**: Minimal, focused interfaces  
✅ **Dependency Injection**: All dependencies injected via constructor  

Service.py reduced from ~500 lines to **191 lines** through handler extraction.