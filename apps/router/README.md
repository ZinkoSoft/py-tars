# Router

Central message orchestration service for TARS voice assistant. The router manages the flow of messages between services, implements routing rules and policies, handles wake word mode transitions, and tracks service health.

## Overview

The router is the **most critical service** in the TARS architecture. It:

- **Routes STT transcripts** to LLM worker
- **Streams LLM responses** to TTS worker with sentence boundary detection
- **Manages wake word mode** transitions (always-listening vs wake-word-activated)
- **Tracks service health** (STT, TTS, and other services)
- **Implements routing policies** including rules-based routing and LLM fallback
- **Handles streaming** with buffering and backpressure management

## Installation

```bash
pip install -e .
```

For development:
```bash
pip install -e ".[dev]"
```

## Usage

### Running the Service

```bash
# Using console script
tars-router

# Using Python module
python -m router

# In Docker
docker compose -f ops/compose.yml up router
```

### Environment Variables

See `.env.example` for complete list.

**Required**:
- `MQTT_URL` - MQTT broker URL (default: `mqtt://localhost:1883`)

**Optional**:
- `LOG_LEVEL` - Logging level (default: `INFO`)
- `ROUTER_LLM_TTS_STREAM` - Enable streaming mode (default: `1`)
- `ROUTER_STREAM_MIN` - Min characters before flush (default: `20`)
- `ROUTER_STREAM_MAX` - Max characters before forced flush (default: `500`)
- `ROUTER_STREAM_BOUNDARY` - Flush only on sentence boundaries (default: `1`)
- `ROUTER_STREAM_QUEUE_MAXSIZE` - Queue size for streaming (default: `100`)
- `ROUTER_STREAM_QUEUE_OVERFLOW` - Overflow strategy: `drop` or `block` (default: `drop`)
- `ROUTER_STREAM_HANDLER_TIMEOUT` - Handler timeout in seconds (default: `30.0`)

**MQTT Topic Configuration** (all have defaults):
- `TOPIC_STT_FINAL` - STT final transcripts (default: `stt/final`)
- `TOPIC_LLM_REQUEST` - LLM requests (default: `llm/request`)
- `TOPIC_LLM_RESPONSE` - LLM responses (default: `llm/response`)
- `TOPIC_LLM_STREAM` - LLM streaming deltas (default: `llm/stream`)
- `TOPIC_LLM_CANCEL` - LLM cancellation (default: `llm/cancel`)
- `TOPIC_TTS_SAY` - TTS speech requests (default: `tts/say`)
- `TOPIC_TTS_STATUS` - TTS status events (default: `tts/status`)
- `TOPIC_WAKE_EVENT` - Wake word events (default: `wake/event`)
- `TOPIC_HEALTH_STT` - STT health status (default: `system/health/stt`)
- `TOPIC_HEALTH_TTS` - TTS health status (default: `system/health/tts`)
- `TOPIC_HEALTH_ROUTER` - Router health status (default: `system/health/router`)

## Configuration

All configuration is via environment variables (12-factor app). The router uses typed configuration objects parsed at startup from `RouterSettings.from_env()`.

## Development

### Running Tests

```bash
# All tests
make test

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# With coverage
pytest tests/ --cov=src/router --cov-report=html
```

### Formatting and Linting

```bash
# Format code
make fmt

# Lint code
make lint

# Run all checks (CI gate)
make check
```

### Available Make Targets

- `make fmt` - Format code with ruff and black
- `make lint` - Lint with ruff and type-check with mypy
- `make test` - Run tests with coverage
- `make check` - Run all checks (CI gate)
- `make build` - Build Python package
- `make clean` - Remove build artifacts

## Architecture

### Components

