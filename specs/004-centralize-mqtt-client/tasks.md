---
description: "Task list for Centralized MQTT Client Module feature implementation"
---

# Tasks: Centralized MQTT Client Module

**Feature Branch**: `004-centralize-mqtt-client`
**Input**: Design documents from `/specs/004-centralize-mqtt-client/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/mqtt_client_api.yaml

**TDD Mandate**: All implementation follows strict Test-Driven Development:
1. Write test FIRST (RED state - test fails)
2. Implement minimum code to pass (GREEN state)
3. Refactor while keeping tests green
4. No implementation without corresponding test written first

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure for centralized MQTT module

- [ ] T001 [P] Verify packages/tars-core package structure exists with src/tars/adapters/
- [ ] T002 [P] Create test directory structure: packages/tars-core/tests/{unit,integration,contract}/
- [ ] T003 [P] Update packages/tars-core/pyproject.toml to ensure dependencies (asyncio-mqtt, pydantic>=2.0, orjson)
- [ ] T004 [P] Create test fixtures file packages/tars-core/tests/conftest.py with MQTT mocking utilities
- [ ] T005 [P] Verify constitution compliance checklist passes for event-driven, typed, async-first, env config

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 Write test for ConnectionParams URL parsing in packages/tars-core/tests/unit/test_connection_params.py [RED]
- [ ] T007 Implement ConnectionParams model in packages/tars-core/src/tars/adapters/mqtt_client.py to pass test [GREEN]
- [ ] T008 Write test for MQTTClientConfig.from_env() in packages/tars-core/tests/unit/test_mqtt_client_config.py [RED]
- [ ] T009 Implement MQTTClientConfig model in packages/tars-core/src/tars/adapters/mqtt_client.py to pass test [GREEN]
- [ ] T010 Write test for HealthStatus validation in packages/tars-core/tests/unit/test_mqtt_client_config.py [RED]
- [ ] T011 Implement HealthStatus and HeartbeatPayload models in packages/tars-core/src/tars/adapters/mqtt_client.py [GREEN]
- [ ] T012 Write test for MessageDeduplicator basic dedup in packages/tars-core/tests/unit/test_message_deduplicator.py [RED]
- [ ] T013 Implement MessageDeduplicator with TTL cache in packages/tars-core/src/tars/adapters/mqtt_client.py [GREEN]
- [ ] T014 Add comprehensive tests for MessageDeduplicator (TTL eviction, max entries, seq/hash keys) [RED→GREEN]

**Checkpoint**: Foundation ready - MQTTClient class can now be implemented with all dependencies available

---

## Phase 3: User Story 1 - Developer Creates New App with MQTT (Priority: P1) 🎯 MVP

**Goal**: Enable developers to integrate MQTT in new services with minimal boilerplate (<10 LOC)

**Independent Test**: Create a test service that imports MQTTClient, connects to broker, publishes a message, receives via subscription - zero custom connection logic required

### Tests for User Story 1 (TDD REQUIRED)

**NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T015 [P] [US1] Write test for MQTTClient.__init__() validation in packages/tars-core/tests/unit/test_mqtt_client_lifecycle.py [RED]
- [ ] T016 [P] [US1] Write test for MQTTClient.connect() success in packages/tars-core/tests/unit/test_mqtt_client_lifecycle.py [RED]
- [ ] T017 [P] [US1] Write test for MQTTClient.connect() invalid URL in packages/tars-core/tests/unit/test_mqtt_client_lifecycle.py [RED]
- [ ] T018 [P] [US1] Write test for MQTTClient.publish_event() wraps Envelope in packages/tars-core/tests/unit/test_mqtt_client_publishing.py [RED]
- [ ] T019 [P] [US1] Write test for MQTTClient.subscribe() registers handler in packages/tars-core/tests/unit/test_mqtt_client_subscribing.py [RED]
- [ ] T020 [P] [US1] Write integration test for end-to-end publish/subscribe in packages/tars-core/tests/integration/test_end_to_end.py [RED]

### Implementation for User Story 1

- [ ] T021 [US1] Implement MQTTClient.__init__() with config validation in packages/tars-core/src/tars/adapters/mqtt_client.py [GREEN]
- [ ] T022 [US1] Implement MQTTClient.connect() with asyncio-mqtt client creation and connection in packages/tars-core/src/tars/adapters/mqtt_client.py [GREEN]
- [ ] T023 [US1] Implement MQTTClient._start_dispatch_task() for background message processing in packages/tars-core/src/tars/adapters/mqtt_client.py [GREEN]
- [ ] T024 [US1] Implement MQTTClient.publish_event() with Envelope wrapping and orjson serialization in packages/tars-core/src/tars/adapters/mqtt_client.py [GREEN]
- [ ] T025 [US1] Implement MQTTClient.subscribe() with handler registration and broker subscription in packages/tars-core/src/tars/adapters/mqtt_client.py [GREEN]
- [ ] T026 [US1] Implement MQTTClient._dispatch_messages() loop with handler invocation and error isolation in packages/tars-core/src/tars/adapters/mqtt_client.py [GREEN]
- [ ] T027 [US1] Implement MQTTClient.client and MQTTClient.connected properties in packages/tars-core/src/tars/adapters/mqtt_client.py [GREEN]
- [ ] T028 [US1] Add structured logging with correlation IDs to all MQTTClient methods in packages/tars-core/src/tars/adapters/mqtt_client.py
- [ ] T029 [US1] Write contract test validating Envelope schema for published messages in packages/tars-core/tests/contract/test_envelope_schemas.py [RED→GREEN]
- [ ] T030 [US1] Update packages/tars-core/README.md with basic usage example for new services

**Checkpoint**: At this point, User Story 1 should be fully functional - new services can import MQTTClient and use publish/subscribe with <10 LOC

---

## Phase 4: User Story 2 - Developer Migrates Existing App to Centralized Client (Priority: P2)

**Goal**: Reduce MQTT-related code in existing services by 50%+ without behavioral changes

**Independent Test**: Migrate memory-worker to use centralized client, run all existing integration tests, verify identical behavior with reduced LOC

### Tests for User Story 2 (TDD REQUIRED)

- [ ] T031 [P] [US2] Write test for MQTTClient.disconnect() clean shutdown in packages/tars-core/tests/unit/test_mqtt_client_lifecycle.py [RED]
- [ ] T032 [P] [US2] Write test for MQTTClient.shutdown() graceful sequence in packages/tars-core/tests/unit/test_mqtt_client_lifecycle.py [RED]
- [ ] T033 [P] [US2] Write test for MQTTClient.publish_health() with QoS 1 + retain in packages/tars-core/tests/unit/test_mqtt_client_publishing.py [RED]
- [ ] T034 [P] [US2] Write test for reconnection with exponential backoff in packages/tars-core/tests/unit/test_mqtt_client_lifecycle.py [RED]
- [ ] T035 [P] [US2] Write test for subscription reestablishment after reconnect in packages/tars-core/tests/integration/test_reconnection.py [RED]

### Implementation for User Story 2

- [ ] T036 [US2] Implement MQTTClient.disconnect() with task cancellation and client cleanup in packages/tars-core/src/tars/adapters/mqtt_client.py [GREEN]
- [ ] T037 [US2] Implement MQTTClient.shutdown() with health publish and graceful timeout in packages/tars-core/src/tars/adapters/mqtt_client.py [GREEN]
- [ ] T038 [US2] Implement MQTTClient.publish_health() with retained health status to system/health/{client_id} in packages/tars-core/src/tars/adapters/mqtt_client.py [GREEN]
- [ ] T039 [US2] Implement MQTTClient._reconnect() with exponential backoff (0.5s → 5s) in packages/tars-core/src/tars/adapters/mqtt_client.py [GREEN]
- [ ] T040 [US2] Implement subscription tracking in _subscriptions set and resubscribe logic on reconnect in packages/tars-core/src/tars/adapters/mqtt_client.py [GREEN]
- [ ] T041 [US2] Implement MQTTClient.__aenter__() and __aexit__() for async context manager support in packages/tars-core/src/tars/adapters/mqtt_client.py [GREEN]
- [ ] T042 [P] [US2] Migrate apps/memory-worker/src/memory_worker/mqtt_client.py to use centralized MQTTClient
- [ ] T043 [P] [US2] Migrate apps/llm-worker/src/llm_worker/mqtt_client.py to use centralized MQTTClient
- [ ] T044 [P] [US2] Update apps/memory-worker tests to verify no behavioral changes after migration
- [ ] T045 [US2] Create migration guide in packages/tars-core/docs/MIGRATION_GUIDE.md with before/after examples

**Checkpoint**: At this point, User Stories 1 AND 2 should both work - new services can use centralized client AND existing services can migrate with reduced code

---

## Phase 5: User Story 3 - Developer Extends MQTT Client for New Use Case (Priority: P3)

**Goal**: Allow service-specific extensions via composition without modifying core module

**Independent Test**: Create extension class that adds custom behavior (e.g., message batching), integrate into service without changing core mqtt_client.py

### Tests for User Story 3 (TDD REQUIRED)

- [ ] T046 [P] [US3] Write test for heartbeat task publishing to system/keepalive/{client_id} in packages/tars-core/tests/unit/test_mqtt_client_lifecycle.py [RED]
- [ ] T047 [P] [US3] Write test for heartbeat watchdog triggering reconnect on 3x failure in packages/tars-core/tests/integration/test_reconnection.py [RED]
- [ ] T048 [P] [US3] Write test for deduplication preventing duplicate processing in packages/tars-core/tests/integration/test_deduplication.py [RED]
- [ ] T049 [P] [US3] Write test for accessing underlying client via .client property in packages/tars-core/tests/unit/test_mqtt_client_lifecycle.py [RED]

### Implementation for User Story 3

- [ ] T050 [US3] Implement MQTTClient._start_heartbeat_task() with configurable interval in packages/tars-core/src/tars/adapters/mqtt_client.py [GREEN]
- [ ] T051 [US3] Implement heartbeat watchdog logic for connection liveness detection in packages/tars-core/src/tars/adapters/mqtt_client.py [GREEN]
- [ ] T052 [US3] Integrate MessageDeduplicator into MQTTClient._dispatch_messages() when dedupe_ttl > 0 in packages/tars-core/src/tars/adapters/mqtt_client.py [GREEN]
- [ ] T053 [US3] Expose underlying mqtt.Client via read-only .client property for advanced operations in packages/tars-core/src/tars/adapters/mqtt_client.py [GREEN]
- [ ] T054 [P] [US3] Create extension example in packages/tars-core/examples/custom_mqtt_wrapper.py showing composition pattern
- [ ] T055 [P] [US3] Document extension patterns in packages/tars-core/README.md (composition, callbacks, direct client access)
- [ ] T056 [US3] Update quickstart.md with extension examples (pattern 4: Extending the Client)

**Checkpoint**: All user stories should now be independently functional - new apps, migrations, and extensions all supported

---

## Phase 6: Documentation & Validation

**Purpose**: Comprehensive documentation and validation across all user stories

- [ ] T057 [P] Update packages/tars-core/README.md with complete API reference and usage examples
- [ ] T058 [P] Create packages/tars-core/docs/API.md with detailed method signatures and parameters
- [ ] T059 [P] Verify all environment variables documented in packages/tars-core/docs/CONFIGURATION.md
- [ ] T060 [P] Update specs/004-centralize-mqtt-client/quickstart.md with additional migration examples
- [ ] T061 [P] Add type hints validation: run mypy packages/tars-core/src/tars/adapters/mqtt_client.py --strict
- [ ] T062 [P] Verify 100% test coverage: pytest packages/tars-core/tests/ --cov=tars.adapters.mqtt_client --cov-report=html
- [ ] T063 Run quickstart.md validation scenarios against real Mosquitto broker
- [ ] T064 Update root README.md with centralized MQTT client as a core feature

---

## Phase 7: Service Migrations (Remaining Services)

**Purpose**: Migrate all remaining services to use centralized client

- [ ] T065 [P] Migrate apps/stt-worker/src/stt_worker/mqtt_utils.py to centralized client (remove MQTTClientWrapper)
- [ ] T066 [P] Migrate apps/router/src/router/__main__.py inline MQTT usage to centralized client
- [ ] T067 [P] Migrate apps/tts-worker/src/tts_worker/service.py inline MQTT usage to centralized client
- [ ] T068 [P] Migrate apps/movement-service/src/movement_service/service.py inline MQTT usage to centralized client
- [ ] T069 [P] Migrate apps/ui-web/src/ui_web/__main__.py inline MQTT usage to centralized client
- [ ] T070 [P] Migrate apps/wake-activation inline MQTT usage to centralized client (if applicable)
- [ ] T071 [P] Migrate apps/mcp-bridge inline MQTT usage to centralized client (if applicable)
- [ ] T072 Update all migrated service READMEs with new MQTT client usage
- [ ] T073 Remove deprecated MQTT wrapper files: apps/{stt-worker,llm-worker,memory-worker}/*/mqtt_{client,utils}.py
- [ ] T074 Verify all service integration tests pass after migration

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final refinements and optimizations

- [ ] T075 [P] Add performance benchmarks for publish latency (<10ms target) in packages/tars-core/tests/benchmark/
- [ ] T076 [P] Add performance benchmarks for reconnection time (<50ms target) in packages/tars-core/tests/benchmark/
- [ ] T077 [P] Optimize hot paths: publish_event() and _dispatch_messages() for throughput target (100+ msg/sec)
- [ ] T078 [P] Code cleanup: refactor any duplicate logic, apply SOLID principles
- [ ] T079 [P] Security review: verify no secrets logged, credentials redacted in error messages
- [ ] T080 [P] Add contract tests for all topic patterns in packages/tars-core/tests/contract/test_mqtt_topic_patterns.py
- [ ] T081 Validate constitution compliance: run constitution checklist against final implementation
- [ ] T082 Update .github/copilot-instructions.md with centralized MQTT client usage patterns
- [ ] T083 Final review: verify module <500 LOC (KISS principle compliance)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - User stories CAN proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Documentation (Phase 6)**: Depends on User Story 1 (MVP) completion at minimum
- **Service Migrations (Phase 7)**: Depends on User Story 2 completion
- **Polish (Phase 8)**: Depends on all user stories and migrations complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Builds on US1 but independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Builds on US1/US2 but independently testable

### Within Each User Story (TDD Workflow)

1. **Write Tests FIRST** (RED state)
   - All test tasks for the story
   - Run tests, verify they FAIL
   - Commit tests in failing state
2. **Implement Minimum Code** (GREEN state)
   - Implementation tasks
   - Run tests, verify they PASS
   - Commit implementation
3. **Refactor** (KEEP GREEN)
   - Improve code quality
   - Tests stay green
   - Commit refactorings

### Parallel Opportunities

**Phase 1 (Setup)**: All 5 tasks can run in parallel (T001-T005)

**Phase 2 (Foundational)**: Sequential pairs for TDD:
- T006 (test) then T007 (impl) - ConnectionParams
- T008 (test) then T009 (impl) - MQTTClientConfig
- T010 (test) then T011 (impl) - HealthStatus/Heartbeat
- T012 (test) then T013 (impl) - MessageDeduplicator
- Pairs can run in parallel with each other

**Phase 3 (User Story 1)**:
- All test tasks T015-T020 can run in parallel (write all tests first)
- Implementation tasks T021-T027 sequential (same file)
- Documentation tasks T028-T030 can run in parallel after implementation

**Phase 4 (User Story 2)**:
- All test tasks T031-T035 can run in parallel
- Implementation tasks T036-T041 sequential (same file)
- Migration tasks T042-T043 can run in parallel
- Documentation tasks T044-T045 can run in parallel

**Phase 5 (User Story 3)**:
- All test tasks T046-T049 can run in parallel
- Implementation tasks T050-T053 sequential (same file)
- Documentation tasks T054-T056 can run in parallel

**Phase 6 (Documentation)**: All tasks T057-T062 can run in parallel, T063-T064 sequential after

**Phase 7 (Service Migrations)**: Tasks T065-T071 can all run in parallel (different services)

**Phase 8 (Polish)**: Tasks T075-T080 can all run in parallel, T081-T083 sequential after

---

## Parallel Example: User Story 1 (TDD Workflow)

```bash
# Step 1: Write ALL tests first (parallel)
Task T015: "Write test for MQTTClient.__init__() validation [RED]"
Task T016: "Write test for MQTTClient.connect() success [RED]"
Task T017: "Write test for MQTTClient.connect() invalid URL [RED]"
Task T018: "Write test for MQTTClient.publish_event() wraps Envelope [RED]"
Task T019: "Write test for MQTTClient.subscribe() registers handler [RED]"
Task T020: "Write integration test for end-to-end publish/subscribe [RED]"

