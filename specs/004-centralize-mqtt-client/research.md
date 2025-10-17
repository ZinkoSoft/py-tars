# Research: Centralized MQTT Client Module

**Feature**: Centralized MQTT Client  
**Branch**: `004-centralize-mqtt-client`  
**Date**: 2025-10-16

## Overview

This document consolidates research findings for centralizing MQTT client functionality across all py-tars services. All unknowns from Technical Context have been resolved through codebase analysis, pattern identification, and best practices research.

## Research Tasks & Findings

### 1. MQTT Connection Patterns Across Services

**Question**: What are the common patterns for MQTT connection management used across all services?

**Findings**:
- **URL Parsing**: All services parse `MQTT_URL` environment variable in format `mqtt://user:pass@host:port`
- **Connection Lifecycle**: Services use asyncio-mqtt's async context manager (`async with mqtt.Client(...) as client`)
- **Client ID**: Each service uses unique client_id (e.g., "tars-stt", "tars-llm", "tars-memory")
- **Keepalive**: Values vary (15s for stt-worker, default 60s for others)
- **Reconnection**: Manual exponential backoff implemented in some services (stt-worker), absent in others

**Pattern Catalog**:
1. **Inline Connection** (router, tts-worker, ui-web): Direct `async with mqtt.Client(...)` in service main loop
2. **Wrapper Class** (stt-worker, llm-worker, memory-worker): Custom wrapper class with connect/disconnect methods
3. **Auto-Reconnect** (stt-worker): Background task with exponential backoff and dispatch loop
4. **No Reconnect** (router, tts-worker): Service crashes on connection loss, relies on Docker restart

**Decision**: Centralized module will implement auto-reconnect pattern with configurable backoff as the default, allowing services to opt-out if needed.

**Rationale**: Auto-reconnect is most robust; prevents service crashes; aligns with constitution's requirement for graceful degradation.

**Alternatives Considered**:
- Manual reconnect per service: Rejected due to code duplication and inconsistent behavior
- No reconnect (fail fast): Rejected as it reduces system resilience on transient network issues

---

### 2. Envelope Wrapping and Message Serialization

**Question**: How do services wrap messages in Envelope contract and serialize to JSON?

**Findings**:
- **Envelope Usage**: All services except camera-service use `tars.contracts.envelope.Envelope`
- **Serialization**: Most use `envelope.model_dump_json().encode()` or `orjson.dumps(envelope.model_dump())`
- **Event Types**: Defined per service (e.g., "stt.final", "llm.response", "health.ping")
- **Correlation IDs**: Passed via Envelope.id or embedded in data payload
- **Timestamp**: Envelope auto-generates timestamp on creation

**Pattern Catalog**:
1. **Direct Pydantic Serialization**: `envelope.model_dump_json().encode()`
2. **orjson with model_dump**: `orjson.dumps(envelope.model_dump())`
3. **Envelope.new() Helper**: Factory method in some wrappers for convenience

**Decision**: Centralized module will provide `publish_event()` method that accepts event_type, data (dict or Pydantic model), and optional correlation ID, automatically wrapping in Envelope and serializing with orjson.

**Rationale**: Consistent serialization performance (orjson); reduces boilerplate; enforces Envelope contract at publish boundary.

**Alternatives Considered**:
- Allow raw bytes publishing: Rejected to enforce Envelope contract compliance
- Support both Pydantic and orjson: Rejected as Pydantic's JSON is slower; standardize on orjson

---

### 3. Subscription and Handler Dispatch

**Question**: How do services subscribe to topics and dispatch messages to handlers?

**Findings**:
- **Subscription Methods**: `await client.subscribe(topic, qos=...)` or `client.filtered_messages(topic)`
- **Message Iteration**: `async for msg in messages:` pattern from asyncio-mqtt
- **Handler Registration**: Some services (stt-worker) use topic → async handler dict
- **Error Handling**: Varies widely; stt-worker isolates handler errors, others may crash
- **Deduplication**: Only in tars-core's AsyncioMQTTSubscriber using envelope ID cache

**Pattern Catalog**:
1. **Inline Processing** (router, tts-worker): Direct message handling in main loop
2. **Handler Registry** (stt-worker): `Dict[str, Callable[[bytes], Awaitable[None]]]` mapping
3. **Filtered Messages** (tars-core): `client.filtered_messages(topic)` for topic-specific iteration

