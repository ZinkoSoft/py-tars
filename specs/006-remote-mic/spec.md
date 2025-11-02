# Feature Specification: Remote Microphone Interface

**Feature Branch**: `006-remote-mic`  
**Created**: 2025-11-02  
**Status**: Draft  
**Input**: User description: "I have a new idea about taking the wake-activation and stt-worker as a new docker compose that i can use on another device. I have puchased and setup a radxa zero 3w that will have a usb-c microphone hooked up to it. What i want to do is have a way to git pull the code, then docker compose up the specific combo for the remote microphone interface. We need to think about how this affects the mqtt and how we connect so we need to most likely expose out the mqtt so that the mic remote zero 3w can access it to let the router know that the wake activation is unmuted, that the listener started and any other endpoints that need to be adjusted."

## Clarifications

### Session 2025-11-02

- Q: Configuration Storage Location - Where/how is MQTT broker address stored and updated? → A: Environment variables in `.env` file (operator creates `.env` with MQTT_HOST/PORT)
- Q: MQTT Broker Connection Capacity - How many concurrent remote microphones should be supported? → A: Single remote microphone (one Radxa Zero 3W device) for initial implementation
- Q: Network Disconnection During Transcription - What happens when network is lost during active transcription? → A: Current transcription is dropped; services reconnect and wait for next wake word
- Q: Deployment Verification Method - How does operator confirm successful deployment? → A: Run `docker compose ps` and verify both services show "healthy" or "running" status
- Q: Observability for Troubleshooting - What specific events must be logged? → A: MQTT connect/disconnect, audio device init success/failure, wake word detections, transcription start/complete, errors with stack traces

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Basic Remote Microphone Setup (Priority: P1)

As a system operator, I want to deploy a standalone remote microphone device (Radxa Zero 3W) that listens for wake words and captures voice input, so that I can place the microphone in a different physical location from the main TARS system while maintaining full voice interaction capabilities.

**Why this priority**: This is the core functionality of the feature. Without this, the remote microphone concept has no value. It enables physical separation of audio input from processing, which is the fundamental use case.

**Independent Test**: Can be fully tested by deploying the remote microphone compose stack on a Radxa Zero 3W, speaking the wake word, and verifying that the wake event and transcription reach the main TARS router. Delivers immediate value by enabling remote voice input.

**Acceptance Scenarios**:

1. **Given** the main TARS system is running on device A, **When** I clone the repository to the Radxa Zero 3W (device B) and run the remote microphone compose stack, **Then** the remote microphone services start successfully and connect to the main TARS MQTT broker
2. **Given** the remote microphone is running and connected, **When** I speak the wake word into the USB-C microphone, **Then** the wake-activation service detects the wake word and publishes a wake event to the MQTT broker that the main TARS router receives
3. **Given** the wake word was detected, **When** I speak a command, **Then** the stt-worker transcribes my speech and publishes the transcription to MQTT where the main TARS router receives it
4. **Given** the remote microphone is deployed, **When** network connectivity to the main system is interrupted, **Then** the remote microphone services log connection errors and automatically reconnect when network is restored

---

### User Story 2 - Simple Deployment Process (Priority: P1)

As a system operator, I want to deploy the remote microphone interface using a simple git pull and docker compose up workflow, so that I can quickly set up additional microphone endpoints without complex configuration.

**Why this priority**: This addresses the explicit user requirement for ease of deployment. If deployment is complex, the feature becomes impractical for its intended use case of adding remote microphones.

**Independent Test**: Can be tested by following a deployment guide on a fresh Radxa Zero 3W installation. Success means the operator can go from device boot to functioning remote microphone with minimal steps and configuration.

**Acceptance Scenarios**:

1. **Given** a Radxa Zero 3W with USB-C microphone connected, **When** I run git pull to get the latest code, **Then** all remote microphone configuration files and compose definitions are updated
2. **Given** the code is current, **When** I run the designated docker compose command for the remote microphone stack, **Then** only the wake-activation and stt-worker services start (not the full TARS stack)
3. **Given** I need to configure the connection, **When** I provide the main TARS system's IP address and MQTT port, **Then** the remote microphone services connect to the remote MQTT broker without requiring changes to multiple configuration files
4. **Given** the remote microphone is deployed, **When** I run `docker compose ps`, **Then** both wake-activation and stt-worker services show "healthy" or "running" status indicating successful deployment

---

### User Story 3 - Network-Accessible MQTT Broker (Priority: P1)

