# Planning Complete: Centralized MQTT Client

**Feature**: Centralized MQTT Client Module  
**Branch**: `004-centralize-mqtt-client`  
**Date**: 2025-10-16  
**Status**: ✅ Phase 0 & Phase 1 COMPLETE

---

## Summary

The planning phase for the centralized MQTT client module is complete. All technical unknowns have been resolved through research, data models have been defined, API contracts have been documented, and a comprehensive quickstart guide has been created.

---

## Artifacts Generated

### Phase 0: Research (COMPLETE)

**File**: `specs/004-centralize-mqtt-client/research.md`

**Contents**:
- 10 research tasks addressing all technical unknowns
- MQTT connection patterns across 8+ services cataloged
- Envelope wrapping and serialization patterns documented
- Subscription and handler dispatch patterns analyzed
- Health status, keepalive, and deduplication strategies evaluated
- QoS/retain patterns from constitution validated
- Graceful shutdown sequence defined
- Best practices for asyncio-mqtt documented
- Extension patterns for service-specific customization
- Technology choices justified (asyncio-mqtt, Pydantic v2, orjson)
- SOLID, DRY, KISS, YAGNI principles applied
- Minimal viable API designed

**Key Decisions**:
1. Auto-reconnect with exponential backoff (0.5s → 5s)
2. Handler registry pattern for topic subscriptions
3. Optional health publishing (disabled by default)
4. Optional application heartbeat with watchdog
5. Optional deduplication using envelope ID cache
6. QoS 0 default with explicit overrides
7. Extension via composition (not inheritance)
8. Configuration via typed MQTTClientConfig from environment

---

### Phase 1: Design & Contracts (COMPLETE)

#### 1. Data Model (`data-model.md`)

**Entities Defined**:
- **MQTTClient**: Central client with 12 configuration parameters, 4 state properties, lifecycle management
- **MQTTClientConfig**: Environment-driven configuration with 11 fields, validation rules
- **ConnectionParams**: Parsed MQTT URL components (hostname, port, credentials)
- **HealthStatus**: Health payload structure (ok, event, error, timestamp)
- **HeartbeatPayload**: Keepalive heartbeat structure (ok, event, timestamp)
- **MessageDeduplicator**: TTL-bound cache for duplicate detection
- **SubscriptionHandler**: Type alias for async message handlers

**State Machines**:
- MQTTClient lifecycle: Created → Connecting → Connected ↔ Reconnecting → Disconnecting → Disconnected
- Message processing flow: Receive → Dedupe check → Handler invocation → Error isolation
- Health publishing flow: Event → Envelope wrapping → Publish with QoS 1 + retain
- Heartbeat loop: Periodic publish with watchdog-triggered reconnection

**Validation Rules**:
- 15+ validation rules for initialization parameters
- Runtime validation for connected state, envelope structure, health status
- Resource constraints: max 1000 subscriptions, 2048 dedupe entries, 5s timeouts

**Test-Driven Development Checklist**:
- 70+ test cases defined covering all entities and methods
- Tests organized by entity: config, params, deduplicator, lifecycle, publishing, subscribing
- Integration tests for end-to-end flows, reconnection, deduplication
- Contract tests for Envelope schemas and topic patterns
- 100% coverage requirement for all public methods

#### 2. API Contract (`contracts/mqtt_client_api.yaml`)

**API Surface**:
- **Lifecycle**: `connect()`, `disconnect()`, `shutdown()` with state transitions
- **Publishing**: `publish_event()`, `publish_health()` with QoS/retain control
- **Subscription**: `subscribe()` with handler registry and error isolation
- **Properties**: `client`, `connected` for state inspection and advanced usage

**Message Flows**:
- Publish with Envelope: 5-step flow from service call to MQTT publish
- Subscribe with handler: 7-step flow from registration to message dispatch
- Reconnection flow: 7-step exponential backoff and recovery
- Graceful shutdown: 7-step health notification and cleanup

**QoS/Retain Patterns**:
- Health topics: QoS 1, retain=True
- Commands/responses: QoS 1, retain=False
- Streams/partials: QoS 0, retain=False
- Keepalive: QoS 0, retain=False

**Error Handling**:
- 6 error codes with recovery strategies
- Handler error isolation (no cascade failures)
- Connection failure auto-recovery

**Performance Targets**:
- Publish latency: <10ms
- Reconnection time: <50ms
- Message throughput: 100+ msg/sec
- Memory usage: ~5MB baseline, +2MB with deduplication

#### 3. Quickstart Guide (`quickstart.md`)

**Coverage**:
- Installation instructions
- 3 basic usage examples (publish-only, subscribe, context manager)
- Configuration via environment (11 variables documented)
- Publishing patterns (basic, correlation ID, QoS/retain, Pydantic models)
- Subscription patterns (topic-specific, wildcards, error isolation)
- Health status publishing (4 event types)
- Application heartbeat with watchdog
- Message deduplication (when to use, how it works)
- Reconnection handling (automatic, configurable backoff)
- Graceful shutdown (2 patterns)
- 4 common patterns (request-response, multi-handler service, streaming, extension)
- Migration guide from custom wrappers
- **Test-Driven Development workflow** (write tests first, RED-GREEN-REFACTOR)
- **Testing examples** (mocking, integration with Mosquitto, TDD process)
- **Example TDD implementation** (MessageDeduplicator feature from test to code)
- **Test organization** by entity with 100% coverage requirement
- Troubleshooting (4 common issues)
- Best practices (5 categories)