**Decision**: Centralized module will provide `subscribe(topic, handler)` method that registers async handler functions and dispatches messages automatically in background task. Error isolation via try/except per handler.

**Rationale**: Handler registry pattern is most flexible; background dispatch prevents blocking; error isolation prevents cascading failures.

**Alternatives Considered**:
- Return message iterator to caller: Rejected as it requires each service to implement dispatch loop
- Single global handler: Rejected as it doesn't support topic-specific logic

---

### 4. Health Status Publishing

**Question**: How do services publish health status to MQTT?

**Findings**:
- **Topic Pattern**: `system/health/<service>` (e.g., "system/health/stt")
- **Payload Structure**: `{"ok": bool, "event": str}` or `{"ok": bool, "err": str}`
- **QoS + Retain**: All health topics use QoS 1 and retain=True for last-known-state
- **Health Events**: "ready", "shutdown", "error", "reconnected"
- **Frequency**: Published on startup, shutdown, and state transitions (not periodic)

**Pattern Catalog**:
1. **Typed Health Model**: Some services use Pydantic HealthPing model
2. **Dict Payload**: Others construct dict manually
3. **Convenience Method**: llm-worker, memory-worker have `publish_health()` wrapper

**Decision**: Centralized module will provide `publish_health(ok, event, err=None)` method that publishes to `system/health/{client_id}` with QoS 1 + retain. Health model will use Pydantic for validation.

**Rationale**: Standardizes health publishing across services; enforces retained health for monitoring; validates payload structure.

**Alternatives Considered**:
- Automatic health on connect/disconnect: Rejected as services need control over health semantics
- Periodic health heartbeat: Rejected as constitution specifies event-driven (state transitions only)

---

### 5. Keepalive and Application-Level Heartbeat

**Question**: Should the module implement application-level keepalive separate from MQTT keepalive?

**Findings**:
- **MQTT Keepalive**: asyncio-mqtt supports keepalive parameter (default 60s, stt-worker uses 15s)
- **Application Heartbeat**: stt-worker publishes to `system/keepalive/{client_id}` every 5s
- **Purpose**: Detects stale connections that MQTT keepalive misses; provides observable liveness
- **Watchdog**: stt-worker triggers reconnect if heartbeat publish fails 3x

**Pattern Analysis**:
- MQTT keepalive: Protocol-level ping/pong between client and broker
- Application heartbeat: Published message visible to all subscribers, proves end-to-end connectivity

**Decision**: Centralized module will implement optional application-level heartbeat (disabled by default) with configurable interval and watchdog. MQTT keepalive remains separate configuration.

**Rationale**: Application heartbeat provides observable liveness for monitoring; watchdog improves resilience; opt-in avoids unnecessary messages for simple services.

**Alternatives Considered**:
- Always-on heartbeat: Rejected to avoid message spam for services that don't need it
- Only MQTT keepalive: Rejected as it doesn't provide observable liveness signal

---

### 6. Message Deduplication Strategy

**Question**: How should the centralized module handle duplicate messages on reconnection?

**Findings**:
- **Current Implementation**: tars-core's MessageDeduplicator uses Envelope ID + seq/hash
- **TTL Cache**: OrderedDict with 30s TTL and 2048 entry limit
- **Deduplication Key**: `{event_type}|{envelope_id}|seq={seq}` or `hash={digest}`
- **Usage**: Only AsyncioMQTTSubscriber implements dedup; not used in service wrappers

**Pattern Analysis**:
- Deduplication prevents duplicate processing during reconnection/redelivery
- TTL-based cache prevents unbounded memory growth
- Sequence numbers work for ordered streams; hash fallback for unordered events

**Decision**: Centralized module will include deduplication as optional feature (disabled by default) using existing MessageDeduplicator implementation. Enable via `dedupe_ttl` and `dedupe_max_entries` config.

**Rationale**: Preserves existing dedup logic; opt-in reduces overhead for idempotent handlers; configurable for different use cases.

**Alternatives Considered**:
- Always-on deduplication: Rejected due to performance overhead for idempotent handlers
- Service-level deduplication: Rejected as it duplicates logic across services

---

### 7. QoS and Retain Flag Patterns

**Question**: What QoS levels and retain flag patterns are used across topics?

