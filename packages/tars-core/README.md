# tars-core

Shared runtime plumbing, MQTT adapters, and Pydantic contracts for the TARS stack.

This package is the canonical home for the `tars` namespace. It can be installed in
editable mode for local development:

```bash
pip install -e packages/tars-core
```

When building Docker images we will produce a wheel from this package and install it
into each service container.

## Quick Start: MQTT Client

The centralized `MQTTClient` enables new services to integrate MQTT in **<10 lines of code**:

### Minimal Example (7 LOC)

```python
from tars.adapters.mqtt_client import MQTTClient

# Create and connect
client = MQTTClient.from_env()  # Reads MQTT_URL, MQTT_CLIENT_ID from environment
await client.connect()

# Publish event
await client.publish_event("my/topic", "my.event.type", {"message": "Hello TARS!"})

# Subscribe to messages
async def handle_message(payload: bytes) -> None:
    print(f"Received: {payload}")

await client.subscribe("incoming/topic", handle_message)

# Cleanup
await client.shutdown()
```

### Environment Configuration

Configure via environment variables (see `.env.example`):

```bash
MQTT_URL=mqtt://user:pass@localhost:1883  # Required
MQTT_CLIENT_ID=my-service                  # Required
MQTT_SOURCE_NAME=my-service                # Optional (defaults to client_id)
MQTT_ENABLE_HEALTH=true                    # Optional (default: false)
MQTT_ENABLE_HEARTBEAT=true                 # Optional (default: false)
MQTT_HEARTBEAT_INTERVAL=30.0               # Optional (default: 30.0)
```

### Features

- **Auto-reconnection**: Handles network interruptions with exponential backoff
- **Health monitoring**: Publishes retained health status to `system/health/{source}`
- **Heartbeat**: Optional periodic heartbeat to indicate liveness
- **Message deduplication**: Filters duplicate messages by envelope ID
- **Wildcard subscriptions**: Supports MQTT `+` (single-level) and `#` (multi-level) wildcards
- **Envelope wrapping**: All messages wrapped in standard `Envelope` structure
- **Type safety**: Full Pydantic validation for configurations and messages
- **Observability**: Structured logging with correlation IDs

### Advanced: Context Manager

```python
from tars.adapters.mqtt_client import MQTTClient

async def main():
    async with MQTTClient.from_env() as client:
        # Automatically connects on enter, disconnects on exit
        await client.publish_event("status", "service.ready", {})
        
        async def handler(payload: bytes):
            print(f"Got: {payload}")
        
        await client.subscribe("commands/#", handler)
        
        # Run forever
        await asyncio.Event().wait()
```

### Advanced: Direct Instantiation

```python
from tars.adapters.mqtt_client import MQTTClient

client = MQTTClient(
    mqtt_url="mqtt://localhost:1883",
    client_id="my-service",
    source_name="my-service",
    enable_health=True,          # Publish health status
    enable_heartbeat=True,       # Send periodic heartbeats
    heartbeat_interval=30.0,     # Every 30 seconds
    dedupe_ttl=60.0,            # Deduplicate messages for 60s
    dedupe_max_entries=1000,    # Max 1000 cached message IDs
    keepalive=60,               # MQTT keepalive (seconds)
    reconnect_min_delay=1.0,    # Min reconnect delay
    reconnect_max_delay=60.0,   # Max reconnect delay
)

await client.connect()
# ... use client ...
await client.shutdown()
```

### Publishing Messages

#### Basic Event

```python
await client.publish_event(
    topic="events/user/login",
    event_type="user.login",
    data={"user_id": "123", "timestamp": time.time()},
)
```

#### With Correlation ID

```python
await client.publish_event(
    topic="llm/response",
    event_type="llm.completion",
    data={"reply": "Hello!"},
    correlation_id="request-456",  # Links response to request
)
```

#### With QoS and Retain

```python
await client.publish_event(
    topic="config/update",
    event_type="config.changed",
    data={"key": "value"},
    qos=1,      # At-least-once delivery
    retain=True,  # Retain for new subscribers
)
```

#### Pydantic Models

```python
from pydantic import BaseModel

class UserEvent(BaseModel):
    user_id: str
    action: str

await client.publish_event(
    topic="events/user",
    event_type="user.action",
    data=UserEvent(user_id="123", action="login"),  # Auto-serialized
)
```

### Health & Status

#### Publish Health

```python
# Publish healthy status with event
await client.publish_health(ok=True, event="startup_complete")

# Publish unhealthy status with error
await client.publish_health(ok=False, error="database_connection_failed")
```

Health messages are:
- Published to `system/health/{source}`
- **QoS 1** (at-least-once delivery)
- **Retained** (new subscribers see last status)
- Wrapped in standard `Envelope` with type `health.status`

### Subscribing to Messages

#### Basic Subscription

```python
async def handle_stt(payload: bytes) -> None:
    envelope = orjson.loads(payload)
    text = envelope["data"]["text"]
    print(f"Transcription: {text}")

await client.subscribe("stt/final", handle_stt)
```

