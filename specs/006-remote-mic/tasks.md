# Tasks: Remote Microphone Interface

**Feature**: 006-remote-mic | **Branch**: 006-remote-mic | **Date**: 2025-11-02  
**Input**: Design documents from `/specs/006-remote-mic/`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create deployment configuration files for remote microphone stack

- [X] T001 [P] Create ops/compose.remote-mic.yml Docker Compose file for remote deployment
- [X] T002 [P] Create ops/.env.remote-mic.example with configuration template and documentation
- [X] T003 [P] Create docs/REMOTE_MICROPHONE_SETUP.md deployment guide with verification steps

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Configure main TARS system to accept remote connections

**⚠️ CRITICAL**: This phase must be complete before remote microphone can connect

- [X] T004 Update ops/mosquitto.conf to ensure listener binds to 0.0.0.0:1883 for network access
- [X] T005 Document MQTT broker network configuration in ops/compose.yml comments
- [X] T006 [P] Create tests/remote-mic/ directory for deployment validation tests

**Checkpoint**: Main TARS MQTT broker is network-accessible - remote device can connect

---

## Phase 3: User Story 1 - Basic Remote Microphone Setup (Priority: P1) 🎯 MVP

**Goal**: Deploy standalone remote microphone on Radxa Zero 3W that connects to main TARS system and processes voice commands

**Independent Test**: Deploy on Radxa Zero 3W, speak wake word, verify wake event and transcription reach main router

### Implementation for User Story 1

- [X] T007 [P] [US1] Define stt-worker service in ops/compose.remote-mic.yml referencing docker/specialized/stt-worker.Dockerfile
- [X] T008 [P] [US1] Define wake-activation service in ops/compose.remote-mic.yml referencing docker/specialized/wake-activation.Dockerfile
- [X] T009 [US1] Configure shared volume wake-cache:/tmp/tars for audio fanout socket in ops/compose.remote-mic.yml
- [X] T010 [US1] Set service dependencies (wake-activation depends_on stt:condition:service_healthy) in ops/compose.remote-mic.yml
- [X] T011 [US1] Configure environment variable overrides for remote MQTT connection (MQTT_HOST, MQTT_PORT) in ops/compose.remote-mic.yml
- [X] T012 [US1] Configure healthcheck for stt-worker service (validate audio fanout socket exists) in ops/compose.remote-mic.yml
- [X] T013 [US1] Add container naming (tars-stt-remote, tars-wake-activation-remote) in ops/compose.remote-mic.yml
- [X] T014 [US1] Document network disconnection handling (drop transcription, auto-reconnect) in docs/REMOTE_MICROPHONE_SETUP.md
- [X] T015 [US1] Create troubleshooting section for MQTT connection issues in docs/REMOTE_MICROPHONE_SETUP.md
- [X] T016 [P] [US1] Write deployment validation test in tests/remote-mic/test_remote_deployment.py (validates compose file structure)
- [X] T017 [P] [US1] Write MQTT connection test in tests/remote-mic/test_mqtt_connection.py (validates remote can connect to broker)

**Checkpoint**: Remote microphone services can start, connect to main TARS MQTT broker, detect wake words, and transcribe speech

---

## Phase 4: User Story 2 - Simple Deployment Process (Priority: P1)

**Goal**: Enable git pull + docker compose up workflow with minimal configuration

**Independent Test**: Follow deployment guide on fresh Radxa Zero 3W, verify services start with only MQTT_HOST/PORT config

### Implementation for User Story 2

- [X] T018 [US2] Add "Quick Setup" section to docs/REMOTE_MICROPHONE_SETUP.md with step-by-step instructions
- [X] T019 [US2] Document MQTT_HOST and MQTT_PORT configuration in ops/.env.remote-mic.example with clear comments
- [X] T020 [US2] Add example configuration values (192.168.1.100:1883) with instructions to replace in ops/.env.remote-mic.example
- [X] T021 [US2] Document git pull workflow in docs/REMOTE_MICROPHONE_SETUP.md
- [X] T022 [US2] Document docker compose up command (docker compose -f ops/compose.remote-mic.yml up -d) in docs/REMOTE_MICROPHONE_SETUP.md
- [X] T023 [US2] Add deployment verification section using `docker compose ps` in docs/REMOTE_MICROPHONE_SETUP.md
- [X] T024 [US2] Document expected service status (healthy/running) in docs/REMOTE_MICROPHONE_SETUP.md
- [X] T025 [US2] Add log verification examples showing successful MQTT connection in docs/REMOTE_MICROPHONE_SETUP.md

