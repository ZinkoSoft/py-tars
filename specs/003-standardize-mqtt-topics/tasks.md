# Tasks: Standardize MQTT Topics

**Feature**: Standardize MQTT Topics and Contracts  
**Branch**: `copilot/standardize-mqtt-topics`  
**Input**: Design documents from `/specs/003-standardize-mqtt-topics/`

## Format: `[ID] [P?] [Domain] Description`
- **[P]**: Can run in parallel (different domains/files, no dependencies)
- **[Domain]**: Which service domain this task belongs to
- All paths are absolute from repository root

## Organization

Tasks are organized by phase and domain. Each domain (stt, tts, llm, etc.) can be worked on independently after Phase 1 is complete.

---

## Phase 1: Audit and Documentation (Foundation)

**Purpose**: Understand current state and identify gaps

- [ ] T001 Inventory all MQTT topics used across all services in `/apps/`
- [ ] T002 Document current publishers and subscribers for each topic
- [ ] T003 Identify topics missing Pydantic contracts in `/packages/tars-core/src/tars/contracts/v1/`
- [ ] T004 Identify topics with non-standard naming (not `<domain>/<action>` pattern)
- [ ] T005 Identify QoS and retention policy mismatches with constitution
- [ ] T006 Create topic inventory spreadsheet in `/specs/003-standardize-mqtt-topics/topic-inventory.md`

**Checkpoint**: Complete understanding of current state and gaps identified

---

## Phase 2: Complete Missing Contracts (Core Infrastructure)

**Purpose**: Ensure all topics have Pydantic v2 contracts in tars-core

### System Domain

- [ ] T007 [P] [system] Add `TOPIC_SYSTEM_CHARACTER_CURRENT` constant to appropriate contract file
- [ ] T008 [P] [system] Create `CharacterUpdate` Pydantic model for `system/character/current` topic
- [ ] T009 [P] [system] Add tests for `CharacterUpdate` model in `/packages/tars-core/tests/`
- [ ] T010 [P] [system] Update `packages/tars-core/src/tars/contracts/v1/__init__.py` to export new models

### Camera Domain

- [ ] T011 [P] [camera] Create `/packages/tars-core/src/tars/contracts/v1/camera.py`
- [ ] T012 [P] [camera] Define topic constants: `TOPIC_CAMERA_CAPTURE`, `TOPIC_CAMERA_IMAGE`
- [ ] T013 [P] [camera] Create `CameraCaptureRequest` Pydantic model
- [ ] T014 [P] [camera] Create `CameraImageResponse` Pydantic model
- [ ] T015 [P] [camera] Add correlation ID fields (`message_id`, `request_id`)
- [ ] T016 [P] [camera] Add tests in `/packages/tars-core/tests/test_camera_contracts.py`
- [ ] T017 [P] [camera] Export camera contracts from v1/__init__.py

### Review Existing Contracts

- [ ] T018 [P] [stt] Review `/packages/tars-core/src/tars/contracts/v1/stt.py` for completeness
- [ ] T019 [P] [stt] Add topic constants if missing: `TOPIC_STT_FINAL`, `TOPIC_STT_PARTIAL`
- [ ] T020 [P] [stt] Ensure correlation ID fields present in all models
- [ ] T021 [P] [tts] Review `/packages/tars-core/src/tars/contracts/v1/tts.py` for completeness
- [ ] T022 [P] [tts] Add topic constants if missing: `TOPIC_TTS_SAY`, `TOPIC_TTS_STATUS`
- [ ] T023 [P] [tts] Ensure correlation ID fields present in all models
- [ ] T024 [P] [llm] Review `/packages/tars-core/src/tars/contracts/v1/llm.py` for completeness
- [ ] T025 [P] [llm] Add topic constants if missing: `TOPIC_LLM_REQUEST`, `TOPIC_LLM_RESPONSE`, `TOPIC_LLM_STREAM`, `TOPIC_LLM_CANCEL`
- [ ] T026 [P] [llm] Ensure correlation ID fields present in all models
- [ ] T027 [P] [wake] Review `/packages/tars-core/src/tars/contracts/v1/wake.py` for completeness
- [ ] T028 [P] [wake] Add topic constant if missing: `TOPIC_WAKE_EVENT`
- [ ] T029 [P] [wake] Ensure correlation ID fields present in all models
- [ ] T030 [P] [memory] Review `/packages/tars-core/src/tars/contracts/v1/memory.py` for completeness
- [ ] T031 [P] [memory] Add topic constants if missing: `TOPIC_MEMORY_QUERY`, `TOPIC_MEMORY_RESULTS`
- [ ] T032 [P] [memory] Ensure correlation ID fields present in all models
- [ ] T033 [P] [mcp] Review `/packages/tars-core/src/tars/contracts/v1/mcp.py` for completeness
- [ ] T034 [P] [mcp] Add topic constants if missing: `TOPIC_MCP_REQUEST`, `TOPIC_MCP_RESPONSE`
- [ ] T035 [P] [mcp] Ensure correlation ID fields present in all models

