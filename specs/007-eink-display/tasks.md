# Tasks: Remote E-Ink Display for TARS Communication

**Input**: Design documents from `/specs/007-eink-display/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Tests are included in this implementation plan following Test-First Development (Constitution IV).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

All paths are relative to repository root (`/data/git/py-tars`):
- **Service code**: `apps/ui-eink-display/src/ui_eink_display/`
- **Tests**: `apps/ui-eink-display/tests/`
- **Docker**: `docker/specialized/`
- **Ops**: `ops/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create directory structure for ui-eink-display service: `apps/ui-eink-display/src/ui_eink_display/`, `apps/ui-eink-display/tests/{unit,integration,contract}/`
- [ ] T002 Create `apps/ui-eink-display/pyproject.toml` with dependencies: asyncio-mqtt>=0.16.1, Pillow>=10.0.0, waveshare-epd, pytest>=7.0, pytest-asyncio>=0.21, pytest-mock
- [ ] T003 [P] Create `apps/ui-eink-display/.env.example` with MQTT_HOST, MQTT_PORT, LOG_LEVEL, DISPLAY_TIMEOUT_SEC, PYTHONPATH
- [ ] T004 [P] Create `apps/ui-eink-display/README.md` with service description, hardware requirements, and setup instructions
- [ ] T005 [P] Create `apps/ui-eink-display/src/ui_eink_display/__init__.py` with module entry point

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 Create `apps/ui-eink-display/src/ui_eink_display/config.py` with DisplayConfig dataclass and from_env() class method for environment variable parsing
- [ ] T007 [P] Create `apps/ui-eink-display/src/ui_eink_display/display_state.py` with DisplayMode enum (STANDBY, LISTENING, PROCESSING, CONVERSATION, ERROR) and DisplayState dataclass
- [ ] T008 [P] Create `apps/ui-eink-display/tests/unit/test_config.py` with tests for environment variable parsing and required field validation (MQTT_HOST)
- [ ] T009 [P] Create `apps/ui-eink-display/tests/unit/test_display_state.py` with tests for DisplayMode enum values and DisplayState initialization
- [ ] T010 Create `apps/ui-eink-display/src/ui_eink_display/display_manager.py` with DisplayManager class skeleton: init, init_display, clear_display, safe_display_update methods with mock hardware mode support
- [ ] T011 Create `apps/ui-eink-display/src/ui_eink_display/mqtt_handler.py` with MQTTHandler class skeleton: connect, subscribe to topics (stt/final, llm/response, wake/event), message routing
- [ ] T012 [P] Create `apps/ui-eink-display/tests/contract/test_mqtt_contracts.py` with tests for parsing FinalTranscript, LLMResponse, WakeEvent from MQTT payloads (valid and invalid with extra="forbid")
- [ ] T013 Create `docker/specialized/ui-eink-display.Dockerfile` with Python 3.11 base, SPI/GPIO libraries, waveshare-epd installation, PIL/Pillow system deps
- [ ] T014 [P] Add ui-eink-display service definition to `ops/compose.remote-mic.yml` with build context, environment variables, device mappings (/dev/spidev*, /dev/gpiomem), volumes, and depends_on stt service health

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - System Status Visualization (Priority: P1) 🎯 MVP

**Goal**: Display system operational state (standby, listening, processing, error) to provide immediate feedback about system availability and readiness

**Independent Test**: Start the service and observe display transitions through different states by publishing wake events over MQTT. Verify standby screen, listening indicator, and error state display without requiring actual voice interaction.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T015 [P] [US1] Create `apps/ui-eink-display/tests/unit/test_display_state.py` tests for state transitions: STANDBY→LISTENING (on wake event), LISTENING→PROCESSING, any→ERROR, ERROR→STANDBY recovery
- [ ] T016 [P] [US1] Create `apps/ui-eink-display/tests/integration/test_display_manager.py` with mocked hardware tests for render_standby(), render_listening(), render_error() methods
- [ ] T017 [P] [US1] Create `apps/ui-eink-display/tests/integration/test_mqtt_display.py` tests for wake/event message → LISTENING state transition and display update