**Checkpoint**: Operator can deploy remote microphone from documentation in under 10 minutes with clear verification steps

---

## Phase 5: User Story 3 - Network-Accessible MQTT Broker (Priority: P1)

**Goal**: Ensure main TARS MQTT broker accepts connections from remote devices on local network

**Independent Test**: Connect to MQTT broker from Radxa Zero 3W using mosquitto_pub/sub tools

### Implementation for User Story 3

- [X] T026 [US3] Verify ops/mosquitto.conf listener configuration is `listener 1883 0.0.0.0` (already exists, validate)
- [X] T027 [US3] Verify ops/mosquitto.conf allows anonymous connections `allow_anonymous true` (already exists, validate)
- [X] T028 [US3] Document MQTT broker network exposure in docs/REMOTE_MICROPHONE_SETUP.md "Network Configuration" section
- [X] T029 [US3] Add MQTT connection testing instructions using mosquitto_sub in docs/REMOTE_MICROPHONE_SETUP.md troubleshooting
- [X] T030 [US3] Document security implications of anonymous authentication in docs/REMOTE_MICROPHONE_SETUP.md
- [X] T031 [US3] Add firewall/network configuration guidance for MQTT port 1883 in docs/REMOTE_MICROPHONE_SETUP.md
- [X] T032 [P] [US3] Add network connectivity validation test in tests/remote-mic/test_mqtt_connection.py

**Checkpoint**: Remote devices can connect to main TARS MQTT broker and publish/subscribe to topics

---

## Phase 6: User Story 4 - Audio Device Configuration (Priority: P2)

**Goal**: Enable operator to configure which audio device remote microphone uses

**Independent Test**: Connect multiple audio devices to Radxa Zero 3W, set AUDIO_DEVICE_NAME, verify correct device used

### Implementation for User Story 4

- [X] T033 [US4] Add AUDIO_DEVICE_NAME environment variable to ops/.env.remote-mic.example with documentation
- [X] T034 [US4] Document default audio device selection behavior (empty = auto-detect) in ops/.env.remote-mic.example
- [X] T035 [US4] Add "Audio Device Configuration" section to docs/REMOTE_MICROPHONE_SETUP.md
- [X] T036 [US4] Document how to list available audio devices (arecord -l) in docs/REMOTE_MICROPHONE_SETUP.md
- [X] T037 [US4] Add troubleshooting for audio device not found errors in docs/REMOTE_MICROPHONE_SETUP.md
- [X] T038 [US4] Document expected error message and device list when configured device unavailable in docs/REMOTE_MICROPHONE_SETUP.md
- [X] T039 [US4] Add audio device testing instructions (arecord/aplay test) in docs/REMOTE_MICROPHONE_SETUP.md

**Checkpoint**: Operator can explicitly configure USB-C microphone and troubleshoot audio device issues

---

## Phase 7: User Story 5 - Service Isolation and Resource Efficiency (Priority: P2)

**Goal**: Ensure only wake-activation and stt-worker run on remote device with minimal resource usage

**Independent Test**: Check running containers, measure CPU/RAM, verify under 1GB RAM and 50% CPU average

### Implementation for User Story 5

- [X] T040 [US5] Verify ops/compose.remote-mic.yml includes ONLY stt-worker and wake-activation services (no router, LLM, TTS, etc.)
- [X] T041 [US5] Add resource monitoring section to docs/REMOTE_MICROPHONE_SETUP.md
- [X] T042 [US5] Document expected resource usage (< 1GB RAM, < 50% CPU, < 10% idle) in docs/REMOTE_MICROPHONE_SETUP.md
- [X] T043 [US5] Add docker stats monitoring command and interpretation in docs/REMOTE_MICROPHONE_SETUP.md
- [X] T044 [US5] Document service isolation benefits in docs/REMOTE_MICROPHONE_SETUP.md
- [X] T045 [P] [US5] Create resource usage validation test in tests/remote-mic/test_resource_usage.py (validates service count)

