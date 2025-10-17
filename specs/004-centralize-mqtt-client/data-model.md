# Data Model: Centralized MQTT Client

**Feature**: Centralized MQTT Client  
**Branch**: `004-centralize-mqtt-client`  
**Date**: 2025-10-16

## Overview

This document defines the entities, relationships, validation rules, and state transitions for the centralized MQTT client module. All entities use Pydantic v2 for validation and type safety.

---

## Core Entities

### 1. MQTTClient

**Purpose**: Central client abstraction that manages MQTT broker connection, publishing, subscribing, and lifecycle.

**Fields**:

| Field | Type | Required | Validation | Description |
|-------|------|----------|------------|-------------|
| mqtt_url | str | Yes | Valid MQTT URL format | Connection URL (mqtt://user:pass@host:port) |
| client_id | str | Yes | Non-empty string | Unique client identifier for broker connection |
| source_name | str \| None | No | - | Source identifier for Envelope messages (defaults to client_id) |
| keepalive | int | No | >= 1, <= 3600 | MQTT protocol keepalive interval in seconds (default: 60) |
| enable_health | bool | No | - | Whether to publish health status (default: False) |
| enable_heartbeat | bool | No | - | Whether to publish application heartbeat (default: False) |
| heartbeat_interval | float | No | >= 1.0 | Application heartbeat interval in seconds (default: 5.0) |
| dedupe_ttl | float | No | >= 0 | Message deduplication TTL in seconds (0=disabled, default: 0) |
| dedupe_max_entries | int | No | >= 0 | Max deduplication cache entries (0=disabled, default: 0) |
| reconnect_min_delay | float | No | >= 0.1 | Min reconnection backoff delay (default: 0.5) |
| reconnect_max_delay | float | No | >= reconnect_min_delay | Max reconnection backoff delay (default: 5.0) |

**State**:
- `_client`: Optional[mqtt.Client] - Underlying asyncio-mqtt client instance
- `_handlers`: Dict[str, Callable] - Registered topic → handler mappings
- `_subscriptions`: Set[str] - Set of active topic subscriptions
- `_dispatch_task`: Optional[asyncio.Task] - Background message dispatch task
- `_heartbeat_task`: Optional[asyncio.Task] - Background heartbeat task
- `_connected`: bool - Connection state flag
- `_shutdown`: bool - Shutdown initiated flag
- `_deduplicator`: Optional[MessageDeduplicator] - Message dedup instance if enabled

**Relationships**:
- Contains 0..1 MessageDeduplicator (if deduplication enabled)
- Manages 0..N topic subscriptions with handlers
- Wraps 1 asyncio-mqtt Client instance

**Validation Rules**:
- mqtt_url must be parseable by urlparse() with mqtt:// scheme
- client_id must be unique across all service instances (enforced by broker)
- reconnect_max_delay >= reconnect_min_delay
- If enable_heartbeat=True, heartbeat_interval must be >= 1.0
- If dedupe_ttl > 0, dedupe_max_entries must be > 0

---

### 2. MQTTClientConfig

**Purpose**: Configuration model for initializing MQTTClient from environment variables.

**Fields**:

| Field | Type | Required | Default | Validation | Environment Variable |
|-------|------|----------|---------|------------|---------------------|
| mqtt_url | str | Yes | - | Valid MQTT URL | MQTT_URL |
| client_id | str | Yes | - | Non-empty | MQTT_CLIENT_ID |
| source_name | str \| None | No | None | - | MQTT_SOURCE_NAME |
| keepalive | int | No | 60 | 1-3600 | MQTT_KEEPALIVE |
| enable_health | bool | No | False | - | MQTT_ENABLE_HEALTH |
| enable_heartbeat | bool | No | False | - | MQTT_ENABLE_HEARTBEAT |
| heartbeat_interval | float | No | 5.0 | >= 1.0 | MQTT_HEARTBEAT_INTERVAL |
| dedupe_ttl | float | No | 0.0 | >= 0 | MQTT_DEDUPE_TTL |
| dedupe_max_entries | int | No | 0 | >= 0 | MQTT_DEDUPE_MAX_ENTRIES |
| reconnect_min_delay | float | No | 0.5 | >= 0.1 | MQTT_RECONNECT_MIN_DELAY |
| reconnect_max_delay | float | No | 5.0 | >= min_delay | MQTT_RECONNECT_MAX_DELAY |

**Methods**:
```python
@classmethod
def from_env(cls) -> MQTTClientConfig:
    """Load configuration from environment variables."""
```

**Validation Rules**:
- All field constraints from MQTTClient apply
- Provides typed config object to prevent os.environ access in call stacks
- Fails fast with clear error if MQTT_URL or MQTT_CLIENT_ID missing

---

### 3. ConnectionParams

**Purpose**: Parsed MQTT connection parameters extracted from URL.

**Fields**:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| hostname | str | Yes | - | MQTT broker hostname or IP |
| port | int | Yes | - | MQTT broker port |
| username | str \| None | No | None | Authentication username |
| password | str \| None | No | None | Authentication password |

**Derivation**:
```python
def parse_mqtt_url(url: str) -> ConnectionParams:
    """Parse MQTT URL into connection parameters."""
    parsed = urlparse(url)
    return ConnectionParams(
        hostname=parsed.hostname or "127.0.0.1",
        port=parsed.port or 1883,
        username=parsed.username,
        password=parsed.password,
    )
```

**Validation Rules**:
- hostname must be valid DNS name or IPv4/IPv6 address
- port must be 1-65535
- username and password redacted in logs

---

### 4. HealthStatus

**Purpose**: Health status payload published to system/health/{client_id} topic.

**Fields**:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| ok | bool | Yes | - | Health status (True=healthy, False=unhealthy) |
| event | str \| None | No | None | Health event name (e.g., "ready", "shutdown") |
| error | str \| None | No | None | Error message if ok=False |
| timestamp | float \| None | No | None | Unix timestamp (auto-generated by Envelope) |

**Validation Rules**:
- If ok=True, error should be None (warning if present)
- If ok=False, should have either event or error
- Serialized as Envelope with event_type="health.status"

**Example Payloads**:
```json
{"ok": true, "event": "ready"}
{"ok": true, "event": "reconnected"}
{"ok": false, "event": "shutdown"}
{"ok": false, "error": "broker connection lost"}
```

---

### 5. HeartbeatPayload

**Purpose**: Application-level keepalive heartbeat payload.

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| ok | bool | Yes | Always True for heartbeat |
| event | str | Yes | Always "heartbeat" |
| timestamp | float | Yes | Unix timestamp of heartbeat |

**Publishing**:
- Topic: `system/keepalive/{client_id}`
- QoS: 0 (best effort)
- Retain: False
- Interval: Configurable via heartbeat_interval (default 5s)

**Validation Rules**:
- timestamp must be within 10s of current time (detect clock skew)
- ok is always True (unhealthy services stop heartbeating)

---

### 6. MessageDeduplicator

**Purpose**: Deduplicate messages using envelope IDs with TTL-bound cache.

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| _ttl | float | Time-to-live for cache entries (seconds) |
| _max_entries | int | Maximum cache size (entries) |
| _seen | OrderedDict[str, float] | Cache mapping message_id → timestamp |

**Methods**:

```python
def is_duplicate(self, payload: bytes) -> bool:
    """Check if message is duplicate based on Envelope ID."""
    
def _extract_message_id(self, payload: bytes) -> str | None:
    """Extract unique message ID from Envelope."""
    # Format: {event_type}|{envelope_id}|seq={seq} or hash={digest}
    
def _evict_expired(self, now: float) -> None:
    """Remove cache entries older than TTL."""
```

**Validation Rules**:
- _ttl must be > 0
- _max_entries must be > 0
- Cache eviction runs on each is_duplicate() call
- Message ID includes seq if present in data, otherwise hash of data

**Deduplication Key Format**:
```
{event_type}|{envelope_id}|seq={seq}        # For sequential messages
{event_type}|{envelope_id}|hash={digest}    # For unordered messages
```

---

### 7. SubscriptionHandler

**Purpose**: Type alias for subscription handler functions.

**Definition**:
```python
SubscriptionHandler = Callable[[bytes], Awaitable[None]]
```

**Contract**:
- Input: Raw message payload (bytes)
- Output: None (side effects only)
- Must be async function
- Should not raise exceptions (isolated by error handling)
- Should be idempotent if deduplication disabled

**Example**:
```python
async def handle_stt_final(payload: bytes) -> None:
    """Handle STT final transcription messages."""
    envelope = Envelope.model_validate_json(payload)
    text = envelope.data.get("text", "")
    logger.info("Transcription: %s", text)
```

---

## Entity Relationships

```
MQTTClient (1)
  ├── contains (0..1) MessageDeduplicator
  ├── manages (0..N) Subscriptions
  │   └── each has (1) SubscriptionHandler
  ├── wraps (1) asyncio_mqtt.Client
  ├── uses (1) ConnectionParams
  └── publishes (0..N) HealthStatus, HeartbeatPayload
```

---

## State Transitions

### MQTTClient Lifecycle States

```
[Created] 
    ↓ connect()
[Connecting] 
    ↓ (success)
[Connected] ←→ [Reconnecting] (on connection loss, auto-retry)
    ↓ shutdown()
[Disconnecting]
    ↓
[Disconnected]
```

**State Rules**:
- `connect()` can only be called from Created or Disconnected state
- `publish_event()` / `subscribe()` only valid in Connected state
- `shutdown()` can be called from any state (idempotent)
- Reconnecting state triggers exponential backoff (min 0.5s → max 5.0s)
- Background tasks (dispatch, heartbeat) only run in Connected state

---

### Connection State Machine

```
[Disconnected]
    ↓ connect()
    ├─→ parse mqtt_url → ConnectionParams
    ├─→ create mqtt.Client(hostname, port, username, password, client_id, keepalive)
    ├─→ await client.__aenter__()
    ├─→ re-subscribe to all topics in _subscriptions
    ├─→ start _dispatch_task
    ├─→ start _heartbeat_task (if enabled)
    └─→ [Connected]

[Connected]
    ├─→ (connection lost) → [Reconnecting]
    └─→ shutdown() → [Disconnecting]

[Reconnecting]
    ├─→ backoff_delay = min(backoff * 2, max_delay)
    ├─→ await asyncio.sleep(backoff_delay)
    ├─→ retry connect()
    │   ├─→ (success) → [Connected]
    │   └─→ (failure) → [Reconnecting] (repeat)
    └─→ shutdown() → [Disconnecting]

[Disconnecting]
    ├─→ publish_health(ok=False, event="shutdown") (if enabled)
    ├─→ cancel _dispatch_task
    ├─→ cancel _heartbeat_task
    ├─→ await tasks with 5s timeout
    ├─→ await client.__aexit__()
    └─→ [Disconnected]
```

---

### Message Processing Flow

```
[Message Received]
    ↓
[Dispatch Task]
    ├─→ lookup handler in _handlers[topic]
    ├─→ (if deduplication enabled)
    │   └─→ is_duplicate(payload)?
    │       ├─→ Yes: skip processing
    │       └─→ No: continue
    ├─→ try:
    │   └─→ await handler(payload)
    └─→ except Exception:
        └─→ log error, isolate failure
```

---

### Health Publishing Flow

```
[Health Event]
    ↓
[publish_health(ok, event, error)]
    ├─→ (if not enable_health): return (no-op)
    ├─→ create HealthStatus(ok, event, error)
    ├─→ wrap in Envelope(event_type="health.status", data=health_status)
    ├─→ topic = f"system/health/{client_id}"
    ├─→ await client.publish(topic, payload, qos=1, retain=True)
    └─→ log health event
```

---

### Heartbeat Loop

```
[Heartbeat Task] (if enabled)
    ↓
    while not shutdown:
        ├─→ (if not connected): await reconnect; continue
        ├─→ now = time.time()
        ├─→ (if last_hb and now - last_hb > 3 * interval):
        │   └─→ trigger reconnect (watchdog)
        ├─→ payload = HeartbeatPayload(ok=True, event="heartbeat", timestamp=now)
        ├─→ topic = f"system/keepalive/{client_id}"
        ├─→ try:
        │   └─→ await client.publish(topic, payload, qos=0, retain=False)
        │       └─→ last_hb = now
        └─→ await asyncio.sleep(heartbeat_interval)
```

---

## Validation Rules Summary

### Initialization Validation
- mqtt_url must be valid format: `mqtt://[user:pass@]host[:port]`
- client_id must be non-empty, unique across instances
- reconnect_max_delay >= reconnect_min_delay
- If enable_heartbeat=True, heartbeat_interval >= 1.0
- If dedupe_ttl > 0, dedupe_max_entries > 0

### Runtime Validation
- publish_event() requires connected state
- subscribe() requires connected state
- handler must be async callable with signature: (bytes) -> None
- Envelope validation on publish (event_type, data fields)
- Health status must have event or error if ok=False

### Resource Constraints
- Max 1000 concurrent subscriptions (practical limit)
- Max 2048 deduplication cache entries (configurable)
- Max 5s shutdown timeout for background tasks
- Max 5s reconnection backoff delay

---

## Serialization Examples

### Envelope with Health Status
```json
{
  "id": "01HZ123...",
  "type": "health.status",
  "timestamp": 1729123456.789,
  "source": "tars-stt",
  "data": {
    "ok": true,
    "event": "ready"
  }
}
```

### Envelope with Event Data
```json
{
  "id": "01HZ456...",
  "type": "stt.final",
  "timestamp": 1729123457.123,
  "source": "tars-stt",
  "correlate": "conv-001",
  "data": {
    "text": "hello world",
    "confidence": 0.95,
    "lang": "en"
  }
}
```

### Heartbeat Payload
```json
{
  "ok": true,
  "event": "heartbeat",
  "timestamp": 1729123458.456
}
```

---

## Type Signatures

### MQTTClient Public API

```python
class MQTTClient:
    def __init__(
        self,
        mqtt_url: str,
        client_id: str,
        source_name: str | None = None,
        *,
        keepalive: int = 60,
        enable_health: bool = False,
        enable_heartbeat: bool = False,
        heartbeat_interval: float = 5.0,
        dedupe_ttl: float = 0,
        dedupe_max_entries: int = 0,
        reconnect_min_delay: float = 0.5,
        reconnect_max_delay: float = 5.0,
    ) -> None: ...

    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def shutdown(self) -> None: ...

    async def publish_event(
        self,
        topic: str,
        event_type: str,
        data: dict[str, Any] | BaseModel,
        *,
        correlation_id: str | None = None,
        qos: int = 0,
        retain: bool = False,
    ) -> None: ...

    async def publish_health(
        self,
        ok: bool,
        event: str | None = None,
        error: str | None = None,
    ) -> None: ...

    async def subscribe(
        self,
        topic: str,
        handler: Callable[[bytes], Awaitable[None]],
        qos: int = 0,
    ) -> None: ...

    @property
    def client(self) -> mqtt.Client | None: ...

    @property
    def connected(self) -> bool: ...
```

---

## Next Steps

1. **Write Tests First (TDD RED)**: Create test suite for each entity before implementation
2. **Implement to Pass Tests (TDD GREEN)**: Write minimum code to make tests pass
3. **Refactor (TDD GREEN)**: Improve code quality while keeping tests passing
4. Generate API contracts (contracts/mqtt_client_api.yaml) - DONE
5. Create quickstart.md with usage examples - DONE
6. Begin implementation of MQTTClient in packages/tars-core/src/tars/adapters/mqtt_client.py

## Test-Driven Development Checklist

Before implementing each entity, write tests covering:

### MQTTClientConfig Tests (Write First)
- [ ] `test_from_env_valid()` - Parse all environment variables correctly
- [ ] `test_from_env_missing_mqtt_url()` - Fail with clear error when MQTT_URL missing
- [ ] `test_from_env_missing_client_id()` - Fail with clear error when MQTT_CLIENT_ID missing
- [ ] `test_from_env_defaults()` - Use correct defaults for optional fields
- [ ] `test_reconnect_delay_validation()` - Reject when max_delay < min_delay
- [ ] `test_dedupe_validation()` - Require max_entries > 0 when ttl > 0
- [ ] `test_heartbeat_interval_validation()` - Require interval >= 1.0 when enabled

### ConnectionParams Tests (Write First)
- [ ] `test_parse_mqtt_url_full()` - Parse mqtt://user:pass@host:port
- [ ] `test_parse_mqtt_url_no_credentials()` - Parse mqtt://host:port
- [ ] `test_parse_mqtt_url_default_port()` - Use 1883 when port omitted
- [ ] `test_parse_mqtt_url_invalid_scheme()` - Reject non-mqtt:// URLs
- [ ] `test_password_redacted_in_logs()` - Never log password in plain text

### MessageDeduplicator Tests (Write First)
- [ ] `test_is_duplicate_first_message()` - Return False for new message ID
- [ ] `test_is_duplicate_repeat_message()` - Return True for duplicate ID
- [ ] `test_ttl_expiration()` - Evict entries older than TTL
- [ ] `test_max_entries_limit()` - Enforce cache size limit (FIFO eviction)
- [ ] `test_extract_message_id_with_seq()` - Use seq number in key
- [ ] `test_extract_message_id_without_seq()` - Use data hash in key
- [ ] `test_extract_message_id_invalid_envelope()` - Return None for invalid JSON

### MQTTClient Lifecycle Tests (Write First)
- [ ] `test_init_creates_instance()` - Initialize with required parameters
- [ ] `test_init_validation_errors()` - Reject invalid configuration
- [ ] `test_connect_establishes_connection()` - Connect to broker successfully
- [ ] `test_connect_invalid_url()` - Fail with clear error for bad URL
- [ ] `test_connect_broker_unavailable()` - Handle connection refused
- [ ] `test_disconnect_closes_connection()` - Clean disconnect from broker
- [ ] `test_shutdown_publishes_health()` - Publish unhealthy status on shutdown
- [ ] `test_shutdown_cancels_tasks()` - Cancel dispatch and heartbeat tasks
- [ ] `test_shutdown_timeout()` - Force cancel tasks after 5s timeout
- [ ] `test_shutdown_idempotent()` - Safe to call multiple times

### MQTTClient Publishing Tests (Write First)
- [ ] `test_publish_event_wraps_envelope()` - Create Envelope with correct fields
- [ ] `test_publish_event_serializes_orjson()` - Use orjson for JSON serialization
- [ ] `test_publish_event_uses_source_name()` - Set Envelope.source from config
- [ ] `test_publish_event_correlation_id()` - Include correlation ID in Envelope
- [ ] `test_publish_event_qos_retain()` - Pass QoS and retain flags to broker
- [ ] `test_publish_event_not_connected()` - Raise RuntimeError if not connected
- [ ] `test_publish_event_pydantic_model()` - Serialize Pydantic models
- [ ] `test_publish_health_qos_retain()` - Always use QoS 1 + retain for health
- [ ] `test_publish_health_topic_format()` - Publish to system/health/{client_id}
- [ ] `test_publish_health_disabled()` - No-op when enable_health=False
- [ ] `test_publish_health_validation()` - Validate HealthStatus fields

### MQTTClient Subscribing Tests (Write First)
- [ ] `test_subscribe_registers_handler()` - Add handler to _handlers dict
- [ ] `test_subscribe_adds_to_subscriptions()` - Add topic to _subscriptions set
- [ ] `test_subscribe_calls_broker()` - Call client.subscribe(topic, qos)
- [ ] `test_subscribe_not_connected()` - Raise RuntimeError if not connected
- [ ] `test_subscribe_wildcard_single_level()` - Support + wildcard
- [ ] `test_subscribe_wildcard_multi_level()` - Support # wildcard
- [ ] `test_subscribe_replaces_handler()` - Replace handler for existing topic
- [ ] `test_handler_receives_message()` - Dispatch message to correct handler
- [ ] `test_handler_error_isolated()` - Log error, continue dispatch on exception
- [ ] `test_deduplication_skips_duplicate()` - Skip duplicate messages when enabled

### MQTTClient Reconnection Tests (Write First)
- [ ] `test_reconnect_exponential_backoff()` - Increase delay: 0.5s → 1s → 2s → 4s → 5s
- [ ] `test_reconnect_max_delay_cap()` - Cap at reconnect_max_delay
- [ ] `test_reconnect_resubscribes_topics()` - Restore all subscriptions
- [ ] `test_reconnect_resets_backoff()` - Reset to min_delay on success
- [ ] `test_reconnect_on_connection_loss()` - Auto-reconnect when connection drops
- [ ] `test_heartbeat_watchdog_triggers_reconnect()` - Reconnect on 3x heartbeat failure

### Integration Tests (Write First)
- [ ] `test_end_to_end_publish_subscribe()` - Full flow with real Mosquitto
- [ ] `test_reconnection_on_broker_restart()` - Survive broker restart
- [ ] `test_deduplication_with_real_messages()` - Dedupe works end-to-end
- [ ] `test_multiple_clients_same_topic()` - Multiple subscribers receive message
- [ ] `test_health_retained_on_reconnect()` - Health persists across reconnection
- [ ] `test_graceful_shutdown_sequence()` - Complete shutdown flow

### Contract Tests (Write First)
- [ ] `test_envelope_schema_validation()` - All published envelopes valid
- [ ] `test_health_status_schema()` - HealthStatus matches contract
- [ ] `test_heartbeat_payload_schema()` - HeartbeatPayload matches contract
- [ ] `test_topic_patterns_compliance()` - Topics follow constitution patterns
