# Tasks: ESP32 MicroPython Servo Control System

**Feature Branch**: `002-esp32-micropython-servo`  
**Input**: Design documents from `/specs/002-esp32-micropython-servo/`  
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓

**Tests**: Manual testing via quickstart.md procedures (MicroPython automated testing not practical for embedded systems)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions
- **Firmware location**: `firmware/esp32_test/`
- **Reference code**: `tars-community-movement-original/`
- **Scripts**: Shell scripts in `firmware/esp32_test/` using mpremote

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and tooling verification

- [X] T001 Verify ESP32-S3 has MicroPython v1.20+ firmware with uasyncio support
- [X] T002 Verify mpremote installed and device accessible at /dev/ttyACM0 or /dev/ttyUSB0
- [X] T003 [P] Test I2C bus with i2c_scanner.py to verify PCA9685 at address 0x40
- [X] T004 [P] Verify WiFi network is 2.4GHz with WPA2 and DHCP enabled
- [X] T005 Run configure_wifi.sh and upload wifi_config.py to ESP32

**Checkpoint**: Hardware verified, WiFi configured, ready for firmware development

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core drivers and infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### PCA9685 I2C Driver (Foundation for all servo control)

- [ ] T006 Create firmware/esp32_test/pca9685.py with PCA9685 class skeleton
- [ ] T007 Implement PCA9685.__init__(i2c, address=0x40) to initialize I2C device and verify communication
- [ ] T008 Implement PCA9685.set_pwm_freq(freq_hz) to configure PWM frequency (50Hz for servos)
- [ ] T009 Implement PCA9685.set_pwm(channel, on, off) to set PWM duty cycle for individual channels
- [ ] T010 Add PCA9685 register definitions (MODE1=0x00, PRESCALE=0xFE, LED0_ON_L=0x06, etc.)
- [ ] T011 Test PCA9685 driver: upload to ESP32, initialize at 50Hz, set channel 0 to 300, verify servo moves

### Boot Sequence (Foundation for system initialization)

- [ ] T012 Update firmware/esp32_test/boot.py to display CPU frequency, free memory, boot timestamp
- [ ] T013 Add garbage collection configuration to boot.py: gc.enable(), gc.collect()
- [ ] T014 Test boot.py: upload to ESP32, reset device, verify serial console output shows boot info

### WiFi Connection (Foundation for web interface)

- [ ] T015 Create firmware/esp32_test/wifi_manager.py with async connect_wifi(ssid, password, timeout=10) function
- [ ] T016 Implement WiFi connection with retry logic (5 attempts, exponential backoff)
- [ ] T017 Display IP address to serial console on successful connection
- [ ] T018 Handle connection timeout gracefully with clear error message
- [ ] T019 Test WiFi connection: upload wifi_manager.py, run connect_wifi(), verify IP displayed and pingable from network

### Servo Configuration (Foundation for all servo operations)

- [ ] T020 Create firmware/esp32_test/servo_config.py with SERVO_CALIBRATION dictionary from V2 config.ini values
- [ ] T021 Define calibration for channels 0-2 (legs - LDX-227 servos): min, max, neutral, label
- [ ] T022 Define calibration for channels 3, 6 (shoulders - MG996R servos): min, max, neutral, label
- [ ] T023 Define calibration for channels 4-5, 7-8 (forearms/hands - MG90S servos): min, max, neutral, label
- [ ] T024 Add SERVO_LABELS list with functional names for all 9 servos
- [ ] T025 Add validation functions: validate_channel(channel), validate_pulse_width(channel, pulse), validate_speed(speed)

**Checkpoint**: Foundation ready - PCA9685 driver working, boot sequence functional, WiFi connects, servo config defined. User story implementation can now begin.

---

## Phase 3: User Story 1 - Hardware Initialization and Connection (Priority: P1) 🎯 MVP

**Goal**: Initialize PCA9685 servo controller, connect to WiFi, verify all 9 servos are responsive

**Independent Test**: Upload firmware, connect to WiFi, verify PCA9685 detected, test individual servos from REPL

### Implementation for User Story 1

- [ ] T026 [P] [US1] Create firmware/esp32_test/servo_controller.py with ServoController class skeleton
- [ ] T027 [US1] Implement ServoController.__init__(pca9685) to initialize controller with positions array [300]*9 and locks [asyncio.Lock()]*9
- [ ] T028 [US1] Add ServoController.emergency_stop flag (boolean) and global_speed attribute (default 1.0)
- [ ] T029 [US1] Implement ServoController.initialize_servos() to move all servos to neutral positions on startup
- [ ] T030 [US1] Update firmware/esp32_test/main.py to import wifi_manager, pca9685, servo_controller
- [ ] T031 [US1] Add main.py startup sequence: await connect_wifi() → initialize I2C (GPIO 8=SDA, 9=SCL) → initialize PCA9685 → set frequency 50Hz
- [ ] T032 [US1] Add main.py: create ServoController instance → call initialize_servos() → display "System ready"
- [ ] T033 [US1] Add error handling in main.py: catch I2C errors (PCA9685 not found), WiFi timeout, memory errors
- [ ] T034 [US1] Upload all files (boot.py, main.py, wifi_config.py, pca9685.py, servo_config.py, servo_controller.py, wifi_manager.py) using upload.sh
- [ ] T035 [US1] Test initialization: reset ESP32, verify serial console shows WiFi connection, PCA9685 detected at 0x40, servos initialize to neutral
- [ ] T036 [US1] Test error handling: disconnect PCA9685 power, reset ESP32, verify clear error message "PCA9685 not detected"
- [ ] T037 [US1] Test manual servo control from REPL: import servo_controller, call set_pwm(0, 0, 350), verify servo 0 moves

