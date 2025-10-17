# Quickstart: Centralized MQTT Client

**Feature**: Centralized MQTT Client  
**Branch**: `004-centralize-mqtt-client`  
**Date**: 2025-10-16

## Overview

This guide shows you how to use the centralized MQTT client module in your py-tars services. The module eliminates boilerplate connection management, provides automatic reconnection, and enforces Envelope contract compliance.

---

## Installation

The centralized MQTT client is part of the `tars-core` package:

```bash
# Already included in tars-core dependencies
pip install -e packages/tars-core
```

---

## Basic Usage

### 1. Minimal Example (Publish Only)

```python
import asyncio
from tars.adapters.mqtt_client import MQTTClient, MQTTClientConfig

async def main():
    # Load configuration from environment
    config = MQTTClientConfig.from_env()
    
    # Create client
    client = MQTTClient(
        mqtt_url=config.mqtt_url,
        client_id="tars-my-service",
    )
    
    # Connect to broker
    await client.connect()
    
    # Publish event
    await client.publish_event(
        topic="my/topic",
        event_type="my.event",
        data={"message": "Hello MQTT!"},
    )
    
    # Graceful shutdown
    await client.shutdown()

asyncio.run(main())
```

### 2. Subscribe to Topics

```python
from tars.adapters.mqtt_client import MQTTClient
from tars.contracts.envelope import Envelope

async def handle_message(payload: bytes) -> None:
    """Handler for received messages."""
    envelope = Envelope.model_validate_json(payload)
    print(f"Received {envelope.type}: {envelope.data}")

async def main():
    client = MQTTClient(
        mqtt_url="mqtt://localhost:1883",
        client_id="tars-subscriber",
    )
    
    await client.connect()
    
    # Subscribe to topics
    await client.subscribe("events/#", handle_message)
    await client.subscribe("commands/+", handle_message)
    
    # Keep running
    await asyncio.Event().wait()  # Wait forever

asyncio.run(main())
```

### 3. Using Context Manager

```python
async def main():
    async with MQTTClient(
        mqtt_url="mqtt://localhost:1883",
        client_id="tars-service",
    ) as client:
        await client.subscribe("my/topic", my_handler)
        await asyncio.sleep(3600)  # Run for 1 hour
    # Automatic shutdown when exiting context
```

---

## Configuration

### Environment Variables

Set these in your `.env` file or environment:

```bash
# Required
MQTT_URL=mqtt://user:password@localhost:1883
MQTT_CLIENT_ID=tars-my-service

# Optional
MQTT_SOURCE_NAME=my-service  # Defaults to client_id
MQTT_KEEPALIVE=60  # MQTT keepalive interval (seconds)

# Health Publishing (optional)
MQTT_ENABLE_HEALTH=true
# Publishes to system/health/{client_id} on connect/disconnect

# Application Heartbeat (optional)
MQTT_ENABLE_HEARTBEAT=true
MQTT_HEARTBEAT_INTERVAL=5.0  # Seconds
# Publishes to system/keepalive/{client_id} periodically

# Deduplication (optional)
MQTT_DEDUPE_TTL=30.0  # Seconds (0=disabled)
MQTT_DEDUPE_MAX_ENTRIES=2048  # Max cache size

# Reconnection (optional)
MQTT_RECONNECT_MIN_DELAY=0.5  # Seconds
MQTT_RECONNECT_MAX_DELAY=5.0  # Seconds
```

### Programmatic Configuration

```python
from tars.adapters.mqtt_client import MQTTClient

client = MQTTClient(
    mqtt_url="mqtt://localhost:1883",
    client_id="tars-custom",
    source_name="custom-worker",
    keepalive=30,
    enable_health=True,
    enable_heartbeat=True,
    heartbeat_interval=10.0,
    dedupe_ttl=60.0,
    dedupe_max_entries=4096,
    reconnect_min_delay=1.0,
    reconnect_max_delay=10.0,
)
```

---

## Publishing Events

### Basic Publishing

```python
await client.publish_event(
    topic="stt/final",
    event_type="stt.final",
    data={"text": "transcribed text", "confidence": 0.95},
)
```

### Publishing with Correlation ID

```python
await client.publish_event(
    topic="llm/response",
    event_type="llm.response",
    data={"reply": "Hello!"},
    correlation_id=request_id,  # For request tracing
)
```

