# Phase 0: Research & Technical Decisions

**Feature**: Remote E-Ink Display for TARS Communication  
**Date**: 2025-11-02

## Research Tasks Completed

### 1. E-Ink Display Hardware Integration

**Decision**: Use Waveshare 2.13" V4 e-ink display with waveshare-epd Python library

**Rationale**:
- User has already validated hardware with `e-paper-example.py`
- Waveshare provides official Python library with 2.13" V4 support (`waveshare_epd.epd2in13_V4`)
- Display specifications: 250x122 pixels, monochrome (1-bit), SPI interface
- GPIO access available on Radxa Zero 3W (40-pin header compatible with Raspberry Pi)
- Library provides low-level buffer management for efficient updates

**Alternatives Considered**:
- **Alternative 1**: Raw SPI control - Rejected: Unnecessary complexity, waveshare-epd already provides tested drivers
- **Alternative 2**: Generic e-paper library (e.g., IT8951) - Rejected: Not compatible with this specific display model
- **Alternative 3**: Frame buffer device - Rejected: waveshare-epd offers better control over partial updates and display modes

**Implementation Details**:
- Library requires PYTHONPATH configuration (as shown in example: `/data/git/e-Paper/RaspberryPi_JetsonNano/python/lib`)
- Display initialization: `epd = epd2in13_V4.EPD()` → `epd.init()` → `epd.Clear(0xFF)`
- Update pattern: Create PIL Image → `epd.display(epd.getbuffer(image))`
- Dimensions: `(epd.height, epd.width)` = (250, 122) in landscape mode
- Cleanup: `epd.sleep()` to reduce power consumption between updates

---

### 2. MQTT Message Handling Pattern

**Decision**: Use asyncio-mqtt with persistent subscriptions and message dispatch to handlers

**Rationale**:
- Consistent with existing py-tars services (stt-worker, wake-activation, router)
- Asyncio-mqtt provides async/await interface compatible with Python 3.11 asyncio
- Persistent subscriptions avoid re-subscription overhead
- Message dispatch pattern allows clean separation: MQTT client → message router → display updater

**Alternatives Considered**:
- **Alternative 1**: paho-mqtt with threading - Rejected: Violates async-first constitution principle
- **Alternative 2**: Polling MQTT broker - Rejected: Inefficient, violates event-driven architecture
- **Alternative 3**: MQTT retained messages for state sync - Rejected: Not needed, display is ephemeral

**Implementation Pattern**:
```python
async with asyncio_mqtt.Client(host, port) as client:
    async with client.messages() as messages:
        await client.subscribe([
            ("stt/final", 1),
            ("llm/response", 1),
            ("wake/event", 1)
        ])
        async for message in messages:
            await handle_message(message.topic, message.payload)
```

**Best Practices**:
- Parse payload to Pydantic models immediately (fail fast on invalid)
- Use topic pattern matching for message routing
- Wrap display updates in `asyncio.to_thread()` to avoid blocking
- Implement graceful shutdown with `asyncio.CancelledError` handling

---

### 3. Display Rendering Strategy

**Decision**: Generate full PIL images in background thread, then update e-ink display atomically

**Rationale**:
- E-ink displays require full refresh (1-2 seconds) - partial updates are complex and limited
- PIL provides robust text rendering with fonts, wrapping, and layout
- Background thread rendering prevents blocking MQTT message loop
- Atomic updates ensure display consistency (no partial/torn renders visible to user)

**Alternatives Considered**:
- **Alternative 1**: Partial display updates - Rejected: Complex, limited hardware support, not worth optimization for this use case
- **Alternative 2**: Pre-render templates - Rejected: Dynamic text content requires runtime rendering
- **Alternative 3**: Direct pixel manipulation - Rejected: PIL provides better text rendering and layout tools

**Implementation Strategy**:
1. **Image Generation** (in thread pool):
   - Create new `Image.new("1", (250, 122), 255)` (1-bit mode, white background)
   - Use `ImageDraw.Draw(image)` for shapes and text
   - Load fonts: `ImageFont.truetype(path, size)` with fallback to default
   - Calculate text bounding boxes for layout
   - Draw message bubbles (rectangles + text)
   - Draw status indicators (icons or text)

