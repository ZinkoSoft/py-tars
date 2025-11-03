# Feature Specification: Adopt TARS AI Movement System Updates

**Feature Branch**: `006-adopt-tars-ai`  
**Created**: October 23, 2025  
**Status**: Draft  
**Input**: User description: "Adopt TARS AI movement system updates from module_btcontroller_v2.py and module_servoctl_v2.py into ESP32 test implementation"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Improved Hardware Initialization with Error Recovery (Priority: P1)

Developers and robot operators need reliable hardware initialization that gracefully handles I2C communication errors and provides clear diagnostic feedback when the PCA9685 servo controller or individual servos fail to initialize.

**Why this priority**: Hardware reliability is fundamental - without proper initialization error handling, the entire servo control system becomes unpredictable and difficult to debug. The updated initialization system from the TARS AI movement code includes retry logic, better error categorization (errno 121 for Remote I/O errors), and thread-safe I2C access patterns.

**Independent Test**: Can be fully tested by powering on the ESP32 with various hardware states (PCA9685 disconnected, loose wiring, proper connection) and verifying that initialization provides clear error messages and attempts recovery where possible.

**Acceptance Scenarios**:

1. **Given** PCA9685 is properly connected, **When** system initializes, **Then** initialization succeeds with "PCA9685 initialized successfully" message and all 16 channels are set to zero duty cycle
2. **Given** PCA9685 has intermittent I2C connection, **When** initialization encounters errno 121 (Remote I/O error), **Then** system retries up to MAX_RETRIES times with 50ms delays between attempts
3. **Given** PCA9685 initialization fails after all retries, **When** servo functions are called, **Then** system returns False and logs warning without crashing
4. **Given** I2C lock is held by another operation, **When** servo command is issued, **Then** operation waits for lock release using thread-safe locking mechanism

---

### User Story 2 - Enhanced PWM Duty Cycle Conversion with Retry Logic (Priority: P1)

Developers need accurate PWM signal generation that converts 12-bit PCA9685 values to 16-bit MicroPython duty cycle values with automatic retry on I2C communication failures.

**Why this priority**: Incorrect PWM conversion causes servos to move to wrong positions or jitter. The duty cycle conversion formula `(pwm_value / 4095.0) * 65535` is critical for servo accuracy. Combined with retry logic for I2C errors, this ensures reliable servo control even with electrical noise or loose connections.

**Independent Test**: Can be tested by sending specific PWM values (0, 2047, 4095) and measuring actual servo positions, then simulating I2C errors to verify retry behavior.

**Acceptance Scenarios**:

1. **Given** PWM value of 2047 (mid-range), **When** converted to duty cycle, **Then** result is 32767 (16-bit mid-range)
2. **Given** I2C communication fails with errno 121, **When** setting PWM, **Then** system retries 3 times with 50ms delays
3. **Given** retry attempts exhausted, **When** I2C still fails, **Then** system logs error and returns False without crashing
4. **Given** PWM set successfully, **When** no errors occur, **Then** function returns True on first attempt

---

### User Story 3 - Blocking Movement Prevention (Priority: P2)

Robot operators need the step_forward() movement to prevent overlapping execution when called multiple times rapidly, ensuring smooth movement completion before accepting new movement commands.

**Why this priority**: Rapid button presses or command flooding can cause movement sequence corruption. The MOVING flag prevents concurrent execution of step_forward(), which is the most commonly used movement and most susceptible to overlap issues.

**Independent Test**: Can be tested by sending multiple step_forward() commands in rapid succession and verifying only one executes at a time.

**Acceptance Scenarios**:

1. **Given** MOVING flag is False, **When** step_forward() is called, **Then** MOVING flag is set to True and movement sequence begins
2. **Given** MOVING flag is True (movement in progress), **When** step_forward() is called again, **Then** function returns immediately without executing
3. **Given** movement sequence completes, **When** disable_all_servos() is called, **Then** MOVING flag is reset to False
4. **Given** multiple rapid calls to step_forward(), **When** first completes, **Then** subsequent queued calls are ignored (not buffered)

---

### User Story 4 - Thread-Safe Position Tracking (Priority: P2)

