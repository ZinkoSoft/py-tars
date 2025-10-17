# Feature Specification: Centralized MQTT Client Module

**Feature Branch**: `004-centralize-mqtt-client`  
**Created**: 2025-10-16  
**Status**: Draft  
**Input**: User description: "we are using mqtt client in mostly all of the apps, some have a specific python file dedicated, some have just a service.py that utilize mqtt as a client. I would like all of my mqtt to be in one core file so that we can utilize it without having to rewrite it over and over again. think re-usability and extension if needed. follow SOLID, YAGNI, KISS, DRY etc"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Developer Creates New App with MQTT (Priority: P1)

A developer creates a new application service (e.g., vision-processor) and needs to publish events and subscribe to topics using MQTT.

**Why this priority**: This is the most common scenario and represents the primary value of centralization - enabling rapid development of new services without duplicating MQTT client code.

**Independent Test**: Can be fully tested by creating a minimal new service that imports the centralized MQTT module, connects to broker, publishes a test message, and receives it via subscription. Success means zero custom MQTT connection logic in the new service.

**Acceptance Scenarios**:

1. **Given** a developer needs MQTT for a new service, **When** they import the centralized module and configure connection via environment variables, **Then** they can connect to the broker without writing connection logic
2. **Given** the centralized module is available, **When** a developer needs to publish events with envelope wrapping, **Then** they can call a single publish method with event type and payload without manual serialization
3. **Given** the service requires topic subscriptions, **When** the developer registers handlers for specific topics, **Then** messages are automatically deserialized and dispatched to handlers

---

### User Story 2 - Developer Migrates Existing App to Centralized Client (Priority: P2)

A developer refactors an existing application (e.g., llm-worker, memory-worker) to use the centralized MQTT module instead of its custom implementation.

**Why this priority**: Migration validates that the centralized module meets all existing use cases and reduces maintenance burden across the codebase.

**Independent Test**: Can be tested by migrating one existing service (e.g., memory-worker) to use the centralized module, running all existing integration tests, and verifying identical behavior with reduced lines of code.

**Acceptance Scenarios**:

1. **Given** an existing service with custom MQTT client code, **When** the developer replaces it with the centralized module, **Then** all existing MQTT functionality continues to work without behavioral changes
2. **Given** the service uses specific patterns (correlation IDs, QoS levels, retained messages), **When** migrated to centralized module, **Then** all patterns are supported through configuration
3. **Given** migration is complete, **When** the developer reviews the code, **Then** MQTT-related code is reduced by at least 50% compared to custom implementation

---

### User Story 3 - Developer Extends MQTT Client for New Use Case (Priority: P3)

A developer needs to add new MQTT functionality (e.g., custom message filtering, batching, circuit breaker) that isn't currently available.

**Why this priority**: Extension scenarios are less frequent than basic usage, but the module must be designed to accommodate future requirements without breaking existing implementations.

**Independent Test**: Can be tested by creating a new mixin or extension class that adds custom behavior (e.g., message batching) and integrating it into one service without modifying the core module.

**Acceptance Scenarios**:

1. **Given** a new MQTT pattern is needed, **When** a developer creates an extension class, **Then** they can add functionality without modifying the core centralized module
2. **Given** the extension is implemented, **When** integrated into a service, **Then** it works alongside existing functionality without conflicts
3. **Given** multiple services use different extensions, **When** they run simultaneously, **Then** each service operates independently with its specific extensions

---

### Edge Cases