**Checkpoint**: User Story 1 complete - ESP32 boots, connects to WiFi, initializes PCA9685, servos respond to commands

---

## Phase 4: User Story 2 - Interactive Web-Based Servo Testing (Priority: P1) 🎯 MVP

**Goal**: Test individual servo movements through a responsive web interface accessible from any device on local network

**Independent Test**: Navigate to ESP32's IP in browser, use interface to control individual servos (0-8), verify smooth movements at different speeds

### Web Server Implementation

- [ ] T038 [P] [US2] Create firmware/esp32_test/web_server.py with async handle_client(reader, writer) function
- [ ] T039 [US2] Implement HTTP request parsing in handle_client(): parse request line (method, path), parse headers (Content-Length), read body for POST
- [ ] T040 [US2] Implement route dispatch in handle_client(): "/" → serve HTML, "/control" → handle commands, "/status" → system status
- [ ] T041 [US2] Implement async start_server(servo_controller) to bind socket on port 80 and accept connections
- [ ] T042 [US2] Add error handling: catch malformed JSON, invalid routes (404), server errors (500)

### HTML Web Interface (Embedded)

- [ ] T043 [US2] Create HTML interface as string constant HTML_INTERFACE in web_server.py
- [ ] T044 [US2] Add HTML structure: <!DOCTYPE html>, responsive viewport meta tag, body with header "TARS Servo Controller"
- [ ] T045 [US2] Add CSS styles: body font/margin, container layout, servo control sections, button styles
- [ ] T046 [US2] Add servo controls section: 9 labeled inputs (servo 0-8 with functional names from SERVO_LABELS)
- [ ] T047 [US2] Add servo controls: numeric inputs for pulse width (range min-max per servo), speed slider (0.1-1.0)
- [ ] T048 [US2] Add "Move Servo" button per servo channel that sends POST /control with {"type":"single", "channel":N, "target":VALUE}
- [ ] T049 [US2] Add JavaScript fetch() calls: moveServo(channel, target, speed) sends POST /control, displays response message
- [ ] T050 [US2] Add JavaScript error handling: display error alerts if response.success=false

### Control Endpoint Implementation

- [ ] T051 [US2] Implement async handle_control(body, servo_controller) in web_server.py
- [ ] T052 [US2] Parse JSON body: extract type, channel, target, speed fields
- [ ] T053 [US2] Implement "single" command type: validate inputs, call servo_controller.move_servo_smooth(channel, target, speed)
- [ ] T054 [US2] Return JSON response: {"success": true, "message": "Servo N moving to TARGET", "server_timestamp": time.time()}
- [ ] T055 [US2] Add error responses for validation failures: invalid channel, pulse width out of range, speed out of range
- [ ] T056 [US2] Add latency tracking: if client sends "timestamp", calculate latency_ms = (server_time - client_time) * 1000

### Servo Movement Implementation

- [ ] T057 [US2] Implement async ServoController.move_servo_smooth(channel, target, speed) in servo_controller.py
- [ ] T058 [US2] Acquire lock for channel: async with self.locks[channel]
- [ ] T059 [US2] Calculate movement: get current position, determine step direction (+1 or -1), loop from current to target
- [ ] T060 [US2] Movement loop: set PWM via pca9685.set_pwm(channel, 0, position), update positions[channel], sleep 0.02*(1.0-speed)
- [ ] T061 [US2] Add emergency_stop check in loop: if self.emergency_stop, raise asyncio.CancelledError
- [ ] T062 [US2] Release lock after movement completes or error

### Integration & Testing

- [ ] T063 [US2] Update main.py to start web server after servo initialization: asyncio.create_task(start_server(servo_controller))
- [ ] T064 [US2] Upload all files: web_server.py, updated servo_controller.py, updated main.py
- [ ] T065 [US2] Test web interface load: navigate to http://<ESP32-IP>, verify HTML loads with 9 servo controls
- [ ] T066 [US2] Test single servo movement: set servo 0 target=350, speed=0.8, click "Move", verify smooth movement in ~2 seconds
- [ ] T067 [US2] Test speed control: move servo 0 at speed=0.1 (slow, ~18 seconds), then speed=1.0 (fast, ~2 seconds), verify visible difference
- [ ] T068 [US2] Test validation: try pulse width=700 (invalid), verify error message "Pulse width 700 exceeds maximum 600"
- [ ] T069 [US2] Test all 9 servos: individually move each servo to min, neutral, max positions, verify mechanical range correct
- [ ] T070 [US2] Test concurrent access: open interface in two browsers, both should be able to control servos (no crash)

**Checkpoint**: User Story 2 complete - Web interface works, individual servos controllable with speed adjustment, validation working

---

## Phase 5: User Story 3 - Emergency Stop/Kill Switch (Priority: P1) 🎯 MVP