# Verify: Run pytest, all tests should FAIL (expected)

# Step 2: Implement sequentially to make tests pass (GREEN)
Task T021: "Implement MQTTClient.__init__() [GREEN]"  # Tests T015 pass
Task T022: "Implement MQTTClient.connect() [GREEN]"    # Tests T016-T017 pass
Task T024: "Implement MQTTClient.publish_event() [GREEN]"  # Test T018 passes
Task T025: "Implement MQTTClient.subscribe() [GREEN]"  # Test T019 passes
# ... continue until all tests pass

# Step 3: Refactor while keeping tests green
# Run pytest after each change to ensure no regressions
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. **Complete Phase 1**: Setup (parallel: T001-T005)
2. **Complete Phase 2**: Foundational (TDD pairs: T006-T014) - **CRITICAL BLOCKING PHASE**
3. **Complete Phase 3**: User Story 1 (TDD: tests T015-T020 first, then impl T021-T030)
4. **STOP and VALIDATE**: 
   - Run all tests: `pytest packages/tars-core/tests/`
   - Test User Story 1 acceptance: Create new test service with <10 LOC MQTT usage
   - Run quickstart scenario: Basic publish/subscribe example
5. **Deploy/Demo MVP**: Centralized client ready for new services

### Incremental Delivery

