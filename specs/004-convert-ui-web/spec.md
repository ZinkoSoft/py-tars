# Feature Specification: Convert ui-web to Vue.js TypeScript Application

**Feature Branch**: `004-convert-ui-web`  
**Created**: 2025-10-17  
**Status**: Draft  
**Input**: User description: "Currently the ui-web is plain html. i want to convert this into a vue.js typescript application instead of relying on html directly so that we can add on new ui modules easily and create re-usable components. the look for the ui web is okay for now, but we should def move this over into a more robust and battle tested web framework."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Basic Chat Interface (Priority: P1)

Users can view the TARS chat interface with existing visual design and interact with the conversation in a Vue.js-powered application.

**Why this priority**: This is the core functionality that must work before any modular features can be added. Without a functioning chat interface, the application has no value.

**Independent Test**: Can be fully tested by loading the application in a browser and verifying that the chat messages display correctly, the composer accepts input, and messages are sent to the backend via WebSocket. Delivers immediate value by preserving existing functionality in the new framework.

**Acceptance Scenarios**:

1. **Given** the user opens the web UI, **When** the page loads, **Then** the chat interface displays with existing styling (dark theme, panels, layout)
2. **Given** messages are received via WebSocket, **When** TARS or user messages arrive, **Then** they appear in the chat log as bubbles with correct styling (tars/user classes)
3. **Given** the user types a message in the composer, **When** they submit the message, **Then** it appears in the chat and is sent via WebSocket
4. **Given** WebSocket connection is established, **When** connection status changes, **Then** appropriate status indicators update (listening, processing, typing)

---

### User Story 2 - Modular Drawer Components (Priority: P2)

Developers can add new monitoring panels as reusable Vue components that slide out as drawers, replacing the existing hardcoded drawer implementation.

**Why this priority**: This enables the extensibility that is the primary goal of the migration. Once chat works (P1), modular drawers are the key improvement over plain HTML.

**Independent Test**: Can be tested by creating a new drawer component (e.g., for a new monitoring feature) and verifying it integrates without modifying core application code. Delivers value by demonstrating the component architecture works for future features.

**Acceptance Scenarios**:

1. **Given** a developer creates a new drawer component, **When** they register it with the drawer system, **Then** it appears in the toolbar and can be opened/closed independently
2. **Given** multiple drawers are defined, **When** a user opens one drawer, **Then** the previously open drawer closes automatically
3. **Given** a drawer is open, **When** the user clicks the backdrop or presses Escape, **Then** the drawer closes smoothly with animation
4. **Given** drawer components receive MQTT data via props, **When** relevant messages arrive, **Then** each drawer updates its display independently

---

### User Story 3 - Reusable UI Components (Priority: P2)

The application provides reusable Vue components for common UI patterns (buttons, panels, status indicators, code blocks) that developers can compose into new features.

**Why this priority**: Component reusability accelerates future development and maintains visual consistency. This should be built alongside drawers (P2) to demonstrate the value of the component architecture.

**Independent Test**: Can be tested by using existing components (button, panel, status indicator) to build a new feature module and verifying consistent styling and behavior. Delivers value by reducing code duplication and ensuring UI consistency.

**Acceptance Scenarios**:

1. **Given** a developer needs a button, **When** they use the Button component with props (label, variant, onClick), **Then** it renders with correct styling and behavior
2. **Given** a developer needs a panel container, **When** they use the Panel component, **Then** it applies consistent border, background, and radius styling
3. **Given** status needs to be displayed, **When** using the StatusIndicator component, **Then** it shows the correct color and label based on state (healthy/unhealthy)
4. **Given** JSON data needs display, **When** using the CodeBlock component, **Then** it formats with syntax highlighting and proper spacing

---

### User Story 4 - Audio Spectrum Visualization (Priority: P3)

Users can view the live audio spectrum visualization in a modular component that updates in real-time as FFT data arrives.

**Why this priority**: This is a specific feature migration that demonstrates how existing functionality translates to component architecture. Less critical than core chat and component framework.

**Independent Test**: Can be tested by sending FFT data via WebSocket and verifying the spectrum canvas updates correctly within its drawer. Delivers value by showing real-time data visualization works in the new framework.

**Acceptance Scenarios**:

1. **Given** FFT audio data arrives via WebSocket, **When** the spectrum drawer is open, **Then** the canvas updates to display the frequency bars
2. **Given** the spectrum is animating, **When** no new data arrives for 2 seconds, **Then** the bars fade to baseline values
3. **Given** the drawer is closed, **When** FFT data arrives, **Then** the component pauses rendering to conserve resources

---

### User Story 5 - MQTT Stream Monitor (Priority: P3)

Users can view all MQTT messages flowing through the system in a dedicated drawer with filtering, payload inspection, and clearable history.

**Why this priority**: This is a debugging tool that's valuable but not essential for core functionality. Can be implemented after the component framework is stable.

**Independent Test**: Can be tested by generating various MQTT messages and verifying they appear in the stream monitor with correct topic, timestamp, and payload formatting. Delivers value as a debugging tool.

**Acceptance Scenarios**:

1. **Given** MQTT messages arrive via WebSocket, **When** the MQTT drawer is open, **Then** each message appears with topic, timestamp, and formatted JSON payload
2. **Given** the log has reached 200 messages, **When** a new message arrives, **Then** the oldest message is removed (FIFO behavior)
3. **Given** the user clicks "Clear", **When** the action completes, **Then** the message history is emptied
4. **Given** a message payload is JSON, **When** displayed, **Then** it is syntax-highlighted and properly formatted