**Goal**: Immediate ability to disable all servos if unexpected behavior occurs during testing or movements

**Independent Test**: Start any servo movement, press emergency stop button, verify all servos stop within 100ms and enter floating state

### Emergency Stop Implementation

- [ ] T071 [P] [US3] Implement async ServoController.emergency_stop_all() in servo_controller.py
- [ ] T072 [US3] Set self.emergency_stop = True flag in emergency_stop_all()
- [ ] T073 [US3] Wait 100ms: await asyncio.sleep(0.1) for active tasks to detect flag and cancel
- [ ] T074 [US3] Disable all 9 servos: loop channels 0-8, call pca9685.set_pwm(ch, 0, 0) to set PWM=0 (floating state)
- [ ] T075 [US3] Reset emergency_stop flag: self.emergency_stop = False after all servos disabled

### Web Interface Emergency Button

- [ ] T076 [P] [US3] Add emergency stop button to HTML_INTERFACE in web_server.py
- [ ] T077 [US3] Style emergency button: position fixed top-right, large circular button (60x60px), red background, white text "STOP"
- [ ] T078 [US3] Add z-index: 1000 to emergency button CSS to ensure it's always on top, visible during scrolling
- [ ] T079 [US3] Add JavaScript emergencyStop() function: sends POST /emergency, displays alert "Emergency stop activated!"
- [ ] T080 [US3] Add onclick handler to emergency button: onclick="emergencyStop()"

### Emergency Endpoint

- [ ] T081 [US3] Add "/emergency" route to handle_client() in web_server.py
- [ ] T082 [US3] Implement handle_emergency(servo_controller): call await servo_controller.emergency_stop_all()
- [ ] T083 [US3] Return success response: {"success": true, "message": "Emergency stop activated - all servos disabled"}
- [ ] T084 [US3] Log emergency stop event to serial console with timestamp

### Resume Functionality

- [ ] T085 [P] [US3] Add "/resume" route to handle_client() in web_server.py
- [ ] T086 [US3] Implement async handle_resume(servo_controller): reset emergency_stop flag, move all servos to neutral positions
- [ ] T087 [US3] Add "Resume" button to web interface below emergency stop button
- [ ] T088 [US3] Add JavaScript resume() function: sends POST /resume, displays message "Servos re-initialized"

### Testing

- [ ] T089 [US3] Upload updated files: web_server.py, servo_controller.py
- [ ] T090 [US3] Test emergency stop during single servo movement: start servo 0 moving 200→500 at speed=0.1, immediately click STOP, verify servo stops within 100ms
- [ ] T091 [US3] Test emergency stop visibility: scroll web page, verify STOP button remains visible (floating, not scrolling away)
- [ ] T092 [US3] Test servo state after emergency stop: verify servos go to floating state (no holding torque, can manually rotate)
- [ ] T093 [US3] Test resume after emergency stop: click Resume, verify servos move back to neutral positions
- [ ] T094 [US3] Measure emergency stop latency: use timer in browser console, measure click to servo stop, verify <100ms (SC-004)
- [ ] T095 [US3] Test emergency stop from REPL: while servo moving, run await servo_controller.emergency_stop_all(), verify immediate stop

**Checkpoint**: User Story 3 complete - Emergency stop functional, <100ms response time, resume working, safety mechanism validated

---

## Phase 6: User Story 4 - Speed-Controlled Smooth Servo Movement (Priority: P2)

**Goal**: Control servo movement speed during both individual servo tests and coordinated movement sequences

**Independent Test**: Set different speed values (0.1 to 1.0), observe servo transitions take proportionally longer at slower speeds

### Speed Control Implementation

- [ ] T096 [US4] Add global speed slider to HTML_INTERFACE in web_server.py: <input type="range" min="0.1" max="1.0" step="0.1" value="1.0" id="globalSpeed">
- [ ] T097 [US4] Add JavaScript updateGlobalSpeed() function: reads slider value, sends POST /control with {"type":"speed", "speed":VALUE}
- [ ] T098 [US4] Add speed display next to slider: <span id="speedDisplay">1.0</span> that updates as slider moves
- [ ] T099 [US4] Add "speed" command type to handle_control() in web_server.py
- [ ] T100 [US4] Implement "speed" handling: validate speed 0.1-1.0, set servo_controller.global_speed = speed, return success response
- [ ] T101 [US4] Update move_servo_smooth() to use self.global_speed if no speed parameter provided
- [ ] T102 [US4] Test speed control UI: move global speed slider from 0.1 to 1.0, verify display updates, verify POST request sent
- [ ] T103 [US4] Test speed=0.1 (slowest): move servo 0 from 300 to 400 (100 units), measure duration ~18 seconds
- [ ] T104 [US4] Test speed=1.0 (fastest): move servo 0 from 300 to 400 (100 units), measure duration ~2 seconds
- [ ] T105 [US4] Test speed=0.5 (medium): move servo 0 from 300 to 400, verify duration ~4 seconds (between slow and fast)
- [ ] T106 [US4] Test per-command speed override: send {"type":"single", "channel":0, "target":350, "speed":0.3}, verify 0.3 used (not global speed)

**Checkpoint**: User Story 4 complete - Speed control working, visible speed differences (0.1=slow, 1.0=fast), per-command override functional