### Implementation for User Story 1

- [ ] T018 [P] [US1] Implement `LayoutConstraints` dataclass in `apps/ui-eink-display/src/ui_eink_display/display_state.py` with display dimensions (250x122), font sizes, margins, and max character limits
- [ ] T019 [US1] Implement state transition logic in `DisplayState` in `apps/ui-eink-display/src/ui_eink_display/display_state.py`: transition_to(mode), validate transitions, update timestamps
- [ ] T020 [US1] Implement `render_standby()` method in `apps/ui-eink-display/src/ui_eink_display/display_manager.py`: create PIL Image, draw sci-fi inspired standby screen with "TARS REMOTE INTERFACE" title and "AWAITING SIGNAL" text
- [ ] T021 [US1] Implement `render_listening()` method in `apps/ui-eink-display/src/ui_eink_display/display_manager.py`: create PIL Image with "● LISTENING ●" indicator centered on screen
- [ ] T022 [US1] Implement `render_error()` method in `apps/ui-eink-display/src/ui_eink_display/display_manager.py`: create PIL Image with "⚠ ERROR ⚠" and error message text
- [ ] T023 [US1] Implement `handle_wake_event()` in `apps/ui-eink-display/src/ui_eink_display/mqtt_handler.py`: parse WakeEvent from MQTT, check detected=true, trigger state transition to LISTENING and call display_manager.render_listening()
- [ ] T024 [US1] Implement hardware initialization in `DisplayManager.init_display()` in `apps/ui-eink-display/src/ui_eink_display/display_manager.py`: import epd2in13_V4, initialize display, handle errors gracefully with mock mode fallback
- [ ] T025 [US1] Implement font loading in `DisplayManager.__init__()` in `apps/ui-eink-display/src/ui_eink_display/display_manager.py`: load DejaVu Sans fonts (20px title, 14px body) with fallback to PIL default
- [ ] T026 [US1] Implement `safe_display_update()` in `apps/ui-eink-display/src/ui_eink_display/display_manager.py`: wrap display update in asyncio.to_thread(), handle exceptions, track error count, publish health status
- [ ] T027 [US1] Add health status publishing to `system/health/ui-eink-display` in `apps/ui-eink-display/src/ui_eink_display/mqtt_handler.py`: publish {"ok": true} on healthy, {"ok": false, "err": "..."} on errors every 30 seconds
- [ ] T028 [US1] Implement MQTT connection handling in `MQTTHandler.connect()` in `apps/ui-eink-display/src/ui_eink_display/mqtt_handler.py`: connect to broker, handle connection errors, show ERROR state on disconnect
- [ ] T029 [US1] Create main entry point in `apps/ui-eink-display/src/ui_eink_display/__main__.py`: load config, initialize DisplayManager and MQTTHandler, start asyncio event loop, handle graceful shutdown

**Checkpoint**: At this point, User Story 1 should be fully functional - display shows standby, transitions to listening on wake event, and handles errors

---

## Phase 4: User Story 2 - Conversation Display with User Input (Priority: P2)

**Goal**: Display user's transcribed speech as right-aligned message bubbles to provide confidence that speech was correctly captured

**Independent Test**: Publish STT final transcript messages over MQTT and verify transcribed text appears as right-aligned message bubbles on the display, with processing indicator while waiting for LLM response.

### Tests for User Story 2

- [ ] T030 [P] [US2] Create `apps/ui-eink-display/tests/unit/test_message_formatter.py` with tests for text wrapping at character limits (22 chars/line), truncation with ellipsis, multi-line formatting
- [ ] T031 [P] [US2] Create `apps/ui-eink-display/tests/integration/test_mqtt_display.py` tests for stt/final message → PROCESSING state transition and user message display
- [ ] T032 [P] [US2] Add tests in `apps/ui-eink-display/tests/integration/test_display_manager.py` for render_processing() with user message bubble (right-aligned)

