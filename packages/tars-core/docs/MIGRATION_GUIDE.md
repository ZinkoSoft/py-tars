# Migration Guide: Centralized MQTT Client

This guide helps you migrate existing py-tars services from legacy MQTT patterns to the centralized `MQTTClient` in `tars-core`.

**Expected Result**: 50%+ reduction in MQTT-related code with zero behavioral changes.

---

## Table of Contents

1. [Quick Migration Checklist](#quick-migration-checklist)
2. [Before & After Comparison](#before--after-comparison)
3. [Step-by-Step Migration](#step-by-step-migration)
4. [Common Patterns](#common-patterns)
5. [Troubleshooting](#troubleshooting)
6. [Service-Specific Examples](#service-specific-examples)

---

## Quick Migration Checklist

- [ ] Read this guide completely
- [ ] Identify all MQTT usage in your service (connection, publish, subscribe)
- [ ] Update `pyproject.toml` to depend on `tars-core` with MQTT client
- [ ] Replace custom MQTT wrapper/utils with `from tars.adapters.mqtt_client import MQTTClient`
- [ ] Update environment variables (see [Configuration](#configuration))
- [ ] Replace connection logic with `MQTTClient.from_env()` or direct instantiation
- [ ] Replace publish calls with `client.publish_event()`
- [ ] Replace subscription logic with `client.subscribe()`
- [ ] Update shutdown/cleanup to use `client.shutdown()`
- [ ] Run all existing tests to verify no behavioral changes
- [ ] Remove old MQTT wrapper files
- [ ] Update service README with new usage

---

## Before & After Comparison

### Connection Setup

**Before** (40+ lines):
```python
# apps/memory-worker/src/memory_worker/mqtt_client.py
import asyncio
from typing import Optional
import asyncio_mqtt as mqtt
from paho.mqtt import client as paho_mqtt
import orjson
from tars.contracts.envelope import Envelope

class MQTTClientWrapper:
    def __init__(self, broker_host: str, broker_port: int, client_id: str):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client_id = client_id
        self._client: Optional[mqtt.Client] = None
        self._connected = False
    
    async def connect(self):
        self._client = mqtt.Client(
            hostname=self.broker_host,
            port=self.broker_port,
            client_id=self.client_id,
        )
        await self._client.__aenter__()
        self._connected = True
    
    async def disconnect(self):
        if self._client and self._connected:
            await self._client.__aexit__(None, None, None)
            self._connected = False
```

**After** (3 lines):
```python
from tars.adapters.mqtt_client import MQTTClient

client = MQTTClient.from_env()  # Reads MQTT_URL, MQTT_CLIENT_ID
await client.connect()
```

**Savings**: 37 lines removed (~92% reduction)

---

### Publishing Messages

**Before** (8-12 lines per publish):
```python
# Manual envelope wrapping + serialization
envelope = Envelope.new(
    event_type="memory.query.result",
    data={
        "query": query_text,
        "results": results,
    },
    correlate=request_id,
)
payload = orjson.dumps(envelope.model_dump())
await self._client.publish("memory/results", payload, qos=1)
```

**After** (1 line):
```python
await client.publish_event(
    "memory/results",
    "memory.query.result",
    {"query": query_text, "results": results},
    correlation_id=request_id,
    qos=1,
)
```

**Savings**: 7-11 lines removed per publish call

---

### Subscribing to Messages

**Before** (20-30 lines):
```python
# Manual subscription + message loop
async with self._client.messages() as messages:
    await self._client.subscribe("memory/query", qos=1)
    
    async for msg in messages:
        if msg.topic == "memory/query":
            try:
                payload = orjson.loads(msg.payload)
                envelope = Envelope(**payload)
                
                # Process message...
                await self._handle_query(envelope.data)
                
            except Exception as e:
                logger.error(f"Message processing error: {e}")
                # Continue processing other messages
```

**After** (3-5 lines):
```python
async def handle_query(payload: bytes) -> None:
    envelope = orjson.loads(payload)
    await self._process_query(envelope["data"])

await client.subscribe("memory/query", handle_query, qos=1)
```

**Savings**: 15-25 lines removed per subscription

---

### Health & Status Publishing

**Before** (10-15 lines):
```python
# Manual health message
health_envelope = Envelope.new(
    event_type="health.status",
    data={"ok": True, "event": "startup_complete"},
)
health_payload = orjson.dumps(health_envelope.model_dump())
await self._client.publish(
    f"system/health/{self.client_id}",
    health_payload,
    qos=1,
    retain=True,
)
```

**After** (1 line):
```python
await client.publish_health(ok=True, event="startup_complete")
```

**Savings**: 9-14 lines removed

---

### Shutdown/Cleanup

**Before** (5-10 lines):
```python
async def shutdown(self):
    # Publish shutdown health
    health_envelope = Envelope.new(
        event_type="health.status",
        data={"ok": False, "event": "shutting_down"},
    )
    await self._client.publish(...)
    
    # Cleanup
    await self._client.disconnect()
```

**After** (1 line):
```python
await client.shutdown()  # Automatically publishes shutdown health if enabled
```

**Savings**: 4-9 lines removed

---

## Step-by-Step Migration

### Step 1: Update Dependencies

**pyproject.toml**:
```toml
[project]
dependencies = [
    "tars-core",  # Add this (includes MQTT client)
    # Remove: "asyncio-mqtt", "paho-mqtt" if they were standalone
]
```

### Step 2: Update Environment Variables

**Old** (per-service custom):
```bash
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_CLIENT_ID=memory-worker
```

**New** (standardized):
```bash
MQTT_URL=mqtt://user:pass@localhost:1883  # Required
MQTT_CLIENT_ID=memory-worker               # Required
MQTT_SOURCE_NAME=memory-worker             # Optional (defaults to client_id)
MQTT_ENABLE_HEALTH=true                    # Optional (default: false)
MQTT_ENABLE_HEARTBEAT=false                # Optional (default: false)
MQTT_HEARTBEAT_INTERVAL=30.0               # Optional (default: 30.0)
```

### Step 3: Replace MQTT Client Initialization

**Before**:
```python
# apps/memory-worker/src/memory_worker/service.py
from .mqtt_client import MQTTClientWrapper

class MemoryService:
    def __init__(self):
        self.mqtt_client = MQTTClientWrapper(
            broker_host=os.getenv("MQTT_BROKER_HOST", "localhost"),
            broker_port=int(os.getenv("MQTT_BROKER_PORT", "1883")),
            client_id=os.getenv("MQTT_CLIENT_ID", "memory-worker"),
        )
    
    async def start(self):
        await self.mqtt_client.connect()
```

**After**:
```python
from tars.adapters.mqtt_client import MQTTClient

class MemoryService:
    def __init__(self):
        self.mqtt_client = MQTTClient.from_env()
    
    async def start(self):
        await self.mqtt_client.connect()
```

### Step 4: Update Publishing Calls

**Pattern**: Replace manual Envelope wrapping with `publish_event()`

**Before**:
```python
from tars.contracts.envelope import Envelope
import orjson

envelope = Envelope.new(event_type="event.type", data=my_data, correlate=req_id)
payload = orjson.dumps(envelope.model_dump())
await self.mqtt_client.publish("topic/name", payload, qos=1, retain=False)
```

**After**:
```python
await self.mqtt_client.publish_event(
    topic="topic/name",
    event_type="event.type",
    data=my_data,
    correlation_id=req_id,
    qos=1,
    retain=False,
)
```

### Step 5: Update Subscription Handlers

**Pattern**: Extract handler function, pass to `subscribe()`

**Before**:
```python
async with self.mqtt_client.messages() as messages:
    await self.mqtt_client.subscribe("input/topic", qos=1)
    
    async for msg in messages:
        if msg.topic == "input/topic":
            payload = orjson.loads(msg.payload)
            # Process payload...
```

**After**:
```python
async def handle_input(payload: bytes) -> None:
    data = orjson.loads(payload)
    # Process data...

await self.mqtt_client.subscribe("input/topic", handle_input, qos=1)
```

**Note**: The centralized client runs a background dispatch loop automatically. Handlers are called when messages arrive.

### Step 6: Update Shutdown Logic

**Before**:
```python
async def shutdown(self):
    # Publish shutdown health
    health = Envelope.new(...)
    await self.mqtt_client.publish(...)
    
    # Cleanup
    await self.mqtt_client.disconnect()
```

**After**:
```python
async def shutdown(self):
    await self.mqtt_client.shutdown()  # Handles health + cleanup
```

### Step 7: Remove Old Files

After migration is complete and tested:

```bash
# Remove old MQTT wrapper files
rm apps/memory-worker/src/memory_worker/mqtt_client.py
rm apps/llm-worker/src/llm_worker/mqtt_client.py
rm apps/stt-worker/src/stt_worker/mqtt_utils.py
```

---

## Common Patterns

### Pattern 1: Request-Response with Correlation IDs

**Scenario**: Service publishes request, waits for response via correlation ID.

**Before**:
```python
request_id = str(uuid.uuid4())
request_env = Envelope.new(
    event_type="llm.request",
    data={"text": prompt},
    correlate=request_id,
)
await mqtt_client.publish("llm/request", orjson.dumps(request_env.model_dump()))

# Wait for response...
async with mqtt_client.messages() as messages:
    await mqtt_client.subscribe("llm/response")
    async for msg in messages:
        response = orjson.loads(msg.payload)
        if response.get("id") == request_id:
            return response
```

**After**:
```python
request_id = str(uuid.uuid4())
self._pending[request_id] = asyncio.Future()

await mqtt_client.publish_event(
    "llm/request",
    "llm.request",
    {"text": prompt},
    correlation_id=request_id,
)

async def handle_response(payload: bytes) -> None:
    data = orjson.loads(payload)
    req_id = data.get("id")
    if req_id in self._pending:
        self._pending.pop(req_id).set_result(data)

await mqtt_client.subscribe("llm/response", handle_response)

# Wait for response with timeout
return await asyncio.wait_for(self._pending[request_id], timeout=30.0)
```

### Pattern 2: Wildcard Subscriptions

**Before**:
```python
await mqtt_client.subscribe("system/health/+")
# Manual topic matching in handler...
```

**After**:
```python
async def handle_health(payload: bytes) -> None:
    data = orjson.loads(payload)
    service = data["source"]
    # Process health from any service...

await mqtt_client.subscribe("system/health/+", handle_health)
```

**Centralized client handles wildcard matching automatically.**

### Pattern 3: Multiple Subscriptions

**Before**:
```python
async with mqtt_client.messages() as messages:
    await mqtt_client.subscribe("topic1")
    await mqtt_client.subscribe("topic2")
    
    async for msg in messages:
        if msg.topic == "topic1":
            # Handle topic1
        elif msg.topic == "topic2":
            # Handle topic2
```

**After**:
```python
async def handle_topic1(payload: bytes) -> None:
    # Handle topic1

async def handle_topic2(payload: bytes) -> None:
    # Handle topic2

await mqtt_client.subscribe("topic1", handle_topic1)
await mqtt_client.subscribe("topic2", handle_topic2)
```

### Pattern 4: Context Manager (Recommended)

**Best Practice**: Use async context manager for automatic cleanup.

```python
async def main():
    async with MQTTClient.from_env() as client:
        # Automatically connects on enter
        
        await client.publish_event("status", "service.ready", {})
        
        async def handler(payload: bytes):
            # Process messages
            pass
        
        await client.subscribe("commands/#", handler)
        
        # Run service logic...
        await asyncio.Event().wait()
        
        # Automatically shuts down on exit (even on exception)
```

---

## Configuration

### Environment Variables

All MQTT configuration is now standardized:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MQTT_URL` | ✅ | - | Broker URL: `mqtt://[user:pass@]host[:port]` |
| `MQTT_CLIENT_ID` | ✅ | - | Unique client identifier |
| `MQTT_SOURCE_NAME` | ❌ | `client_id` | Source name in Envelope messages |
| `MQTT_KEEPALIVE` | ❌ | `60` | MQTT keepalive interval (seconds) |
| `MQTT_ENABLE_HEALTH` | ❌ | `false` | Enable health status publishing |
| `MQTT_ENABLE_HEARTBEAT` | ❌ | `false` | Enable periodic heartbeat |
| `MQTT_HEARTBEAT_INTERVAL` | ❌ | `30.0` | Heartbeat interval (seconds) |
| `MQTT_DEDUPE_TTL` | ❌ | `0.0` | Message deduplication TTL (0=disabled) |
| `MQTT_DEDUPE_MAX_ENTRIES` | ❌ | `10000` | Max cached message IDs |
| `MQTT_RECONNECT_MIN_DELAY` | ❌ | `0.5` | Min reconnect delay (seconds) |
| `MQTT_RECONNECT_MAX_DELAY` | ❌ | `5.0` | Max reconnect delay (seconds) |

### Configuration in Code

Alternatively, configure directly in code:

```python
client = MQTTClient(
    mqtt_url="mqtt://localhost:1883",
    client_id="my-service",
    source_name="my-service",
    enable_health=True,
    enable_heartbeat=True,
    heartbeat_interval=30.0,
    dedupe_ttl=60.0,
    dedupe_max_entries=1000,
    keepalive=60,
    reconnect_min_delay=1.0,
    reconnect_max_delay=60.0,
)
```

---

## Troubleshooting

### Issue: "Module 'tars.adapters.mqtt_client' not found"

**Solution**: Ensure `tars-core` is installed:

```bash
pip install -e packages/tars-core
```

### Issue: "KeyError: 'MQTT_URL'" or "ValidationError"

**Solution**: Set required environment variables:

```bash
export MQTT_URL="mqtt://localhost:1883"
export MQTT_CLIENT_ID="my-service"
```

Or use `.env` file:

```bash
# .env
MQTT_URL=mqtt://localhost:1883
MQTT_CLIENT_ID=my-service
```

### Issue: Messages not being received

**Checklist**:
1. Verify broker is running: `docker compose up -d mosquitto`
2. Check subscription topic matches published topic exactly (or uses wildcard)
3. Ensure `await client.connect()` completes before subscribing
4. Verify handler is async: `async def handler(payload: bytes) -> None:`
5. Check logs for connection errors

### Issue: "RuntimeError: not connected"

**Solution**: Call `await client.connect()` before publish/subscribe operations.

### Issue: Duplicate messages received

**Solution**: Enable deduplication:

```bash
MQTT_DEDUPE_TTL=60.0  # Deduplicate for 60 seconds
MQTT_DEDUPE_MAX_ENTRIES=10000
```

Or in code:

```python
client = MQTTClient(..., dedupe_ttl=60.0, dedupe_max_entries=10000)
```

---

## Service-Specific Examples

### Memory Worker Migration

**Files changed**:
- `apps/memory-worker/src/memory_worker/service.py` - Use centralized client
- `apps/memory-worker/src/memory_worker/mqtt_client.py` - **REMOVED**

**Before** (100+ lines of MQTT code):
```python
# Custom MQTT wrapper
from .mqtt_client import MQTTClientWrapper

class MemoryService:
    def __init__(self):
        self.mqtt = MQTTClientWrapper(...)
    
    async def run(self):
        await self.mqtt.connect()
        
        async with self.mqtt.messages() as messages:
            await self.mqtt.subscribe("memory/query")
            async for msg in messages:
                # Manual dispatch...
```

**After** (20 lines):
```python
from tars.adapters.mqtt_client import MQTTClient

class MemoryService:
    def __init__(self):
        self.mqtt = MQTTClient.from_env()
    
    async def run(self):
        await self.mqtt.connect()
        await self.mqtt.subscribe("memory/query", self._handle_query)
    
    async def _handle_query(self, payload: bytes) -> None:
        data = orjson.loads(payload)
        # Process query...
```

**Result**: ~80 lines removed (80% reduction)

### LLM Worker Migration

**Focus**: Request-response pattern with correlation IDs

**Before**:
- Manual Future management
- Polling for responses
- Complex message dispatch

**After**:
```python
from tars.adapters.mqtt_client import MQTTClient

class LLMService:
    def __init__(self):
        self.mqtt = MQTTClient.from_env()
        self._pending = {}
    
    async def start(self):
        await self.mqtt.connect()
        await self.mqtt.subscribe("llm/request", self._handle_request)
    
    async def _handle_request(self, payload: bytes) -> None:
        data = orjson.loads(payload)
        request_id = data["id"]
        
        # Process LLM request...
        response = await self._generate_response(data["data"])
        
        # Publish response with same correlation ID
        await self.mqtt.publish_event(
            "llm/response",
            "llm.completion",
            {"reply": response},
            correlation_id=request_id,
        )
```

---

## Testing After Migration

### Verify No Behavioral Changes

Run all existing integration tests:

```bash
# Memory worker tests
pytest apps/memory-worker/tests/ -v

# LLM worker tests
pytest apps/llm-worker/tests/ -v
```

All tests should pass without modification.

### Test Checklist

- [ ] Service connects to broker successfully
- [ ] Messages are published to correct topics
- [ ] Subscriptions receive expected messages
- [ ] Health status published on startup (if enabled)
- [ ] Graceful shutdown publishes unhealthy status
- [ ] No errors in logs during normal operation
- [ ] Integration tests pass
- [ ] LOC reduction ≥50%

---

## Migration Metrics (Target)

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Lines of Code | 100-150 | 20-50 | **-50% to -80%** |
| Files | 2-3 | 1 | **-50% to -66%** |
| Dependencies | 2+ | 1 | **-50%** |
| Envelope wrapping | Manual | Automatic | **100% reduction** |
| Error handling | Custom | Built-in | **100% reduction** |
| Health monitoring | Manual | Built-in | **100% reduction** |

---

## Need Help?

1. **Documentation**: See `packages/tars-core/README.md`
2. **API Reference**: See `packages/tars-core/docs/API.md`
3. **Examples**: See `packages/tars-core/examples/`
4. **Tests**: See `packages/tars-core/tests/` for usage patterns

---

**Status**: Ready for production migration  
**Last Updated**: October 16, 2025