---

## Phase 7: User Story 5 - Preset Movement Sequences (Priority: P2)

**Goal**: Execute pre-programmed movement sequences (walking, waving, etc.) adapted from original tars-community-movement-original code

**Independent Test**: Select preset movement (e.g., "Step Forward") from web interface, observe multi-step servo choreography execute smoothly

### Movement Presets Module

- [ ] T107 [P] [US5] Create firmware/esp32_test/movement_presets.py with PRESETS dictionary
- [ ] T108 [US5] Define preset "reset_positions" in PRESETS: 5 steps to move all servos to neutral positions
- [ ] T109 [US5] Define preset "step_forward" in PRESETS: 5 steps from tars-community-movement-original app-servotester.py stepForward()
- [ ] T110 [US5] Define preset "step_backward" in PRESETS: 5 steps from stepBackward()
- [ ] T111 [US5] Define preset "turn_right" in PRESETS: 7 steps from turnRight()
- [ ] T112 [US5] Define preset "turn_left" in PRESETS: 7 steps from turnLeft() (mirror of turn_right)
- [ ] T113 [US5] Define preset "right_hi" (greet) in PRESETS: wave sequence from rightHi()
- [ ] T114 [US5] Define preset "laugh" in PRESETS: bouncing motion from laugh()
- [ ] T115 [US5] Define preset "swing_legs" in PRESETS: side-to-side swinging from swingLegs()
- [ ] T116 [US5] Define preset "balance" in PRESETS: balancing motion from balance()
- [ ] T117 [US5] Define preset "mic_drop" in PRESETS: dramatic arm drop from micDrop()
- [ ] T118 [US5] Define preset "monster" (defensive posture) in PRESETS: arms up from monster()
- [ ] T119 [US5] Define preset "pose" in PRESETS: strike a pose from pose()
- [ ] T120 [US5] Define preset "bow" in PRESETS: bow forward from bow()

### Preset Execution Implementation

- [ ] T121 [US5] Implement async ServoController.execute_preset(preset_name) in servo_controller.py
- [ ] T122 [US5] Check if self.active_sequence is not None, raise RuntimeError "Sequence already running"
- [ ] T123 [US5] Get preset from PRESETS dict, raise ValueError if preset_name not found
- [ ] T124 [US5] Set self.active_sequence = preset_name
- [ ] T125 [US5] Loop through preset['steps']: for each step, call move_multiple(step['targets'], step['speed']), await asyncio.sleep(step['delay_after'])
- [ ] T126 [US5] After all steps complete, call self.disable_all_servos() to remove holding torque
- [ ] T127 [US5] Set self.active_sequence = None in finally block
- [ ] T128 [US5] Add emergency_stop check in loop: if self.emergency_stop, raise CancelledError

### Multiple Servo Movement

- [ ] T129 [US5] Implement async ServoController.move_multiple(targets, speed) in servo_controller.py
- [ ] T130 [US5] Create list of async tasks: for each (channel, target) in targets.items(), append create_task(move_servo_smooth(channel, target, speed))
- [ ] T131 [US5] Use asyncio.gather(*tasks, return_exceptions=True) to run all tasks in parallel
- [ ] T132 [US5] Return when all movements complete

### Web Interface Preset Buttons

- [ ] T133 [US5] Add preset buttons section to HTML_INTERFACE: <div id="presets">
- [ ] T134 [US5] Add 13 preset buttons: one for each preset movement with display names from PRESETS
- [ ] T135 [US5] Style preset buttons: grid layout 3 columns, buttons 100px wide, clear labels
- [ ] T136 [US5] Add JavaScript executePreset(presetName) function: sends POST /control with {"type":"preset", "preset":NAME}
- [ ] T137 [US5] Add onclick handlers to preset buttons: onclick="executePreset('step_forward')" etc.
- [ ] T138 [US5] Add status indicator: show "Executing: [preset]" while sequence running, clear when complete

### Control Endpoint Preset Handling

- [ ] T139 [US5] Add "preset" command type to handle_control() in web_server.py
- [ ] T140 [US5] Parse preset field from JSON body, validate preset exists in PRESETS
- [ ] T141 [US5] Call await servo_controller.execute_preset(preset_name)
- [ ] T142 [US5] Return success response: {"success": true, "message": "Preset 'NAME' started"}
- [ ] T143 [US5] Handle errors: unknown preset (400), sequence already running (409), emergency stop (503)

### Testing

- [ ] T144 [US5] Upload all files: movement_presets.py, updated servo_controller.py, updated web_server.py
- [ ] T145 [US5] Test reset_positions: click button, verify all servos move to neutral smoothly, servos disable after
- [ ] T146 [US5] Test step_forward: click button, verify walking motion (lower → rotate → lift → return), duration ~2-3 seconds
- [ ] T147 [US5] Test step_backward: verify reverse walking motion
- [ ] T148 [US5] Test turn_right: verify 90° turning motion with leg rotation
- [ ] T149 [US5] Test right_hi (greet): verify right arm raises and waves 3 times
- [ ] T150 [US5] Test laugh: verify rapid bouncing motion (5 cycles)
- [ ] T151 [US5] Test all 13 presets: execute each preset, verify choreography matches original code, no mechanical binding
- [ ] T152 [US5] Test sequence blocking: start step_forward, immediately try turn_right, verify error "Sequence already running"
- [ ] T153 [US5] Test emergency stop during preset: start mic_drop (long sequence), press emergency stop, verify immediate cancellation
- [ ] T154 [US5] Test preset completion: after preset finishes, verify servos are disabled (no holding torque), verify can start new preset

