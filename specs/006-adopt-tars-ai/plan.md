````

---

## Phase 0: Research & Technical Decisions ✅ COMPLETE

**Output**: [research.md](./research.md)

### Key Decisions Made

1. **PWM Conversion**: NOT NEEDED - ESP32 driver uses 12-bit values directly
2. **Locking Strategy**: `asyncio.Lock()` with `async with` syntax
3. **Error Handling**: Defensive errno checking with string fallback
4. **Position Tracking**: Enhance existing `self.positions` list (no new dict)
5. **Movement Protection**: Reuse `self.active_sequence` (no new MOVING flag)
6. **Step Forward**: Update PRESET_STEP_FORWARD with new percentages

### Technologies Selected

- **I2C Locking**: MicroPython `asyncio.Lock`
- **Retry Delay**: `await asyncio.sleep(0.05)` (50ms)
- **Error Detection**: `hasattr(e, 'errno')` check + string matching
- **Position Updates**: Incremental during movement loop

---

## Phase 1: Design & Contracts ✅ COMPLETE

**Outputs**:
- [data-model.md](./data-model.md) - ServoController enhancements
- [contracts/movement-presets.md](./contracts/movement-presets.md) - Preset validation rules
- [quickstart.md](./quickstart.md) - Hardware testing guide

### Artifacts Created

#### Data Model
- Enhanced ServoController with I2C retry logic
- New `_set_pwm_with_retry()` method
- Updated PRESET_STEP_FORWARD sequence
- I2C error state machine

#### Contracts
- Movement preset structure validation
- Pulse width range constraints
- Speed and timing validation rules
- Test cases for contract compliance

#### Testing Guide
- 8 test scenarios (normal, retry, failure, movement, performance, regression)
- Hardware setup instructions
- Debugging tips and common issues
- Success criteria checklist

---

## Phase 2: Task Breakdown

**Note**: This phase is completed by the `/speckit.tasks` command (NOT created by `/speckit.plan`)

Task breakdown will include:
- Modify `servo_controller.py` to add retry logic
- Update `movement_presets.py` with new step_forward sequence
- Add contract tests for movement presets
- Hardware integration testing
- Documentation updates

---

## Implementation Checklist

### Prerequisites
- [x] Constitution check passed
- [x] Research decisions documented
- [x] Data model defined
- [x] Contracts specified
- [x] Testing guide created

### Ready for Implementation
- [ ] `/speckit.tasks` command to generate task breakdown
- [ ] Development branch created from `006-adopt-tars-ai`
- [ ] Hardware test environment prepared (ESP32 + PCA9685 + servos)
- [ ] Baseline measurements taken (timing, behavior)

### Post-Implementation
- [ ] All contract tests passing
- [ ] Hardware integration tests completed
- [ ] Performance regression < 5%
- [ ] Documentation updated
- [ ] PR submitted for review

---

## Risk Mitigation Summary

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| PWM conversion mismatch | LOW | HIGH | Research confirmed no conversion needed ✅ |
| Lock contention delays | MEDIUM | LOW | Profile before/after; lock is fast |
| Position tracking memory | LOW | LOW | Only 36 bytes overhead |
| Errno 121 unavailable | MEDIUM | LOW | Defensive checking with fallback ✅ |
| MOVING flag edge cases | LOW | MEDIUM | Reuse active_sequence instead ✅ |

---

## Next Command

Run `/speckit.tasks` to generate detailed implementation task breakdown.markdown
# Implementation Plan: Adopt TARS AI Movement System Updates

**Branch**: `006-adopt-tars-ai` | **Date**: 2025-10-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-adopt-tars-ai/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Adopt reliability improvements from the TARS AI community movement system (Raspberry Pi/Python) into the ESP32 MicroPython servo controller. Primary changes include: (1) PCA9685 initialization with retry logic and errno 121 detection, (2) PWM to duty cycle conversion with I2C error recovery, (3) thread-safe servo position tracking for smooth gradual movements, (4) MOVING flag to prevent concurrent step_forward() execution, and (5) refined walking gait sequence. Implementation requires adapting Python threading patterns to MicroPython asyncio equivalents while maintaining the existing async-first architecture.

## Technical Context

**Language/Version**: MicroPython v1.20+ on ESP32  
**Primary Dependencies**: 
- Custom PCA9685 driver (`pca9685.py`) - I2C PWM controller
- `uasyncio` (MicroPython asyncio) for async/await patterns
- `machine` module for I2C hardware access
- Existing `servo_config.py` for calibration data
- Existing `servo_controller.py` for async servo control