2. **Display Update** (in thread pool):
   - Convert PIL image to display buffer: `epd.getbuffer(image)`
   - Send to display: `epd.display(buffer)`
   - Wait for refresh to complete (blocking, hence thread pool)

3. **Update Throttling**:
   - Debounce rapid updates (e.g., if LLM response arrives <500ms after STT)
   - Queue updates and process in order
   - Skip intermediate updates if queue backs up (show latest only)

**Font Selection**:
- Primary: DejaVu Sans (proven in example, available on Linux)
- Sizes: 20px for headers, 14px for body text (per example)
- Paths: `/usr/share/fonts/truetype/dejavu/DejaVuSans*.ttf`
- Fallback: PIL default font if custom fonts unavailable

---

### 4. Display State Machine

**Decision**: Implement explicit state machine with transitions triggered by MQTT events

**Rationale**:
- Clear state transitions make behavior predictable and testable
- Prevents race conditions (e.g., rapid wake events during conversation)
- Timeout handling is natural with state transitions
- Easy to extend with new states (e.g., error, updating)

**State Definitions**:

| State | Trigger | Display Content | Next State |
|-------|---------|-----------------|------------|
| `STANDBY` | System startup, timeout | Sci-fi standby screen | `LISTENING` on wake event |
| `LISTENING` | Wake event detected | Listening indicator | `PROCESSING` on STT final |
| `PROCESSING` | STT final received | User message bubble + processing icon | `CONVERSATION` on LLM response |
| `CONVERSATION` | LLM response received | User + TARS message bubbles | `STANDBY` on timeout |
| `ERROR` | MQTT disconnect, display failure | Error message | `STANDBY` on recovery |

**Transition Rules**:
- New wake event during `CONVERSATION` → reset to `LISTENING` (clear previous)
- Timeout in `CONVERSATION` (30-60 sec) → `STANDBY`
- Rapid STT + LLM (< 500ms apart) → skip `PROCESSING`, go straight to `CONVERSATION`
- Display failure → `ERROR` state, log error, attempt recovery

**State Storage**:
```python
@dataclass
class DisplayState:
    mode: str  # STANDBY, LISTENING, PROCESSING, CONVERSATION, ERROR
    last_update: float  # Timestamp
    user_message: str | None = None
    tars_response: str | None = None
    conversation_id: str | None = None  # Correlation from MQTT messages
```

**Alternatives Considered**:
- **Alternative 1**: Implicit state (just track last message) - Rejected: Makes behavior harder to reason about and test
- **Alternative 2**: Database-backed state - Rejected: Overkill for ephemeral display state
- **Alternative 3**: Finite state machine library - Rejected: Simple enum-based state is sufficient

---

### 5. Text Layout & Wrapping

**Decision**: Implement custom text wrapping with character limits and ellipsis truncation

**Rationale**:
- PIL's text wrapping requires manual line splitting
- Display space is limited (250x122 pixels = ~25 chars wide at 14px font)
- Need to prioritize LLM response when both messages don't fit
- Predictable layout ensures readability

**Layout Strategy**:

**Standby Mode**:
```
┌──────────────────────────┐
│  TARS REMOTE INTERFACE   │  <- Large font, centered
│                          │
│   ◉ AWAITING SIGNAL ◉    │  <- Sci-fi aesthetic
│                          │
│     192.168.1.80         │  <- IP address (optional)
└──────────────────────────┘
```

**Listening Mode**:
```
┌──────────────────────────┐
│      ● LISTENING ●        │  <- Animated or bold
│                          │
│         ▂ ▄ ▆ █          │  <- Visualizer (optional)
└──────────────────────────┘
```

**Conversation Mode (Both Fit)**:
```
┌──────────────────────────┐
│  "Hello TARS"         ┌─┐│  <- User (right)
│                       └─┘│
│┌─┐                       │
││ │ "Hello! How can I     │  <- TARS (left)
│└─┘  help you?"           │
└──────────────────────────┘
```

**Conversation Mode (LLM Priority)**:
```
┌──────────────────────────┐
│┌─┐                       │
││ │ "The capital of       │  <- TARS only
│└─┘  France is Paris.     │
│     It is known for..."  │
└──────────────────────────┘
```

