---

## Phase 0 Complete: Research

All technical unknowns resolved. Key decisions documented in [research.md](./research.md):

- **PCA9685 Driver**: Custom minimal driver (~150 lines) ported from Adafruit CircuitPython
- **Async HTTP Server**: Custom implementation using uasyncio + raw sockets (no framework overhead)
- **Servo Coordination**: asyncio.create_task() for parallel movements with Lock per channel
- **WiFi Management**: network.WLAN with retry logic, display IP on serial console
- **Web Interface**: Embedded HTML/CSS/JS string (~8KB) for simplified deployment
- **Calibration Storage**: Hard-coded constants in servo_controller.py with config.ini references

## Phase 1 Complete: Design & Contracts

### Data Model Defined

[data-model.md](./data-model.md) specifies:
- **6 core entities**: ServoState, MovementStep, MovementSequence, SystemStatus, ControlCommand, ControlResponse
- **State management**: Global controller state with positions array, locks, emergency stop flag
- **Validation rules**: Channel (0-8), pulse width (0-600), speed (0.1-1.0), state transitions
- **Memory estimates**: ~20KB total application footprint, 150KB minimum free RAM threshold

### Contracts Defined

[contracts/http-api.md](./contracts/http-api.md) documents:
- **6 HTTP endpoints**: GET /, GET /status, POST /control (4 command types), POST /emergency, POST /resume
- **Request/response schemas**: JSON structures for all commands and responses
- **Error handling**: 4XX/5XX status codes with detailed error messages
- **Performance SLAs**: <200ms command latency, <100ms emergency stop, <10s boot time

[contracts/servo-commands.md](./contracts/servo-commands.md) documents:
- **5 core commands**: move_servo_smooth, move_multiple, emergency_stop_all, disable_all_servos, reset_positions
- **13 preset sequences**: Complete choreography for all movements from original code
- **Validation rules**: Input validation, state validation, error recovery procedures
- **Performance characteristics**: Timing and resource usage for all operations

### Quickstart Guide Created

[quickstart.md](./quickstart.md) provides:
- **9-step setup process**: Flash firmware → configure WiFi → upload files → test servos
- **Comprehensive testing**: Single servo, speed control, emergency stop, all presets, performance validation
- **Troubleshooting**: 5 common issues with solutions (I2C, WiFi, memory, mechanical, web interface)
- **Maintenance**: Daily/weekly/monthly checklists and development workflow
- **Quick reference**: Command cheatsheets for file upload, serial console, API testing

### Agent Context Updated

- Added MicroPython v1.20+ on ESP32-S3 to `.github/copilot-instructions.md`
- Preserved manual additions between markers

### Tooling Standardized

[MPREMOTE_WORKFLOW.md](./MPREMOTE_WORKFLOW.md) documents:
- **Single tool**: All ESP32 interactions use `mpremote` exclusively (no ampy/rshell/screen)
- **Shell scripts**: 7 automation scripts in `firmware/esp32_test/` (upload, configure, diagnose, etc.)
- **Common workflows**: Deploy, debug, update, status check patterns
- **Troubleshooting**: Device detection, permissions, connection issues

### Hardware Configuration Verified

[V2_CONFIG_VERIFICATION.md](./V2_CONFIG_VERIFICATION.md) documents:
- **V2 calibration values**: All servos configured per config.ini MOVEMENT_VERSION=V2
- **Servo inventory**: 3x LDX-227 (legs), 2x MG996R (shoulders), 4x MG90S (forearms/hands)
- **I2C pins**: Custom GPIO 8 (SDA), GPIO 9 (SCL) instead of default 21/22
- **Safety warnings**: Critical min/max limits and testing protocols

## Phase 1 Re-Evaluation: Constitution Check

**Post-Design Assessment**: ✅ PASS

All constitution principles remain compliant after detailed design:

1. **Async-First Concurrency**: Confirmed via data-model.md - all servo movements use uasyncio with proper Lock management and CancelledError handling
2. **Configuration via Environment**: Justified exception maintained - wifi_config.py and calibration constants documented in contracts
3. **Observability**: Confirmed via http-api.md - /status endpoint provides comprehensive system state, serial console structured logging
4. **Simplicity**: Confirmed via research.md - minimal custom implementations (no frameworks), flat module structure, ~800-1200 LOC total

No new violations introduced during design phase.

## Next Steps

**Phase 2: Task Breakdown** - Ready for `/speckit.tasks` command

Implementation tasks ready to be generated:
- [ ] PCA9685 driver implementation (pca9685.py)
- [ ] Servo controller with async coordination (servo_controller.py)
- [ ] Movement presets port (movement_presets.py)
- [ ] Web server with routes (web_server.py)
- [ ] HTML interface (embedded in web_server.py)
- [ ] WiFi initialization (updates to main.py)
- [ ] Testing via quickstart guide procedures