Developers need accurate tracking of current servo positions with thread-safe access to support smooth gradual movements and prevent race conditions when multiple movement functions execute concurrently.

**Why this priority**: Without position tracking, gradual servo movements cannot calculate step increments. The servo_positions dictionary combined with i2c_lock ensures thread-safe reads/writes when move_legs() and move_arm() spawn multiple threads.

**Independent Test**: Can be tested by executing concurrent move_legs() and move_arm() calls while monitoring servo_positions dictionary for corruption.

**Acceptance Scenarios**:

1. **Given** servo position is unknown, **When** move_servo_gradually_thread() is called, **Then** servo moves immediately to target without gradual steps
2. **Given** servo position is tracked, **When** move_servo_gradually_thread() calculates steps, **Then** movement is smooth with 0.02 * (1.0 - speed_factor) delay per step
3. **Given** multiple threads access servo_positions, **When** using i2c_lock, **Then** no race conditions occur and position values remain accurate
4. **Given** movement completes, **When** target position is reached, **Then** servo_positions is updated with new position

---

### User Story 5 - Improved step_forward() Movement Sequence (Priority: P3)

Robot operators need the forward walking movement to be more stable and natural-looking with refined leg positions and timing.

**Why this priority**: The movement sequence was updated with new percentage values and timing adjustments for smoother walking gait. While important for user experience, this is cosmetic compared to the core infrastructure improvements.

**Independent Test**: Can be tested by executing step_forward() and visually confirming smooth, stable forward motion without wobbling or tipping.

**Acceptance Scenarios**:

1. **Given** robot is in neutral position, **When** step_forward() executes, **Then** sequence is: 50% height → 22% height → 40% height/17% leg rotation → 85% height → 50% neutral
2. **Given** each movement step, **When** executed, **Then** delays match timing: 0.2s, 0.2s, 0.2s, 0.2s, 0.5s
3. **Given** sequence completes, **When** disable_all_servos() is called, **Then** servos enter floating state to save power

---

### Edge Cases

- What happens when I2C bus is busy with another operation during servo command? **Answer**: i2c_lock ensures thread-safe access, operation waits for lock release
- How does system handle PCA9685 becoming disconnected mid-operation? **Answer**: set_servo_pwm() returns False, retry logic attempts recovery, system logs error but continues running
- What happens if step_forward() is called while MOVING flag is stuck True due to previous error? **Answer**: MOVING flag is reset by disable_all_servos() at end of sequence; manual reset may be needed via emergency stop
- How does system handle servo_positions dictionary corruption? **Answer**: If position is None or missing, move_servo_gradually_thread() treats as unknown position and moves immediately to target
- What happens when MAX_RETRIES is exhausted but servo operation is critical? **Answer**: Function returns False, calling code must handle failure (current implementation logs warning and continues)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST implement `initialize_pca9685()` function that initializes PCA9685 with I2C address 0x40, sets frequency to 50Hz, and returns success/failure boolean
- **FR-002**: System MUST implement retry logic with MAX_RETRIES=3 attempts for I2C operations, with 50ms delay between attempts
- **FR-003**: System MUST detect and handle errno 121 (Remote I/O error) separately from other I2C errors with specific error messages
- **FR-004**: System MUST implement thread-safe I2C access using `i2c_lock` for all PCA9685 operations (adapted to asyncio.Lock for MicroPython)
- **FR-005**: System MUST implement `pwm_to_duty_cycle()` function that converts 12-bit PWM values (0-4095) to 16-bit duty cycle values (0-65535)
- **FR-006**: System MUST implement `set_servo_pwm()` function that uses `pwm_to_duty_cycle()`, applies i2c_lock, and returns success/failure boolean
- **FR-007**: System MUST initialize all 16 PCA9685 channels to 0 duty cycle during `initialize_servos()`
- **FR-008**: System MUST implement `MOVING` global flag to prevent concurrent execution of `step_forward()` function
- **FR-009**: System MUST maintain `servo_positions` dictionary with thread-safe access for tracking current servo positions
- **FR-010**: System MUST implement `move_servo_gradually_thread()` that uses `servo_positions` to calculate gradual movement steps
- **FR-011**: System MUST update `step_forward()` sequence to: move_legs(50,50,50,0.4) → wait 0.2s → move_legs(22,50,50,0.6) → wait 0.2s → move_legs(40,17,17,0.65) → wait 0.2s → move_legs(85,50,50,0.8) → wait 0.2s → move_legs(50,50,50,1) → wait 0.5s → disable_all_servos()
- **FR-012**: System MUST handle `pca is None` condition gracefully in all servo functions by returning False or logging warning