### Publishing with QoS and Retain

```python
# Critical command (QoS 1, not retained)
await client.publish_event(
    topic="tts/say",
    event_type="tts.say",
    data={"text": "Shutdown initiated"},
    qos=1,
    retain=False,
)

# State that should persist (QoS 1, retained)
await client.publish_event(
    topic="system/config",
    event_type="config.update",
    data={"mode": "production"},
    qos=1,
    retain=True,
)
```

### Publishing with Pydantic Models

```python
from pydantic import BaseModel

class STTFinal(BaseModel):
    text: str
    confidence: float
    lang: str = "en"

# Data can be dict or Pydantic model
result = STTFinal(text="hello", confidence=0.98)
await client.publish_event(
    topic="stt/final",
    event_type="stt.final",
    data=result,  # Automatically serialized
)
```

---

## Subscribing to Topics

### Topic-Specific Handler

```python
async def handle_wake_event(payload: bytes) -> None:
    envelope = Envelope.model_validate_json(payload)
    wake_word = envelope.data.get("wake_word")
    print(f"Wake word detected: {wake_word}")

await client.subscribe("wake/event", handle_wake_event)
```

### Multiple Topics with Same Handler

```python
async def handle_all_events(payload: bytes) -> None:
    envelope = Envelope.model_validate_json(payload)
    print(f"Event: {envelope.type}")

# Subscribe to multiple topics
await client.subscribe("stt/#", handle_all_events)
await client.subscribe("llm/#", handle_all_events)
await client.subscribe("tts/#", handle_all_events)
```

### Wildcard Subscriptions

```python
# Single-level wildcard (+)
await client.subscribe("system/health/+", health_handler)
# Matches: system/health/stt, system/health/llm, etc.

# Multi-level wildcard (#)
await client.subscribe("events/#", event_handler)
# Matches: events/user, events/user/login, events/system/startup, etc.
```

### Handler Error Isolation

```python
async def safe_handler(payload: bytes) -> None:
    try:
        # Your processing logic
        envelope = Envelope.model_validate_json(payload)
        process(envelope.data)
    except Exception as e:
        # Errors are logged and isolated
        # Other handlers continue to work
        logger.error("Handler error: %s", e)

# Errors in handlers don't crash the dispatch loop
await client.subscribe("my/topic", safe_handler)
```

---

## Health Status

### Enable Health Publishing

```python
client = MQTTClient(
    mqtt_url="mqtt://localhost:1883",
    client_id="tars-stt",
    enable_health=True,  # Enable health publishing
)
```

### Publish Health Events

```python
# Service ready
await client.publish_health(ok=True, event="ready")

# Service reconnected
await client.publish_health(ok=True, event="reconnected")

# Service shutting down
await client.publish_health(ok=False, event="shutdown")

# Service error
await client.publish_health(ok=False, error="Database connection lost")
```

Health messages are published to `system/health/{client_id}` with QoS 1 and retain=True.

---

## Application Heartbeat

### Enable Heartbeat

```python
client = MQTTClient(
    mqtt_url="mqtt://localhost:1883",
    client_id="tars-worker",
    enable_heartbeat=True,
    heartbeat_interval=5.0,  # Publish every 5 seconds
)

await client.connect()
# Heartbeat automatically starts publishing to system/keepalive/{client_id}
```

### Heartbeat Watchdog

The heartbeat includes a watchdog that triggers reconnection if heartbeat publishing fails 3x consecutively. This detects stale connections that MQTT keepalive might miss.

---

## Message Deduplication

### Enable Deduplication

```python
client = MQTTClient(
    mqtt_url="mqtt://localhost:1883",
    client_id="tars-dedupe",
    dedupe_ttl=30.0,  # Keep messages in cache for 30 seconds
    dedupe_max_entries=2048,  # Max 2048 cached message IDs
)
```

### How Deduplication Works

Messages are deduplicated based on Envelope ID:
- Key format: `{event_type}|{envelope_id}|seq={seq}` (for sequential messages)
- Key format: `{event_type}|{envelope_id}|hash={digest}` (for unordered messages)
- Cache is TTL-bound and size-limited
- Duplicate messages are silently skipped (logged at DEBUG level)

### When to Use Deduplication