**Findings** (from constitution and codebase):
- **Health Topics**: QoS 1, retain=True (system/health/*)
- **Commands/Requests**: QoS 1, retain=False (llm/request, tts/say, memory/query)
- **Responses**: QoS 1, retain=False (llm/response, memory/results)
- **Streaming/Partials**: QoS 0, retain=False (stt/partial, llm/stream)
- **Keepalive**: QoS 0, retain=False (system/keepalive/*)

**Pattern Summary**:
- QoS 1: Critical messages that must be delivered (commands, responses, health)
- QoS 0: High-frequency or transient messages where loss is acceptable (streams, partials)
- Retain: Only for state that must persist across client restarts (health)

**Decision**: Centralized module will default to QoS 0, retain=False for publish methods. Provide explicit parameters for callers to override. Document QoS/retain patterns in quickstart.

**Rationale**: Safe defaults (QoS 0 = best performance); explicit overrides prevent accidental retained messages; aligns with constitution's guidance.

**Alternatives Considered**:
- QoS 1 default: Rejected due to performance cost for high-frequency streams
- Topic-based auto-detection: Rejected as it's too magical; prefer explicit configuration

---

### 8. Graceful Shutdown Sequence

**Question**: How should the module handle graceful shutdown and cleanup?

**Findings**:
- **Current Patterns**: Services call `client.__aexit__()` or `disconnect()` on shutdown
- **Task Cancellation**: Some services cancel background tasks; others rely on context manager cleanup
- **Health on Shutdown**: Good practice to publish unhealthy status before disconnecting
- **Message Draining**: No services wait for in-flight messages to complete

**Pattern Analysis**:
- AsyncIO shutdown: Cancel tasks → wait for cancellation → close resources
- MQTT disconnect: Publish will message OR disconnect gracefully
- Task supervision: asyncio.TaskGroup propagates cancellation to child tasks

**Decision**: Centralized module will provide `shutdown()` method that:
1. Publishes health(ok=False, event="shutdown") if health enabled
2. Cancels background tasks (dispatch, keepalive)
3. Waits for tasks with timeout (5s)
4. Calls `client.__aexit__()` to disconnect gracefully

Services should call `shutdown()` in try/finally or use async context manager.

**Rationale**: Predictable shutdown sequence; health signal for monitoring; prevents resource leaks; aligns with TaskGroup pattern.

**Alternatives Considered**:
- Automatic cleanup in __del__: Rejected as __del__ is unreliable in async contexts
- No explicit shutdown: Rejected as it may leave stale health status retained

---

### 9. Best Practices for asyncio-mqtt Usage

**Question**: What are the recommended patterns for asyncio-mqtt in async applications?

**Research Sources**:
- asyncio-mqtt documentation: https://github.com/sbtinstruments/asyncio-mqtt
- asyncio best practices: PEP 3156, Python docs
- Existing tars-core implementation analysis

**Findings**:
1. **Context Manager Required**: Always use `async with Client(...) as client:`
2. **Message Iteration**: Use `async with client.messages() as messages:` for subscription
3. **Filtered Messages**: Prefer `client.filtered_messages(topic)` for topic-specific handling
4. **Reconnection**: Not built-in; must be implemented by application
5. **Concurrency**: Client is not thread-safe; use from single event loop only
6. **QoS 2**: Rarely needed; QoS 1 sufficient for most use cases
7. **Backpressure**: Use bounded queues if processing is slower than message arrival

**Decision**: Centralized module will:
- Wrap client in persistent connection (not context manager per operation)
- Implement reconnection with exponential backoff (0.5s → 5s max)
- Use background task for message dispatch to prevent blocking
- Provide bounded queue for message buffering (configurable size)
- Use single client instance per service (not thread-safe)

**Rationale**: Persistent connection reduces overhead; exponential backoff prevents connection storms; background dispatch enables concurrent processing; bounded queue provides backpressure.

**Alternatives Considered**:
- Per-operation context manager: Rejected due to connection overhead
- Thread-safe client: Rejected as py-tars is fully async (no threading)

---

### 10. Extension and Customization Patterns

**Question**: How should services extend the centralized module for custom behavior?

**Research Sources**:
- SOLID principles (Open/Closed Principle)
- Python composition patterns
- Existing service-specific MQTT code analysis

**Findings**:
- **Service-Specific Needs**: Tool execution (llm-worker), RAG queries (memory-worker), phrase caching (tts-worker)
- **Current Pattern**: Service-specific wrapper classes around mqtt.Client
- **Extensibility**: Composition > Inheritance for flexibility

**Pattern Options**:
1. **Composition**: Service creates instance, adds custom methods that call centralized methods
2. **Subclassing**: Service subclasses centralized client, overrides methods
3. **Mixins**: Service applies mixin classes to centralized client
4. **Callbacks**: Service registers callbacks for lifecycle events (connect, disconnect, message)

**Decision**: Centralized module will support extension via **composition** pattern:
- Client exposes underlying mqtt.Client for advanced operations
- Services can wrap client in service-specific class
- Lifecycle events available via optional callbacks (on_connect, on_disconnect, on_message)

**Rationale**: Composition maintains loose coupling; callbacks provide extension points; direct client access for advanced use cases; avoids inheritance complexity.

**Alternatives Considered**:
- Mandatory subclassing: Rejected as it tightly couples services to client implementation
- Plugin system: Rejected as over-engineering for current needs (YAGNI)

---

## Technology Choices

### Primary Technologies

| Technology | Version | Purpose | Justification |
|------------|---------|---------|---------------|
| asyncio-mqtt | Latest (0.16.x) | MQTT client library | Already used across all services; wraps paho-mqtt with async/await support |
| Pydantic | v2.x | Config and message validation | Constitution requirement; already in tars-core |
| orjson | Latest | JSON serialization | Constitution requirement for performance; already in tars-core |
| Python | 3.11+ | Language | Constitution requirement for TaskGroup and performance |

### Testing Technologies

| Technology | Purpose | Justification |
|------------|---------|---------------|
| pytest | Test framework | Standard across py-tars |
| pytest-asyncio | Async test support | Required for testing async MQTT operations |
| Mosquitto | MQTT broker for integration tests | Already used in ops/compose.yml |

---

## Design Principles Application

### SOLID Principles

1. **Single Responsibility**: MQTTClient manages only MQTT connection lifecycle, publishing, and subscribing
2. **Open/Closed**: Extensible via composition and callbacks; closed to modification of core logic
3. **Liskov Substitution**: Implements Publisher/Subscriber protocols from tars.domain.ports
4. **Interface Segregation**: Separate methods for publish, subscribe, health, keepalive (not monolithic)
5. **Dependency Inversion**: Depends on Publisher/Subscriber abstractions, not concrete implementations

### DRY (Don't Repeat Yourself)

- Eliminates 1000+ LOC of duplicated MQTT connection/reconnection/envelope logic
- Single source of truth for MQTT URL parsing, client configuration, error handling

### KISS (Keep It Simple, Stupid)

- Module <500 LOC
- Simple API: connect(), publish_event(), subscribe(), shutdown()
- No unnecessary abstractions or patterns beyond documented use cases

### YAGNI (You Aren't Gonna Need It)

- No speculative features (e.g., message queuing, circuit breakers, rate limiting)
- Deduplication and keepalive are optional (disabled by default)
- Extension via composition, not built-in plugin system

---

## Summary of Decisions

### Core Module API (Minimal Viable Interface)

```python
class MQTTClient:
    """Centralized MQTT client for py-tars services."""
    
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
    ): ...
    
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def shutdown(self) -> None: ...
    
    async def publish_event(
        self,
        topic: str,
        event_type: str,
        data: dict | BaseModel,
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
    def client(self) -> mqtt.Client: ...  # For advanced usage
```

### Configuration Model

```python
class MQTTClientConfig(BaseModel):
    """Configuration for centralized MQTT client."""
    
    mqtt_url: str
    client_id: str
    source_name: str | None = None
    keepalive: int = 60
    enable_health: bool = False
    enable_heartbeat: bool = False
    heartbeat_interval: float = 5.0
    dedupe_ttl: float = 0
    dedupe_max_entries: int = 0
    reconnect_min_delay: float = 0.5
    reconnect_max_delay: float = 5.0
```

---

## Open Questions (None Remaining)

All unknowns from Technical Context have been resolved through research.

---

## Next Steps (Phase 1)

1. Create data-model.md defining MQTTClient, MQTTClientConfig, and supporting entities
2. Generate API contracts in contracts/ directory (OpenAPI-style MQTT client interface)
3. Create quickstart.md with usage examples for common patterns
4. Update agent context with this research (run update-agent-context.sh)