**Storage**: Flash storage for MicroPython modules (no database)  
**Testing**: Hardware integration tests (ESP32 + PCA9685 + servos); contract tests for movement presets  
**Target Platform**: ESP32-S3 (custom GPIO: SDA=8, SCL=9) with PCA9685 servo controller (16 channels, 9 servos used)  
**Project Type**: Embedded firmware (single MicroPython application)  
**Performance Goals**: 
- I2C operations <50ms per servo command
- Movement sequences execute smoothly without stutter
- Recovery from I2C errors within 150ms (3 retries × 50ms)

**Constraints**:
- Limited RAM (~320KB usable on ESP32-S3)
- MicroPython subset of Python 3.4 (no full threading module, limited stdlib)
- Must maintain async-first architecture (no blocking I/O in event loop)
- Cannot use Python `threading.Lock` - must adapt to `asyncio.Lock`

**Scale/Scope**:
- 9 servo channels active (3 leg servos, 6 arm servos)
- ~12 movement preset functions
- Single ServoController class managing all movements
- Web interface control (existing, no changes needed)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **Event-Driven Architecture** | ✅ PASS | Not applicable - embedded firmware, no MQTT in servo controller |
| **Typed Contracts** | ✅ PASS | Not applicable - no message passing, servo control is direct hardware I/O |
| **Async-First Concurrency** | ✅ PASS | CRITICAL - Must maintain asyncio.Lock pattern, verify no blocking I2C calls |
| **Test-First Development** | ⚠️ PARTIAL | Hardware tests required but cannot be automated; contract tests for presets are feasible |
| **Configuration via Environment** | ✅ PASS | Configuration in servo_config.py (hardcoded calibration data, acceptable for embedded) |
| **Observability** | ✅ PASS | Console logging via print() acceptable for embedded; no health topics needed |
| **Simplicity & YAGNI** | ✅ PASS | Adopting proven patterns from working system; no new abstractions |
| **Python Standards** | ⚠️ ADAPTED | MicroPython 3.4 subset - no ruff/black/mypy; manual code review required |

**Critical Requirements**:
1. **Async-First**: ALL I2C operations must be wrapped in `asyncio.to_thread()` or use async-compatible patterns
2. **Lock Usage**: Replace Python `threading.Lock` with `asyncio.Lock` and use `async with` syntax
3. **No Blocking**: Convert `time.sleep()` to `await asyncio.sleep()` throughout

**Risk Assessment**:
- **HIGH**: PWM duty cycle conversion - if PCA9685 driver API differs, servos could move incorrectly
- **MEDIUM**: asyncio.Lock performance - potential lock contention during concurrent movements
- **LOW**: MOVING flag edge cases - could permanently lock if not reset on errors

**Justification for Constitution Adaptations**:
- **Testing**: Hardware-dependent testing cannot be fully automated; integration tests on actual hardware required
- **Python Standards**: MicroPython lacks tooling (ruff/mypy) but code will follow PEP 8 manually; type hints in comments

## Project Structure

### Documentation (this feature)

```
specs/006-adopt-tars-ai/
├── spec.md              # Feature specification
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output - PWM conversion analysis, asyncio.Lock patterns
├── data-model.md        # Phase 1 output - ServoController state model
├── quickstart.md        # Phase 1 output - Testing guide for hardware
├── contracts/           # Phase 1 output - Movement preset contracts
├── CHANGES_ANALYSIS.md  # Detailed code comparison (already created)
└── checklists/
    └── requirements.md  # Specification quality checklist (already created)
```

### Source Code (repository root)

```
firmware/esp32_test/
├── main.py                    # Entry point (minor updates for initialization)
├── pca9685.py                 # PCA9685 driver (investigate duty cycle conversion)
├── servo_controller.py        # PRIMARY: Add retry logic, position tracking, MOVING flag
├── servo_config.py            # No changes (calibration data)
├── movement_presets.py        # UPDATE: step_forward sequence values
├── web_server.py              # No changes (HTTP control interface)
├── wifi_manager.py            # No changes
└── wifi_config.py             # No changes

firmware/esp32_test/tars-community-movement-original/
├── module_btcontroller_v2.py  # REFERENCE: Source of changes
└── module_servoctl_v2.py      # REFERENCE: Source of changes

tests/
└── firmware/
    └── esp32_test/
        ├── test_servo_presets.py      # NEW: Contract tests for movement sequences
        └── test_pwm_conversion.py     # NEW: Unit tests for PWM conversion
```

**Structure Decision**: Embedded single-project structure. All changes contained within `firmware/esp32_test/` directory. No multi-tier architecture needed. Tests will be Python (not MicroPython) contract tests that validate movement preset data structures.

## Complexity Tracking

*No constitution violations requiring justification. Feature maintains simplicity by adopting proven patterns from reference implementation.*