### Implementation for User Story 2

- [ ] T033 [P] [US2] Create `MessageAlignment` enum (LEFT, RIGHT) and `MessageBubble` dataclass in `apps/ui-eink-display/src/ui_eink_display/display_state.py` with text, alignment, wrapped_lines, bounds fields
- [ ] T034 [US2] Create `apps/ui-eink-display/src/ui_eink_display/message_formatter.py` with MessageFormatter class: calculate_text_bounds(), wrap_text(), format_message() methods
- [ ] T035 [US2] Implement `wrap_text()` in `apps/ui-eink-display/src/ui_eink_display/message_formatter.py`: split text by words, fit to max_chars_per_line (22), handle multi-line wrapping up to max_lines_per_bubble (4)
- [ ] T036 [US2] Implement `format_message()` in `apps/ui-eink-display/src/ui_eink_display/message_formatter.py`: create MessageBubble from text and alignment, calculate wrapped_lines, compute bounding box, truncate with "..." if too long
- [ ] T037 [US2] Implement `render_processing()` method in `apps/ui-eink-display/src/ui_eink_display/display_manager.py`: create PIL Image, draw user message bubble (right-aligned) with text, add processing indicator ("transmitting...")
- [ ] T038 [US2] Implement `draw_message_bubble()` helper in `apps/ui-eink-display/src/ui_eink_display/display_manager.py`: draw rectangle for bubble, render wrapped text lines, position based on alignment (LEFT vs RIGHT)
- [ ] T039 [US2] Implement `handle_stt_final()` in `apps/ui-eink-display/src/ui_eink_display/mqtt_handler.py`: parse FinalTranscript from MQTT, extract text field, store in DisplayState.user_message, transition to PROCESSING, call display_manager.render_processing()
- [ ] T040 [US2] Update DisplayState in `apps/ui-eink-display/src/ui_eink_display/display_state.py` to include user_message and conversation_id fields for correlation

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently - system shows standby, transitions to listening, displays user message bubbles

---

## Phase 5: User Story 3 - Response Display from TARS (Priority: P2)

**Goal**: Display TARS's response as left-aligned message bubbles to complete the conversation loop and allow users to read responses

**Independent Test**: Publish LLM response messages over MQTT and verify TARS response appears as left-aligned message bubble. Test with varying message lengths to verify truncation and priority rules.

### Tests for User Story 3

- [ ] T041 [P] [US3] Add tests in `apps/ui-eink-display/tests/unit/test_message_formatter.py` for priority rule: when both user+TARS messages exceed capacity, show TARS only
- [ ] T042 [P] [US3] Create `apps/ui-eink-display/tests/integration/test_mqtt_display.py` tests for llm/response message → CONVERSATION state transition and TARS message display
- [ ] T043 [P] [US3] Add tests in `apps/ui-eink-display/tests/integration/test_display_manager.py` for render_conversation() with both user and TARS message bubbles, and TARS-only mode when too long

### Implementation for User Story 3

- [ ] T044 [P] [US3] Implement `calculate_total_lines()` in `apps/ui-eink-display/src/ui_eink_display/message_formatter.py`: count total lines needed for both user and TARS messages, check against max_total_lines (6)
- [ ] T045 [P] [US3] Implement `apply_priority_rule()` in `apps/ui-eink-display/src/ui_eink_display/message_formatter.py`: if both messages exceed capacity, return only TARS message bubble (skip user message)
- [ ] T046 [US3] Implement `render_conversation()` method in `apps/ui-eink-display/src/ui_eink_display/display_manager.py`: create PIL Image, format both messages as MessageBubbles, apply priority rule if needed, draw user bubble (right) and TARS bubble (left)
- [ ] T047 [US3] Implement `handle_llm_response()` in `apps/ui-eink-display/src/ui_eink_display/mqtt_handler.py`: parse LLMResponse from MQTT, extract reply field, handle error field if present, store in DisplayState.tars_response, transition to CONVERSATION, call display_manager.render_conversation()
- [ ] T048 [US3] Update DisplayState in `apps/ui-eink-display/src/ui_eink_display/display_state.py` to include tars_response field
- [ ] T049 [US3] Add error handling in `handle_llm_response()` in `apps/ui-eink-display/src/ui_eink_display/mqtt_handler.py`: if LLMResponse.error is present, transition to ERROR state instead of CONVERSATION