- What happens when MQTT broker connection is lost during message publish?
- How does the system handle rapid reconnection attempts (connection storms)?
- What happens when a service subscribes to a topic that receives high-volume messages (backpressure)?
- How are duplicate messages handled when connection is re-established (deduplication)?
- What happens when environment configuration is missing or malformed?
- How does the module handle concurrent publish operations from multiple async tasks?
- What happens when message payload exceeds broker limits?
- How are subscription handler errors isolated to prevent cascading failures?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Module MUST provide a single entry point for MQTT connection management that accepts configuration via environment variables
- **FR-002**: Module MUST support publishing messages with automatic envelope wrapping, event typing, and correlation ID support
- **FR-003**: Module MUST support subscribing to topics with automatic message deserialization and handler dispatch
- **FR-004**: Module MUST parse MQTT URLs (mqtt://user:pass@host:port) into connection parameters automatically
- **FR-005**: Module MUST provide automatic reconnection with exponential backoff when broker connection is lost
- **FR-006**: Module MUST support QoS levels (0, 1, 2) and retained message flags for both publish and subscribe operations
- **FR-007**: Module MUST handle message deduplication using envelope IDs to prevent duplicate processing on reconnection
- **FR-008**: Module MUST provide structured logging with correlation IDs for all MQTT operations (connect, disconnect, publish, subscribe)
- **FR-009**: Module MUST support health status publishing with retained messages for system monitoring
- **FR-010**: Module MUST allow services to register multiple topic subscriptions with independent message handlers
- **FR-011**: Module MUST support graceful shutdown that closes connections cleanly and cancels background tasks
- **FR-012**: Module MUST be compatible with asyncio-mqtt library and async/await patterns used across all services
- **FR-013**: Module MUST provide type hints for all public APIs to support IDE autocomplete and static type checking
- **FR-014**: Module MUST support both dictionary payloads and Pydantic model serialization for message publishing
- **FR-015**: Module MUST allow optional extensions through composition without requiring modification of core functionality
- **FR-016**: Module MUST maintain compatibility with existing Envelope contract and event type registry
- **FR-017**: Module MUST support application-level keepalive heartbeat publishing for connection monitoring
- **FR-018**: Module MUST handle publish failures with configurable retry logic and drop messages after max retries

### Key Entities

- **MQTTClient**: Central client abstraction that manages broker connection, reconnection, and lifecycle
- **Connection Configuration**: Host, port, username, password, client ID, keepalive interval parsed from environment
- **Message Envelope**: Wrapper containing event type, correlation ID, timestamp, source, and payload data
- **Subscription Handler**: Async callable that processes messages for a specific topic
- **Publisher Interface**: Abstract interface for publishing messages to topics with QoS and retain flags
- **Subscriber Interface**: Abstract interface for subscribing to topics and receiving messages
- **Deduplicator**: Component that tracks seen message IDs using TTL-based cache to prevent duplicate processing

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: New services integrate MQTT functionality in under 10 lines of code (import, configure, connect, subscribe/publish)
- **SC-002**: Existing services reduce MQTT-related code by at least 50% when migrated to centralized module
- **SC-003**: Zero MQTT connection logic is duplicated across any two services after migration
- **SC-004**: All existing MQTT-based integration tests pass without modification after services migrate to centralized module
- **SC-005**: Module supports all current MQTT usage patterns (10+ different patterns across 8+ services) through single unified interface
- **SC-006**: New developers can integrate MQTT into a service without reading broker-specific documentation (self-documenting API)
- **SC-007**: Services using centralized module automatically reconnect within 10 seconds of broker availability after connection loss
- **SC-008**: 100% of centralized module APIs have complete type hints that pass mypy strict mode validation

## Assumptions *(optional)*

- All services use Python 3.11+ with asyncio support
- All services use asyncio-mqtt library as the underlying MQTT client (not paho-mqtt directly)
- All services wrap messages in Envelope contract for event typing and correlation
- All services use orjson for JSON serialization due to performance requirements
- All services configure MQTT connection via MQTT_URL environment variable
- Existing tars-core package in packages/tars-core is the appropriate location for centralized module
- Existing adapters/mqtt_asyncio.py module serves as foundation but needs consolidation with other patterns
- Services require both Publisher and Subscriber interfaces but may use them independently
- Connection failures should not crash services (automatic reconnection is expected)
- Message ordering is not guaranteed across reconnections (idempotent handlers required)

## Dependencies *(optional)*

- **tars-core package**: Centralized module will be added to existing packages/tars-core/src/tars/adapters/
- **Envelope contract**: Module depends on tars.contracts.envelope.Envelope for message wrapping
- **asyncio-mqtt library**: Module wraps asyncio-mqtt.Client for async MQTT operations
- **orjson library**: Used for high-performance JSON serialization of message payloads
- **Pydantic v2**: Used for model validation and serialization in Envelope and event contracts
- **Existing services**: Migration requires updating 8+ services in apps/ directory
- **Environment configuration**: All services must provide MQTT_URL environment variable

## Out of Scope *(optional)*

- Support for MQTT v5 specific features (current architecture uses MQTT v3.1.1)
- Built-in circuit breaker or rate limiting (services implement this at domain level if needed)
- Message persistence or queuing beyond broker capabilities
- Alternative message brokers (e.g., RabbitMQ, Kafka) - MQTT-specific implementation
- GUI or CLI tools for MQTT debugging (separate tooling concern)
- Automatic topic registration or discovery (topic contracts defined in code/docs)
- Message encryption beyond TLS transport (application-level encryption handled separately)
- Support for synchronous (non-async) MQTT operations (all services use asyncio)

## Technical Constraints *(optional)*

- Must maintain backward compatibility with existing Envelope contract structure
- Must not break existing service-specific MQTT patterns during migration period
- Must work with mosquitto broker configuration used in ops/compose.yml
- Must support both development (local) and production (Docker network) environments
- Module file size should remain under 500 lines to maintain KISS principle
- Must not introduce new external dependencies beyond what's already in tars-core
- Must support running multiple service instances with unique client IDs
- Must handle network_mode: host configuration used in Docker services

## Risk Analysis *(optional)*

**Risk 1 - Migration Breaking Changes**  
**Likelihood**: Medium | **Impact**: High  
**Description**: Migrating existing services to centralized module introduces subtle behavior changes that break existing functionality  
**Mitigation**: Comprehensive integration test suite; gradual migration one service at a time; feature flags to switch between old/new implementations

**Risk 2 - Performance Regression**  
**Likelihood**: Low | **Impact**: Medium  
**Description**: Additional abstraction layers in centralized module introduce latency or throughput degradation  
**Mitigation**: Benchmark publish/subscribe latency before and after migration; optimize hot paths; use profiling to identify bottlenecks

**Risk 3 - Over-Engineering**  
**Likelihood**: Medium | **Impact**: Medium  
**Description**: Attempting to accommodate all potential future use cases creates overly complex API that violates YAGNI/KISS  
**Mitigation**: Start with minimal viable API covering current use cases only; add extensions when actually needed; regular code review against SOLID principles

**Risk 4 - Incomplete Pattern Coverage**  
**Likelihood**: Medium | **Impact**: Medium  
**Description**: Centralized module doesn't support all existing MQTT patterns, forcing services to maintain custom workarounds  
**Mitigation**: Comprehensive audit of all existing MQTT usage patterns; create pattern catalog; validate each pattern against centralized API before migration