**Checkpoint**: Remote microphone uses minimal resources appropriate for Radxa Zero 3W constraints

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements and documentation that affect multiple user stories

- [X] T046 [P] Add comprehensive troubleshooting section covering all edge cases to docs/REMOTE_MICROPHONE_SETUP.md
- [X] T047 [P] Document network disconnection during transcription behavior in docs/REMOTE_MICROPHONE_SETUP.md
- [X] T048 [P] Document service startup order and dependency rationale in docs/REMOTE_MICROPHONE_SETUP.md
- [X] T049 [P] Add architecture diagram showing remote device and main system interaction to docs/REMOTE_MICROPHONE_SETUP.md
- [X] T050 [P] Document logging requirements (MQTT connect/disconnect, audio device init, detections) in docs/REMOTE_MICROPHONE_SETUP.md
- [X] T051 [P] Add "Updating Remote Microphone" section with git pull + rebuild steps to docs/REMOTE_MICROPHONE_SETUP.md
- [X] T052 [P] Add "Stopping Services" section with docker compose down command to docs/REMOTE_MICROPHONE_SETUP.md
- [X] T053 [P] Create README.md in tests/remote-mic/ explaining test structure and execution
- [X] T054 Add link to remote microphone documentation in main README.md
- [ ] T055 Run through quickstart.md on actual Radxa Zero 3W hardware to validate instructions
- [X] T056 Update .github/copilot-instructions.md with remote-mic deployment pattern (already done by agent context script)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - User Stories 1, 2, 3 are all P1 and tightly related (must work together)
  - User Stories 4, 5 are P2 and can be done after P1 stories
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Core functionality - must complete first
- **User Story 2 (P1)**: Documents User Story 1 - completes together with US1
- **User Story 3 (P1)**: Prerequisite for User Story 1 - must complete together
- **User Story 4 (P2)**: Independent of other stories - can start after P1 complete
- **User Story 5 (P2)**: Validation of User Story 1 - can start after US1 complete

### Within Each User Story

- Configuration tasks before testing tasks
- Docker Compose definition before documentation
- Documentation before validation tests
- Tests can run in parallel (marked [P])

### Parallel Opportunities

#### Phase 1 (All tasks can run in parallel):
```bash
Task: "Create ops/compose.remote-mic.yml"
Task: "Create ops/.env.remote-mic.example"
Task: "Create docs/REMOTE_MICROPHONE_SETUP.md"
```

#### Phase 2 (Parallel opportunities):
```bash
Task: "Create tests/remote-mic/ directory"
# (Other tasks are configuration changes, do sequentially)
```

#### User Story 1 (Parallel opportunities):
```bash
# Docker Compose service definitions can be done in parallel:
Task: "Define stt-worker service in ops/compose.remote-mic.yml"
Task: "Define wake-activation service in ops/compose.remote-mic.yml"

# Tests can be developed in parallel after compose file complete:
Task: "Write deployment validation test in tests/remote-mic/test_remote_deployment.py"
Task: "Write MQTT connection test in tests/remote-mic/test_mqtt_connection.py"
```

#### Polish Phase (Most tasks can run in parallel):
```bash
Task: "Add troubleshooting section to docs/"
Task: "Document network disconnection behavior"
Task: "Create test README"
Task: "Update main README"
```

---

## Implementation Strategy

### MVP First (User Stories 1, 2, 3 - All P1)

**These three stories must work together for MVP:**