---

### User Story 6 - Health Status Dashboard (Priority: P3)

Users can view the health status of all TARS services (ESP32, STT, LLM, TTS, Memory, Camera) in a dedicated health drawer with last-ping timestamps and error details.

**Why this priority**: Health monitoring is important for operations but not critical for the initial migration. Existing health indicators can remain in the header while this is built out.

**Independent Test**: Can be tested by simulating health status messages from various services and verifying the health drawer displays current status, timestamps, and error details correctly. Delivers value for operational monitoring.

**Acceptance Scenarios**:

1. **Given** health status messages arrive for each service, **When** the health drawer is open, **Then** each service shows current status (healthy/unhealthy) with color indicator
2. **Given** a service reports an error, **When** the status updates, **Then** the error message is displayed alongside the service name
3. **Given** health messages arrive, **When** a service hasn't reported in over 30 seconds, **Then** it is marked as "stale" or "unknown"
4. **Given** all services are healthy, **When** the header health button is clicked, **Then** a summary indicator shows overall system health

---

### Edge Cases

- What happens when WebSocket connection is lost? The application should display a disconnection warning and attempt to reconnect automatically.
- How does the UI handle extremely rapid MQTT messages (e.g., high-frequency FFT data)? Components should throttle rendering to maintain 60fps performance.
- What happens if a drawer component fails to render? The error should be caught and logged without crashing the entire application (Vue error boundaries).
- How does the application behave on mobile/narrow viewports? Drawers should adapt to smaller screens (responsive width, touch-friendly close gestures).
- What happens when multiple users connect to the same WebSocket? Each client receives the same messages independently (no shared state conflicts).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST serve a modern single-page application that replaces the current static HTML interface
- **FR-002**: System MUST maintain the existing backend with WebSocket bridge and MQTT integration unchanged
- **FR-003**: System MUST preserve the current visual design (colors, layout, styling) in the new implementation
- **FR-004**: Users MUST be able to send and receive chat messages through the interface that communicates via WebSocket
- **FR-005**: System MUST provide a component-based architecture where new UI modules can be added without modifying core application code
- **FR-006**: System MUST support slide-out drawer panels that can be registered dynamically and opened/closed independently
- **FR-007**: System MUST provide reusable UI components for common patterns: buttons, panels, status indicators, code blocks
- **FR-008**: System MUST maintain WebSocket connectivity with automatic reconnection on connection loss
- **FR-009**: System MUST broadcast MQTT messages to UI components via a centralized state management system
- **FR-010**: System MUST provide type safety for all application code to catch errors at development time
- **FR-011**: System MUST build the application into static assets that the backend server can serve
- **FR-012**: System MUST support the existing MQTT topics and message formats without backend changes
- **FR-013**: System MUST maintain support for all current features: chat, memory query, spectrum visualization, MQTT stream, health status
- **FR-014**: System MUST implement proper error handling with error boundaries to prevent component failures from crashing the application
- **FR-015**: System MUST be responsive and functional on desktop and mobile viewports

### Key Entities

- **UI Component**: Reusable UI element with configurable properties, internal state, and lifecycle behaviors (e.g., ChatBubble, DrawerContainer, SpectrumCanvas)
- **Drawer Module**: A slide-out panel component that displays specific monitoring data (e.g., MicrophoneDrawer, MQTTStreamDrawer, HealthDrawer)
- **MQTT Message**: Event data received from WebSocket containing topic and payload, distributed to components via state store
- **WebSocket Connection**: Persistent bidirectional connection to backend server for real-time MQTT message streaming
- **Application State**: Centralized store managing WebSocket connection status, MQTT messages, drawer visibility, and component data

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can perform all current UI actions (view chat, send messages, open drawers, view spectrum, inspect MQTT) without functional degradation
- **SC-002**: Developers can add a new drawer component with less than 50 lines of code without modifying core application files
- **SC-003**: The application maintains 60fps rendering performance when receiving high-frequency MQTT messages (100+ messages/second)
- **SC-004**: The application build process completes in under 30 seconds for production builds
- **SC-005**: All application code has 100% type coverage to prevent runtime type errors
- **SC-006**: The application reconnects to WebSocket within 3 seconds of connection loss
- **SC-007**: The built application bundle size is under 500KB (gzipped) for initial load
- **SC-008**: New developers can create their first custom drawer component within 30 minutes using provided component templates and documentation

## Assumptions

- The existing FastAPI backend (`apps/ui-web/src/ui_web/__main__.py`) remains unchanged except for serving the Vue.js build artifacts
- The Vue.js application will be built using Vite as the build tool (industry standard for Vue + TypeScript)
- State management will use Pinia (official Vue state management library) for centralized state
- The application will use Vue 3 with Composition API for modern, type-safe component development
- Existing CSS variables and styling patterns will be migrated to Vue component scoped styles
- The build output will be placed in a `dist/` directory that FastAPI serves as static files
- Development will use hot-module-replacement (HMR) for rapid iteration during development
- Component library structure will follow feature-based organization (components, composables, stores, types)
- WebSocket communication protocol (JSON messages with topic/payload structure) remains unchanged
- The MQTT message schemas published by backend services remain stable during migration