- **Use deduplication** for non-idempotent operations (e.g., database writes, API calls)
- **Skip deduplication** for idempotent operations (e.g., cache updates, state overwrites)

---

## Reconnection Handling

### Automatic Reconnection

Reconnection is automatic with exponential backoff:

```python
client = MQTTClient(
    mqtt_url="mqtt://localhost:1883",
    client_id="tars-resilient",
    reconnect_min_delay=0.5,  # Start with 0.5s delay
    reconnect_max_delay=5.0,  # Cap at 5s delay
)

# Connection lost → automatic reconnection
# Delay: 0.5s → 1s → 2s → 4s → 5s (capped)
```

### Reconnection Behavior

- All subscriptions are automatically re-established
- Background tasks (dispatch, heartbeat) resume
- Health status is re-published (if enabled)
- No manual intervention required

---

## Graceful Shutdown

### Using shutdown() Method

```python
async def main():
    client = MQTTClient("mqtt://localhost:1883", "tars-service")
    await client.connect()
    
    try:
        # Service logic
        await run_service()
    finally:
        # Always shutdown gracefully
        await client.shutdown()
```

### Using Context Manager

```python
async def main():
    async with MQTTClient("mqtt://localhost:1883", "tars-service") as client:
        await run_service()
    # Automatic shutdown on exit
```

### Shutdown Sequence

1. Publish health(ok=False, event="shutdown") if enabled
2. Cancel background tasks (dispatch, heartbeat)
3. Wait up to 5 seconds for tasks to complete
4. Disconnect from MQTT broker
5. Clean up resources

---

## Common Patterns

### 1. Request-Response with Correlation ID

```python
import uuid

# Request side
request_id = str(uuid.uuid4())
await client.publish_event(
    topic="llm/request",
    event_type="llm.request",
    data={"text": "What is the weather?"},
    correlation_id=request_id,
)

# Response handler
pending_requests = {}

async def handle_response(payload: bytes) -> None:
    envelope = Envelope.model_validate_json(payload)
    req_id = envelope.correlate
    if req_id in pending_requests:
        future = pending_requests.pop(req_id)
        future.set_result(envelope.data)

await client.subscribe("llm/response", handle_response)
```

### 2. Service with Multiple Handlers

```python
class MyService:
    def __init__(self, mqtt_url: str):
        self.client = MQTTClient(
            mqtt_url=mqtt_url,
            client_id="tars-my-service",
            enable_health=True,
        )
    
    async def handle_command(self, payload: bytes) -> None:
        envelope = Envelope.model_validate_json(payload)
        # Process command
    
    async def handle_event(self, payload: bytes) -> None:
        envelope = Envelope.model_validate_json(payload)
        # Process event
    
    async def run(self) -> None:
        await self.client.connect()
        await self.client.subscribe("commands/#", self.handle_command)
        await self.client.subscribe("events/#", self.handle_event)
        await self.client.publish_health(ok=True, event="ready")
        
        try:
            await asyncio.Event().wait()  # Run forever
        finally:
            await self.client.shutdown()
```

### 3. Streaming Data

```python
# High-frequency streaming (use QoS 0)
async def stream_partials():
    while streaming:
        partial_text = await get_partial_transcription()
        await client.publish_event(
            topic="stt/partial",
            event_type="stt.partial",
            data={"text": partial_text, "is_final": False},
            qos=0,  # Best-effort for streams
        )
        await asyncio.sleep(0.1)  # 10 messages/sec
```

### 4. Extending the Client

```python
class CustomMQTTClient:
    """Service-specific wrapper around centralized client."""
    
    def __init__(self, mqtt_url: str):
        self.client = MQTTClient(
            mqtt_url=mqtt_url,
            client_id="tars-custom",
            enable_health=True,
        )
        self.cache = {}
    
    async def connect(self) -> None:
        await self.client.connect()
        await self.client.subscribe("cache/update", self._handle_cache)
    
    async def _handle_cache(self, payload: bytes) -> None:
        envelope = Envelope.model_validate_json(payload)
        key = envelope.data.get("key")
        value = envelope.data.get("value")
        self.cache[key] = value
    
    async def publish_with_cache(self, topic: str, event_type: str, data: dict) -> None:
        """Custom method combining publish + cache update."""
        await self.client.publish_event(topic, event_type, data)
        cache_key = f"{topic}:{event_type}"
        self.cache[cache_key] = data
```