---

## Artifacts Generated

```
specs/002-esp32-micropython-servo/
├── plan.md                          # This file (Phase 0+1 complete)
├── research.md                      # Technology decisions & patterns
├── data-model.md                    # State structures & entities
├── quickstart.md                    # Setup, deployment, testing guide
└── contracts/
    ├── http-api.md                  # HTTP API specification
    └── servo-commands.md            # Internal servo control spec
```

**Branch**: 002-esp32-micropython-servo  
**Status**: Phase 0+1 Complete, Ready for Phase 2 (Task Breakdown)  
**Date**: 2025-10-15

````markdown
# Implementation Plan: ESP32 MicroPython Servo Control System

**Branch**: `002-esp32-micropython-servo` | **Date**: 2025-10-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-esp32-micropython-servo/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build a MicroPython-based servo control system for ESP32-S3 that modernizes the existing tars-community-movement-original code. Replace multiprocessing with asyncio (uasyncio) for parallel servo movements, add a web interface for remote control and testing, and implement emergency stop functionality. The system controls 9 servos via PCA9685 I2C PWM driver, provides 13 preset movement sequences, and exposes controls through an async HTTP server accessible over WiFi.

**Key Innovation**: Convert blocking multiprocessing servo control to non-blocking asyncio while maintaining smooth coordinated movements and adding web-based remote control.

## Technical Context

**Language/Version**: MicroPython v1.20+ on ESP32-S3 (requires uasyncio support)
**Primary Dependencies**: 
- MicroPython stdlib: `machine`, `network`, `socket`, `uasyncio`, `json`, `time`, `gc`
- I2C PCA9685 driver library (MicroPython-compatible, may need to port/adapt from Adafruit CircuitPython)
- Async HTTP server (implement using uasyncio + socket, or use micropython-async library)

**Storage**: 
- Configuration stored in WiFi credentials file (written by configure_wifi.sh)
- Servo calibration values hard-coded or in minimal JSON config file
- No persistent state needed beyond configuration

**Testing**: 
- Manual testing via web interface (primary)
- Serial console output for debugging
- Contract tests would require MicroPython test runner (optional, manual verification sufficient)

**Target Platform**: ESP32-S3 SoC (240MHz dual-core, 512KB SRAM, 4MB+ flash, WiFi 2.4GHz)

**Project Type**: Embedded firmware (single MicroPython application)

**Performance Goals**:
- Boot to web server ready: <10 seconds
- Servo command latency: <200ms from HTTP request to PWM output
- Emergency stop response: <100ms
- Web server concurrent requests: Handle 2-3 simultaneous connections
- Memory footprint: <300KB RAM usage (leaving 200KB+ free for async tasks)

**Constraints**:
- MicroPython stdlib only (no pip packages at runtime)
- Single-threaded async execution (no multiprocessing, no threading beyond C-level)
- Limited RAM (512KB total, ~400-450KB available to Python after firmware)
- Flash size determines code complexity limit
- Must work with existing upload.sh and configure_wifi.sh scripts

**Scale/Scope**:
- 9 servos (channels 0-8 on PCA9685)
- 13 preset movement sequences
- Single web interface client at a time (no session management needed)
- Approximately 800-1200 lines of Python code total

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Applicable Constitution Principles

**✅ PASS - III. Async-First Concurrency**: 
- **Applies**: System uses asyncio (uasyncio) for all servo movement coordination
- **Compliance**: Design specifies `asyncio.create_task()` for parallel servo movements, `asyncio.gather()` for coordination, and `asyncio.wait_for()` for emergency stop with timeout
- **Note**: MicroPython uasyncio is subset of Python asyncio but covers needed primitives

**⚠️ PARTIAL - V. Configuration via Environment**:
- **Applies**: WiFi credentials and servo calibration need configuration
- **Compliance Issue**: MicroPython doesn't have `os.environ` or `.env` file support
- **Justified Exception**: Use configure_wifi.sh to write wifi_config.py file with credentials as Python constants; servo calibration as module-level constants or minimal JSON file
- **Rationale**: Embedded systems use compiled-in config or simple file-based config; shell scripts already exist for this pattern

**✅ PASS - VI. Observability & Health Monitoring**:
- **Applies**: System should provide operational visibility
- **Compliance**: Serial console logging with structured output; web interface displays system status (WiFi state, PCA9685 status, servo positions)
- **Note**: No MQTT on ESP32 (would add significant memory overhead); health via web status endpoint is sufficient

**✅ PASS - VII. Simplicity & YAGNI**:
- **Applies**: Keep implementation minimal for embedded constraints
- **Compliance**: No frameworks, no ORM, no complex abstractions; plain MicroPython async patterns
- **Justification**: Embedded systems require simplicity; limited RAM/flash enforces this