1. **RouterPolicy** (`tars.domain.router`) - Core routing logic and policy decisions
2. **RouterSettings** (`tars.domain.router`) - Configuration management
3. **RouterMetrics** (`tars.domain.router`) - Metrics tracking and reporting
4. **Dispatcher** (`tars.runtime.dispatcher`) - Message dispatching and handler execution
5. **Ctx** (`tars.runtime.ctx`) - Request context with publisher, logger, metrics

### Message Flow

```
STT Final → Router → LLM Request → LLM Worker
                    ↓
            LLM Response/Stream → Router → TTS Say → TTS Worker
```

### Streaming Flow

When `ROUTER_LLM_TTS_STREAM=1`:

1. **LLM Stream Deltas** arrive via `llm/stream` topic
2. **Buffer accumulation** in RouterPolicy
3. **Sentence boundary detection** using regex patterns
4. **Flush on boundary** or when buffer exceeds `ROUTER_STREAM_MAX`
5. **Publish to TTS** via `tts/say` topic

### Wake Word Mode

The router manages two modes:

- **Always-Listening Mode**: All STT transcripts sent to LLM
- **Wake-Word Mode**: Only transcripts after wake word detection

Mode transitions triggered by `wake/event` messages.

### Health Monitoring

The router:
- Subscribes to `system/health/stt` and `system/health/tts`
- Publishes own health to `system/health/router` (retained)
- Tracks service availability in RouterPolicy
- Adjusts routing behavior based on service health

## MQTT Topics

### Subscribed Topics

| Topic | Message Type | QoS | Purpose |
|-------|--------------|-----|---------|
| `stt/final` | `FinalTranscript` | 1 | STT final transcriptions |
| `llm/response` | `LLMResponse` | 1 | LLM complete responses |
| `llm/stream` | `LLMStreamDelta` | 1 | LLM streaming deltas |
| `llm/cancel` | `LLMCancel` | 1 | LLM cancellation requests |
| `wake/event` | `WakeEvent` | 1 | Wake word detection events |
| `tts/status` | `TtsStatus` | 1 | TTS status events (speaking_start, speaking_end) |
| `system/health/stt` | `HealthPing` | 1 | STT service health |
| `system/health/tts` | `HealthPing` | 1 | TTS service health |

### Published Topics

| Topic | Message Type | QoS | Retain | Purpose |
|-------|--------------|-----|--------|---------|
| `llm/request` | `LLMRequest` | 1 | No | LLM inference requests |
| `tts/say` | `TtsSay` | 1 | No | TTS speech requests |
| `system/health/router` | `HealthPing` | 1 | Yes | Router health status |

### Message Schemas

All message types use **Pydantic v2** models from `tars.contracts.v1`. See contract documentation for detailed schemas.

**Key message types**:
- `FinalTranscript` - STT final transcription with text, confidence, timestamp
- `LLMRequest` - LLM request with text, optional RAG, system prompt
- `LLMResponse` - LLM complete response with text, tokens, provider info
- `LLMStreamDelta` - LLM streaming delta with sequence number, delta text
- `TtsSay` - TTS request with text, voice, utterance ID
- `WakeEvent` - Wake word event with detection confidence
- `HealthPing` - Service health with ok flag and optional error message

## Testing

### Test Organization

- `tests/unit/` - Fast, isolated unit tests (config, metrics, helpers)
- `tests/integration/` - Integration tests (MQTT, dispatcher, streaming)
- `tests/contract/` - MQTT contract validation tests

### Running Tests

```bash
# All tests
pytest tests/

# Unit tests (fast)
pytest tests/unit/

# Integration tests (requires mocks)
pytest tests/integration/

# Specific test file
pytest tests/unit/test_router_config.py

# With verbose output
pytest tests/ -v

# With coverage
pytest tests/ --cov=src/router --cov-report=term-missing
```

### Test Fixtures

See `tests/conftest.py` for shared fixtures:
- `mock_mqtt_client` - Mock MQTT client
- `mock_publisher` - Mock MQTT publisher
- `mock_subscriber` - Mock MQTT subscriber
- `event_loop` - Async event loop for async tests