---

## Migrating from Custom MQTT Wrappers

### Before (Custom Wrapper)

```python
# Old pattern in apps/stt-worker/src/stt_worker/mqtt_utils.py
from stt_worker.mqtt_utils import MQTTClientWrapper

mqtt = MQTTClientWrapper(MQTT_URL, "tars-stt")
await mqtt.connect()
await mqtt.subscribe_stream("wake/event", handle_wake)
await mqtt.safe_publish("stt/final", {"text": "hello"}, retain=False)
await mqtt.disconnect()
```

### After (Centralized Client)

```python
# New pattern using centralized client
from tars.adapters.mqtt_client import MQTTClient

client = MQTTClient(MQTT_URL, "tars-stt", enable_health=True)
await client.connect()
await client.subscribe("wake/event", handle_wake)
await client.publish_event(
    topic="stt/final",
    event_type="stt.final",
    data={"text": "hello"},
)
await client.shutdown()
```

### Migration Checklist

- [ ] Replace custom wrapper import with `from tars.adapters.mqtt_client import MQTTClient`
- [ ] Update `connect()` calls (no parameters needed)
- [ ] Replace `safe_publish()` with `publish_event(topic, event_type, data)`
- [ ] Replace `subscribe_stream()` with `subscribe(topic, handler)`
- [ ] Replace `disconnect()` with `shutdown()`
- [ ] Enable health publishing if service had custom health logic
- [ ] Update tests to mock centralized client

---

## Testing

### Test-Driven Development Workflow

**CRITICAL**: All implementation follows strict TDD - tests written BEFORE code.

#### TDD Process for New Features

```python
# Step 1: Write test first (RED)
# File: tests/unit/test_mqtt_client_config.py

import pytest
from tars.adapters.mqtt_client import MQTTClientConfig

def test_from_env_parses_mqtt_url():
    """Test that MQTTClientConfig.from_env() parses MQTT_URL correctly."""
    import os
    os.environ["MQTT_URL"] = "mqtt://user:pass@localhost:1883"
    os.environ["MQTT_CLIENT_ID"] = "test-client"
    
    config = MQTTClientConfig.from_env()
    
    assert config.mqtt_url == "mqtt://user:pass@localhost:1883"
    assert config.client_id == "test-client"

# Step 2: Run test (should FAIL - ImportError or AttributeError)
# $ pytest tests/unit/test_mqtt_client_config.py::test_from_env_parses_mqtt_url
# Expected: FAILED (class doesn't exist yet)

# Step 3: Implement minimum code to pass (GREEN)
# File: src/tars/adapters/mqtt_client.py

from pydantic import BaseModel

class MQTTClientConfig(BaseModel):
    mqtt_url: str
    client_id: str
    
    @classmethod
    def from_env(cls) -> "MQTTClientConfig":
        import os
        return cls(
            mqtt_url=os.environ["MQTT_URL"],
            client_id=os.environ["MQTT_CLIENT_ID"],
        )

# Step 4: Run test again (should PASS)
# $ pytest tests/unit/test_mqtt_client_config.py::test_from_env_parses_mqtt_url
# Expected: PASSED

# Step 5: Refactor while keeping tests green
# Add validation, defaults, etc. - run tests after each change
```

### Mocking for Unit Tests

```python
from unittest.mock import AsyncMock, MagicMock
import pytest

@pytest.fixture
def mock_mqtt_client(mocker):
    """Mock centralized MQTT client."""
    client = MagicMock()
    client.connect = AsyncMock()
    client.publish_event = AsyncMock()
    client.subscribe = AsyncMock()
    client.shutdown = AsyncMock()
    client.connected = True
    return client

async def test_my_service(mock_mqtt_client):
    service = MyService(client=mock_mqtt_client)
    await service.run()
    
    # Verify MQTT operations
    mock_mqtt_client.connect.assert_called_once()
    mock_mqtt_client.publish_event.assert_called_with(
        topic="my/topic",
        event_type="my.event",
        data={"key": "value"},
    )
```

### Integration Testing with Mosquitto