1. **Foundation Ready** (Phase 1 + 2): Core models and infrastructure complete
2. **MVP Delivery** (+ Phase 3): New services can use centralized client - **SHIP IT**
3. **Migration Ready** (+ Phase 4): Existing services can migrate - **SHIP IT**
4. **Extension Ready** (+ Phase 5): Services can extend for custom use cases - **SHIP IT**
5. **Full Migration** (+ Phase 7): All services using centralized client
6. **Production Ready** (+ Phase 8): Optimized, documented, validated

Each increment adds value without breaking previous functionality.

### Parallel Team Strategy

With multiple developers after Foundational phase completes:

- **Developer A**: User Story 1 (Phase 3) - Core client implementation
- **Developer B**: User Story 2 (Phase 4) - Migration support (starts after US1 T021-T027)
- **Developer C**: User Story 3 (Phase 5) - Extension patterns (starts after US1 T021-T027)
- **Developer D**: Documentation (Phase 6) - Can start in parallel with US2/US3

Stories complete and integrate independently.

---

## Success Metrics Tracking

Track these metrics after each phase to validate success criteria:

### After User Story 1 (MVP)
- [ ] New service integrates MQTT in <10 lines of code (SC-001)
- [ ] All public APIs have complete type hints passing mypy strict (SC-008)
- [ ] End-to-end test passes: publish → subscribe with zero custom connection logic

