# Feature Specification: ESP32 MicroPython Servo Control System with Web Interface

**Feature Branch**: `002-esp32-micropython-servo`  
**Created**: 2025-10-15  
**Status**: Draft  
**Input**: User description: "ESP32 MicroPython Servo Control System with Web Interface"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Hardware Initialization and Connection (Priority: P1)

A developer setting up the ESP32-based TARS robot needs to initialize the PCA9685 servo controller, connect to WiFi, and verify all 9 servos are responsive before attempting complex movements.

**Why this priority**: Without proper hardware initialization and connectivity, no other features can function. This is the foundational layer that all other functionality depends upon.

**Independent Test**: Can be fully tested by uploading the firmware, connecting to WiFi (via configuration script), and accessing the web interface to verify the PCA9685 is detected and servos can be individually tested.

**Acceptance Scenarios**:

1. **Given** ESP32 is powered on and running the firmware, **When** boot.py executes, **Then** system displays CPU frequency, free memory, and confirms boot completion
2. **Given** WiFi credentials are configured via configure_wifi.sh, **When** the ESP32 starts, **Then** it connects to the WiFi network and displays its assigned IP address
3. **Given** PCA9685 is connected via I2C, **When** the system initializes, **Then** the PCA9685 class successfully communicates with the hardware and reports ready status
4. **Given** all 9 servos are connected to the PCA9685, **When** initialization runs, **Then** servos move to their default neutral positions smoothly
5. **Given** WiFi connection fails after timeout, **When** fallback mode activates, **Then** system provides clear error message indicating connection status

---

### User Story 2 - Interactive Web-Based Servo Testing (Priority: P1)

A developer needs to test individual servo movements and calibrate servo ranges through a responsive web interface accessible from any device on the local network.

**Why this priority**: Direct servo control and testing is essential for calibration, debugging hardware issues, and verifying mechanical range of motion. This is the primary interface for interacting with the robot during development.

**Independent Test**: Can be fully tested by navigating to the ESP32's IP address in a web browser, using the interface to control individual servos (0-8), adjusting pulse widths, and observing smooth servo movements.

**Acceptance Scenarios**:

1. **Given** ESP32 is connected to WiFi, **When** user navigates to the IP address in a browser, **Then** the web interface loads with controls for all 9 servos
2. **Given** web interface is open, **When** user selects servo channel (0-8) and sets a pulse width value, **Then** the selected servo moves smoothly to that position at the configured speed
3. **Given** user is adjusting servo position, **When** they use a slider or numeric input to change pulse width, **Then** the interface provides real-time visual feedback of the current value
4. **Given** multiple servos need testing, **When** user switches between servo channels, **Then** the interface remembers and displays the last known position for each servo
5. **Given** user wants to test range limits, **When** they input pulse width values outside the safe range (0-600), **Then** the system rejects the input and displays a validation message
6. **Given** user needs to quickly identify servo channels, **When** viewing the interface, **Then** each servo is labeled with its functional name (e.g., "Main Legs Lift", "Left Leg Rotation", "Right Leg Main Arm")

---

### User Story 3 - Emergency Stop/Kill Switch (Priority: P1)

During servo testing or movement sequences, user needs immediate ability to disable all servos if unexpected behavior occurs (binding, overheating, mechanical interference).

**Why this priority**: Safety is paramount when working with physical robotics. A malfunctioning servo can damage the robot, consume excessive power, or create unsafe conditions. The kill switch must be instantly accessible.

**Independent Test**: Can be tested by initiating any servo movement, then pressing the emergency stop button - all servos should immediately stop and enter floating/disabled state regardless of current operation.

**Acceptance Scenarios**:

1. **Given** any servo movement is in progress, **When** user presses the emergency stop button, **Then** all 9 servos immediately disable (PWM set to 0) within 100ms
2. **Given** emergency stop is activated, **When** servos are disabled, **Then** visual feedback on the web interface confirms stop state (button turns red, status message displayed)
3. **Given** web interface is displayed, **When** page loads, **Then** emergency stop button is prominently displayed as a floating element that remains visible during scrolling
4. **Given** servos are in disabled state after emergency stop, **When** user wants to resume operation, **Then** they can re-initialize servos through a separate "Resume" action that requires confirmation
5. **Given** emergency stop button must be quickly accessible, **When** user views the interface on mobile or desktop, **Then** the button is sized appropriately (minimum 60x60px touch target) and positioned in an easy-to-reach location