**Note**: Movement contracts were completed in prior work (see `/plan/mqtt-contracts-refactor-COMPLETE.md`)

**Checkpoint**: All topics have Pydantic v2 contracts in tars-core with topic constants

---

## Phase 3: Update Services to Use Contracts

**Purpose**: Migrate all services from string literals and dict parsing to typed contracts

### STT Worker

- [ ] T036 [stt] Update `/apps/stt-worker/src/stt_worker/` to import contracts from tars-core
- [ ] T037 [stt] Replace topic string literals with `TOPIC_*` constants
- [ ] T038 [stt] Use Pydantic models for message validation
- [ ] T039 [stt] Add correlation IDs to all published messages
- [ ] T040 [stt] Update logging to include correlation IDs
- [ ] T041 [stt] Set QoS levels per constitution (final=1, partial=0)
- [ ] T042 [stt] Test and verify `make check` passes

### TTS Worker

- [ ] T043 [tts] Update `/apps/tts-worker/src/tts_worker/` to import contracts from tars-core
- [ ] T044 [tts] Replace topic string literals with `TOPIC_*` constants
- [ ] T045 [tts] Use Pydantic models for message validation
- [ ] T046 [tts] Add correlation IDs to all published messages
- [ ] T047 [tts] Update logging to include correlation IDs
- [ ] T048 [tts] Set QoS levels per constitution (say=1, status=0)
- [ ] T049 [tts] Test and verify `make check` passes

### LLM Worker

- [ ] T050 [llm] Update `/apps/llm-worker/src/llm_worker/` to import contracts from tars-core
- [ ] T051 [llm] Replace topic string literals with `TOPIC_*` constants
- [ ] T052 [llm] Use Pydantic models for message validation
- [ ] T053 [llm] Add correlation IDs to all published messages
- [ ] T054 [llm] Update logging to include correlation IDs
- [ ] T055 [llm] Set QoS levels per constitution (request/response=1, stream=0)
- [ ] T056 [llm] Test and verify `make check` passes

### Router

- [ ] T057 [router] Update `/apps/router/src/router/` to import contracts from tars-core
- [ ] T058 [router] Replace topic string literals with `TOPIC_*` constants
- [ ] T059 [router] Use Pydantic models for message validation
- [ ] T060 [router] Ensure correlation ID propagation across all flows
- [ ] T061 [router] Update logging to include correlation IDs
- [ ] T062 [router] Set QoS levels per constitution
- [ ] T063 [router] Test and verify `make check` passes

### Memory Worker

- [ ] T064 [memory] Update `/apps/memory-worker/src/memory_worker/` to import contracts from tars-core
- [ ] T065 [memory] Replace topic string literals with `TOPIC_*` constants
- [ ] T066 [memory] Use Pydantic models for message validation
- [ ] T067 [memory] Add correlation IDs to all published messages
- [ ] T068 [memory] Update logging to include correlation IDs
- [ ] T069 [memory] Set QoS levels per constitution
- [ ] T070 [memory] Test and verify `make check` passes

### Wake Activation

- [ ] T071 [wake] Update `/apps/wake-activation/src/wake_activation/` to import contracts from tars-core
- [ ] T072 [wake] Replace topic string literals with `TOPIC_*` constants
- [ ] T073 [wake] Use Pydantic models for message validation
- [ ] T074 [wake] Add correlation IDs to all published messages
- [ ] T075 [wake] Update logging to include correlation IDs
- [ ] T076 [wake] Set QoS levels per constitution (wake/event=1)
- [ ] T077 [wake] Test and verify `make check` passes

### Camera Service

- [ ] T078 [camera] Update `/apps/camera-service/src/camera_service/` to import contracts from tars-core
- [ ] T079 [camera] Replace topic string literals with `TOPIC_*` constants
- [ ] T080 [camera] Use Pydantic models for message validation
- [ ] T081 [camera] Add correlation IDs to all published messages
- [ ] T082 [camera] Update logging to include correlation IDs
- [ ] T083 [camera] Set QoS levels per constitution
- [ ] T084 [camera] Test and verify `make check` passes

### MCP Bridge

- [ ] T085 [mcp] Update `/apps/mcp-bridge/src/mcp_bridge/` to import contracts from tars-core
- [ ] T086 [mcp] Replace topic string literals with `TOPIC_*` constants
- [ ] T087 [mcp] Use Pydantic models for message validation
- [ ] T088 [mcp] Add correlation IDs to all published messages
- [ ] T089 [mcp] Update logging to include correlation IDs
- [ ] T090 [mcp] Set QoS levels per constitution
- [ ] T091 [mcp] Test and verify `make check` passes

### UI Services

- [ ] T092 [P] [ui] Update `/apps/ui/src/ui/` to import contracts from tars-core
- [ ] T093 [P] [ui] Replace topic string literals with `TOPIC_*` constants
- [ ] T094 [P] [ui] Use Pydantic models for message validation
- [ ] T095 [P] [ui] Test and verify `make check` passes
- [ ] T096 [P] [ui-web] Update `/apps/ui-web/src/ui_web/` to import contracts from tars-core
- [ ] T097 [P] [ui-web] Replace topic string literals with `TOPIC_*` constants
- [ ] T098 [P] [ui-web] Use Pydantic models for message validation
- [ ] T099 [P] [ui-web] Test and verify `make check` passes