**Text Wrapping Algorithm**:
1. Calculate available width (pixels) per message bubble
2. Measure text: `draw.textbbox((0, 0), text, font=font)`
3. If text fits: draw as-is
4. If text exceeds: split by words, wrap to multiple lines
5. If lines exceed display: truncate with "..." at character limit
6. Priority rule: If total > display, show TARS response only

**Character Limits** (estimated):
- Single line: ~20-25 characters at 14px font
- Max lines per bubble: 3-4 lines
- Max characters per message: ~60-100 (depends on wrapping)
- When both messages: ~40 chars each
- LLM priority mode: ~100-150 chars

**Alternatives Considered**:
- **Alternative 1**: Auto-scroll long text - Rejected: E-ink refresh too slow for smooth scrolling
- **Alternative 2**: Multi-page pagination - Rejected: Out of scope (see spec)
- **Alternative 3**: Smaller font for long text - Rejected: Readability concerns

---

### 6. Timeout & Session Management

**Decision**: Implement timeout using asyncio.Task with automatic reset on new conversations

**Rationale**:
- asyncio provides native timeout support via `asyncio.wait_for()` and `asyncio.sleep()`
- Task-based approach allows cancellation when new conversation starts
- No polling required (event-driven)

**Implementation Pattern**:
```python
class DisplayManager:
    def __init__(self):
        self.timeout_task: asyncio.Task | None = None
        self.timeout_duration = 45.0  # seconds (from env var)
    
    async def _start_timeout(self):
        """Start or restart conversation timeout"""
        if self.timeout_task:
            self.timeout_task.cancel()
        self.timeout_task = asyncio.create_task(self._timeout_handler())
    
    async def _timeout_handler(self):
        try:
            await asyncio.sleep(self.timeout_duration)
            await self.transition_to_standby()
        except asyncio.CancelledError:
            pass  # Timeout was reset, not an error
    
    async def on_wake_event(self):
        """New conversation started, cancel old timeout"""
        if self.timeout_task:
            self.timeout_task.cancel()
        await self.transition_to_listening()
    
    async def on_llm_response(self, response: str):
        await self.show_conversation(response)
        await self._start_timeout()  # Start countdown to standby
```

**Timeout Configuration**:
- Environment variable: `DISPLAY_TIMEOUT_SEC` (default: 45)
- Reasonable range: 30-60 seconds
- Timeout applies after LLM response is displayed
- Timeout is cancelled if new wake event occurs

**Alternatives Considered**:
- **Alternative 1**: Time-based polling - Rejected: Inefficient, violates async-first principle
- **Alternative 2**: MQTT message timeout - Rejected: Timeout is display-side concern, not MQTT concern
- **Alternative 3**: No timeout (manual reset) - Rejected: Display would stay on indefinitely

---

### 7. Error Handling & Recovery

**Decision**: Graceful degradation with error state display and automatic retry

**Rationale**:
- Hardware failures (GPIO, display) should not crash service
- MQTT disconnections should be transparent to user (with notification)
- Display errors should show error state, not black screen
- Automatic recovery on transient failures

**Error Scenarios & Handling**:

| Error Type | Detection | Recovery | Display |
|------------|-----------|----------|---------|
| Display init failure | Exception in `epd.init()` | Retry 3x with backoff | ERROR state (if possible) |
| Display update failure | Exception in `epd.display()` | Skip update, log error | Keep last good state |
| MQTT disconnect | Connection lost event | Reconnect automatically | ERROR state if >5 sec |
| Invalid MQTT payload | Pydantic validation error | Log error, ignore message | No change |
| GPIO permission denied | Exception on SPI access | Exit service (systemd restart) | N/A |

**Error State Display**:
```
┌──────────────────────────┐
│      ⚠ ERROR ⚠          │
│                          │
│   Connection Lost        │  <- Error message
│   Retrying...            │
└──────────────────────────┘
```

**Recovery Strategy**:
```python
async def safe_display_update(self, image: Image.Image):
    """Update display with error handling"""
    try:
        await asyncio.to_thread(self._display_update_sync, image)
    except Exception as e:
        logger.error(f"Display update failed: {e}")
        self.error_count += 1
        if self.error_count > 5:
            await self.show_error_state("Display Error")
        # Don't crash, keep service running
```