---

### User Story 4 - Speed-Controlled Smooth Servo Movement (Priority: P2)

Developer needs to control servo movement speed during both individual servo tests and coordinated movement sequences to prevent mechanical stress and ensure realistic motion.

**Why this priority**: Speed control is critical for smooth animations, preventing servo damage from rapid movements, and creating natural-looking robot behaviors. This builds upon basic servo control (P1) to enable production-quality movements.

**Independent Test**: Can be tested by setting different speed values (0.1 to 1.0) and observing servo transitions take proportionally longer at slower speeds, with consistent smooth motion regardless of speed setting.

**Acceptance Scenarios**:

1. **Given** user wants to control movement speed, **When** they adjust a speed slider in the web interface (range 0.1-1.0), **Then** subsequent servo movements execute at that speed factor
2. **Given** a servo movement is commanded at speed 0.5, **When** the servo moves from position A to position B, **Then** the movement takes approximately twice as long as it would at speed 1.0
3. **Given** speed control is set to 0.1 (slowest), **When** servo moves across its full range, **Then** movement appears smooth without visible steps or jerkiness
4. **Given** user is testing preset movements, **When** they execute a movement sequence, **Then** each movement respects its configured speed setting for that step
5. **Given** multiple servos move simultaneously at different speeds, **When** executing coordinated movements, **Then** each servo completes its movement according to its individual speed setting (asyncio allows true parallel execution)

---

### User Story 5 - Preset Movement Sequences (Priority: P2)

Developer wants to execute pre-programmed movement sequences (from the original tars-community-movement-original code) such as walking forward, turning, waving, and other animations.

**Why this priority**: Preset movements demonstrate the robot's capabilities and provide ready-to-use animations. These movements are already proven in the original Python code and need to be ported to MicroPython with asyncio for non-blocking execution.

**Independent Test**: Can be tested by selecting a preset movement (e.g., "Step Forward") from the web interface, observing the multi-step servo choreography execute smoothly, and confirming the robot returns to a stable position afterward.

**Acceptance Scenarios**:

1. **Given** web interface is loaded, **When** user views available actions, **Then** interface displays all preset movements: Reset, Move Forward, Move Backward, Turn Right, Turn Left, Greet, Laugh, Swing Legs, Balance, Mic Drop, Defensive Posture, Pose, Bow
2. **Given** user selects "Step Forward" preset, **When** the command executes, **Then** the robot performs the multi-step walking motion using the leg servos (0-2) with appropriate timing delays
3. **Given** a preset movement is executing, **When** in progress, **Then** the web interface indicates the current state and prevents starting additional movements until complete
4. **Given** preset movement completes, **When** final step executes, **Then** servos automatically disable to prevent holding torque and overheating
5. **Given** user wants to understand movement sequence, **When** viewing preset options, **Then** each preset includes a brief description of what the movement does

---

### User Story 6 - Coordinated Multi-Servo Async Control (Priority: P3)

System needs to move multiple servos simultaneously using asyncio for true parallelism, replacing the multiprocessing approach from the original Python code.

**Why this priority**: Async control provides smoother coordinated movements and better resource utilization on the ESP32. While important for advanced movements, basic functionality can work without full async implementation.

**Independent Test**: Can be tested by commanding multiple servos to move simultaneously to different positions at different speeds, and confirming all movements complete in parallel rather than sequentially.

**Acceptance Scenarios**:

1. **Given** a movement requires 3 servos to move at once, **When** the command executes, **Then** all servos begin moving simultaneously rather than waiting for each to complete
2. **Given** servos are moving in parallel, **When** one servo completes its movement before others, **Then** it stops at the target position while remaining servos continue
3. **Given** async tasks are managing servo movements, **When** emergency stop is triggered, **Then** all async tasks are cancelled gracefully within 100ms
4. **Given** system uses asyncio for coordination, **When** servos are moving, **Then** the web server remains responsive to new requests (non-blocking execution)
5. **Given** multiple movement tasks are queued, **When** processed by asyncio, **Then** system prevents conflicting commands from executing simultaneously on the same servo

---

### Edge Cases