**Note**: Movement service already updated in prior work

**Checkpoint**: All services use tars-core contracts, no string literals

---

## Phase 4: Integration Testing and Documentation

**Purpose**: Verify end-to-end flows and document the system

### Integration Tests

- [ ] T100 Create `/tests/integration/test_mqtt_topic_standards.py`
- [ ] T101 Test STT → Router → LLM → TTS flow with correlation ID propagation
- [ ] T102 Test wake event flow with proper message validation
- [ ] T103 Test memory query/results flow
- [ ] T104 Test movement command flow
- [ ] T105 Test camera capture flow
- [ ] T106 Test MCP request/response flow
- [ ] T107 Test error handling for malformed messages
- [ ] T108 Test QoS delivery guarantees
- [ ] T109 Verify all integration tests pass

### Documentation

- [ ] T110 Create comprehensive topic registry in `/specs/003-standardize-mqtt-topics/topic-registry.md`
- [ ] T111 Document breaking change policy in `/specs/003-standardize-mqtt-topics/breaking-changes.md`
- [ ] T112 Update each service README with:
  - Topics published (with contracts)
  - Topics subscribed (with contracts)
  - Correlation ID strategy
  - QoS levels used
- [ ] T113 Update main `/README.md` with link to topic registry
- [ ] T114 Update `.github/copilot-instructions.md` with MQTT standardization patterns
- [ ] T115 Create migration guide in `/specs/003-standardize-mqtt-topics/migration-guide.md`
- [ ] T116 Update constitution if needed based on learnings

### Validation and Completion

- [ ] T117 Run full system test: `docker compose -f ops/compose.yml up`
- [ ] T118 Verify all services start without errors
- [ ] T119 Verify message flows work end-to-end
- [ ] T120 Verify correlation IDs propagate correctly
- [ ] T121 Run `make check` in all app directories
- [ ] T122 Create completion report in `/specs/003-standardize-mqtt-topics/COMPLETION_REPORT.md`

**Checkpoint**: ✅ All tasks complete, system validated, documentation finalized

---

## Dependencies & Execution Order

### Phase Dependencies

1. **Phase 1 (Audit)**: No dependencies - understanding current state
2. **Phase 2 (Contracts)**: Depends on Phase 1 completion
3. **Phase 3 (Services)**: Depends on Phase 2 completion for domain-specific contracts
4. **Phase 4 (Testing/Docs)**: Depends on Phase 3 completion

### Parallelization Opportunities

**Phase 1**: All tasks run sequentially (single audit)

**Phase 2**: 
- System, camera, and review tasks for different domains marked [P] can run in parallel
- Each domain (stt, tts, llm, wake, memory, mcp) is independent

**Phase 3**:
- All service updates can run in parallel after Phase 2
- Each service is independent
- UI and ui-web marked [P] explicitly

**Phase 4**:
- Integration tests run after all services updated
- Documentation tasks marked [P] can run in parallel
- Validation must run last

### Within Each Service Update

Standard sequence:
1. Import contracts from tars-core
2. Replace string literals with constants
3. Add Pydantic validation
4. Add correlation IDs
5. Update logging
6. Set QoS levels
7. Test

---

## Success Criteria

Standardization complete when:

1. ✅ All topics have Pydantic v2 contracts in tars-core
2. ✅ All services use topic constants (no string literals)
3. ✅ All messages include correlation IDs
4. ✅ QoS levels match constitutional standards
5. ✅ All services pass `make check`
6. ✅ Integration tests prove end-to-end flows work
7. ✅ Topic registry documents all topics
8. ✅ Service READMEs document MQTT contracts
9. ✅ Breaking change policy documented
10. ✅ Migration guide available for future changes

---

## Notes

- **[P] markers**: Tasks that can run in parallel (different domains/services)
- **[Domain] labels**: Track which service domain each task belongs to
- **Validation**: Test after each service update before moving to next
- **Git workflow**: Commit after logical groups (e.g., after each service)
- **Constitution compliance**: All changes must follow Event-Driven Architecture principles
- **Backward compatibility**: No breaking changes to existing message formats
- **Type safety**: Pydantic models with `extra="forbid"` for all contracts

---

## Estimated Timeline

- **Phase 1**: 1 day (audit and document)
- **Phase 2**: 2-3 days (create missing contracts and tests)
- **Phase 3**: 3-5 days (update all services)
- **Phase 4**: 2-3 days (integration tests and documentation)

**Total**: 8-12 days (can be reduced with parallel work)

---

## Risk Mitigation

- Start with non-critical services (UI, camera) before core services (router, stt, tts, llm)
- Test each service independently before integration
- Keep changes minimal and focused
- Commit frequently for easy rollback
- Document any discovered issues or architectural concerns
- Update constitution if patterns need adjustment
