# Tasks: Adopt TARS AI Movement System Updates

**Input**: Design documents from `/specs/006-adopt-tars-ai/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/movement-presets.md, quickstart.md

**Tests**: Hardware integration tests required (cannot be fully automated). Contract tests for movement presets are included.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4, US5)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare development environment and baseline measurements

- [x] T001 Create development branch from `006-adopt-tars-ai`
- [ ] T002 Setup ESP32 hardware test environment (PCA9685 + 9 servos + power supply)
- [ ] T003 [P] Take baseline measurements of current `step_forward()` timing and behavior (record video)
- [ ] T004 [P] Verify WiFi connectivity and web interface functionality with current code

**Checkpoint**: Hardware ready, baseline documented, web interface confirmed working

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure changes that ALL user stories depend on

**⚠️ CRITICAL**: No user story implementation can begin until this phase is complete

- [x] T005 Add `i2c_lock = asyncio.Lock()` to `ServoController.__init__()` in `firmware/esp32_test/servo_controller.py`
- [x] T006 Add `MAX_RETRIES = 3` constant to `firmware/esp32_test/servo_controller.py`
- [x] T007 Implement `_set_pwm_with_retry()` helper method in `firmware/esp32_test/servo_controller.py`
- [x] T008 Verify `pca9685.py` uses 12-bit PWM values (0-4095) directly - NO conversion needed (research decision confirmed)

**Checkpoint**: Foundation ready - I2C retry infrastructure in place, all user stories can now begin

---

## Phase 3: User Story 1 - Improved Hardware Initialization (Priority: P1) 🎯 MVP

**Goal**: Reliable PCA9685 initialization with retry logic and errno 121 detection

**Independent Test**: Power on ESP32 with various hardware states (connected, disconnected, loose wiring) and verify initialization messages

### Implementation for User Story 1

- [x] T009 [US1] Update `initialize_servos()` to initialize all 16 PCA9685 channels to 0 (not just 9) in `firmware/esp32_test/servo_controller.py`
- [x] T010 [US1] Add `async with self.i2c_lock:` wrapper to PCA9685 operations in `initialize_servos()` in `firmware/esp32_test/servo_controller.py`
- [x] T011 [US1] Replace direct `self.pca9685.set_pwm()` calls with `await self._set_pwm_with_retry()` in `initialize_servos()` in `firmware/esp32_test/servo_controller.py`
- [x] T012 [US1] Add defensive errno 121 detection in `_set_pwm_with_retry()`: check `hasattr(e, 'errno') and e.errno == 121` OR `"Remote I/O" in str(e)` in `firmware/esp32_test/servo_controller.py`
- [x] T013 [US1] Add retry logging: `print(f"I2C retry {attempt+1}/{MAX_RETRIES} on ch{channel}")` in `firmware/esp32_test/servo_controller.py`
- [x] T014 [US1] Add `await asyncio.sleep(0.05)` between retry attempts in `_set_pwm_with_retry()` in `firmware/esp32_test/servo_controller.py`

### Hardware Testing for User Story 1

- [ ] T015 [US1] Execute Test 1 from `quickstart.md`: Normal operation - verify no retry messages
- [ ] T016 [US1] Execute Test 2 from `quickstart.md`: I2C error recovery - wiggle wires, verify retry messages and recovery
- [ ] T017 [US1] Execute Test 3 from `quickstart.md`: Retry exhaustion - disconnect PCA9685, verify graceful failure

**Checkpoint**: US1 complete - Hardware initialization reliable with automatic error recovery

---

## Phase 4: User Story 2 - Enhanced PWM with Retry Logic (Priority: P1)

**Goal**: Accurate PWM operations with automatic I2C error retry

**Independent Test**: Send specific PWM values and verify servos move to correct positions even with induced I2C errors

### Implementation for User Story 2

- [x] T018 [US2] Update `move_servo_smooth()` to use `async with self.i2c_lock:` around PCA9685 operations in `firmware/esp32_test/servo_controller.py`
- [x] T019 [US2] Replace direct `self.pca9685.set_pwm()` with `await self._set_pwm_with_retry()` in gradual movement loop in `firmware/esp32_test/servo_controller.py`
- [x] T020 [US2] Add error handling: if `_set_pwm_with_retry()` returns `False`, log warning and break movement loop in `firmware/esp32_test/servo_controller.py`
- [x] T021 [US2] Update `move_to_safe_positions()` to use `await self._set_pwm_with_retry()` in `firmware/esp32_test/servo_controller.py` (N/A - method doesn't exist)

### Contract Testing for User Story 2

- [x] T022 [P] [US2] Create `tests/firmware/esp32_test/test_pwm_conversion.py` with test cases for 12-bit PWM values (0, 2047, 4095) - VERIFY NO CONVERSION NEEDED
- [x] T023 [P] [US2] Create contract test for retry behavior: mock I2C errors and verify 3 retry attempts with 50ms delays in `tests/firmware/esp32_test/test_pwm_conversion.py`

### Hardware Testing for User Story 2

- [ ] T024 [US2] Send PWM value 0 → verify servo at minimum position
- [ ] T025 [US2] Send PWM value 2047 → verify servo at mid-range position
- [ ] T026 [US2] Send PWM value 4095 → verify servo at maximum position
- [ ] T027 [US2] Induce I2C error during movement → verify retry messages and recovery

**Checkpoint**: US2 complete - PWM operations reliable with retry logic, servos move accurately

---

## Phase 5: User Story 3 - Blocking Movement Prevention (Priority: P2)

**Goal**: Prevent concurrent `step_forward()` execution using existing `active_sequence` attribute

**Independent Test**: Send multiple rapid `step_forward()` commands and verify only one executes at a time

### Implementation for User Story 3

- [x] T028 [US3] Verify `execute_preset()` already checks `if self.active_sequence is not None` in `firmware/esp32_test/servo_controller.py`
- [x] T029 [US3] Add check in `execute_preset()`: if active, log `"Movement already in progress: {self.active_sequence}"` and return immediately in `firmware/esp32_test/servo_controller.py`
- [x] T030 [US3] Ensure `active_sequence` is set in `try` block and cleared in `finally` block for guaranteed cleanup in `firmware/esp32_test/servo_controller.py`
- [x] T031 [US3] Verify `disable_all_servos()` is called in `finally` block to reset movement state in `firmware/esp32_test/servo_controller.py` (called in try block before finally)

### Hardware Testing for User Story 3

- [ ] T032 [US3] Execute Test 4 from `quickstart.md`: Send 10 rapid `step_forward()` commands within 1 second
- [ ] T033 [US3] Verify only first command executes, subsequent commands ignored with log messages
- [ ] T034 [US3] Verify movement completes smoothly without interruption
- [ ] T035 [US3] Verify `active_sequence` is cleared after completion (check via serial console or second command)

**Checkpoint**: US3 complete - Movement protection prevents concurrent execution

---

## Phase 6: User Story 4 - Thread-Safe Position Tracking (Priority: P2)

**Goal**: Accurate servo position tracking during movement with thread-safe updates

**Independent Test**: Execute concurrent leg and arm movements while monitoring `self.positions` for corruption

### Implementation for User Story 4

- [x] T036 [US4] Update `move_servo_smooth()` to update `self.positions[channel] = position` DURING gradual movement loop (not just at end) in `firmware/esp32_test/servo_controller.py`
- [x] T037 [US4] Ensure position update happens INSIDE `async with self.locks[channel]:` context in `firmware/esp32_test/servo_controller.py`
- [x] T038 [US4] Add position tracking to `_set_pwm_with_retry()` calls: update `self.positions[channel]` after successful PWM write in `firmware/esp32_test/servo_controller.py`
- [x] T039 [US4] Add debug logging (optional): `print(f"Position updated: ch{channel} = {position}")` in `firmware/esp32_test/servo_controller.py` (not added - would be too verbose)

### Hardware Testing for User Story 4

- [ ] T040 [US4] Execute Test 5 from `quickstart.md`: Run "Wave Right" preset (concurrent arm + leg movements)
- [ ] T041 [US4] Monitor serial console for position tracking errors or corruption
- [ ] T042 [US4] Verify all servos complete movement smoothly without stuttering
- [ ] T043 [US4] Execute multiple presets in sequence - verify positions remain accurate across operations

**Checkpoint**: US4 complete - Position tracking accurate during concurrent movements

---

## Phase 7: User Story 5 - Improved step_forward() Movement (Priority: P3)

**Goal**: Updated walking gait with new percentage values and timing for smoother, more stable forward motion

**Independent Test**: Execute `step_forward()` and visually confirm lower crouch, higher lift, and longer pause

### Implementation for User Story 5

- [x] T044 [P] [US5] Update `PRESET_STEP_FORWARD` in `firmware/esp32_test/movement_presets.py`:
  - Step 1: `make_leg_targets(50, 50, 50)` speed=0.4 wait=0.2
  - Step 2: `make_leg_targets(22, 50, 50)` speed=0.6 wait=0.2 (was 28%)
  - Step 3: `make_leg_targets(40, 17, 17)` speed=0.65 wait=0.2 (NEW combined motion)
  - Step 4: `make_leg_targets(85, 50, 50)` speed=0.8 wait=0.2 (was 55%)
  - Step 5: `make_leg_targets(50, 50, 50)` speed=1.0 wait=0.5 (was 0.2s pause)
- [x] T045 [P] [US5] Update step descriptions in `PRESET_STEP_FORWARD` for clarity in `firmware/esp32_test/movement_presets.py`

### Contract Testing for User Story 5

- [x] T046 [P] [US5] Create `tests/firmware/esp32_test/test_servo_presets.py` with validation for `PRESET_STEP_FORWARD` structure per `contracts/movement-presets.md`
- [x] T047 [P] [US5] Validate all target pulse widths are within `SERVO_CALIBRATION` min/max ranges in `tests/firmware/esp32_test/test_servo_presets.py`
- [x] T048 [P] [US5] Validate speed values (0.4, 0.6, 0.65, 0.8, 1.0) are all in range 0.1-1.0 in `tests/firmware/esp32_test/test_servo_presets.py`
- [x] T049 [P] [US5] Validate wait values (0.2, 0.2, 0.2, 0.2, 0.5) are all ≥ 0 in `tests/firmware/esp32_test/test_servo_presets.py`

### Hardware Testing for User Story 5

- [ ] T050 [US5] Execute Test 4 from `quickstart.md`: Run `step_forward()` and record video
- [ ] T051 [US5] Verify lower crouch is visible (22% vs 28% baseline)
- [ ] T052 [US5] Verify higher lift is visible (85% vs 55% baseline)
- [ ] T053 [US5] Verify longer final pause (0.5s vs 0.2s baseline) with stopwatch
- [ ] T054 [US5] Measure total sequence timing: should be ~1.3 seconds (0.2+0.2+0.2+0.2+0.5)
- [ ] T055 [US5] Visual inspection: confirm no wobbling or loss of balance during movement

**Checkpoint**: US5 complete - step_forward() gait improved and stable

---

## Phase 8: Regression Testing & Performance Validation

**Purpose**: Ensure changes don't break existing functionality and meet performance targets

- [ ] T056 [P] Execute Test 7 from `quickstart.md`: Run all movement presets (Step Forward, Step Backward, Turn Left, Turn Right, Wave Right, etc.)
- [ ] T057 [P] Verify all presets execute without errors or stuttering
- [ ] T058 Execute Test 8 from `quickstart.md`: Emergency stop during long preset
- [ ] T059 Verify emergency stop response <100ms, all servos disabled
- [ ] T060 Execute Test 6 from `quickstart.md`: Measure `step_forward()` timing with lock overhead
- [ ] T061 Compare timing to baseline (from T003) - verify performance degradation <5%
- [ ] T062 [P] Run contract tests: `pytest tests/firmware/esp32_test/` (if Python contract tests created)

**Checkpoint**: All regressions fixed, performance acceptable

---

## Phase 9: Polish & Documentation

**Purpose**: Finalize implementation with documentation and code cleanup

- [ ] T063 [P] Add docstrings to new `_set_pwm_with_retry()` method with parameters, return values, and retry logic explanation in `firmware/esp32_test/servo_controller.py`
- [ ] T064 [P] Add inline comments explaining errno 121 detection and retry logic in `firmware/esp32_test/servo_controller.py`
- [ ] T065 [P] Update `README.md` in `firmware/esp32_test/` with new movement capabilities and retry behavior
- [ ] T066 [P] Document hardware setup requirements (I2C wiring, pull-up resistors, power supply specs) in `firmware/esp32_test/README.md`
- [ ] T067 Code review: Ensure all async functions use `await` for sleep/lock operations
- [ ] T068 Code review: Verify no blocking calls in async context (all I2C operations use asyncio patterns)
- [ ] T069 [P] Create hardware testing summary document: baseline vs. final measurements, video comparisons, success criteria checklist
- [ ] T070 Final validation: Execute all 8 test scenarios from `quickstart.md` and document results

**Checkpoint**: Documentation complete, code ready for review

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase (Phase 2) completion
  - User Story 1 (P1) → User Story 2 (P1): Can run in parallel (different methods)
  - User Story 3 (P2) → User Story 4 (P2): Can run in parallel (different concerns)
  - User Story 5 (P3): Can run in parallel with P2 stories (different file: movement_presets.py)
- **Regression Testing (Phase 8)**: Depends on all user stories (Phase 3-7) being complete
- **Polish (Phase 9)**: Depends on Regression Testing (Phase 8) completion

### User Story Dependencies

- **User Story 1 (US1)**: Depends only on Foundational (Phase 2) - NO dependencies on other stories
- **User Story 2 (US2)**: Depends on Foundational (Phase 2) AND uses `_set_pwm_with_retry()` from US1 → Should implement AFTER US1 or in parallel if coordinated
- **User Story 3 (US3)**: Depends only on Foundational (Phase 2) - uses existing `active_sequence` → Can run in parallel with US1/US2
- **User Story 4 (US4)**: Depends only on Foundational (Phase 2) - modifies position tracking → Can run in parallel with US1/US2/US3
- **User Story 5 (US5)**: Depends only on Foundational (Phase 2) - different file → Can run in parallel with ALL other stories

### Within Each User Story

- Implementation tasks before hardware testing
- Contract tests (if included) can run in parallel with implementation (TDD approach)
- Hardware tests must run sequentially (require physical setup and observation)

### Parallel Opportunities

**Setup Phase (Phase 1)**:
```bash
# Can run in parallel:
T003: Take baseline measurements (video recording)
T004: Verify web interface (separate from hardware)
```

**Foundational Phase (Phase 2)**:
```bash
# Must run sequentially (same file):
T005 → T006 → T007 → T008
```

**User Story 2 Contract Tests**:
```bash
# Can run in parallel:
T022: Create PWM conversion tests
T023: Create retry behavior tests
```

**User Story 5 Contract Tests**:
```bash
# Can run in parallel:
T046, T047, T048, T049: All preset validation tests
```

**User Story 5 Implementation**:
```bash
# Can run in parallel (if preset structure allows):
T044: Update PRESET_STEP_FORWARD values
T045: Update step descriptions
```

**Regression Testing (Phase 8)**:
```bash
# Can run in parallel:
T056: Test all presets
T057: Verify preset execution
T062: Run contract tests
```

**Polish (Phase 9)**:
```bash
# Can run in parallel:
T063: Add docstrings
T064: Add inline comments
T065: Update README - new capabilities
T066: Document hardware setup
T069: Create testing summary
```

---

## Parallel Example: Multiple User Stories

```bash
# After Foundational (Phase 2) completes, launch user stories in parallel:

Developer A (US1 - Hardware Init):
  T009 → T010 → T011 → T012 → T013 → T014
  T015 → T016 → T017

Developer B (US2 - PWM Retry):
  T018 → T019 → T020 → T021
  T022 || T023  # Contract tests in parallel
  T024 → T025 → T026 → T027

Developer C (US3 - Movement Protection):
  T028 → T029 → T030 → T031
  T032 → T033 → T034 → T035

Developer D (US4 - Position Tracking):
  T036 → T037 → T038 → T039
  T040 → T041 → T042 → T043

Developer E (US5 - step_forward):
  T044 || T045  # Preset updates in parallel
  T046 || T047 || T048 || T049  # Contract tests in parallel
  T050 → T051 → T052 → T053 → T054 → T055
```

---

## Implementation Strategy

### MVP First (P1 Stories Only)

1. **Phase 1**: Setup (T001-T004)
2. **Phase 2**: Foundational (T005-T008) ← BLOCKS everything
3. **Phase 3**: User Story 1 (T009-T017) ← Hardware initialization
4. **Phase 4**: User Story 2 (T018-T027) ← PWM retry logic
5. **Phase 8**: Regression Testing (T056-T062) ← Validate P1 stories
6. **STOP and VALIDATE**: Test P1 functionality on hardware
7. Deploy if ready or continue to P2/P3 stories

### Incremental Delivery (Recommended)

1. **Foundation** (Phase 1 + Phase 2): Setup + retry infrastructure
2. **P1 Increment** (Phase 3 + Phase 4): Hardware init + PWM retry → Test independently → Deploy/Demo
3. **P2 Increment** (Phase 5 + Phase 6): Movement protection + position tracking → Test independently → Deploy/Demo
4. **P3 Increment** (Phase 7): Updated gait → Test independently → Deploy/Demo
5. **Final** (Phase 8 + Phase 9): Regression testing + documentation

Each increment adds value without breaking previous functionality.

### Single Developer Strategy (Sequential by Priority)

1. Setup (Phase 1)
2. Foundational (Phase 2)
3. User Story 1 (Phase 3) → Test → Validate
4. User Story 2 (Phase 4) → Test → Validate
5. User Story 3 (Phase 5) → Test → Validate
6. User Story 4 (Phase 6) → Test → Validate
7. User Story 5 (Phase 7) → Test → Validate
8. Regression Testing (Phase 8)
9. Polish (Phase 9)

---

## Task Count Summary

- **Total Tasks**: 70
- **Phase 1 (Setup)**: 4 tasks
- **Phase 2 (Foundational)**: 4 tasks (BLOCKING)
- **Phase 3 (US1 - P1)**: 9 tasks (6 implementation + 3 hardware tests)
- **Phase 4 (US2 - P1)**: 10 tasks (4 implementation + 2 contract tests + 4 hardware tests)
- **Phase 5 (US3 - P2)**: 8 tasks (4 implementation + 4 hardware tests)
- **Phase 6 (US4 - P2)**: 8 tasks (4 implementation + 4 hardware tests)
- **Phase 7 (US5 - P3)**: 12 tasks (2 implementation + 4 contract tests + 6 hardware tests)
- **Phase 8 (Regression)**: 7 tasks
- **Phase 9 (Polish)**: 8 tasks

**Parallel Opportunities Identified**: 15+ tasks can run in parallel (marked with [P])

**Independent Test Criteria**: Each user story has clear hardware test scenarios in quickstart.md

**Suggested MVP Scope**: 
- Phase 1 (Setup) + Phase 2 (Foundational) + Phase 3 (US1) + Phase 4 (US2) = P1 priorities only
- Delivers: Reliable hardware initialization + retry logic (28 tasks total)

---

## Notes

- [P] tasks = different files or independent operations, no dependencies
- [Story] label (US1-US5) maps task to specific user story for traceability
- Each user story is independently testable using scenarios from `quickstart.md`
- Hardware tests require physical ESP32 setup - cannot be fully automated
- Contract tests validate data structures - can run in Python without hardware
- Verify all async functions use `await` for sleep/lock operations (async-first critical)
- Commit after each task or logical group (e.g., after each user story phase)
- Stop at any checkpoint to validate story independently before proceeding