As a system operator, I want the main TARS MQTT broker to accept connections from remote devices on the network, so that the remote microphone can communicate with the main system over TCP/IP.

**Why this priority**: Without network access to MQTT, the remote device cannot communicate with the main system. This is a prerequisite for the entire remote microphone concept.

**Independent Test**: Can be tested by attempting to connect to the MQTT broker from the Radxa Zero 3W using an MQTT client tool (like mosquitto_pub/sub). Delivers value by enabling any MQTT client to connect remotely, not just the microphone services.

**Acceptance Scenarios**:

1. **Given** the main TARS MQTT broker is configured for network access, **When** I attempt to connect from the Radxa Zero 3W on the same network, **Then** the connection succeeds and I can publish/subscribe to topics
2. **Given** the MQTT broker is exposed on the network, **When** unauthorized devices attempt to connect, **Then** connections are accepted (anonymous authentication is sufficient for initial implementation)
3. **Given** the remote microphone is connected to MQTT, **When** the main TARS services publish messages (like TTS status updates), **Then** the remote microphone services receive those messages if subscribed
4. **Given** MQTT is network-accessible, **When** I check the broker configuration, **Then** the listening address is set to accept connections from any network interface (not just localhost)

---

### User Story 4 - Audio Device Configuration (Priority: P2)

As a system operator, I want to configure which audio device the remote microphone uses for input, so that the system uses the USB-C microphone connected to the Radxa Zero 3W rather than any built-in microphone.

**Why this priority**: While important for production use, this is secondary to getting basic connectivity working. Default audio device selection might work, but explicit configuration ensures reliability.

**Independent Test**: Can be tested by connecting multiple audio devices to the Radxa Zero 3W and verifying that the configured device is used for input. Delivers value by preventing audio input issues.

**Acceptance Scenarios**:

1. **Given** multiple audio devices are available on the Radxa Zero 3W, **When** I configure the audio device name in the environment configuration, **Then** the stt-worker uses the specified USB-C microphone for audio input
2. **Given** no explicit audio device is configured, **When** the stt-worker starts, **Then** it selects a reasonable default device (system default or first available capture device)
3. **Given** the configured audio device is not available, **When** the stt-worker starts, **Then** it logs an error with the list of available devices and fails gracefully
4. **Given** the audio device configuration is correct, **When** I test the microphone input, **Then** audio is captured from the USB-C microphone as expected

---

### User Story 5 - Service Isolation and Resource Efficiency (Priority: P2)

As a system operator, I want the remote microphone stack to run only the necessary services (wake-activation and stt-worker), so that the lightweight Radxa Zero 3W device uses minimal resources and doesn't run unnecessary components.

**Why this priority**: This is an optimization that makes the solution practical for resource-constrained devices, but the feature can work without perfect resource optimization.

**Independent Test**: Can be tested by checking running containers on the Radxa Zero 3W and measuring resource usage. Success means only wake-activation and stt-worker are running, using minimal CPU/memory.

**Acceptance Scenarios**:

1. **Given** the remote microphone compose stack is started, **When** I list running containers, **Then** only wake-activation and stt-worker containers are present (no router, LLM, TTS, UI, etc.)
2. **Given** the services are running, **When** I check resource usage, **Then** CPU and memory usage remain within acceptable limits for the Radxa Zero 3W (under 50% CPU average, under 1GB RAM)
3. **Given** the services are running, **When** there is no voice activity, **Then** CPU usage drops to idle levels (under 10%)
4. **Given** the remote microphone is processing audio, **When** measuring resource usage during wake word detection and transcription, **Then** the device remains responsive and doesn't experience resource exhaustion

---



### Edge Cases

- **Network loss during transcription**: Current transcription is dropped; services automatically reconnect and resume listening for next wake word
- How does the system handle the remote microphone starting before the main TARS system is ready?
- What happens if the MQTT broker on the main system is restarted while remote microphones are connected?
- How does the system behave if the USB-C microphone is disconnected while services are running?