**Checkpoint**: All core user stories (US1, US2, US3) should now be independently functional - complete conversation flow from standby through wake, user speech, and TARS response

---

## Phase 6: User Story 4 - Conversation Flow Management (Priority: P3)

**Goal**: Intelligently manage screen real estate and conversation lifecycle with timeouts and reset on new wake events

**Independent Test**: Conduct multiple conversation rounds and verify display handles transitions correctly: timeout returns to standby, new wake event clears previous conversation, multiple exchanges display correctly.

### Tests for User Story 4

- [ ] T050 [P] [US4] Create `apps/ui-eink-display/tests/integration/test_timeout.py` with tests for conversation timeout returning to STANDBY after configurable duration (45 seconds default)
- [ ] T051 [P] [US4] Add tests in `apps/ui-eink-display/tests/integration/test_mqtt_display.py` for new wake event clearing previous conversation and resetting to LISTENING state
- [ ] T052 [P] [US4] Add tests in `apps/ui-eink-display/tests/unit/test_display_state.py` for conversation_id tracking and correlation with MQTT message_id fields

### Implementation for User Story 4

- [ ] T053 [US4] Implement timeout mechanism in `apps/ui-eink-display/src/ui_eink_display/display_manager.py`: add _timeout_task field, _start_timeout() method using asyncio.sleep(timeout_sec), _timeout_handler() to transition to STANDBY
- [ ] T054 [US4] Update `render_conversation()` in `apps/ui-eink-display/src/ui_eink_display/display_manager.py` to call _start_timeout() after displaying LLM response
- [ ] T055 [US4] Update `handle_wake_event()` in `apps/ui-eink-display/src/ui_eink_display/mqtt_handler.py` to cancel existing timeout task, clear DisplayState (user_message and tars_response to None), reset conversation state
- [ ] T056 [US4] Add conversation_id correlation in `apps/ui-eink-display/src/ui_eink_display/mqtt_handler.py`: track message_id from FinalTranscript and match with LLMResponse.id field for request correlation
- [ ] T057 [US4] Implement rapid message handling in `apps/ui-eink-display/src/ui_eink_display/mqtt_handler.py`: if STT and LLM arrive <500ms apart, skip PROCESSING state and go directly to CONVERSATION

**Checkpoint**: All user stories should now be independently functional with proper conversation lifecycle management

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and final deployment readiness