**Checkpoint**: User Story 5 complete - All 13 presets working, smooth coordinated movements, sequence blocking functional, emergency stop works during presets

---

## Phase 8: User Story 6 - Coordinated Multi-Servo Async Control (Priority: P3)

**Goal**: Move multiple servos simultaneously using asyncio for true parallelism, replacing multiprocessing from original code

**Independent Test**: Command multiple servos to move to different positions at different speeds, confirm all movements complete in parallel

### Already Implemented in Phase 7

Note: move_multiple() was already implemented in Phase 7 (T129-T132) for preset support. This phase validates parallel execution behavior.

### Validation & Testing

- [ ] T155 [US6] Test parallel movement: send POST /control with {"type":"multiple", "targets":{"0":350, "1":400, "2":200}, "speed":0.6}
- [ ] T156 [US6] Verify all 3 servos start moving simultaneously (not sequentially) - observe robot with all servos moving at once
- [ ] T157 [US6] Test servos with different travel distances: move servo 0 (50 units, finishes in 1 second) and servo 1 (200 units, finishes in 4 seconds), verify servo 0 stops at target while servo 1 continues
- [ ] T158 [US6] Test web server responsiveness during movement: while servos moving, send GET /status request, verify response within 500ms (SC-008)
- [ ] T159 [US6] Test 6 servos simultaneously: move channels 0-5 in parallel at speed=0.5, verify web server remains responsive (SC-005)
- [ ] T160 [US6] Test lock behavior: send move command for servo 0 to target A, immediately send second command for servo 0 to target B, verify second command waits for first to complete (or times out with error)
- [ ] T161 [US6] Measure async overhead: compare 6 servos moving in parallel (should take ~2 seconds for 100 units) vs sequential (would take ~12 seconds if blocking), verify parallel execution
- [ ] T162 [US6] Test CancelledError propagation: start 6 servo movements, trigger emergency stop, verify all 6 tasks cancel gracefully within 100ms

**Checkpoint**: User Story 6 complete - Parallel servo control validated, asyncio provides true parallelism, web server non-blocking during movements

---

## Phase 9: Status Monitoring & System Information (Cross-Cutting)

**Goal**: Provide comprehensive system status via web interface and /status endpoint

### Status Endpoint Implementation

- [ ] T163 [P] Add "/status" route to handle_client() in web_server.py
- [ ] T164 Implement async handle_status(servo_controller) in web_server.py
- [ ] T165 Gather WiFi status: import network, get wlan.ifconfig(), wlan.status('rssi')
- [ ] T166 Gather hardware status: PCA9685 detected, I2C address, PWM frequency
- [ ] T167 Gather servo states: loop through 9 servos, get channel, label, position, state (idle/moving/disabled), min/max
- [ ] T168 Gather memory status: import gc, call gc.mem_free() and gc.mem_total()
- [ ] T169 Calculate uptime: import time, track boot_time, calculate uptime = time.time() - boot_time
- [ ] T170 Build SystemStatus dict following data-model.md structure
- [ ] T171 Return JSON response with status data: {"success": true, "data": {...}}

### Status Display in Web Interface

- [ ] T172 Add status panel to HTML_INTERFACE: <div id="status">
- [ ] T173 Add status fields: WiFi (connected, IP, signal), Hardware (PCA9685 detected, frequency), Memory (free/total), Uptime
- [ ] T174 Add "Refresh Status" button that calls JavaScript getStatus()
- [ ] T175 Implement JavaScript getStatus() function: fetch GET /status, update status panel with response data
- [ ] T176 Add auto-refresh: setInterval(getStatus, 5000) to refresh status every 5 seconds
- [ ] T177 Add servo position indicators: display current position for each servo in status panel
- [ ] T178 Add emergency stop indicator: show "Emergency Stop: Active/Inactive" in status panel

### Testing

- [ ] T179 Test /status endpoint: curl http://<ESP32-IP>/status, verify JSON response with all fields populated
- [ ] T180 Test status display in web interface: click Refresh Status, verify all fields update correctly
- [ ] T181 Test status during movement: start servo movement, refresh status, verify servo state shows "moving" and position updates
- [ ] T182 Test memory monitoring: run system for 30 minutes, periodically check status, verify memory doesn't continuously decrease (SC-009)
- [ ] T183 Test signal strength display: move ESP32 closer/farther from router, refresh status, verify RSSI changes
- [ ] T184 Test uptime counter: check status multiple times over 10 minutes, verify uptime increases correctly

**Checkpoint**: Status monitoring complete - /status endpoint functional, web interface displays comprehensive system state

---

## Phase 10: Error Handling & Validation (Cross-Cutting)

**Goal**: Robust error handling for all edge cases and validation failures

### Input Validation