- What happens when the I2C bus to PCA9685 becomes unresponsive during a movement sequence?
- How does the system handle servo pulse width values that would exceed mechanical limits and cause servo binding?
- What occurs if WiFi connection drops during a movement - does the robot continue executing or safely stop?
- How does the system recover if the web interface is accessed simultaneously from multiple devices issuing conflicting commands?
- What happens when the ESP32 runs out of memory during async task creation?
- How does the system handle servos that reach their physical limit before reaching the commanded pulse width?
- What occurs if upload.sh is run while the main.py web server is active - will file updates be applied safely?
- How does the emergency stop interact with async movement tasks that are queued but not yet started?

## Requirements *(mandatory)*

### Functional Requirements

#### Hardware Control Layer

- **FR-001**: System MUST provide a PCA9685 class that initializes the I2C bus (using standard MicroPython I2C), configures PWM frequency to 50Hz for servo control, and verifies communication with the hardware
- **FR-002**: System MUST support controlling exactly 9 servos mapped to PCA9685 channels 0-8 corresponding to: [0] Main Legs Lift, [1] Left Leg Rotation, [2] Right Leg Rotation, [3] Right Leg Main Arm, [4] Right Leg Forearm, [5] Right Leg Hand, [6] Left Leg Main Arm, [7] Left Leg Forearm, [8] Left Leg Hand
- **FR-003**: System MUST accept pulse width values in the range 0-600 for servo control, with validation to reject out-of-range values
- **FR-004**: System MUST track the last known position of each servo to enable smooth transitions from current to target positions
- **FR-005**: System MUST implement graceful servo movement where position changes occur incrementally with configurable delay between steps (not instantaneous jumps)

#### Async Control Layer

- **FR-006**: System MUST use asyncio (MicroPython uasyncio) for all servo movement coordination, replacing multiprocessing patterns from the original code
- **FR-007**: System MUST support simultaneous movement of multiple servos through parallel async tasks
- **FR-008**: System MUST support speed control for servo movements using a speed factor (0.1 to 1.0) that affects the delay between incremental position steps
- **FR-009**: System MUST provide an emergency stop function that cancels all active servo movement tasks and sets all servo PWM outputs to 0 (floating state)
- **FR-010**: System MUST ensure only one movement command per servo executes at any given time (prevent conflicting simultaneous commands to the same channel)

#### Web Interface

- **FR-011**: System MUST provide a web server accessible via HTTP on port 80 that serves an HTML interface for servo control
- **FR-012**: Web interface MUST display controls for all 9 servos with clearly labeled channel numbers and functional descriptions
- **FR-013**: Web interface MUST provide input mechanisms (sliders, numeric inputs, or buttons) to set target pulse width for each servo
- **FR-014**: Web interface MUST include a prominently displayed emergency stop button implemented as a floating UI element
- **FR-015**: Web interface MUST display current system status including: WiFi connection state, IP address, PCA9685 connection status, and current servo positions
- **FR-016**: Web interface MUST provide controls to trigger all preset movement sequences from the original tars-community code
- **FR-017**: Web interface MUST include a speed control slider/input that affects all subsequent servo movements
- **FR-018**: Web interface MUST remain responsive during servo movements (non-blocking async server)
- **FR-019**: Web interface MUST be accessible from any device on the same network using the ESP32's assigned IP address
- **FR-020**: Web interface MUST provide real-time feedback when commands are sent, received, and executed

#### Network & Configuration

- **FR-021**: System MUST connect to a WiFi network using credentials configured via the configure_wifi.sh script
- **FR-022**: System MUST display the assigned IP address to the serial console upon successful WiFi connection
- **FR-023**: System MUST support WiFi connection with configurable timeout and fallback behavior if connection fails
- **FR-024**: System MUST provide boot.py that initializes ESP32 system settings (CPU frequency, garbage collection) before main.py execution

#### Preset Movements

- **FR-025**: System MUST implement the following preset movement sequences adapted from the original code: reset_positions, step_forward, step_backward, turn_right, turn_left, right_hi (greet), laugh, swing_legs, balance, mic_drop, monster (defensive posture), pose, bow
- **FR-026**: Each preset movement MUST execute its servo choreography using the async movement system
- **FR-027**: Preset movements MUST automatically disable servos upon completion to prevent prolonged holding torque
- **FR-028**: System MUST prevent new preset movements from starting while another movement sequence is in progress

#### Development Workflow

- **FR-029**: System MUST work with the existing upload.sh script for uploading .py files to the ESP32
- **FR-030**: System MUST work with the existing configure_wifi.sh script for WiFi setup
- **FR-031**: The i2c_scanner.py utility MUST remain functional for I2C bus diagnosis
- **FR-032**: System MUST support MicroPython on ESP32-S3 hardware