### Key Entities

- **PCA9685 Controller**: Represents the hardware servo driver with I2C communication, 16 PWM channels, 50Hz frequency, retry logic, and initialization state tracking
- **Servo Position State**: Dictionary mapping servo channels (0-15) to current PWM values, accessed thread-safely, used for gradual movement calculations
- **Movement Lock**: Global MOVING boolean flag preventing concurrent step_forward() execution, set at sequence start, cleared at sequence end
- **I2C Lock**: Async lock object ensuring exclusive access to PCA9685 I2C operations, preventing race conditions in multi-threaded movement functions
- **Error Retry State**: Retry counter (0 to MAX_RETRIES) tracking I2C operation attempts, 50ms delay between retries, errno-specific error handling

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: System successfully initializes PCA9685 with 95% success rate on first attempt under normal conditions (proper wiring, stable power)
- **SC-002**: I2C communication errors recover automatically within 3 retry attempts in 90% of cases involving transient electrical noise
- **SC-003**: Concurrent movement commands (move_legs + move_arm) execute without position tracking corruption in 100% of test cases
- **SC-004**: step_forward() movement completes smoothly without interruption or stuttering in 100% of executions
- **SC-005**: Rapid repeated step_forward() commands (10 calls within 1 second) correctly ignore overlapping requests with 0% execution of concurrent sequences
- **SC-006**: PWM to duty cycle conversion produces mathematically correct values within ±1 count for all input values 0-4095
- **SC-007**: System provides clear diagnostic error messages categorizing I2C failures (errno 121 vs other errors) in 100% of failure cases
- **SC-008**: Servo position tracking maintains accuracy across 1000 consecutive movement operations without drift or corruption

## Assumptions *(optional but recommended)*

- ESP32 MicroPython environment supports `asyncio.Lock` for thread-safe operations
- I2C bus speed is configured at 100kHz (standard mode) to balance reliability and performance
- PCA9685 external oscillator frequency is 25MHz (standard for most modules)
- Servo positions can be reliably tracked using last commanded PWM value (no external position feedback sensors)
- Maximum concurrent servo movements is 6 (legs + arms executing simultaneously)
- I2C wiring uses proper pull-up resistors (typically 4.7kΩ on SDA and SCL lines)
- Power supply to PCA9685 and servos is stable 5V-6V with sufficient current capacity
- Code will be adapted from Raspberry Pi Python environment to ESP32 MicroPython with necessary syntax adjustments (e.g., `threading.Lock` → `asyncio.Lock`, `time.sleep()` → `await asyncio.sleep()`)

## Dependencies *(optional)*

### External Dependencies
- MicroPython firmware on ESP32 with asyncio support
- PCA9685 MicroPython driver (existing pca9685.py module)
- Existing servo_config.py with SERVO_CALIBRATION data
- Existing movement_presets.py with movement sequences

### Internal Dependencies
- Changes to servo_controller.py (equivalent of module_servoctl_v2.py)
- Changes to web_server.py or command handler (equivalent of module_btcontroller_v2.py movement calls)
- WiFi connectivity (optional - only for web interface control)

## Out of Scope *(optional but recommended)*

- Bluetooth gamepad integration (exists in original module_btcontroller_v2.py but ESP32 test uses web interface)
- Secret code detection for video playback (module_secrets.py functionality)
- Message queue system (queue_message() calls - ESP32 uses print() instead)
- Config file parsing (ESP32 uses hardcoded servo_config.py instead of INI files)
- Full port of all movement preset functions (only step_forward() changes are critical)
- Position feedback sensors or encoder integration
- Adaptive retry delays based on error frequency patterns
- Power consumption monitoring during servo operations
- Dynamic speed adjustment based on battery voltage