**Health Monitoring**:
- Publish to `system/health/ui-eink-display` every 30 seconds
- Payload: `{"ok": true}` when healthy, `{"ok": false, "err": "description"}` on errors
- Display update failures set health to unhealthy
- MQTT disconnect sets health to unhealthy
- Recovery sets health back to healthy

**Alternatives Considered**:
- **Alternative 1**: Crash on error (restart container) - Rejected: Transient errors would cause constant restarts
- **Alternative 2**: Ignore all errors silently - Rejected: Makes debugging impossible
- **Alternative 3**: Queue failed updates for retry - Rejected: Not needed, showing latest state is sufficient

---

## Technology Stack Summary

**Core Dependencies**:
- `asyncio-mqtt` (>= 0.16.1) - MQTT client
- `Pillow` (>= 10.0.0) - Image generation and rendering
- `waveshare-epd` (from GitHub or manual install) - Display driver
- `pydantic` (>= 2.0) - Contract validation (from tars-core)

**System Dependencies**:
- Python 3.11+ (required)
- SPI drivers (`/dev/spidev*`)
- GPIO access (BCM GPIO library, built into waveshare-epd)
- Fonts: DejaVu Sans (standard Linux package)

**Development Dependencies**:
- `pytest` (>= 7.0)
- `pytest-asyncio` (>= 0.21)
- `pytest-mock` (for mocking display hardware)
- `ruff` (linter)
- `mypy` (type checker)

**Docker Base Image**:
- `python:3.11-slim-bookworm` (ARM64 compatible)
- Additional packages: `gcc`, `python3-dev`, `spidev`, `gpio` libraries

---

## Integration Points

**MQTT Topics (Subscribe)**:
- `stt/final` (QoS 1) → FinalTranscript model → Show user message
- `llm/response` (QoS 1) → LLMResponse model → Show TARS response
- `wake/event` (QoS 1) → WakeEvent model → Transition to listening

**MQTT Topics (Publish)**:
- `system/health/ui-eink-display` (QoS 1, retained) → Health status

**Configuration (Environment)**:
- `MQTT_HOST` - Main TARS system IP (e.g., "192.168.1.100")
- `MQTT_PORT` - MQTT broker port (default: 1883)
- `MQTT_URL` - Full MQTT URL (alternative to HOST+PORT)
- `LOG_LEVEL` - Logging verbosity (default: INFO)
- `DISPLAY_TIMEOUT_SEC` - Conversation timeout (default: 45)
- `PYTHONPATH` - Include waveshare-epd library path

**Hardware Requirements**:
- Radxa Zero 3W or compatible SBC with 40-pin GPIO header
- Waveshare 2.13" V4 e-ink display connected via SPI
- SPI enabled in kernel (`/dev/spidev0.0` accessible)
- GPIO permissions for non-root user (or run as root in container)

---

## Performance Expectations

**Latency Targets** (from success criteria):
- MQTT message receipt → display update start: <300ms (processing time)
- Display update start → visible refresh complete: 1-2 seconds (hardware limitation)
- Total: wake event → display shows "listening": <500ms
- Total: STT final → user message visible: <2.3 seconds (300ms + 2s refresh)

**Resource Usage**:
- Memory: <50 MB (Python + PIL + MQTT client)
- CPU: <5% average (mostly idle, spikes during rendering)
- Display refresh: ~1.5 seconds per update (hardware fixed)

**Update Frequency**:
- Typical conversation: 3-5 display updates (standby → listening → processing → conversation → standby)
- Max update rate: Limited by display refresh (~0.5 Hz)
- No need for update throttling beyond hardware limit

---

## Open Questions & Assumptions

**Assumptions Made**:
1. Waveshare library is pre-installed or available at known PYTHONPATH
2. Display is properly connected and initialized before service starts
3. Font files are present at standard Linux paths
4. MQTT broker is already running and accessible
5. Service runs as root or user has GPIO permissions
6. Display can be safely initialized/cleared on service restart

**No Further Clarifications Needed**: All technical decisions have been made with sufficient information from the specification, existing codebase patterns, and hardware documentation.