### Key Entities

- **PCA9685Controller**: Manages I2C communication with the PCA9685 16-channel PWM driver; handles PWM frequency configuration (50Hz); provides methods to set PWM duty cycle per channel; validates channel numbers (0-15) and pulse width values (0-4095 range, constrained to 0-600 for servos)

- **ServoChannel**: Represents a single servo with attributes: channel number (0-8), current pulse width position, target pulse width, movement speed factor, functional label (e.g., "Main Legs Lift"); tracks movement state (idle, moving, disabled)

- **MovementSequence**: Defines a choreographed multi-servo animation with attributes: sequence name, list of movement steps (each containing servo targets, speed, delay), current step index, execution state (ready, running, completed, aborted)

- **WebServer**: Async HTTP server handling requests with routes: / (main interface), /control (servo commands), /emergency (stop), /status (system state), /preset/<name> (execute movement); maintains WebSocket or Server-Sent Events connection for real-time status updates

- **WiFiConnection**: Manages network connectivity with attributes: SSID, connection status, assigned IP address, connection retry count; provides methods for connection establishment and status monitoring

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: ESP32 boots and connects to WiFi network within 10 seconds of power-on, displaying IP address to serial console
- **SC-002**: Web interface loads and becomes interactive within 2 seconds when accessed from a browser on the same network
- **SC-003**: Individual servo commands execute and servo begins moving within 200ms of receiving the command through the web interface
- **SC-004**: Emergency stop disables all servos within 100ms of button press, regardless of current movement state
- **SC-005**: System supports at least 6 simultaneous servo movements executing in parallel via asyncio without blocking the web server
- **SC-006**: Servo speed control provides visibly different movement speeds across the range (0.1 slowest to 1.0 fastest), with slowest speed taking at least 5x longer than fastest for the same movement
- **SC-007**: All 13 preset movement sequences execute successfully from web interface commands and complete without servo errors or timeout
- **SC-008**: Web interface remains responsive (responds to new requests within 500ms) while preset movement sequences are executing
- **SC-009**: System operates continuously for at least 30 minutes of active servo use without memory exhaustion or requiring reboot
- **SC-010**: Developer can upload new firmware using upload.sh and have changes take effect after ESP32 reboot with zero manual file copying
- **SC-011**: PCA9685 initialization succeeds on boot with 95% reliability when hardware is properly connected (I2C device detected and PWM frequency set)
- **SC-012**: System recovers gracefully from at least 3 common error conditions (I2C communication failure, WiFi disconnect, invalid servo command) by logging error and continuing to serve web interface

### Assumptions

1. **Hardware Assumptions**:
   - ESP32-S3 has sufficient GPIO pins for I2C (SDA/SCL) and they are properly wired to PCA9685
   - PCA9685 is powered separately with adequate current for 9 servos
   - Servos are standard analog servos expecting 50Hz PWM signal
   - I2C bus operates at standard speed (100kHz) or fast mode (400kHz) supported by both ESP32 and PCA9685

2. **Network Assumptions**:
   - WiFi network is 2.4GHz (ESP32 does not support 5GHz)
   - Network uses standard WPA2 security (configure_wifi.sh handles credentials)
   - DHCP is available for IP address assignment
   - No firewall rules block HTTP traffic on port 80 within the local network

3. **MicroPython Assumptions**:
   - MicroPython firmware includes uasyncio module
   - Standard libraries available: machine, network, socket, json, time, gc
   - ESP32-S3 has minimum 4MB flash for firmware + application code
   - Available RAM is sufficient for async task management (at least 100KB free after boot)

4. **Development Assumptions**:
   - Developer has working upload.sh that uses ampy, mpremote, or similar tool
   - Serial console access is available for viewing boot messages and IP address
   - Developer has access to the local network from a device with a web browser

5. **Servo Calibration Assumptions**:
   - Pulse width range 0-600 is safe for the specific servos used (does not cause binding or damage)
   - Servo calibration values from config.ini in original code can be adapted or will be recalibrated
   - Default servo positions (neutral) are mechanically safe starting points

6. **Operational Assumptions**:
   - Power supply provides stable voltage (servos can cause voltage drops under load)
   - Servos are mechanically free to move (no binding or obstruction)
   - Room temperature operation (servos and ESP32 not in extreme thermal conditions)