- [ ] T058 [P] Add structured logging throughout all modules in `apps/ui-eink-display/src/ui_eink_display/`: INFO for state transitions, DEBUG for MQTT messages, ERROR for failures with context
- [ ] T059 [P] Add graceful shutdown handling in `apps/ui-eink-display/src/ui_eink_display/__main__.py`: handle SIGTERM/SIGINT, cancel tasks with asyncio.CancelledError, cleanup display (epd.sleep())
- [ ] T060 [P] Add display refresh optimization in `apps/ui-eink-display/src/ui_eink_display/display_manager.py`: track last displayed image, skip update if image unchanged, use partial refresh if supported
- [ ] T061 [P] Add special character handling in `apps/ui-eink-display/src/ui_eink_display/message_formatter.py`: filter or replace emojis, handle non-ASCII text gracefully (strip or replace with "?")
- [ ] T062 [P] Create integration test suite in `apps/ui-eink-display/tests/integration/test_full_flow.py`: test complete conversation flow from wake to timeout, test multiple conversations, test error recovery
- [ ] T063 [P] Add unit tests for edge cases in `apps/ui-eink-display/tests/unit/`: test empty messages, very long messages (>200 chars), rapid message arrival, out-of-order messages
- [ ] T064 Update `apps/ui-eink-display/README.md` with complete setup instructions, hardware wiring guide, troubleshooting section, configuration reference
- [ ] T065 [P] Create pytest configuration in `apps/ui-eink-display/pytest.ini` with asyncio mode, test discovery patterns, coverage settings
- [ ] T066 [P] Add development scripts in `apps/ui-eink-display/scripts/`: run-tests.sh, run-with-mock.sh, publish-test-messages.sh for manual testing
- [ ] T067 Run quickstart.md validation: verify all setup steps work, test hardware initialization, verify MQTT connection, validate display rendering, test conversation flow

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User Story 1 (P1) can start after Foundational
  - User Story 2 (P2) can start after Foundational (builds on US1 but independently testable)
  - User Story 3 (P2) can start after Foundational (completes US2 conversation flow)
  - User Story 4 (P3) can start after US1-3 (adds lifecycle management)
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
  - Delivers: Standby screen, listening indicator, error display, MQTT connection
  - MVP candidate: This alone provides system status visibility
  
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Builds on US1 display infrastructure but independently testable
  - Delivers: User message display as right-aligned bubbles
  - Requires US1 for: DisplayManager, MQTT infrastructure, state machine
  - Independent test: Can display user messages without LLM responses
  
- **User Story 3 (P2)**: Can start after Foundational (Phase 2) - Completes conversation display
  - Delivers: TARS response display as left-aligned bubbles, priority rules
  - Requires US2 for: MessageFormatter, bubble rendering
  - Independent test: Can display TARS messages without user input (test mode)
  
- **User Story 4 (P3)**: Depends on US1-3 completion - Adds conversation lifecycle
  - Delivers: Timeout mechanism, conversation reset, message correlation
  - Requires US1-3 for: Complete conversation flow to manage
  - Independent test: Can reset and timeout even with incomplete conversations

### Within Each User Story

1. Tests MUST be written and FAIL before implementation (Test-First Development)
2. Data models (DisplayState, MessageBubble) before services (MessageFormatter)
3. Core rendering methods before MQTT handlers that call them
4. Basic functionality before optimization and edge cases
5. Story complete and independently testable before moving to next priority

### Parallel Opportunities

**Within Setup (Phase 1)**:
- T003, T004, T005 can all run in parallel (different files)

**Within Foundational (Phase 2)**:
- T007, T008, T009 can run in parallel (different test files)
- T013 (Dockerfile) and T014 (compose.yml) can run in parallel with core code

**Within User Story 1**:
- T015, T016, T017 (all tests) can run in parallel
- T018 (LayoutConstraints) and T025 (font loading) can run in parallel
- T020, T021, T022 (render methods) can run in parallel after T019 (state transitions)

**Within User Story 2**:
- T030, T031, T032 (all tests) can run in parallel
- T033 (MessageBubble) and T034 (MessageFormatter) can start in parallel

**Within User Story 3**:
- T041, T042, T043 (all tests) can run in parallel
- T044, T045 (formatting logic) can run in parallel

**Within User Story 4**:
- T050, T051, T052 (all tests) can run in parallel

**Within Polish (Phase 7)**:
- T058, T059, T060, T061, T062, T063, T064, T065, T066 can all run in parallel (different files/concerns)

**Across User Stories** (if team capacity allows):
- After Foundational phase, US1, US2, US3 can be worked on in parallel by different developers
- US4 must wait for US1-3 to complete

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Create test_display_state.py tests for state transitions"
Task: "Create test_display_manager.py with mocked hardware tests for render methods"
Task: "Create test_mqtt_display.py tests for wake event handling"