---

### Phase 1: Agent Context Update (COMPLETE)

**Command**: `.specify/scripts/bash/update-agent-context.sh copilot`

**Changes Made**:
- Added Python 3.11+ to technology stack
- Added asyncio-mqtt, Pydantic v2, orjson to frameworks
- Added "N/A (message broker interaction only)" for database
- Updated `.github/copilot-instructions.md` with centralized MQTT client context

---

### Constitutional Compliance (Re-validated)

All 7 constitutional principles PASS after Phase 1 design:

✅ **I. Event-Driven Architecture** - Enforces MQTT-only communication via Envelope contract  
✅ **II. Typed Contracts** - Complete Pydantic v2 models, no `Any` types in public API  
✅ **III. Async-First Concurrency** - Background tasks, no blocking, graceful cancellation  
✅ **IV. Test-First Development** - **70+ test cases defined, TDD workflow enforced, tests written BEFORE implementation**  
✅ **V. Configuration via Environment** - 11 env vars, typed config object  
✅ **VI. Observability & Health Monitoring** - Structured logging, health/heartbeat APIs  
✅ **VII. Simplicity & YAGNI** - 7 public methods, optional features, <500 LOC target  

**TDD Enforcement Added**:
- All objects/methods require tests FIRST (RED state)
- Minimum implementation to pass tests (GREEN state)
- Refactor while keeping tests green
- 100% coverage requirement for public methods
- Test checklist with 70+ test cases defined in data-model.md
- TDD workflow examples in quickstart.md
- Test organization by entity (config, lifecycle, publishing, subscribing, etc.)

---

## Complexity Justification (Validated)

| Aspect | Justification |
|--------|---------------|
| Abstraction layer | Eliminates ~1000 LOC of duplicated code across 8+ services |
| Module size | <500 LOC for centralized module vs. sum of existing implementations |
| Extension pattern | Composition over inheritance reduces coupling |
| Optional features | Dedup/heartbeat/health disabled by default (YAGNI compliant) |

**Simpler Alternative Rejected**: Keep duplicated code → maintenance burden, inconsistent error handling, bug fix propagation

---

## Technical Context (All Unknowns Resolved)

✅ Language/Version: Python 3.11+ (asyncio.TaskGroup, better typing)  
✅ Dependencies: asyncio-mqtt, Pydantic v2, orjson (all existing in tars-core)  
✅ Testing: pytest, pytest-asyncio, Mosquitto for integration  
✅ Target Platform: Linux servers + Docker (Orange Pi 5 Max)  
✅ Project Type: Shared library (packages/tars-core)  
✅ Performance: <10ms publish, <50ms reconnect, 100+ msg/sec  
✅ Constraints: <500 LOC, no event loop blocking  
✅ Scale: 8+ services, 10+ usage patterns  

---

## File Locations

```
specs/004-centralize-mqtt-client/
├── plan.md                          # ← Implementation plan (this overview)
├── research.md                      # ← Phase 0 research findings
├── data-model.md                    # ← Phase 1 entity definitions
├── quickstart.md                    # ← Phase 1 usage guide
└── contracts/
    └── mqtt_client_api.yaml         # ← Phase 1 API contract
```

---

## Next Steps (Phase 2 - NOT done by /speckit.plan)

The planning phase ends here. The next phase (`/speckit.tasks`) will:

1. Break down implementation into concrete tasks
2. Create task breakdown in `specs/004-centralize-mqtt-client/tasks.md`
3. Prioritize tasks for incremental development
4. Define acceptance criteria for each task
5. Identify task dependencies and ordering

**Do NOT proceed to Phase 2 without user confirmation**.

---

## Branch Status

- **Branch**: `004-centralize-mqtt-client`
- **Planning Status**: ✅ COMPLETE
- **Implementation Status**: ⏸️ NOT STARTED (awaiting user approval)
- **Next Command**: `/speckit.tasks` (when ready to proceed)

---

## Summary for User

I've completed the planning phase for the centralized MQTT client module. Here's what was generated:

1. **Research Document** (`research.md`): 10 research tasks covering all MQTT patterns, best practices, and design decisions
2. **Data Model** (`data-model.md`): 7 entities, state machines, validation rules, type signatures
3. **API Contract** (`contracts/mqtt_client_api.yaml`): Complete API specification with methods, flows, QoS patterns, performance targets
4. **Quickstart Guide** (`quickstart.md`): Comprehensive usage guide with examples, migration path, testing, troubleshooting
5. **Agent Context Update**: Updated `.github/copilot-instructions.md` with new technology stack

**Constitutional Compliance**: All 7 principles validated ✅  
**Technical Unknowns**: All resolved ✅  
**Ready for Implementation**: Yes (pending approval) ✅  

The centralized MQTT client will:
- Eliminate ~1000 LOC of duplicated code across 8+ services
- Provide consistent reconnection, health publishing, and error handling
- Support optional deduplication, heartbeat, and health monitoring
- Use <500 LOC for the core module
- Follow SOLID, DRY, KISS, YAGNI principles
- Maintain full backward compatibility during migration

**Location**: All artifacts in `/home/james/git/py-tars/specs/004-centralize-mqtt-client/`  
**Branch**: `004-centralize-mqtt-client`  

Ready to proceed with implementation? Run `/speckit.tasks` to break down into concrete development tasks.
