# Implementation Plan: Centralized MQTT Client Module

**Branch**: `004-centralize-mqtt-client` | **Date**: 2025-10-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-centralize-mqtt-client/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Centralize MQTT client logic into a reusable module in `packages/tars-core` that provides connection management, automatic reconnection, envelope-based publishing/subscribing, health monitoring, and graceful shutdown. This eliminates code duplication across 8+ services and establishes a consistent, type-safe MQTT interface aligned with SOLID principles and constitutional requirements for event-driven architecture.

## Technical Context

**Language/Version**: Python 3.11+ (required for asyncio.TaskGroup, better typing)  
**Primary Dependencies**: asyncio-mqtt (wraps paho-mqtt<2.0), Pydantic v2, orjson  
**Storage**: N/A (message broker interaction only)  
**Testing**: pytest, pytest-asyncio for async tests, Mosquitto broker for integration  
**Target Platform**: Linux servers + Docker containers (Orange Pi 5 Max hardware)  
**Project Type**: Shared library package (packages/tars-core)  
**Performance Goals**: <10ms publish latency, <50ms reconnection, handle 100+ msg/sec  
**Constraints**: Must not block event loop (all CPU work via asyncio.to_thread), max 500 LOC for core module  
**Scale/Scope**: 8+ existing services, 10+ MQTT usage patterns to consolidate  