- [ ] T185 [P] Implement validate_channel(channel) in servo_config.py: check 0-8 range, raise ValueError if invalid
- [ ] T186 [P] Implement validate_pulse_width(channel, pulse) in servo_config.py: check against SERVO_CALIBRATION min/max, raise ValueError if out of range
- [ ] T187 [P] Implement validate_speed(speed) in servo_config.py: check 0.1-1.0 range, raise ValueError if invalid
- [ ] T188 [P] Implement validate_targets(targets) in servo_config.py: loop through targets dict, validate each channel and pulse
- [ ] T189 Add input validation to handle_control() in web_server.py: call validate functions before executing commands
- [ ] T190 Return 400 Bad Request for validation errors with clear error messages

### Error Response Formatting

- [ ] T191 Create error_response(message, error_detail, status_code) helper function in web_server.py
- [ ] T192 Format error responses per contracts/http-api.md: {"success": false, "message": "...", "error": "...", "server_timestamp": ...}
- [ ] T193 Add HTTP status codes: 400 (Bad Request), 404 (Not Found), 409 (Conflict), 503 (Service Unavailable)
- [ ] T194 Map Python exceptions to HTTP status codes: ValueError→400, RuntimeError→409, OSError→503

### Memory Safety

- [ ] T195 Implement check_memory() in servo_controller.py: call gc.mem_free(), raise RuntimeError if <150KB
- [ ] T196 Add memory check before executing presets in execute_preset()
- [ ] T197 Add memory check before multiple servo movements in move_multiple()
- [ ] T198 Call gc.collect() after each preset sequence completes
- [ ] T199 Call gc.collect() after each HTTP request in handle_client()

### I2C Error Handling

- [ ] T200 Add I2C error handling to PCA9685.set_pwm(): catch OSError, retry 3 times with 100ms delay
- [ ] T201 Add I2C error handling to PCA9685.__init__(): catch OSError, provide clear error "PCA9685 not detected at address 0x40"
- [ ] T202 Add I2C bus recovery: if 3 retries fail, attempt to reinitialize I2C bus once

### Testing

- [ ] T203 Test invalid channel: send {"type":"single", "channel":10, "target":300}, verify 400 error "Invalid channel 10. Must be 0-8."
- [ ] T204 Test pulse width out of range: send {"type":"single", "channel":0, "target":700}, verify 400 error "Pulse 700 out of range"
- [ ] T205 Test invalid speed: send {"type":"speed", "speed":2.0}, verify 400 error "Speed out of range [0.1, 1.0]"
- [ ] T206 Test unknown preset: send {"type":"preset", "preset":"dance"}, verify 400 error "Unknown preset"
- [ ] T207 Test sequence conflict: start preset, immediately start another preset, verify 409 error "Sequence already running"
- [ ] T208 Test emergency stop blocking: activate emergency stop, try to move servo, verify 503 error "System in emergency stop mode"
- [ ] T209 Test low memory: artificially reduce memory (create large arrays), try preset, verify 503 error "Insufficient memory"
- [ ] T210 Test I2C failure: disconnect PCA9685 during operation, try servo move, verify 503 error and 3 retry attempts logged
- [ ] T211 Test malformed JSON: send POST /control with invalid JSON, verify 400 error "Malformed JSON"
- [ ] T212 Test unknown route: send GET /unknown, verify 404 error "Not found"

**Checkpoint**: Error handling complete - All edge cases handled gracefully, clear error messages, robust validation

---

## Phase 11: Documentation & Deployment (Polish)

**Goal**: Complete documentation and deployment automation for production use

### Shell Scripts Enhancement

- [ ] T213 [P] Verify upload.sh uses mpremote exclusively and uploads all required .py files
- [ ] T214 [P] Add firmware/esp32_test/test_servos.sh script: automated test sequence (move each servo to min/neutral/max)
- [ ] T215 [P] Add firmware/esp32_test/status.sh script: fetch and display /status endpoint in formatted output
- [ ] T216 [P] Update diagnose.sh to check PCA9685 detection, WiFi connection, memory status
- [ ] T217 Update list_files.sh to also display file sizes and total flash usage
- [ ] T218 Update start_server.sh to display QR code for web interface URL (if qrencode installed)

### Documentation Updates

- [ ] T219 Verify quickstart.md step-by-step procedures match actual implementation
- [ ] T220 Add firmware/esp32_test/README.md with quick reference: upload steps, common commands, troubleshooting
- [ ] T221 Update contracts/http-api.md with actual latency measurements and performance data
- [ ] T222 Add firmware/esp32_test/CALIBRATION.md: document how to adjust SERVO_CALIBRATION values for specific hardware
- [ ] T223 Create firmware/esp32_test/TROUBLESHOOTING.md: common issues (I2C errors, WiFi issues, servo binding) with solutions

### Performance Validation