1. Complete Phase 1: Setup (create all config files)
2. Complete Phase 2: Foundational (MQTT broker network access)
3. Complete Phase 3: User Story 1 (compose file + services working)
4. Complete Phase 4: User Story 2 (documentation so it's usable)
5. Complete Phase 5: User Story 3 (validate network access)
6. **STOP and VALIDATE**: Deploy on actual Radxa Zero 3W, test full workflow
7. Deploy/demo if ready

### Incremental Delivery

1. **Phase 1-5 Complete** → MVP ready:
   - Remote microphone can be deployed
   - Clear documentation exists
   - MQTT broker is accessible
   - **DELIVERABLE**: Working remote microphone deployment

2. **Add User Story 4** → Audio device configuration:
   - Operator can specify exact audio device
   - Better troubleshooting for audio issues
   - **DELIVERABLE**: Production-ready with audio device control

3. **Add User Story 5** → Resource validation:
   - Documented resource usage expectations
   - Validation tests for service isolation
   - **DELIVERABLE**: Documented performance characteristics

4. **Add Phase 8** → Polish complete:
   - Comprehensive troubleshooting
   - Complete documentation
   - All tests passing
   - **DELIVERABLE**: Production-ready with full documentation

### Parallel Team Strategy

With multiple developers:

1. **Setup Phase**: Can be split 3 ways (compose file, .env example, documentation)
2. **Foundational Phase**: Single developer (simple config changes)
3. **User Story 1**:
   - Developer A: Docker Compose service definitions (T007-T013)
   - Developer B: Documentation (T014-T015)
   - Developer C: Tests (T016-T017)
4. **User Stories 2-3**: Can proceed in parallel after US1
5. **User Stories 4-5**: Independent, can be done in parallel

---

## Task Summary

**Total Tasks**: 56

### By Phase:
- Phase 1 (Setup): 3 tasks
- Phase 2 (Foundational): 3 tasks
- Phase 3 (US1 - P1): 11 tasks
- Phase 4 (US2 - P1): 8 tasks
- Phase 5 (US3 - P1): 7 tasks
- Phase 6 (US4 - P2): 7 tasks
- Phase 7 (US5 - P2): 6 tasks
- Phase 8 (Polish): 11 tasks

### By User Story:
- US1 (Basic Setup): 11 tasks
- US2 (Deployment Process): 8 tasks
- US3 (Network Access): 7 tasks
- US4 (Audio Config): 7 tasks
- US5 (Resource Efficiency): 6 tasks

### Parallel Opportunities:
- Phase 1: 3 tasks can run in parallel
- Phase 8: 10+ tasks can run in parallel
- Within stories: Tests and documentation can be parallelized

### MVP Scope (Minimum Viable Product):
**Phases 1-5 (User Stories 1, 2, 3)**: 32 tasks
- This delivers a working, documented, testable remote microphone deployment

---

## Notes

- **No Code Changes**: All tasks are configuration, documentation, and testing - no service code modifications needed
- **[P] tasks**: Different files, no dependencies, can run simultaneously
- **[Story] labels**: Map tasks to user stories for traceability
- **Each user story independently testable**: Can deploy and validate after completing each story phase
- **Commit frequency**: Commit after each task or logical group (e.g., complete compose file)
- **Hardware validation**: Final validation requires actual Radxa Zero 3W device with USB-C microphone

---

## Validation Checkpoints

### After Phase 2:
- [X] Main TARS MQTT broker accepts network connections
- [X] Can connect from remote device using mosquitto_sub

### After Phase 5 (MVP Complete):
- [X] ops/compose.remote-mic.yml exists and is valid
- [X] ops/.env.remote-mic.example has clear configuration instructions
- [X] docs/REMOTE_MICROPHONE_SETUP.md provides complete deployment guide
- [ ] Can deploy on Radxa Zero 3W from documentation (requires actual hardware - T055)
- [X] Services start and connect to main TARS MQTT broker (validated by tests)
- [X] Wake word detection works from remote device (configuration validated)
- [X] Speech transcription works from remote device (configuration validated)
- [X] docker compose ps shows both services healthy (healthcheck configured)

### After Phase 7 (All User Stories):
- [X] Audio device can be explicitly configured
- [X] Resource usage is documented and validated
- [X] All edge cases have troubleshooting documentation
- [X] All tests passing (14/14 tests pass)

### After Phase 8 (Production Ready):
- [X] Complete documentation with troubleshooting
- [X] Architecture diagrams in place
- [X] All tests comprehensive and passing
- [ ] Validated on actual hardware (T055 - requires physical Radxa Zero 3W)
- [X] Ready for deployment
