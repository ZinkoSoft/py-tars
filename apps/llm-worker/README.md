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

### Tool Calling (MCP)
- `TOOL_CALLING_ENABLED` - Enable tool calling (default: `false`)
- `TOPIC_TOOLS_REGISTRY` - Topic for tool registry updates (default: `tools/registry`)
- `TOPIC_TOOL_CALL_REQUEST` - Topic for tool call requests (default: `tools/call/request`)
- `TOPIC_TOOL_CALL_RESULT` - Topic for tool call results (default: `tools/call/result`)

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

## SOLID Compliance

✅ **Single Responsibility**: Each handler owns one domain  
✅ **Open/Closed**: Easy to add handlers without modifying existing code  
✅ **Liskov Substitution**: Handlers implement clean protocols  
✅ **Interface Segregation**: Minimal, focused interfaces  
✅ **Dependency Injection**: All dependencies injected via constructor  

Service.py reduced from ~500 lines to **191 lines** through handler extraction.