**Existing Patterns Identified**:
1. **URL Parsing**: All services parse `MQTT_URL` environment variable (mqtt://user:pass@host:port)
2. **Connection Management**: Manual reconnection logic with exponential backoff (varies by service)
3. **Envelope Wrapping**: Most services use `tars.contracts.envelope.Envelope` for message structure
4. **Health Publishing**: Services publish retained health to `system/health/<service>` topics
5. **Keepalive Heartbeats**: Some services (stt-worker) implement application-level heartbeats
6. **Subscription Handlers**: Pattern of registering topic → async handler mappings
7. **Message Deduplication**: Some services (tars-core adapters) dedupe by envelope ID
8. **QoS + Retain Flags**: Varies by service and topic type (health=QoS1+retain, streams=QoS0)
9. **Graceful Shutdown**: Cancel background tasks, close client cleanly
10. **Structured Logging**: Correlation IDs (request_id, utt_id) logged for MQTT operations

**Current Implementations to Consolidate**:
- `packages/tars-core/src/tars/adapters/mqtt_asyncio.py` - Publisher/Subscriber interfaces (partial)
- `apps/stt-worker/src/stt_worker/mqtt_utils.py` - MQTTClientWrapper (most complete)
- `apps/llm-worker/src/llm_worker/mqtt_client.py` - LLM-specific wrapper
- `apps/memory-worker/src/memory_worker/mqtt_client.py` - Memory-specific wrapper
- `apps/tts-worker/src/tts_worker/service.py` - Inline connection management
- `apps/router/src/router/__main__.py` - Inline connection management
- `apps/movement-service/src/movement_service/service.py` - Inline connection management
- `apps/ui-web/src/ui_web/__main__.py` - Inline connection management

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Event-Driven Architecture ✅ PASS (Re-validated)
- **Status**: COMPLIANT - Module enables services to communicate exclusively via MQTT
- **Validation**: Centralized client enforces Envelope contract, typed Pydantic models, orjson serialization
- **Post-Design**: API contract validates all published events use Envelope wrapping; no direct service calls

### II. Typed Contracts ✅ PASS (Re-validated)
- **Status**: COMPLIANT - All public APIs have complete type hints
- **Validation**: MQTTClient, MQTTClientConfig, HealthStatus, ConnectionParams all use Pydantic v2
- **Post-Design**: data-model.md shows complete type coverage; no `Any` types in public API

### III. Async-First Concurrency ✅ PASS (Re-validated)
- **Status**: COMPLIANT - Module uses asyncio with proper event loop hygiene
- **Validation**: Background tasks for dispatch/heartbeat; reconnection via exponential backoff; graceful cancellation
- **Post-Design**: State machine shows no blocking operations; all I/O is async

### IV. Test-First Development ✅ PASS (Re-validated)
- **Status**: COMPLIANT - Contract tests, integration tests, async tests planned
- **Validation**: quickstart.md includes testing examples; test fixtures for mocking
- **Post-Design**: Test strategy defined for unit (mocking), integration (Mosquitto), contract (Envelope validation)
- **TDD Workflow Enforced**: 
  - Write tests FIRST for each new object/method (MQTTClient, MQTTClientConfig, MessageDeduplicator, etc.)
  - Define expected behavior in test assertions before implementation
  - Verify tests FAIL (red state)
  - Implement minimum code to make tests PASS (green state)
  - Refactor while keeping tests green
  - Each entity in data-model.md requires corresponding test suite before implementation

### V. Configuration via Environment ✅ PASS (Re-validated)
- **Status**: COMPLIANT - All configuration from environment variables
- **Validation**: MQTTClientConfig.from_env() parses environment once at startup
- **Post-Design**: 11 environment variables documented; typed config object prevents runtime os.environ access

### VI. Observability & Health Monitoring ✅ PASS (Re-validated)
- **Status**: COMPLIANT - Structured logging with correlation IDs built-in
- **Validation**: publish_health() API provided; HealthStatus model enforces structure
- **Post-Design**: Health publishing to system/health/{client_id} with QoS 1 + retain; heartbeat to system/keepalive/{client_id}

### VII. Simplicity & YAGNI ✅ PASS (Re-validated)
- **Status**: COMPLIANT - Minimal API covering documented use cases
- **Justification**: Consolidating 8+ duplicate implementations into <500 LOC module
- **Post-Design Validation**:
  - Core module has 7 public methods (connect, disconnect, shutdown, publish_event, publish_health, subscribe, 2 properties)
  - Optional features are disabled by default (health, heartbeat, deduplication)
  - No speculative features beyond current usage patterns
  - Extension via composition (not inheritance or plugins)
- **Complexity Reduction**: Eliminates ~1000 LOC of duplicated MQTT code across services

## Project Structure

### Documentation (this feature)

```
specs/004-centralize-mqtt-client/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
└── contracts/           # Phase 1 output (/speckit.plan command)
    └── mqtt_client_api.yaml  # OpenAPI-style interface definition
```

### Source Code (repository root)

```
packages/tars-core/
├── src/tars/
│   ├── adapters/
│   │   ├── mqtt_asyncio.py       # EXISTING - Publisher/Subscriber interfaces
│   │   └── mqtt_client.py        # NEW - Centralized MQTT client manager
│   ├── domain/
│   │   └── ports.py              # EXISTING - Publisher/Subscriber protocols
│   └── contracts/
│       └── envelope.py           # EXISTING - Message envelope contract
└── tests/
    ├── unit/
    │   └── test_mqtt_client.py   # NEW - Unit tests for client logic
    ├── integration/
    │   └── test_mqtt_integration.py  # NEW - Integration tests with Mosquitto
    └── contract/
        └── test_mqtt_contracts.py    # NEW - Envelope validation tests

apps/
├── stt-worker/
│   └── src/stt_worker/
│       └── mqtt_utils.py         # MIGRATE - Remove after migration to centralized
├── llm-worker/
│   └── src/llm_worker/
│       └── mqtt_client.py        # MIGRATE - Remove after migration to centralized
├── memory-worker/
│   └── src/memory_worker/
│       └── mqtt_client.py        # MIGRATE - Remove after migration to centralized
├── tts-worker/
│   └── src/tts_worker/
│       └── service.py            # MIGRATE - Use centralized client
├── router/
│   └── src/router/
│       └── __main__.py           # MIGRATE - Use centralized client
└── [other services follow same pattern]
```

**Structure Decision**: Single shared library project using existing `packages/tars-core` package. The centralized MQTT client will live in `src/tars/adapters/mqtt_client.py` and build upon existing `mqtt_asyncio.py` Publisher/Subscriber interfaces. Services will import from `tars.adapters.mqtt_client` and migrate away from custom MQTT wrappers.

**Test-Driven Development Workflow**: All implementation follows strict TDD:
1. Write test defining expected behavior (red)
2. Implement minimum code to pass (green)
3. Refactor while keeping tests green
4. Each object/method has tests written BEFORE implementation

## Complexity Tracking

*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Abstraction layer over asyncio-mqtt | Eliminate 8+ duplicate MQTT implementations; enforce consistent envelope handling, reconnection, and error handling | Direct asyncio-mqtt usage in each service leads to code duplication, inconsistent error handling, drift in reconnection strategies, and requires updating all services for MQTT-related bug fixes |
| Module size approaching 500 LOC | Consolidate connection management, reconnection logic, envelope publishing, subscription dispatch, deduplication, keepalive, health publishing, and graceful shutdown | Splitting into multiple smaller modules would fragment cohesive MQTT client lifecycle management and make imports more complex for consuming services |

**Justification Summary**: The abstraction reduces total system complexity by consolidating 1000+ LOC of duplicated MQTT code across services into <500 LOC centralized module. This aligns with DRY principle while maintaining KISS through a single, well-documented API surface.

## Test-Driven Development Workflow

**Mandatory TDD Process** (per Constitution Principle IV):

### Implementation Order for Each Object/Method

1. **Write Test First (RED)**
   - Define test class/function for the object being created
   - Write assertions describing expected behavior
   - Include edge cases and error conditions
   - Run test suite → verify test FAILS with expected error
   - Commit test in "red" state

2. **Implement Minimum Code (GREEN)**
   - Write simplest implementation to make test pass
   - Avoid over-engineering or premature optimization
   - Run test suite → verify test PASSES
   - Commit implementation in "green" state

3. **Refactor (KEEP GREEN)**
   - Improve code quality while tests remain green
   - Apply SOLID principles, remove duplication
   - Run test suite after each refactor → verify still PASSES
   - Commit refactored code

### Object-by-Object Test Coverage

Each entity from data-model.md requires tests BEFORE implementation:

**MQTTClientConfig**:
- `test_from_env_valid()` - Parse valid environment variables
- `test_from_env_missing_required()` - Fail on missing MQTT_URL
- `test_reconnect_delay_validation()` - Reject max < min delay
- `test_dedupe_validation()` - Require max_entries if ttl > 0

**ConnectionParams**:
- `test_parse_mqtt_url_full()` - Parse URL with credentials
- `test_parse_mqtt_url_minimal()` - Parse URL without credentials
- `test_parse_mqtt_url_invalid()` - Reject invalid URL format

**MessageDeduplicator**:
- `test_is_duplicate_first_message()` - Return False for new message
- `test_is_duplicate_repeat_message()` - Return True for duplicate
- `test_ttl_expiration()` - Evict expired entries
- `test_max_entries_limit()` - Enforce cache size limit

**MQTTClient** (lifecycle):
- `test_init_creates_client()` - Initialize with valid config
- `test_connect_establishes_connection()` - Connect to broker
- `test_connect_invalid_url()` - Fail on bad MQTT_URL
- `test_disconnect_closes_connection()` - Clean disconnect
- `test_shutdown_publishes_health()` - Publish health on shutdown

**MQTTClient** (publishing):
- `test_publish_event_wraps_envelope()` - Wrap data in Envelope
- `test_publish_event_serializes_orjson()` - Use orjson serialization
- `test_publish_event_not_connected()` - Fail if not connected
- `test_publish_health_qos_retain()` - Use QoS 1 + retain
- `test_publish_health_disabled()` - No-op if not enabled

**MQTTClient** (subscribing):
- `test_subscribe_registers_handler()` - Add handler to registry
- `test_subscribe_calls_client_subscribe()` - Subscribe to broker
- `test_subscribe_not_connected()` - Fail if not connected
- `test_handler_receives_message()` - Dispatch message to handler
- `test_handler_error_isolated()` - Continue on handler exception

**MQTTClient** (reconnection):
- `test_reconnect_exponential_backoff()` - Increase delay on retry
- `test_reconnect_resubscribes_topics()` - Restore subscriptions
- `test_reconnect_max_delay_cap()` - Cap at max_delay

**Integration Tests**:
- `test_end_to_end_publish_subscribe()` - Full flow with Mosquitto
- `test_reconnection_on_broker_restart()` - Survive broker restart
- `test_deduplication_prevents_reprocessing()` - Dedupe works

### Test Execution Before Implementation

**Rule**: No implementation commit without corresponding test commit first.

**Process**:
```bash
# 1. Write test for MQTTClientConfig.from_env()
git add tests/unit/test_mqtt_client_config.py
git commit -m "test: Add test for MQTTClientConfig.from_env() [RED]"

# 2. Run test suite (should fail)
pytest tests/unit/test_mqtt_client_config.py::test_from_env_valid
# Expected: ImportError or AttributeError (class doesn't exist yet)

# 3. Implement MQTTClientConfig.from_env()
git add src/tars/adapters/mqtt_client.py
git commit -m "feat: Implement MQTTClientConfig.from_env() [GREEN]"

# 4. Run test suite (should pass)
pytest tests/unit/test_mqtt_client_config.py::test_from_env_valid
# Expected: PASSED

# 5. Refactor if needed
git add src/tars/adapters/mqtt_client.py
git commit -m "refactor: Extract URL parsing to helper [GREEN]"
```

### Coverage Requirements

- **Unit tests**: 100% coverage of public methods
- **Integration tests**: Cover all message flows from API contract
- **Contract tests**: Validate all Envelope schemas and topic patterns
- **Async tests**: Use pytest-asyncio for all async methods

### Test Organization

```
packages/tars-core/tests/
├── unit/
│   ├── test_mqtt_client_config.py       # Config validation
│   ├── test_connection_params.py        # URL parsing
│   ├── test_message_deduplicator.py     # Dedup logic
│   ├── test_mqtt_client_lifecycle.py    # Connect/disconnect
│   ├── test_mqtt_client_publishing.py   # Publish methods
│   └── test_mqtt_client_subscribing.py  # Subscribe methods
├── integration/
│   ├── test_mqtt_end_to_end.py          # Full publish/subscribe flow
│   ├── test_mqtt_reconnection.py        # Connection resilience
│   └── test_mqtt_deduplication.py       # Dedupe with real messages
└── contract/
    ├── test_envelope_schemas.py         # Envelope validation
    └── test_mqtt_topic_patterns.py      # Topic pattern compliance
```