# Launch parallel implementation tasks:
Task: "Implement LayoutConstraints dataclass"
Task: "Implement font loading in DisplayManager"

# After state transitions complete, launch all render methods:
Task: "Implement render_standby() method"
Task: "Implement render_listening() method"
Task: "Implement render_error() method"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T005)
2. Complete Phase 2: Foundational (T006-T014) - CRITICAL foundation
3. Complete Phase 3: User Story 1 (T015-T029)
4. **STOP and VALIDATE**: 
   - Test display shows standby screen on startup
   - Publish wake event over MQTT → verify "LISTENING" appears
   - Disconnect MQTT → verify error state
   - All US1 tests pass
5. **Deploy/demo if ready**: MVP delivers system status visibility

### Incremental Delivery

1. **Foundation** (Phases 1-2) → Project structure and infrastructure ready
2. **US1 (P1)** → Test independently → Deploy/Demo (MVP!) → System status visible
3. **US2 (P2)** → Test independently → Deploy/Demo → User messages displayed
4. **US3 (P2)** → Test independently → Deploy/Demo → Complete conversation flow
5. **US4 (P3)** → Test independently → Deploy/Demo → Lifecycle management
6. **Polish** (Phase 7) → Final hardening and optimization

Each story adds value without breaking previous stories.

### Parallel Team Strategy

With multiple developers after Foundational phase completes:

**Option 1: Sequential Priority (Recommended for 1-2 devs)**
- Developer A: US1 → US2 → US3 → US4
- Focus on getting MVP (US1) done first, then incrementally add features

**Option 2: Parallel Stories (3+ developers)**
- Developer A: User Story 1 (status visualization)
- Developer B: User Story 2 (user message display) - depends on A for infrastructure
- Developer C: User Story 3 (TARS response display) - depends on B for formatting
- All integrate at end for US4 (lifecycle management)

**Option 3: Hybrid (2 developers)**
- Developer A: US1 foundation
- Developer B: Tests for US1, US2
- Then split: A→US2, B→US3
- Both collaborate on US4

---

## Task Summary

**Total Tasks**: 67 tasks

**Breakdown by Phase**:
- Phase 1 (Setup): 5 tasks
- Phase 2 (Foundational): 9 tasks (CRITICAL - blocks all stories)
- Phase 3 (User Story 1 - P1): 14 tasks (MVP)
- Phase 4 (User Story 2 - P2): 11 tasks
- Phase 5 (User Story 3 - P2): 9 tasks
- Phase 6 (User Story 4 - P3): 8 tasks
- Phase 7 (Polish): 11 tasks

**Parallel Opportunities**: 34 tasks marked [P] can run in parallel

**Independent Test Criteria**:
- **US1**: Display shows standby/listening/error states without voice interaction
- **US2**: User messages display as right-aligned bubbles (can test with simulated STT)
- **US3**: TARS messages display as left-aligned bubbles (can test with simulated LLM)
- **US4**: Timeouts and conversation resets work (can test with timer manipulation)

**Suggested MVP Scope**: Phase 1 + Phase 2 + Phase 3 (US1 only) = 28 tasks
- Delivers core value: System status visibility on e-ink display
- Fully functional and independently testable
- Can deploy and demo to validate approach before adding conversation features

---

## Notes

- **[P] tasks**: Different files, no dependencies, can run in parallel
- **[Story] label**: Maps task to specific user story for traceability
- **Test-First**: All test tasks (T008-T009, T015-T017, T030-T032, T041-T043, T050-T052) must be written and FAIL before implementation
- **Constitution compliance**: All tasks follow async-first, typed contracts, event-driven architecture principles
- **Hardware mocking**: Tests use mock display mode for development without physical hardware
- **Incremental validation**: Each user story checkpoint provides independent test criteria
- **File paths**: All tasks include exact file paths for immediate execution
- **MQTT contracts**: Reuses existing contracts from tars-core (no new contracts needed)
