# Memory Worker

Provides hybrid memory and retrieval over MQTT, plus character/persona management.

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
