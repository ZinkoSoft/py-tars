# Feature Specification: Remote E-Ink Display for TARS Communication

**Feature Branch**: `007-eink-display`  
**Created**: 2025-11-02  
**Status**: Draft  
**Input**: User description: "as a remote system for py-tars which handles the speech to text and wakeword activation, i would like to create a ui-eink-display app that should be setup via the ops/compose.remote-mic-yml. we should show the user that the system is listening with a graphic versus when it is not listening, when we recieve a stt final message we should display it like a text message sending it to the py-tars main robot, when we get the response back from the llm, we should show a text message like bubble to the left showing what was said, if the message is too big to fit in the screen we sould not show what the stt final say and just show the llm response. we should also have a standby mode where it shows that the system is up, waiting for requests. think scifi interstellar communication device. i have already tested the eink display on this device and you can see an example that i have in the e-paper-example.py."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - System Status Visualization (Priority: P1)

A user approaches the remote TARS device and needs to know if the system is operational and whether it's actively listening. The display should clearly communicate the system's current state without requiring any interaction.

**Why this priority**: Core functionality that provides immediate feedback about system availability and listening state. Without this, users cannot tell if the device is functional or ready to receive commands.

**Independent Test**: Can be fully tested by starting the remote system and observing the display through different states (standby, listening, processing) without requiring actual voice interaction. Delivers immediate value by showing system health and readiness.

**Acceptance Scenarios**:

1. **Given** the system is running but no wake word detected, **When** the user looks at the display, **Then** the display shows a sci-fi inspired standby mode indicating the system is operational and waiting
2. **Given** the system is in standby mode, **When** a wake word is detected, **Then** the display transitions to show an active listening indicator
3. **Given** the system is processing audio or waiting for a response, **When** the user observes the display, **Then** a clear visual indicator shows the system is working
4. **Given** the system loses MQTT connection or encounters an error, **When** the user checks the display, **Then** an error or offline state is displayed

---

### User Story 2 - Conversation Display with User Input (Priority: P2)

A user speaks to TARS through the remote device and wants to see their spoken words displayed as they're being sent to the main system, similar to sending a text message.

**Why this priority**: Provides confidence that speech was correctly captured and gives context for the upcoming response. This is essential for user trust in the system.

**Independent Test**: Can be tested by speaking to the device after wake word detection and verifying that transcribed text appears as a message bubble on the right side of the screen, even if LLM response is not yet implemented.

**Acceptance Scenarios**:

1. **Given** the system receives an STT final transcript, **When** the message is under the character limit for the display, **Then** the text appears in a right-aligned message bubble styled as outgoing communication
2. **Given** the user's transcribed message is displayed, **When** waiting for the LLM response, **Then** the display shows a processing or "transmitting" indicator
3. **Given** multiple short exchanges occur in sequence, **When** the user views the display, **Then** the most recent conversation is visible with proper message flow

---

### User Story 3 - Response Display from TARS (Priority: P2)

A user has sent a voice command and wants to see TARS's response displayed on the e-ink screen in a clear, readable format that resembles receiving a message.

**Why this priority**: Completes the conversation loop and allows users to read responses without audio output. Critical for understanding what TARS is communicating back.

**Independent Test**: Can be tested by simulating an LLM response over MQTT and verifying it appears as a left-aligned message bubble. Works independently if user message display (P2 Story 2) is implemented.

**Acceptance Scenarios**:

1. **Given** the system receives an LLM response message, **When** the response fits within screen constraints, **Then** the text appears in a left-aligned message bubble styled as incoming communication
2. **Given** an LLM response is too long to fit with the user's input, **When** displaying the conversation, **Then** only the LLM response is shown with appropriate text wrapping or truncation
3. **Given** an LLM response is displayed, **When** the conversation completes, **Then** the display shows both messages or returns to standby after a timeout
4. **Given** the LLM response contains multiple sentences, **When** the text exceeds display capacity, **Then** the most important or recent portion is prioritized for display

---

### User Story 4 - Conversation Flow Management (Priority: P3)

A user engages in multiple consecutive interactions with TARS and needs the display to intelligently manage screen real estate, showing the most relevant information at each stage.

**Why this priority**: Enhances user experience for extended conversations but not critical for basic functionality. The system remains usable even if this is simplified.

**Independent Test**: Can be tested by conducting multiple conversation rounds and observing how the display handles transitions, timeouts, and content prioritization.

**Acceptance Scenarios**:

1. **Given** a conversation exchange completes (both user input and TARS response shown), **When** a timeout period passes with no new activity, **Then** the display returns to standby mode
2. **Given** the user initiates a new conversation while a previous one is displayed, **When** the new wake word is detected, **Then** the display clears and prepares for the new exchange
3. **Given** both user input and LLM response are short enough to fit together, **When** both messages are available, **Then** they are displayed in conversation format with visual distinction between sender and receiver

---

### Edge Cases