```python
import pytest
from testcontainers.core.container import DockerContainer

@pytest.fixture(scope="session")
def mosquitto_broker():
    """Start Mosquitto broker for integration tests."""
    container = DockerContainer("eclipse-mosquitto:latest")
    container.with_exposed_ports(1883)
    with container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(1883)
        yield f"mqtt://{host}:{port}"

async def test_integration(mosquitto_broker):
    client = MQTTClient(mosquitto_broker, "test-client")
    await client.connect()
    
    messages = []
    async def handler(payload: bytes) -> None:
        messages.append(payload)
    
    await client.subscribe("test/topic", handler)
    await client.publish_event("test/topic", "test.event", {"msg": "hi"})
    
    await asyncio.sleep(0.1)  # Wait for message
    assert len(messages) == 1
    
    await client.shutdown()
```

### Example: Writing Tests Before Implementation

**Scenario**: Adding deduplication feature to MQTTClient

```python
# Step 1: Write test defining expected behavior (RED)
# File: tests/unit/test_message_deduplicator.py

import pytest
from tars.adapters.mqtt_client import MessageDeduplicator
from tars.contracts.envelope import Envelope
import orjson

def test_is_duplicate_returns_false_for_new_message():
    """First occurrence of message should not be marked as duplicate."""
    deduplicator = MessageDeduplicator(ttl=30.0, max_entries=100)
    
    envelope = Envelope.new(event_type="test.event", data={"key": "value"})
    payload = orjson.dumps(envelope.model_dump())
    
    result = deduplicator.is_duplicate(payload)
    
    assert result is False  # First time seeing this message

def test_is_duplicate_returns_true_for_repeat_message():
    """Second occurrence of same message should be marked as duplicate."""
    deduplicator = MessageDeduplicator(ttl=30.0, max_entries=100)
    
    envelope = Envelope.new(event_type="test.event", data={"key": "value"})
    payload = orjson.dumps(envelope.model_dump())
    
    # First call
    deduplicator.is_duplicate(payload)
    
    # Second call with same message
    result = deduplicator.is_duplicate(payload)
    
    assert result is True  # Duplicate detected

# Step 2: Run tests (FAIL)
# $ pytest tests/unit/test_message_deduplicator.py
# Expected: ImportError (MessageDeduplicator doesn't exist)

# Step 3: Implement to make tests pass (GREEN)
# File: src/tars/adapters/mqtt_client.py

from collections import OrderedDict
import time

class MessageDeduplicator:
    def __init__(self, *, ttl: float, max_entries: int) -> None:
        self._ttl = ttl
        self._max_entries = max_entries
        self._seen: OrderedDict[str, float] = OrderedDict()
    
    def is_duplicate(self, payload: bytes) -> bool:
        message_id = self._extract_message_id(payload)
        if not message_id:
            return False
        
        now = time.monotonic()
        if message_id in self._seen:
            self._seen.move_to_end(message_id)
            self._seen[message_id] = now
            return True
        
        self._seen[message_id] = now
        if len(self._seen) > self._max_entries:
            self._seen.popitem(last=False)
        return False
    
    def _extract_message_id(self, payload: bytes) -> str | None:
        try:
            envelope = Envelope.model_validate_json(payload)
            return f"{envelope.type}|{envelope.id}"
        except Exception:
            return None

# Step 4: Run tests (PASS)
# $ pytest tests/unit/test_message_deduplicator.py
# Expected: 2 passed

# Step 5: Add more tests for edge cases
def test_ttl_evicts_expired_entries():
    """Entries older than TTL should be evicted from cache."""
    deduplicator = MessageDeduplicator(ttl=1.0, max_entries=100)
    
    envelope = Envelope.new(event_type="test.event", data={"key": "value"})
    payload = orjson.dumps(envelope.model_dump())
    
    # First call
    assert deduplicator.is_duplicate(payload) is False
    
    # Wait for TTL to expire
    import time
    time.sleep(1.5)
    
    # Should not be duplicate anymore (evicted)
    assert deduplicator.is_duplicate(payload) is False

# Step 6: Implement TTL eviction (GREEN)
# Add _evict_expired() method and call it in is_duplicate()
```

### Test Organization by Entity

Each data model entity has dedicated test file:

```
tests/
├── unit/
│   ├── test_mqtt_client_config.py       # MQTTClientConfig tests
│   ├── test_connection_params.py        # ConnectionParams tests
│   ├── test_message_deduplicator.py     # MessageDeduplicator tests
│   ├── test_mqtt_client_lifecycle.py    # connect/disconnect/shutdown
│   ├── test_mqtt_client_publishing.py   # publish_event/publish_health
│   └── test_mqtt_client_subscribing.py  # subscribe/handler dispatch
├── integration/
│   ├── test_end_to_end.py               # Full publish/subscribe flow
│   ├── test_reconnection.py             # Connection resilience
│   └── test_deduplication.py            # Dedupe with real messages
└── contract/
    ├── test_envelope_schemas.py         # Envelope validation
    └── test_topic_patterns.py           # Topic compliance
```

### Coverage Requirements

Before marking implementation complete:

- [ ] **100% coverage** of public methods (unit tests)
- [ ] **All message flows** covered (integration tests)
- [ ] **All Envelope schemas** validated (contract tests)
- [ ] **All async methods** tested with pytest-asyncio
- [ ] **All error paths** tested (exceptions, timeouts, failures)

```bash
# Check coverage
pytest --cov=tars.adapters.mqtt_client --cov-report=html

# Coverage must be 100% for:
# - MQTTClientConfig
# - ConnectionParams  
# - MessageDeduplicator
# - MQTTClient (all public methods)
```

---

## Troubleshooting

### Connection Failures

**Problem**: `ConnectionError: Failed to connect to MQTT broker`

**Solutions**:
- Verify MQTT_URL format: `mqtt://user:password@host:port`
- Check broker is running: `docker compose ps mosquitto`
- Verify network connectivity: `ping <broker_host>`
- Check credentials in `ops/passwd`

### Messages Not Received

**Problem**: Subscription handler not being called

**Solutions**:
- Verify client is connected: `client.connected`
- Check topic subscription: ensure wildcards are correct
- Enable DEBUG logging: `logging.getLogger("tars.adapters.mqtt_client").setLevel(logging.DEBUG)`
- Check broker logs: `docker compose logs mosquitto`

### Duplicate Messages

**Problem**: Handler called multiple times for same message

**Solutions**:
- Enable deduplication: `dedupe_ttl=30.0, dedupe_max_entries=2048`
- Make handler idempotent (safe to call multiple times)
- Check if multiple clients have same client_id (broker kicks old client)

### High Memory Usage

**Problem**: Client consuming excessive memory

**Solutions**:
- Reduce `dedupe_max_entries` (default 2048)
- Reduce `dedupe_ttl` (default 30s)
- Limit number of subscriptions (<1000 topics)
- Profile handler functions for memory leaks

---

## Best Practices

### 1. Client ID Naming

```python
# Good: Unique per service, descriptive
client_id = "tars-stt"
client_id = "tars-llm-worker-1"
client_id = f"tars-memory-{instance_id}"

# Bad: Generic, conflicts possible
client_id = "client"
client_id = "mqtt"
```

### 2. QoS Selection

```python
# QoS 0: High-frequency streams, loss acceptable
await client.publish_event("stt/partial", "stt.partial", data, qos=0)

# QoS 1: Critical commands/responses, must deliver
await client.publish_event("tts/say", "tts.say", data, qos=1)

# QoS 2: Rarely needed (use QoS 1 instead)
```

### 3. Error Handling

```python
async def safe_handler(payload: bytes) -> None:
    """Always handle errors in handlers."""
    try:
        envelope = Envelope.model_validate_json(payload)
        await process(envelope.data)
    except ValidationError as e:
        logger.error("Invalid envelope: %s", e)
    except Exception as e:
        logger.error("Handler error: %s", e, exc_info=True)
```

### 4. Graceful Shutdown

```python
async def main():
    client = MQTTClient(...)
    await client.connect()
    
    try:
        await run_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await client.shutdown()
```

### 5. Logging

```python
import logging

# Enable MQTT client debug logs
logging.getLogger("tars.adapters.mqtt_client").setLevel(logging.DEBUG)

# Correlation IDs in logs
logger.info("Processing request %s", correlation_id)
```

---

## Next Steps

- **Implementation**: See `packages/tars-core/src/tars/adapters/mqtt_client.py`
- **API Contract**: See `specs/004-centralize-mqtt-client/contracts/mqtt_client_api.yaml`
- **Data Models**: See `specs/004-centralize-mqtt-client/data-model.md`
- **Migration Guide**: See service-specific migration documentation in each app's README