- [ ] T224 Measure boot time: reset ESP32, time from reset to "System ready", verify <10 seconds (SC-001)
- [ ] T225 Measure web interface load time: clear browser cache, load interface, verify <2 seconds (SC-002)
- [ ] T226 Measure command latency: send servo command, measure time to servo starts moving, verify <200ms (SC-003)
- [ ] T227 Measure emergency stop latency: start movement, press stop, time to servo stops, verify <100ms (SC-004)
- [ ] T228 Test 6 parallel servos: verify all move simultaneously without blocking web server (SC-005)
- [ ] T229 Test speed control range: verify slowest speed takes 5x+ longer than fastest (SC-006)
- [ ] T230 Test all 13 presets: verify all complete without errors (SC-007)
- [ ] T231 Test web server responsiveness: verify responds within 500ms during presets (SC-008)
- [ ] T232 Test 30-minute stability: run continuous presets for 30 minutes, verify no memory exhaustion or crashes (SC-009)
- [ ] T233 Measure upload workflow: time upload.sh execution, verify changes take effect after reboot (SC-010)
- [ ] T234 Test PCA9685 reliability: boot 20 times, measure success rate, verify >95% (SC-011)

### Final Integration Testing

- [ ] T235 Run complete quickstart.md procedure from Step 1 (flash firmware) to Step 9 (performance validation)
- [ ] T236 Test all acceptance scenarios from spec.md User Story 1 (hardware initialization)
- [ ] T237 Test all acceptance scenarios from spec.md User Story 2 (web-based servo testing)
- [ ] T238 Test all acceptance scenarios from spec.md User Story 3 (emergency stop)
- [ ] T239 Test all acceptance scenarios from spec.md User Story 4 (speed control)
- [ ] T240 Test all acceptance scenarios from spec.md User Story 5 (preset sequences)
- [ ] T241 Test all acceptance scenarios from spec.md User Story 6 (async parallel control)
- [ ] T242 Test all edge cases from spec.md: I2C unresponsive, pulse width exceeding limits, WiFi drop during movement, multiple simultaneous web clients, out of memory, servo physical limit, upload during operation, emergency stop with queued tasks
- [ ] T243 Verify all success criteria (SC-001 through SC-012) pass

**Checkpoint**: Feature complete - All user stories implemented, all tests passing, documentation complete, ready for production use

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-8)**: All depend on Foundational phase completion
  - US1 (Phase 3): Hardware initialization - MUST complete first (other stories depend on working hardware)
  - US2 (Phase 4): Web interface - depends on US1 (needs ServoController)
  - US3 (Phase 5): Emergency stop - depends on US2 (web interface routes)
  - US4 (Phase 6): Speed control - depends on US2 (web interface), can run in parallel with US3
  - US5 (Phase 7): Preset sequences - depends on US1, US2, US3 (needs servo control, web interface, safety)
  - US6 (Phase 8): Parallel control validation - depends on US5 (move_multiple already implemented)
- **Cross-Cutting (Phase 9-11)**: Depends on all desired user stories being complete

### Recommended Execution Order

**MVP (Minimum Viable Product) - Get basic functionality working:**
1. Phase 1: Setup (T001-T005) → Hardware verified
2. Phase 2: Foundational (T006-T025) → Core drivers ready
3. Phase 3: US1 (T026-T037) → Hardware initialization working
4. Phase 4: US2 (T038-T070) → Web interface functional
5. Phase 5: US3 (T071-T095) → Safety mechanism in place

**Stop here for initial demo** - You now have: bootable system, web interface, individual servo control, emergency stop

**Extended Features - Add advanced functionality:**
6. Phase 6: US4 (T096-T106) → Speed control
7. Phase 7: US5 (T107-T154) → Preset movements (longest phase - 48 tasks)
8. Phase 8: US6 (T155-T162) → Validation of parallel execution

**Polish - Production readiness:**
9. Phase 9: Status monitoring (T163-T184)
10. Phase 10: Error handling (T185-T212)
11. Phase 11: Documentation & deployment (T213-T243)

### Parallel Opportunities

**Within Phase 2 (Foundational):**
- T006-T011 (PCA9685 driver) can run in parallel with T020-T025 (servo config)
- T012-T014 (boot.py) can run in parallel with all other foundational tasks

**Within Phase 3 (US1):**
- T026-T029 (ServoController class) in parallel with T030-T032 (main.py startup)

**Within Phase 4 (US2):**
- T038-T042 (web server) in parallel with T043-T050 (HTML interface)
- T051-T056 (control endpoint) in parallel with T057-T062 (servo movement)

**Within Phase 5 (US3):**
- T071-T075 (emergency stop logic) in parallel with T076-T080 (web UI button)
- T085-T088 (resume functionality) can start early

**Within Phase 7 (US5):**
- All preset definitions T108-T120 (13 presets) can run in parallel
- T133-T137 (web interface buttons) in parallel with T139-T143 (endpoint handling)

**Within Phase 10 (Error Handling):**
- All validation functions T185-T188 can run in parallel
- T213-T218 (shell scripts) can all run in parallel

### Parallel Example: Phase 7 (Preset Sequences)

```bash
# All preset definitions can be written in parallel by different developers:
Task T108: Define preset "reset_positions"
Task T109: Define preset "step_forward"
Task T110: Define preset "step_backward"
Task T111: Define preset "turn_right"
Task T112: Define preset "turn_left"
# ... all 13 presets ...

# Web interface and endpoint handling can also be parallel:
Task T133-T137: Add preset buttons to HTML (Developer A)
Task T139-T143: Add preset handling to /control endpoint (Developer B)
```

---

## Implementation Strategy

### MVP First (US1 + US2 + US3 Only)