**❌ NOT APPLICABLE - I. Event-Driven Architecture**:
- **Reason**: This is a standalone embedded system, not a service in the py-tars MQTT ecosystem
- **Note**: No MQTT broker on ESP32; direct HTTP control appropriate for embedded use case

**❌ NOT APPLICABLE - II. Typed Contracts**:
- **Reason**: MicroPython doesn't support Pydantic or type checking at runtime
- **Alternative**: Use docstrings to document expected dict structures; validate inputs manually

**❌ NOT APPLICABLE - IV. Test-First Development**:
- **Reason**: MicroPython testing requires device access; manual testing via web interface is more practical
- **Alternative**: Comprehensive manual test plan in quickstart.md

### Summary

**GATE STATUS: ✅ PASS WITH JUSTIFIED EXCEPTIONS**

Exceptions justified by embedded platform constraints:
1. Configuration via Python file instead of environment variables (no MicroPython stdlib support)
2. Manual testing instead of automated test suite (limited MicroPython test tooling)
3. No Pydantic/typing (MicroPython limitation)
4. No MQTT integration (memory constraints + standalone system)

These exceptions are **acceptable** because:
- They're imposed by platform limitations, not design choices
- Simpler alternatives (env vars, pytest, Pydantic) are not available in MicroPython
- The implemented alternatives (config files, manual testing, docstrings) are standard embedded practices

## Project Structure

### Documentation (this feature)

```
specs/002-esp32-micropython-servo/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (technology decisions & patterns)
├── data-model.md        # Phase 1 output (state structures & entities)
├── quickstart.md        # Phase 1 output (setup, deployment, testing guide)
└── contracts/           # Phase 1 output (HTTP API schemas, servo commands)
    ├── http-api.yaml    # OpenAPI-style documentation of web endpoints
    └── servo-commands.md # Documentation of servo control data structures
```

### Source Code (firmware/esp32_test/)

**Structure Decision**: Flat MicroPython module structure with minimal nesting (embedded best practice).

```
firmware/esp32_test/
├── boot.py                      # [EXISTS] ESP32 initialization (CPU freq, GC)
├── main.py                      # [EXISTS] Entry point - starts web interface
├── wifi_config.py               # [CREATED BY configure_wifi.sh] WiFi credentials
│
├── pca9685.py                   # [NEW] PCA9685 I2C PWM driver class
├── servo_controller.py          # [NEW] Async servo movement coordination
├── movement_presets.py          # [NEW] 13 preset movement sequences
├── web_server.py                # [NEW] Async HTTP server with routes
├── web_interface.html           # [NEW] Single-page HTML UI (embedded in .py as string)
│
├── i2c_scanner.py               # [EXISTS] I2C bus diagnostic utility
├── upload.sh                    # [EXISTS] File upload script (ampy/mpremote)
├── configure_wifi.sh            # [EXISTS] WiFi configuration script
├── connect.sh                   # [EXISTS] Serial console connection
├── diagnose.sh                  # [EXISTS] System diagnostics
├── clean.sh                     # [EXISTS] Remove files from ESP32
├── list_files.sh                # [EXISTS] List files on ESP32
└── start_server.sh              # [EXISTS] Start serial monitoring

tars-community-movement-original/  # [REFERENCE ONLY] Original Python code
├── app-servotester.py           # Source for preset movements
├── module_servoctl_v2.py        # Source for servo control patterns
└── config.ini                   # Source for calibration values
```

**Key Files**:

1. **boot.py** (existing, minimal changes): Sets CPU frequency, enables GC, displays boot info
2. **main.py** (existing, major refactor): Imports and starts `web_server.main()`
3. **pca9685.py** (new): MicroPython I2C driver for PCA9685 (port from CircuitPython or write minimal driver)
4. **servo_controller.py** (new): Core async servo movement logic, tracks positions, handles emergency stop
5. **movement_presets.py** (new): 13 preset sequences adapted from `module_servoctl_v2.py`
6. **web_server.py** (new): Async HTTP server with routes for control, status, emergency stop
7. **web_interface.html** (new): Single-page interface with servo sliders, preset buttons, emergency stop

**Dependencies from Existing Code**:
- Reference `tars-community-movement-original/module_servoctl_v2.py` for movement choreography
- Reference `tars-community-movement-original/config.ini` for servo calibration values (min/max pulse widths)

## Complexity Tracking

*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Config via Python file (not env) | MicroPython has no os.environ or .env support | Environment variables don't exist in MicroPython runtime; configure_wifi.sh already writes Python file |
| No automated tests | MicroPython testing requires device access; pytest/unittest don't run on device | Cross-compilation testing not practical; manual testing via web UI more efficient for embedded |
| No Pydantic/typing | MicroPython doesn't support Pydantic or runtime type checking | Static typing not available; docstrings + manual validation is standard MicroPython practice |