- What happens when the e-ink display hardware fails to initialize or becomes disconnected?
- How does the system handle extremely long LLM responses that exceed multiple screens worth of text?
- What happens if STT final message and LLM response arrive out of expected order or with significant delay?
- How does the display behave during system startup while MQTT connection is being established?
- What happens when rapid-fire wake events occur before previous conversation completes?
- How does the system handle special characters, emojis, or non-ASCII text in messages?
- What happens if the display refresh rate cannot keep up with message flow?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST subscribe to MQTT topics `stt/final`, `llm/response`, and `wake/event` to receive conversation events
- **FR-002**: System MUST display a sci-fi inspired standby screen when no active conversation is in progress
- **FR-003**: System MUST display a distinct "listening" indicator when a wake event is detected (wake/event with detected=true)
- **FR-004**: System MUST display user's transcribed speech as a right-aligned message bubble when STT final transcript is received
- **FR-005**: System MUST display TARS's response as a left-aligned message bubble when LLM response is received
- **FR-006**: System MUST implement text size and wrapping logic to fit messages within the e-ink display's physical dimensions (250x122 pixels for Waveshare 2.13" V4)
- **FR-007**: System MUST prioritize displaying the LLM response over the user input when both cannot fit on screen simultaneously
- **FR-008**: System MUST handle MQTT connection states (connecting, connected, disconnected) with appropriate display indicators
- **FR-009**: System MUST be deployable as a service within the ops/compose.remote-mic.yml Docker Compose configuration
- **FR-010**: System MUST use the same MQTT connection configuration as other remote-mic services (connecting to main TARS system's broker)
- **FR-011**: System MUST gracefully handle e-ink display initialization failures and log appropriate errors
- **FR-012**: System MUST update the display efficiently to minimize e-ink refresh artifacts and extend display lifespan
- **FR-013**: System MUST implement proper text truncation or scrolling when message content exceeds available display space
- **FR-014**: System MUST clear or reset the display state when starting a new conversation (new wake event after previous conversation completes)
- **FR-015**: System MUST implement a timeout mechanism to return to standby mode after conversation inactivity (suggested: 30-60 seconds)

### Key Entities

- **Display State**: Represents the current mode of the e-ink display (Standby, Listening, Processing, Conversation, Error). Includes timestamp of last update and active message content.
- **Message Bubble**: Visual representation of a conversation message. Contains text content, alignment (left/right), timestamp, and source identifier (user/tars).
- **Conversation Session**: Represents an active interaction session. Includes correlation IDs from MQTT messages, user input text, TARS response text, and session lifecycle state.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can determine system operational status within 1 second of viewing the display in standby mode
- **SC-002**: Wake word detection state changes are reflected on the display within 500ms of the wake event being published
- **SC-003**: STT final transcripts appear on the display within 300ms of message receipt over MQTT
- **SC-004**: LLM responses are displayed within 500ms of message receipt over MQTT
- **SC-005**: Display refreshes occur without visible tearing or artifacts that make text unreadable
- **SC-006**: Users can read full LLM responses for messages up to 200 characters without manual intervention
- **SC-007**: System maintains stable MQTT connection for 24+ hour operation period without display state corruption
- **SC-008**: Display correctly prioritizes and shows LLM response when total conversation exceeds display capacity (95% of test cases)
- **SC-009**: System recovers gracefully from display hardware disconnection and reconnection without requiring service restart
- **SC-010**: Conversation timeout returns display to standby mode within 5 seconds of timeout threshold being reached

## Assumptions

- The Waveshare 2.13" V4 e-ink display is connected and accessible via the standard Waveshare Python library
- The remote device (Radxa Zero 3W) has sufficient GPIO access and permissions to control the e-ink display
- The PYTHONPATH or installation includes the Waveshare epd library (as shown in e-paper-example.py)
- Font files (DejaVu Sans) are available at standard Linux paths for text rendering
- MQTT broker on the main TARS system is accessible from the remote device over the network
- Display refresh rate limitations of e-ink technology (1-2 seconds per full refresh) are acceptable for this use case
- The device will be positioned where users can view the display while speaking (line-of-sight during interaction)
- Conversation messages are primarily English text (multi-language support is not required for MVP)

## Dependencies

- MQTT broker running on main TARS system (configured in ops/compose.remote-mic.yml)
- Waveshare epd2in13_V4 Python library installed and configured
- PIL/Pillow library for image rendering
- STT worker service publishing to `stt/final` topic
- LLM worker service publishing to `llm/response` topic
- Wake activation service publishing to `wake/event` topic
- Docker and Docker Compose for service deployment
- Existing tars-core package for MQTT contract definitions (FinalTranscript, LLMResponse, WakeEvent)

## Out of Scope

- Touch screen interaction or user input via display
- Audio output or speaker integration
- Multi-page scrolling or pagination of long messages
- Conversation history persistence across service restarts
- Display brightness or contrast adjustment controls
- Support for displays other than Waveshare 2.13" V4
- Real-time LLM streaming display (partial updates as response generates)
- Multi-language font rendering and right-to-left text support
- Display rotation or orientation changes
- Color or grayscale display modes (black and white only)
