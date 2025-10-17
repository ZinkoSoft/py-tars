# MQTTClient API Reference

Complete API documentation for the centralized MQTT client module.

**Module**: `tars.adapters.mqtt_client`  
**Version**: 1.0.0  
**Python**: 3.11+

---

## Table of Contents

- [Classes](#classes)
  - [MQTTClient](#mqttclient)
  - [MQTTClientConfig](#mqttclientconfig)
  - [HealthPayload](#healthpayload)
  - [HeartbeatPayload](#heartbeatpayload)
  - [MessageDeduplicator](#messagededuplicator)
- [Type Aliases](#type-aliases)
- [Examples](#examples)

---

## Classes

### MQTTClient

The main MQTT client class providing connection management, publishing, and subscribing.

#### Constructor

```python
def __init__(
    mqtt_url: str,
    client_id: str,
    source_name: Optional[str] = None,
    enable_health: bool = False,
    enable_heartbeat: bool = False,
    heartbeat_interval: float = 30.0,
    dedupe_ttl: float = 0.0,
    dedupe_max_entries: int = 0,
    reconnect_min_delay: float = 1.0,
    reconnect_max_delay: float = 5.0,
)
```

**Parameters**:

- **mqtt_url** (`str`): MQTT broker URL (e.g., `"mqtt://localhost:1883"` or `"mqtt://user:pass@host:port"`)
- **client_id** (`str`): Unique client identifier for MQTT connection
- **source_name** (`Optional[str]`): Source name for envelope metadata (defaults to `client_id`)
- **enable_health** (`bool`): Enable health status publishing to `system/health/{client_id}` (default: `False`)
- **enable_heartbeat** (`bool`): Enable periodic heartbeat publishing (default: `False`)
- **heartbeat_interval** (`float`): Heartbeat interval in seconds, must be ≥1.0 (default: `30.0`)
- **dedupe_ttl** (`float`): Message deduplication time-to-live in seconds, 0=disabled (default: `0.0`)
- **dedupe_max_entries** (`int`): Maximum deduplication cache entries, required when `dedupe_ttl > 0` (default: `0`)
- **reconnect_min_delay** (`float`): Minimum reconnection delay in seconds (default: `1.0`)
- **reconnect_max_delay** (`float`): Maximum reconnection delay in seconds (default: `5.0`)

**Raises**:

- `ValueError`: If configuration validation fails

#### Class Method: from_env

```python
@classmethod
def from_env(cls) -> MQTTClient
```

Create MQTTClient from environment variables.

**Environment Variables**:

- `MQTT_URL` (required): MQTT broker URL
- `MQTT_CLIENT_ID` (required): Client identifier
- `MQTT_SOURCE_NAME` (optional): Source name for envelopes
- `MQTT_ENABLE_HEALTH` (optional): Enable health publishing (`"true"` / `"false"`)
- `MQTT_ENABLE_HEARTBEAT` (optional): Enable heartbeat (`"true"` / `"false"`)
- `MQTT_HEARTBEAT_INTERVAL` (optional): Heartbeat interval in seconds
- `MQTT_DEDUPE_TTL` (optional): Deduplication TTL in seconds
- `MQTT_DEDUPE_MAX_ENTRIES` (optional): Deduplication cache size
- `MQTT_RECONNECT_MIN_DELAY` (optional): Min reconnection delay
- `MQTT_RECONNECT_MAX_DELAY` (optional): Max reconnection delay

**Returns**: `MQTTClient` instance

**Raises**:

- `ValueError`: If required environment variables missing

**Example**:

```python
# Set environment variables
os.environ["MQTT_URL"] = "mqtt://localhost:1883"
os.environ["MQTT_CLIENT_ID"] = "my-service"

# Create client from environment
client = MQTTClient.from_env()
await client.connect()
```

#### Properties

##### client

```python
@property
def client(self) -> Optional[mqtt.Client]
```

Access underlying `asyncio_mqtt.Client` for advanced operations.

**Returns**: `mqtt.Client` if connected, `None` otherwise

**Example**:

```python
# Access underlying client for advanced features
underlying = client.client
if underlying:
    # Use asyncio-mqtt features directly
    await underlying.subscribe("custom/topic")
```

##### connected

```python
@property
def connected(self) -> bool
```

Check if client is currently connected to broker.

**Returns**: `True` if connected, `False` otherwise

#### Lifecycle Methods

##### connect

```python
async def connect(self) -> None
```

Connect to MQTT broker and start background tasks.

**Behavior**:

- Establishes connection to broker
- Starts message dispatch background task
- Starts heartbeat background task (if enabled)
- Publishes initial health status (if enabled)

**Raises**:

- `RuntimeError`: If connection fails

**Example**:

```python
client = MQTTClient("mqtt://localhost:1883", "my-service")
await client.connect()
print(f"Connected: {client.connected}")  # True
```

##### disconnect

```python
async def disconnect(self) -> None
```

Disconnect from MQTT broker gracefully.

**Behavior**:

- Publishes final health status (if enabled)
- Cancels background tasks
- Closes broker connection

**Note**: Prefer `shutdown()` for complete cleanup including health status

**Example**:

```python
await client.disconnect()
print(f"Connected: {client.connected}")  # False
```

##### shutdown

```python
async def shutdown(self) -> None
```

Gracefully shutdown client with proper cleanup.

**Behavior**:

- Publishes unhealthy status (if enabled)
- Cancels all background tasks
- Closes broker connection
- Sets shutdown flag

**Example**:

```python
try:
    await client.connect()
    # ... use client ...
finally:
    await client.shutdown()
```

#### Context Manager

The `MQTTClient` supports async context manager protocol for automatic lifecycle management:

```python
async with MQTTClient("mqtt://localhost:1883", "my-service") as client:
    # Auto-connect on enter
    await client.publish_event("test/topic", "test.event", {"data": "value"})
    # Auto-shutdown on exit
```

#### Publishing Methods

##### publish_event

```python
async def publish_event(
    self,
    topic: str,
    event_type: str,
    data: dict[str, Any] | BaseModel,
    *,
    correlation_id: Optional[str] = None,
    qos: int = 0,
    retain: bool = False,
) -> None
```

Publish event wrapped in Envelope to MQTT topic.

**Parameters**:

- **topic** (`str`): MQTT topic to publish to
- **event_type** (`str`): Event type identifier (e.g., `"stt.final"`, `"llm.response"`)
- **data** (`dict[str, Any] | BaseModel`): Event data (dict or Pydantic model)
- **correlation_id** (`Optional[str]`): Optional correlation ID for request tracing
- **qos** (`int`): MQTT QoS level (0, 1, or 2), default: `0`
- **retain** (`bool`): Whether to retain message on broker, default: `False`

**Raises**:

- `RuntimeError`: If not connected to broker

**Example**:

```python
# Publish with dict data
await client.publish_event(
    topic="stt/final",
    event_type="stt.final",
    data={"text": "hello world", "confidence": 0.95},
    correlation_id="req-123",
    qos=1,
)

# Publish with Pydantic model
from pydantic import BaseModel

class STTResult(BaseModel):
    text: str
    confidence: float

result = STTResult(text="hello world", confidence=0.95)
await client.publish_event(
    topic="stt/final",
    event_type="stt.final",
    data=result,
    qos=1,
)
```

##### publish_health

```python
async def publish_health(
    self,
    ok: bool,
    *,
    event: Optional[str] = None,
    error: Optional[str] = None,
) -> None
```

Publish health status to `system/health/{client_id}`.

**Parameters**:

- **ok** (`bool`): Health status (`True` = healthy, `False` = unhealthy)
- **event** (`Optional[str]`): Health event description (e.g., `"connected"`, `"ready"`)
- **error** (`Optional[str]`): Error message (only when `ok=False`)

**Behavior**:

- Published with QoS 1 (at-least-once delivery)
- Retained on broker (latest status always available)
- No-op if `enable_health=False`

**Raises**:

- `RuntimeError`: If not connected to broker

**Example**:

```python
# Publish healthy status
await client.publish_health(ok=True, event="ready")

# Publish unhealthy status with error
await client.publish_health(ok=False, error="Database connection failed")
```

#### Subscribing Methods

##### subscribe

```python
async def subscribe(
    self,
    topic: str,
    handler: Callable[[bytes], Awaitable[None]],
    qos: int = 0,
) -> None
```

Subscribe to MQTT topic with async message handler.

**Parameters**:

- **topic** (`str`): MQTT topic pattern (supports wildcards: `+` single-level, `#` multi-level)
- **handler** (`Callable[[bytes], Awaitable[None]]`): Async callback receiving message payload
- **qos** (`int`): MQTT QoS level (0, 1, or 2), default: `0`

**Behavior**:

- Registers handler for topic pattern
- Subscribes to broker
- Handlers are invoked for matching messages
- Handler errors are logged and isolated (don't crash dispatch loop)

**Raises**:

- `RuntimeError`: If not connected to broker

**Example**:

```python
from tars.contracts.envelope import Envelope

async def handle_event(payload: bytes) -> None:
    envelope = Envelope.model_validate_json(payload)
    print(f"Received: {envelope.type} - {envelope.data}")

# Single topic
await client.subscribe("events/my-topic", handle_event)

# Single-level wildcard (+)
await client.subscribe("events/+/status", handle_event)

# Multi-level wildcard (#)
await client.subscribe("events/#", handle_event, qos=1)
```

---

## MQTTClientConfig

Configuration model for MQTTClient (Pydantic BaseModel).

### Fields

```python
class MQTTClientConfig(BaseModel):
    mqtt_url: str
    client_id: str
    source_name: str
    enable_health: bool = False
    enable_heartbeat: bool = False
    heartbeat_interval: float = Field(default=30.0, ge=1.0)
    dedupe_ttl: float = Field(default=0.0, ge=0.0)
    dedupe_max_entries: int = Field(default=0, ge=0)
    reconnect_min_delay: float = Field(default=1.0, ge=0.1)
    reconnect_max_delay: float = Field(default=5.0, ge=0.5)
```

**Field Validation**:

- `heartbeat_interval`: Must be ≥ 1.0 seconds
- `reconnect_max_delay`: Must be ≥ `reconnect_min_delay`
- `dedupe_max_entries`: Must be > 0 when `dedupe_ttl > 0`

### Class Method: from_env

```python
@classmethod
def from_env(cls) -> MQTTClientConfig
```

Load configuration from environment variables.

See [MQTTClient.from_env](#class-method-from_env) for environment variable list.

---

## HealthPayload

Health status payload model (Pydantic BaseModel).

Published to `system/health/{client_id}` when `enable_health=True`.

### Fields

```python
class HealthPayload(BaseModel):
    ok: bool
    event: Optional[str] = None
    error: Optional[str] = None
    timestamp: float  # Unix timestamp
```

**Example**:

```json
{
  "ok": true,
  "event": "connected",
  "timestamp": 1697472000.123
}
```

---

## HeartbeatPayload

Heartbeat payload model (Pydantic BaseModel).

Published to `system/keepalive/{client_id}` when `enable_heartbeat=True`.

### Fields

```python
class HeartbeatPayload(BaseModel):
    ok: bool = True
    event: str = "heartbeat"
    timestamp: float  # Unix timestamp
```

**Example**:

```json
{
  "ok": true,
  "event": "heartbeat",
  "timestamp": 1697472000.123
}
```

---

## MessageDeduplicator

Internal class for message deduplication (not directly used by consumers).

Deduplicates messages by envelope ID using TTL-bound LRU cache.

### Constructor

```python
def __init__(self, ttl: float, max_entries: int)
```

### Methods

#### is_duplicate

```python
def is_duplicate(self, payload: bytes) -> bool
```

Check if message payload is a duplicate within TTL window.

**Parameters**:

- **payload** (`bytes`): Message payload bytes

**Returns**: `True` if duplicate, `False` if first occurrence or TTL expired

---

## Type Aliases

```python
# Message handler callback type
SubscriptionHandler = Callable[[bytes], Awaitable[None]]
```

---

## Examples

### Basic Usage

```python
import asyncio
from tars.adapters.mqtt_client import MQTTClient
from tars.contracts.envelope import Envelope

async def main():
    # Create and connect
    client = MQTTClient("mqtt://localhost:1883", "my-service", enable_health=True)
    await client.connect()
    
    # Publish event
    await client.publish_event(
        topic="test/topic",
        event_type="test.event",
        data={"message": "Hello MQTT!"},
        qos=1,
    )
    
    # Subscribe with handler
    async def handle_message(payload: bytes) -> None:
        envelope = Envelope.model_validate_json(payload)
        print(f"Received: {envelope.type}")
    
    await client.subscribe("test/#", handle_message)
    
    # Wait for messages
    await asyncio.sleep(5)
    
    # Shutdown
    await client.shutdown()

asyncio.run(main())
```

### Context Manager

```python
async def main():
    async with MQTTClient("mqtt://localhost:1883", "my-service") as client:
        await client.publish_event("test/topic", "test.event", {"data": "value"})
        # Auto-shutdown on exit
```

### Environment Configuration

```bash
# .env file
MQTT_URL=mqtt://user:pass@localhost:1883
MQTT_CLIENT_ID=my-service
MQTT_ENABLE_HEALTH=true
MQTT_ENABLE_HEARTBEAT=true
MQTT_HEARTBEAT_INTERVAL=30
MQTT_DEDUPE_TTL=5.0
MQTT_DEDUPE_MAX_ENTRIES=1000
```

```python
# Load from environment
client = MQTTClient.from_env()
await client.connect()
```

### Request-Response with Correlation ID

```python
import uuid
from asyncio import Future

# Request side
request_id = str(uuid.uuid4())
response_futures: dict[str, Future] = {}

async def handle_response(payload: bytes) -> None:
    envelope = Envelope.model_validate_json(payload)
    if envelope.correlate and envelope.correlate in response_futures:
        response_futures[envelope.correlate].set_result(envelope.data)

await client.subscribe("llm/response", handle_response)

# Send request
response_future = Future()
response_futures[request_id] = response_future

await client.publish_event(
    topic="llm/request",
    event_type="llm.request",
    data={"text": "What is the weather?"},
    correlation_id=request_id,
)

# Wait for response
response = await asyncio.wait_for(response_future, timeout=5.0)
print(f"Response: {response}")
```

### Wildcard Subscriptions

```python
# Single-level wildcard: matches one segment
await client.subscribe("sensors/+/temperature", handle_sensor)
# Matches: sensors/room1/temperature, sensors/room2/temperature
# Does NOT match: sensors/room1/humidity, sensors/room1/outdoor/temperature

# Multi-level wildcard: matches all remaining segments
await client.subscribe("sensors/#", handle_all_sensors)
# Matches: sensors/room1/temperature, sensors/room1/outdoor/temperature, sensors/anything/nested
```

### Heartbeat and Health

```python
# Enable heartbeat and health
client = MQTTClient(
    "mqtt://localhost:1883",
    "my-service",
    enable_health=True,
    enable_heartbeat=True,
    heartbeat_interval=30.0,  # Publish keepalive every 30s
)

await client.connect()

# Manual health updates
await client.publish_health(ok=True, event="service_ready")
# ... later ...
await client.publish_health(ok=False, error="Database connection lost")
```

### Message Deduplication

```python
# Enable deduplication with 5s TTL and 1000 entry cache
client = MQTTClient(
    "mqtt://localhost:1883",
    "my-service",
    dedupe_ttl=5.0,
    dedupe_max_entries=1000,
)

await client.connect()

# Duplicate messages (same envelope ID) within 5s are automatically filtered
```

### Direct Client Access

```python
# Access underlying asyncio-mqtt client for advanced features
client = MQTTClient("mqtt://localhost:1883", "my-service")
await client.connect()

underlying = client.client
if underlying:
    # Use asyncio-mqtt features directly
    async with underlying.messages() as messages:
        await underlying.subscribe("custom/topic")
        async for msg in messages:
            print(f"Raw message: {msg.topic} - {msg.payload}")
```

---

## Error Handling

### Connection Errors

```python
try:
    await client.connect()
except RuntimeError as e:
    logger.error(f"Connection failed: {e}")
```

### Publishing Without Connection

```python
client = MQTTClient("mqtt://localhost:1883", "my-service")
# NOT connected yet

try:
    await client.publish_event("topic", "event", {})  # RuntimeError
except RuntimeError:
    logger.error("Must connect before publishing")
```

### Handler Errors

Handler errors are automatically logged and isolated:

```python
async def buggy_handler(payload: bytes) -> None:
    raise ValueError("Oops!")  # Logged, doesn't crash dispatch loop

await client.subscribe("test/topic", buggy_handler)
# Dispatch loop continues processing other messages
```

---

## Best Practices

### 1. Use Context Manager for Lifecycle

```python
# ✅ GOOD: Auto-cleanup
async with MQTTClient.from_env() as client:
    await client.publish_event("topic", "event", {})

# ❌ BAD: Manual cleanup can be forgotten
client = MQTTClient.from_env()
await client.connect()
# ... might forget shutdown
```

### 2. Validate Envelopes in Handlers

```python
async def handle_event(payload: bytes) -> None:
    try:
        envelope = Envelope.model_validate_json(payload)
        # Process envelope.data
    except ValidationError as e:
        logger.error(f"Invalid envelope: {e}")
```

### 3. Use Correlation IDs for Request-Response

```python
# Always use correlation IDs for tracing requests
request_id = str(uuid.uuid4())
await client.publish_event(
    "llm/request",
    "llm.request",
    {"text": "..."},
    correlation_id=request_id,
)
```

### 4. Choose Appropriate QoS

- **QoS 0** (best-effort): High-frequency data, partials, logs
- **QoS 1** (at-least-once): Important events, commands, final results
- **QoS 2** (exactly-once): Critical transactions (rarely needed)

### 5. Enable Health and Heartbeat for Services

```python
# Production services should enable health and heartbeat
client = MQTTClient(
    mqtt_url,
    client_id,
    enable_health=True,
    enable_heartbeat=True,
    heartbeat_interval=30.0,
)
```

---

## Thread Safety

**Not thread-safe**. `MQTTClient` must be used within a single asyncio event loop.

For multi-threaded applications, create one `MQTTClient` per thread with its own event loop.

---

## Changelog

### v1.0.0 (2025-01-16)

- Initial release
- Core functionality: connect, disconnect, shutdown, publish_event, publish_health, subscribe
- Configuration via environment
- Automatic reconnection with exponential backoff
- Message deduplication
- Health status publishing
- Heartbeat with watchdog
- Context manager support
- Comprehensive type hints (mypy --strict compliant)

---

## See Also

- [Migration Guide](MIGRATION_GUIDE.md): Migrating from custom MQTT wrappers
- [Configuration Guide](CONFIGURATION.md): Environment variable reference
- [Quickstart](../specs/004-centralize-mqtt-client/quickstart.md): Usage patterns and examples
- [Envelope Contract](../src/tars/contracts/envelope.py): Message envelope schema