1. Complete Phase 1: Setup (5 tasks) → ~1 hour
2. Complete Phase 2: Foundational (20 tasks) → ~4-6 hours
3. Complete Phase 3: US1 - Hardware initialization (12 tasks) → ~2-3 hours
4. Complete Phase 4: US2 - Web interface (33 tasks) → ~6-8 hours
5. Complete Phase 5: US3 - Emergency stop (25 tasks) → ~3-4 hours
6. **STOP and VALIDATE**: Test MVP with quickstart.md Steps 1-6 → ~1 hour

**Total MVP Effort**: ~17-23 hours of focused work

**MVP Delivers**: Bootable ESP32, web interface, individual servo control, speed adjustment, emergency stop safety. This is sufficient for basic servo testing and calibration.

### Incremental Delivery

1. **MVP (Phases 1-5)** → Test independently → Demo basic servo control
2. **Add US4 (Phase 6)** → 11 tasks, ~2 hours → Demo variable speed control
3. **Add US5 (Phase 7)** → 48 tasks, ~8-10 hours → Demo all 13 preset movements (biggest phase)
4. **Add US6 (Phase 8)** → 8 tasks, ~1 hour → Validate parallel execution
5. **Polish (Phases 9-11)** → 78 tasks, ~10-12 hours → Production-ready system

**Total Full Implementation**: ~40-48 hours of focused work for complete feature with all user stories

### Parallel Team Strategy

With 3 developers working simultaneously:

1. **All developers together**: Complete Setup (Phase 1) + Foundational (Phase 2) → ~5-7 hours
2. **Once Foundational complete, split work:**
   - **Developer A**: Phase 3 (US1) → Phase 4 (US2) → Phase 9 (Status)
   - **Developer B**: Phase 5 (US3) → Phase 6 (US4) → Phase 10 (Error handling)
   - **Developer C**: Phase 7 (US5 - preset definitions) → Phase 8 (US6) → Phase 11 (Documentation)
3. **Integrate and test** → Phases 9-11 polish tasks

**Total Parallel Effort**: ~15-20 hours calendar time with 3 developers

---

## Task Count Summary

| Phase | Tasks | Estimated Hours |
|-------|-------|----------------|
| Phase 1: Setup | 5 | 1 |
| Phase 2: Foundational | 20 | 4-6 |
| Phase 3: US1 - Hardware Init | 12 | 2-3 |
| Phase 4: US2 - Web Interface | 33 | 6-8 |
| Phase 5: US3 - Emergency Stop | 25 | 3-4 |
| Phase 6: US4 - Speed Control | 11 | 2 |
| Phase 7: US5 - Preset Sequences | 48 | 8-10 |
| Phase 8: US6 - Parallel Control | 8 | 1 |
| Phase 9: Status Monitoring | 22 | 3-4 |
| Phase 10: Error Handling | 28 | 4-5 |
| Phase 11: Documentation | 31 | 4-6 |
| **Total** | **243 tasks** | **40-48 hours** |

**MVP Subset (Phases 1-5)**: 95 tasks, ~17-23 hours

---

## Notes

- All tasks are designed for MicroPython on ESP32-S3 (no automated pytest/CI)
- Testing is manual via quickstart.md procedures and web interface
- [P] tasks indicate different files with no dependencies (can run in parallel)
- [Story] labels (US1-US6) map tasks to specific user stories for traceability
- Preset definitions (T108-T120) require careful porting from tars-community-movement-original code
- Servo calibration values (SERVO_CALIBRATION) may need adjustment for specific hardware
- Phase 2 (Foundational) MUST complete before any user story work begins
- Emergency stop (US3) is critical safety feature - should be tested thoroughly
- Performance validation (Phase 11) ensures all success criteria (SC-001 through SC-012) are met
- Each checkpoint provides natural stopping point to validate and demo progress

**Key Files to Create:**
- `pca9685.py` (T006-T011) - I2C PWM driver
- `servo_config.py` (T020-T025) - Calibration constants
- `servo_controller.py` (T026-T032, T057-T062, T071-T075, T121-T132) - Core servo control logic
- `wifi_manager.py` (T015-T019) - WiFi connection management
- `web_server.py` (T038-T056, T076-T084, T133-T143, T163-T171) - Async HTTP server with embedded HTML
- `movement_presets.py` (T107-T120) - All 13 preset choreographies
- `main.py` (T030-T032, T063) - Entry point that ties everything together

**Development Workflow:**
1. Write task code locally in `firmware/esp32_test/`
2. Test syntax locally if possible (MicroPython compatible Python)
3. Upload to ESP32 using `./upload.sh <filename.py>` or `mpremote fs cp <filename.py> :`
4. Reset ESP32 (Ctrl+D in REPL or press physical reset button)
5. Monitor serial console for errors using `./start_server.sh` or `mpremote connect /dev/ttyACM0`
6. Test functionality via web interface or REPL commands
7. Iterate until task complete, then move to next task

**Constitution Compliance:**
- ✅ Async-first: All servo movements use uasyncio (T057-T062, T129-T132)
- ⚠️ Config via Python file: Justified exception for MicroPython (T020-T025, wifi_config.py)
- ✅ Observability: Serial console logging, /status endpoint (T163-T184)
- ✅ Simplicity: Minimal custom implementations, no frameworks, flat structure