- How does the system handle mismatched versions between the main TARS system and remote microphone code?
- What happens if the Radxa Zero 3W runs out of disk space for container images or logs?
- How does the system respond if network latency between devices exceeds acceptable thresholds?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a separate Docker Compose configuration that deploys only the wake-activation and stt-worker services suitable for remote deployment
- **FR-002**: Remote microphone services MUST connect to a network-accessible MQTT broker on the main TARS system rather than running a local broker
- **FR-003**: Main TARS MQTT broker MUST be configurable to accept connections from remote devices on the local network
- **FR-004**: Remote microphone deployment MUST support configuration via environment variables in a `.env` file for specifying the main system's MQTT broker address (MQTT_HOST) and port (MQTT_PORT)
- **FR-005**: Remote microphone services MUST publish wake events to the same MQTT topics that local services use, maintaining contract compatibility
- **FR-006**: Remote microphone services MUST publish speech transcriptions to the same MQTT topics that local services use, maintaining contract compatibility
- **FR-007**: System MUST allow configuration of the audio input device for the stt-worker to specify the USB-C microphone
- **FR-008**: Remote microphone services MUST publish health status to MQTT topics indicating their operational state
- **FR-009**: Remote microphone services MUST implement automatic reconnection to the MQTT broker when network connectivity is lost and restored; any in-progress transcription MUST be dropped and services MUST wait for the next wake word after reconnection
- **FR-010**: System MUST provide documentation or a deployment guide for setting up the remote microphone on a Radxa Zero 3W, including verification steps using `docker compose ps` to confirm service health
- **FR-011**: Remote microphone Docker Compose stack MUST NOT include services that are not required for audio input (router, LLM, TTS, memory, UI, movement, etc.)
- **FR-012**: System MUST share the same audio fanout socket mechanism between wake-activation and stt-worker on the remote device as used in the main system
- **FR-013**: Remote microphone services MUST subscribe to necessary control topics (wake/mic, tts/status) to coordinate with main system behavior
- **FR-014**: System MUST validate that the configured MQTT broker is reachable before starting audio processing
- **FR-015**: System MUST log the following events to facilitate troubleshooting: MQTT broker connection/disconnection events, audio device initialization success/failure, wake word detection events, transcription start/completion events, and all errors with stack traces

### Key Entities *(include if feature involves data)*

- **Remote Microphone Device**: A physical device (Radxa Zero 3W) running a subset of TARS services focused on audio input, connected via network to the main TARS system
- **MQTT Broker Connection**: Network connection configuration specifying the main TARS system's MQTT broker host, port, and optional authentication credentials
- **Audio Input Device**: USB-C microphone hardware configuration including device identifier, sample rate, and audio format settings
- **Docker Compose Profile**: Deployment configuration that defines which services run on the remote microphone vs. the main system
- **Service Health Status**: Operational state information for remote services including connection status, audio device status, and processing capability

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: System operator can deploy a functioning remote microphone from git clone to accepting voice commands in under 10 minutes on a fresh Radxa Zero 3W
- **SC-002**: Remote microphone wake word detection latency is within 200ms of local deployment wake word detection latency
- **SC-003**: Remote microphone transcription accuracy matches local deployment transcription accuracy (no degradation due to remote architecture)
- **SC-004**: Remote microphone services automatically reconnect to MQTT broker within 5 seconds of network restoration after connectivity loss
- **SC-005**: Remote microphone Docker Compose stack uses less than 1GB of RAM and less than 50% average CPU on Radxa Zero 3W during normal operation
- **SC-006**: Single remote microphone device operates reliably without message conflicts or dropped events (multi-device support is out of scope for initial implementation)
- **SC-007**: System maintains 99% uptime for remote microphone services over a 24-hour period under normal network conditions
- **SC-008**: Configuration changes to MQTT broker address can be made and applied in under 2 minutes without service downtime

## Assumptions

- Radxa Zero 3W has Docker and Docker Compose installed and configured
- Radxa Zero 3W and main TARS system are on the same local network with reliable connectivity
- USB-C microphone is compatible with ALSA and appears as a standard audio capture device
- Network latency between remote microphone and main TARS system is under 50ms (typical LAN conditions)
- MQTT message delivery is reliable on the local network (standard MQTT QoS guarantees)
- Both devices will be running the same version of the TARS codebase for contract compatibility
- The main TARS system has sufficient MQTT broker capacity to handle additional remote connections
- Anonymous MQTT authentication is acceptable for initial implementation (authentication can be added later if needed)
- The Radxa Zero 3W has sufficient storage for Docker images and container logs

## Out of Scope

- Multiple remote microphone support (single device only for initial implementation)
- Secure authentication between remote microphone and main TARS system (future enhancement)
- Automatic discovery of the main TARS system on the network (manual IP configuration required)
- Audio output capabilities on the remote microphone device (TTS playback remains on main system)
- Bidirectional audio streaming or audio routing between devices
- Remote microphone management UI or centralized device registry
- Over-the-internet remote access (local network only)
- Audio encryption in transit between devices
- Automatic synchronization of configuration updates from main system to remote devices
- Load balancing or failover for multiple MQTT brokers