### After User Story 2 (Migration)
- [ ] Migrated service reduces MQTT code by 50%+ (SC-002)
- [ ] Zero MQTT connection logic duplicated between migrated services (SC-003)
- [ ] All existing integration tests pass without modification (SC-004)

### After User Story 3 (Extension)
- [ ] Extension example works without modifying core module (composition pattern validated)
- [ ] Service-specific custom behavior integrates cleanly

### Final Validation (After Phase 8)
- [ ] All 10+ MQTT usage patterns supported through single interface (SC-005)
- [ ] New developer integrates MQTT without reading broker docs (SC-006)
- [ ] Services reconnect within 10s of broker availability (SC-007)
- [ ] 100% type hint coverage passing mypy strict (SC-008)
- [ ] Module <500 LOC (KISS compliance)

---

## Notes

- **[P]** tasks = different files, no dependencies, can run in parallel
- **[Story]** label (US1, US2, US3) maps task to specific user story for traceability
- **[RED]** = Test written first, must fail before implementation
- **[GREEN]** = Implementation makes test pass
- Each user story should be independently completable and testable
- **TDD is mandatory**: Write tests BEFORE implementation for all entities
- Commit after each task or logical TDD cycle (RED → GREEN → REFACTOR)
- Stop at any checkpoint to validate story independently
- Constitution compliance validated at Phase 1 (T005) and Phase 8 (T081)

---

## Total Task Count Summary

- **Phase 1 (Setup)**: 5 tasks
- **Phase 2 (Foundational)**: 9 tasks (TDD pairs)
- **Phase 3 (User Story 1 - MVP)**: 16 tasks (6 tests + 10 impl/docs)
- **Phase 4 (User Story 2 - Migration)**: 15 tasks (5 tests + 10 impl/migration)
- **Phase 5 (User Story 3 - Extension)**: 11 tasks (4 tests + 7 impl/docs)
- **Phase 6 (Documentation)**: 8 tasks
- **Phase 7 (Service Migrations)**: 10 tasks
- **Phase 8 (Polish)**: 9 tasks

**Total: 83 tasks**

**Parallel Opportunities**: ~40% of tasks marked [P] can run in parallel within phases

**Suggested MVP Scope**: Phase 1 + Phase 2 + Phase 3 (30 tasks total) delivers core value with new service integration support