## Deployment

### Docker

The router is deployed via Docker Compose:

```bash
# Build
docker compose -f ops/compose.yml build router

# Run
docker compose -f ops/compose.yml up router

# Run with full stack
docker compose -f ops/compose.yml up
```

### Dockerfile

Uses generic `docker/app.Dockerfile` with build args:
- `APP_PATH=apps/router`
- `APP_MODULE=router.__main__`
- `PY_VERSION=3.11`

### Health Checks

The router publishes health status to `system/health/router` (retained, QoS 1):

```json
{
  "ok": true,
  "event": "ready"
}
```

Monitor this topic to verify router availability.

## Observability

### Structured Logging

The router emits structured JSON logs with correlation fields:
- `service: "router"`
- `timestamp`
- `level`
- `message`
- `extra`: Additional context (MQTT topics, service states, etc.)

### Metrics

RouterMetrics tracks:
- Message counts by topic
- Latency histograms
- Error rates
- Service health states
- Wake mode transitions

Access metrics via `RouterMetrics` instance in RouterPolicy.

### Log Events

Key log events:
- `router.mqtt.connect` - MQTT connection attempt
- `router.mqtt.connected` - MQTT connection established
- `router.mqtt.disconnected` - MQTT disconnection with backoff
- `router.topics` - Topic configuration at startup
- `router.run.error` - Fatal errors

## Troubleshooting

### Router not starting

1. Check MQTT broker is running: `docker compose ps mosquitto`
2. Verify MQTT_URL environment variable
3. Check logs: `docker compose logs router`
4. Verify network connectivity: `ping mosquitto` (inside container)

### Messages not routing

1. Check service health: Monitor `system/health/*` topics
2. Verify topic configuration in environment
3. Enable DEBUG logging: `LOG_LEVEL=DEBUG`
4. Monitor MQTT traffic: `mosquitto_sub -t '#' -v`

### Streaming issues

1. Check `ROUTER_LLM_TTS_STREAM` is enabled
2. Verify `ROUTER_STREAM_*` configuration
3. Check LLM worker is publishing to `llm/stream`
4. Monitor TTS queue with `ROUTER_STREAM_QUEUE_OVERFLOW=block` to detect backpressure

### High latency

1. Check `ROUTER_STREAM_HANDLER_TIMEOUT` setting
2. Monitor queue size with metrics
3. Verify network latency to MQTT broker
4. Check service health states

## Performance

### Latency Targets

- STT → LLM request: <10ms
- LLM stream → TTS: <20ms per chunk
- Health ping processing: <5ms

### Throughput

Designed for:
- 10-30 messages/second sustained
- 100 messages/second burst (with queue overflow)

### Resource Usage

- Memory: ~50MB baseline
- CPU: <5% idle, <20% under load
- Network: Minimal (MQTT messages are small, <10KB each)

## References

- **Constitution**: `.specify/memory/constitution.md` - Architectural principles
- **Copilot Instructions**: `.github/copilot-instructions.md` - Development patterns
- **Contracts**: `packages/tars-contracts/` - Message schemas
- **Domain Logic**: `packages/tars-core/src/tars/domain/router/` - Router policies
- **Runtime**: `packages/tars-core/src/tars/runtime/` - Dispatcher and context

## Contributing

When modifying the router:

1. **Follow constitution** - Event-driven architecture, typed contracts, async-first
2. **Update tests** - Add/update tests for behavior changes
3. **Document MQTT changes** - Update this README for topic/schema changes
4. **Run checks** - `make check` must pass before commit
5. **Test integration** - Verify with full stack: `docker compose up`

The router is **critical infrastructure**. All changes should be:
- Small and focused (one behavior change per PR)
- Well-tested (unit + integration)
- Documented (README, docstrings)
- Reviewed carefully (router failures affect entire system)

## License

Part of the TARS voice assistant project.