#### Wildcard Subscriptions

```python
# Single-level wildcard (+) - matches one topic level
async def handle_health(payload: bytes) -> None:
    envelope = orjson.loads(payload)
    service = envelope["source"]
    ok = envelope["data"]["ok"]
    print(f"{service}: {'healthy' if ok else 'unhealthy'}")

await client.subscribe("system/health/+", handle_health)

# Multi-level wildcard (#) - matches multiple levels
async def handle_all_events(payload: bytes) -> None:
    envelope = orjson.loads(payload)
    print(f"Event: {envelope['type']}")

await client.subscribe("events/#", handle_all_events)
```

#### Error Handling in Handlers

```python
async def resilient_handler(payload: bytes) -> None:
    try:
        envelope = orjson.loads(payload)
        # Process message...
    except Exception as e:
        logger.error(f"Handler error: {e}")
        # Error is logged but doesn't crash dispatch loop

await client.subscribe("topic", resilient_handler)
```

### Message Envelope Structure

All published messages follow the `Envelope` contract:

```python
{
    "id": "a1b2c3d4e5f6...",           # Unique message ID (UUID hex)
    "type": "event.type",               # Event type string
    "ts": 1729123456.789,               # Unix timestamp (float)
    "source": "service-name",           # Source service identifier
    "data": {                           # Event-specific payload
        "key": "value",
        "nested": {"data": "here"}
    }
}
```

### Testing

See `tests/` for comprehensive examples:

- **Unit tests**: `tests/unit/test_mqtt_client_*.py` - Fast, isolated tests with mocks
- **Integration tests**: `tests/integration/test_end_to_end.py` - Real broker tests
- **Contract tests**: `tests/contract/test_envelope_schemas.py` - Schema validation

Run tests:

```bash
# Unit tests (fast, no broker needed)
pytest tests/unit/ -v

# Integration tests (requires Mosquitto broker)
docker compose -f ops/compose.yml up -d mosquitto
pytest tests/integration/ -v -m integration

# Contract tests (schema validation)
pytest tests/contract/ -v -m contract

# All tests
pytest tests/ -v
```

### Migration from Legacy MQTT Code

Migrating existing services typically reduces MQTT code by **50%+**. See the migration guide in `specs/004-centralize-mqtt-client/MIGRATION.md` for detailed steps.

Before (legacy pattern):

```python
# 40+ lines of boilerplate per service
import asyncio_mqtt as mqtt
from paho.mqtt import client as paho_mqtt

# Manual connection setup
mqtt_client = mqtt.Client(
    hostname="localhost",
    port=1883,
    username="user",
    password="pass",
    client_id="my-service",
)

# Manual message wrapping
envelope = Envelope.new(event_type="my.event", data={"key": "value"})
payload = orjson.dumps(envelope.model_dump())
await mqtt_client.publish("topic", payload)

# Manual subscription handling
async with mqtt_client.messages() as messages:
    await mqtt_client.subscribe("topic")
    async for msg in messages:
        # Manual dispatch logic...
```

After (centralized client):

```python
# 7 lines with centralized client
client = MQTTClient.from_env()
await client.connect()
await client.publish_event("topic", "my.event", {"key": "value"})
await client.subscribe("topic", handler)
await client.shutdown()
```

## Extension Patterns

The `MQTTClient` is designed for extension via **composition** rather than inheritance,
keeping the core module clean while allowing service-specific customization.

### Pattern 1: Domain-Specific Wrapper

Wrap `MQTTClient` with domain-specific convenience methods:

```python
class STTMQTTClient:
    """STT service-specific MQTT wrapper."""
    
    def __init__(self, mqtt_url: str, client_id: str):
        self._client = MQTTClient(mqtt_url, client_id)
    
    async def connect(self) -> None:
        await self._client.connect()
    
    async def publish_final_transcription(
        self,
        text: str,
        confidence: float,
        lang: str = "en",
    ) -> None:
        """Publish STT final result with domain-specific schema."""
        await self._client.publish_event(
            topic="stt/final",
            event_type="stt.final",
            data={
                "text": text,
                "confidence": confidence,
                "lang": lang,
                "is_final": True,
            },
            qos=1,
        )

# Usage
stt_client = STTMQTTClient("mqtt://localhost:1883", "stt-worker")
await stt_client.connect()
await stt_client.publish_final_transcription("hello world", 0.95)
```

**Benefits**:
- Domain methods instead of generic `publish_event()`
- Encapsulates topic/event_type conventions
- No pollution of core `MQTTClient` with service-specific vocabulary

### Pattern 2: Message Batching

Extend with batching to reduce publishing overhead for high-frequency events:

