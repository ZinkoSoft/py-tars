# Memory Worker

Provides hybrid memory and retrieval over MQTT, plus character/persona management.

## Installation

From the repository root:

```bash
cd apps/memory-worker
pip install -e .
```

For development:
```bash
pip install -e ".[dev]"
```

## Memory Topics

- **memory/query**: `{ text, top_k? }` - Query the memory database
- **memory/results**: `{ query, k, results: [{document, score}] }` - Query results with relevance scores
- **system/health/memory**: retained health status

Persists to `/data/{MEMORY_FILE}` (default: `memory.pickle.gz`).

## Character/Persona Topics

- **character/get**: `{ section? }` - Request character data (entire snapshot or specific section)
- **character/result**: Returns `CharacterSnapshot` or `CharacterSection`
- **system/character/current**: **Retained** - Current character configuration published on startup

### Character Configuration

Character data is loaded from TOML files at startup:
- Path: `{CHARACTER_DIR}/{CHARACTER_NAME}/character.toml`
- Default: `/config/characters/TARS/character.toml`

**Structure:**
```toml
[info]
name = "TARS"
description = "Trustworthy, witty, and pragmatic AI assistant"
systemprompt = "Your system prompt for LLM..."

[traits]
# Personality traits (0-100 scale or any format)
honesty = 95
humor = 90
sarcasm = 70
# ... any custom traits

[voice]
voice_id = "TARS"
rate = 1.0
pitch = 0.0

[meta]
version = 1
# ... any metadata
```

The `traits` dictionary is published to `system/character/current` (retained) so all services can access TARS's personality configuration. LLM workers can use this to adjust behavior dynamically.

## Environment Variables

**Memory:**
- `MQTT_URL` - Broker connection (host, port, credentials)
- `MEMORY_DIR` - Storage directory (default: `/data`)
- `MEMORY_FILE` - Database filename (default: `memory.pickle.gz`)
- `RAG_STRATEGY` - Retrieval strategy: `naive` | `hybrid`
- `MEMORY_TOP_K` - Default number of results (default: `5`)
- `EMBED_MODEL` - SentenceTransformer model (default: `sentence-transformers/all-MiniLM-L6-v2`)

**Character:**
- `CHARACTER_NAME` - Character to load (default: `TARS`)
- `CHARACTER_DIR` - Characters directory (default: `/config/characters`)

## Usage Example

**Query memory:**
```bash
mosquitto_pub -t memory/query -m '{"text": "What did I say about pizza?"}'
```

**Get character persona:**
```bash
# Get entire character
mosquitto_pub -t character/get -m '{}'

# Get specific section
mosquitto_pub -t character/get -m '{"section": "traits"}'
```

**Subscribe to character updates:**
```bash
mosquitto_sub -t system/character/current -v
```

## MQTT Client Architecture

**Centralized Client**: Uses `tars.adapters.mqtt_client.MQTTClient` from `tars-core` package.

**Key Features**:
- **Auto-Reconnection**: Exponential backoff (0.5s-5s configurable) with session recovery
- **Health Monitoring**: Publishes health status to `system/health/memory` (retained)
- **Heartbeat**: Optional keepalive messages to `system/keepalive/memory`
- **Message Deduplication**: TTL cache prevents duplicate processing during reconnects
- **Subscription Handlers**: Clean async handler pattern replaces manual message loops

**Handler Pattern**:
```python
async def _handle_memory_query(self, payload: bytes) -> None:
    """Handler registered with client.add_subscription_handler()"""
    # Parse, validate, process
    query = MemoryQuery.model_validate_json(payload)
    # ...

# Registration
await self._client.add_subscription_handler("memory/query", self._handle_memory_query)
```

**Health Integration**:
- Health check reports embedder and vector DB status
- Auto-publishes to `system/health/memory` on connect/disconnect
- Heartbeat maintains session presence

**Migration Benefits** (from local wrapper):
- Eliminated ~150 lines of duplicate reconnection logic
- Centralized health monitoring across all services
- Consistent error handling and logging patterns
- Reduced maintenance burden (single implementation)

## Development

### Running Tests

```bash
make test
```

### Formatting and Linting

```bash
make check
```

### Available Make Targets

- `make fmt` - Format code with ruff and black
- `make lint` - Lint and type-check with ruff and mypy
- `make test` - Run tests with coverage
- `make check` - Run all checks (CI gate)
- `make build` - Build Python package
- `make clean` - Remove build artifacts
- `make install` - Install in editable mode
- `make install-dev` - Install with dev dependencies

### Project Structure

```
apps/memory-worker/
├── src/memory_worker/          # Source code
│   ├── __main__.py             # Entry point
│   ├── config.py               # Configuration
│   ├── service.py              # Core service logic (MQTT lifecycle, handler registration)
│   ├── hyperdb.py              # Vector database
│   ├── embedder_factory.py    # Embedder selection
│   └── npu_embedder.py         # NPU-accelerated embeddings
├── tests/
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── contract/               # MQTT contract tests
├── characters/                 # Character configurations
├── examples/                   # Usage examples
└── scripts/                    # Utility scripts

```

## Architecture

The memory worker provides two primary services:

### 1. Hybrid RAG (Retrieval-Augmented Generation)

- **Naive strategy**: Pure vector similarity search using SentenceTransformer embeddings
- **Hybrid strategy**: Combines BM25 keyword search with vector search, then reranks results

Uses HyperDB for vector storage with configurable retrieval strategies and optional NPU acceleration (rknnlite) for embeddings on supported hardware.

### 2. Character/Persona Management

Loads character configuration from TOML files and publishes to MQTT for other services (LLM workers, UI) to consume. Characters define personality traits, voice settings, and system prompts.