```python
from collections import defaultdict

class BatchingMQTTClient:
    """Batches messages before publishing."""
    
    def __init__(
        self,
        mqtt_url: str,
        client_id: str,
        batch_size: int = 10,
        batch_interval: float = 1.0,
    ):
        self._client = MQTTClient(mqtt_url, client_id)
        self._batches: dict[str, list[dict]] = defaultdict(list)
        self._batch_size = batch_size
        self._flush_task: Optional[asyncio.Task] = None
    
    async def connect(self) -> None:
        await self._client.connect()
        # Start background flush task
        self._flush_task = asyncio.create_task(self._flush_loop())
    
    async def publish_batched(self, topic: str, data: dict) -> None:
        """Add message to batch."""
        self._batches[topic].append(data)
        if len(self._batches[topic]) >= self._batch_size:
            await self._flush_topic(topic)
    
    async def _flush_topic(self, topic: str) -> None:
        """Flush batch for topic."""
        batch = self._batches[topic]
        self._batches[topic] = []
        await self._client.publish_event(
            f"{topic}/batch",
            f"{topic}.batch",
            {"items": batch, "count": len(batch)},
        )
    
    async def shutdown(self) -> None:
        # Flush remaining batches, cancel flush task, shutdown
        ...

# Usage
batch_client = BatchingMQTTClient("mqtt://localhost:1883", "sensor-service", batch_size=50)
await batch_client.connect()
for reading in sensor_readings:
    await batch_client.publish_batched("sensors/temperature", reading)
```

**Benefits**:
- Reduces MQTT overhead for high-frequency data
- Automatic batching with size and time limits
- Independent from core client

### Pattern 3: Direct Client Access

Use the `.client` property to access underlying `asyncio_mqtt.Client` for advanced features:

```python
class AdvancedMQTTClient:
    """Uses direct client access for custom features."""
    
    def __init__(self, mqtt_url: str, client_id: str):
        self._client = MQTTClient(mqtt_url, client_id)
    
    async def connect(self) -> None:
        await self._client.connect()
    
    async def subscribe_with_filter(
        self,
        topic: str,
        filter_fn: Callable[[Any], bool],
        handler: Callable[[bytes], None],
    ) -> None:
        """Subscribe with custom message filtering."""
        # Access underlying asyncio-mqtt client
        underlying = self._client.client
        await underlying.subscribe(topic)
        
        # Manual message iteration with filtering
        async def filtered_dispatch():
            async with underlying.messages() as messages:
                async for msg in messages:
                    if filter_fn(msg):
                        await handler(msg.payload)
        
        asyncio.create_task(filtered_dispatch())

# Usage
advanced = AdvancedMQTTClient("mqtt://localhost:1883", "advanced-service")
await advanced.connect()
await advanced.subscribe_with_filter(
    "sensors/#",
    lambda msg: "temperature" in msg.topic,  # Filter messages
    handler,
)
```

**Benefits**:
- Full access to asyncio-mqtt capabilities
- Custom subscription logic
- Low-level control when needed

### Extension Example

See `examples/custom_mqtt_wrapper.py` for complete working examples of all three patterns.

```bash
# Run extension examples (requires Mosquitto)
cd packages/tars-core
python -m examples.custom_mqtt_wrapper
```

## API Reference

Complete API documentation available in [`docs/API.md`](docs/API.md).

### Core Classes

- **`MQTTClient`**: Main MQTT client class
  - `from_env()`: Create client from environment variables
  - `connect()`: Connect to MQTT broker
  - `disconnect()`: Disconnect from broker
  - `shutdown()`: Graceful shutdown with cleanup
  - `publish_event()`: Publish event wrapped in Envelope
  - `publish_health()`: Publish health status
  - `subscribe()`: Subscribe to topic with handler
  - `.client`: Access underlying asyncio-mqtt client
  - `.connected`: Check connection status

- **`MQTTClientConfig`**: Configuration model (Pydantic)
  - `from_env()`: Load from environment variables
  - See [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) for all environment variables

- **`HealthPayload`**: Health status payload model
- **`HeartbeatPayload`**: Heartbeat payload model
- **`MessageDeduplicator`**: Message deduplication (internal)

### Quick Links

- 📖 [Complete API Reference](docs/API.md) - Detailed method signatures, parameters, examples
- ⚙️ [Configuration Guide](docs/CONFIGURATION.md) - All environment variables and validation rules
- 🔄 [Migration Guide](docs/MIGRATION_GUIDE.md) - Migrating from custom MQTT wrappers
- 🚀 [Quickstart](../../specs/004-centralize-mqtt-client/quickstart.md) - Usage patterns and examples

## Development

### Running Tests

```bash
# Install dev dependencies
pip install -e "packages/tars-core[dev]"

# Run all checks
make -C packages/tars-core check  # fmt + lint + test

# Individual targets
make -C packages/tars-core fmt    # Format with ruff + black
make -C packages/tars-core lint   # Lint with ruff + mypy
make -C packages/tars-core test   # Run pytest with coverage
```

### Adding New Adapters

Follow the pattern in `src/tars/adapters/`:

1. Create typed configuration model (Pydantic)
2. Implement adapter with async methods
3. Write unit tests first (TDD)
4. Add integration tests if needed
5. Update this README with usage example

