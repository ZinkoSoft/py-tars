# Phase 1: Data Model

**Feature**: Remote E-Ink Display for TARS Communication  
**Date**: 2025-11-02

## Overview

This document defines the internal data models for the ui-eink-display service. The service does not create new MQTT contracts (it consumes existing contracts from tars-core) and does not persist data (display state is ephemeral).

---

## Internal State Models

### DisplayState

Represents the current operational state of the display.

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class DisplayMode(str, Enum):
    """Display operational modes"""
    STANDBY = "standby"           # Waiting for wake word
    LISTENING = "listening"        # Wake word detected, listening for speech
    PROCESSING = "processing"      # STT received, waiting for LLM
    CONVERSATION = "conversation"  # Showing user + TARS messages
    ERROR = "error"                # Error state (display or MQTT failure)

@dataclass
class DisplayState:
    """Current display state"""
    mode: DisplayMode
    last_update: float  # Timestamp (time.time())
    user_message: Optional[str] = None
    tars_response: Optional[str] = None
    conversation_id: Optional[str] = None  # From MQTT message_id for correlation
    error_message: Optional[str] = None
```

**Validation Rules**:
- `mode` must be one of the DisplayMode enum values
- `last_update` must be set on every state change
- `user_message` and `tars_response` are only populated in PROCESSING/CONVERSATION modes
- `error_message` is only populated in ERROR mode

**State Transitions**:
```
STANDBY → LISTENING (on wake event)
LISTENING → PROCESSING (on STT final)
PROCESSING → CONVERSATION (on LLM response)
CONVERSATION → STANDBY (on timeout or new wake event)
Any → ERROR (on failure)
ERROR → STANDBY (on recovery)
```

---

### MessageBubble

Represents a formatted message for display rendering.

```python
from dataclasses import dataclass
from enum import Enum

class MessageAlignment(str, Enum):
    """Message bubble alignment"""
    LEFT = "left"    # TARS responses
    RIGHT = "right"  # User input

@dataclass
class MessageBubble:
    """Formatted message for display"""
    text: str
    alignment: MessageAlignment
    wrapped_lines: list[str]  # Pre-wrapped text lines
    bounds: tuple[int, int, int, int]  # (x1, y1, x2, y2) bounding box
    
    def character_count(self) -> int:
        """Total character count"""
        return len(self.text)
    
    def line_count(self) -> int:
        """Number of wrapped lines"""
        return len(self.wrapped_lines)
```

**Validation Rules**:
- `text` must not be empty
- `wrapped_lines` must have at least one line
- `bounds` must have valid coordinates (x2 > x1, y2 > y1)

**Usage**:
- Created by `MessageFormatter.format_message(text, alignment)`
- Used by `DisplayManager.render_conversation(bubbles)`

---

### LayoutConstraints

Display physical constraints and layout parameters.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class LayoutConstraints:
    """Display layout constraints"""
    display_width: int = 250   # pixels
    display_height: int = 122  # pixels
    
    # Font sizes
    title_font_size: int = 20
    body_font_size: int = 14
    
    # Margins and padding
    margin: int = 5            # pixels from edge
    bubble_padding: int = 3    # pixels inside bubble
    bubble_spacing: int = 2    # pixels between bubbles
    
    # Text limits
    max_chars_per_line: int = 22  # Approximate for 14px font
    max_lines_per_bubble: int = 4
    max_total_lines: int = 6      # Across all bubbles
    
    # Layout areas
    header_height: int = 25       # For status indicators
    content_height: int = 97      # display_height - header_height
    
    def max_bubble_width(self) -> int:
        """Maximum width for message bubble"""
        return self.display_width - (2 * self.margin) - 10  # 10px for bubble marker
    
    def max_bubble_height(self) -> int:
        """Maximum height for message bubble"""
        return self.content_height - (2 * self.margin)
```

---

## External Contract Models (Reference Only)

These models are imported from `tars.contracts.v1` and are NOT defined in this service.

### FinalTranscript (from tars-core)

```python
# From packages/tars-core/src/tars/contracts/v1/stt.py
from pydantic import BaseModel, ConfigDict

class FinalTranscript(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    message_id: str          # UUID
    text: str                # Transcribed text
    lang: str = "en"
    confidence: float | None = None
    utt_id: str | None = None
    ts: float               # Timestamp
    is_final: bool = True
```

**Display Usage**: Extract `text` field to show as user message bubble.

---

### LLMResponse (from tars-core)

```python
# From packages/tars-core/src/tars/contracts/v1/llm.py
from pydantic import BaseModel, ConfigDict

class LLMResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    message_id: str          # UUID
    id: str                  # Request correlation ID
    reply: str | None = None
    error: str | None = None
    provider: str | None = None
    model: str | None = None
    tokens: dict | None = None
```

**Display Usage**: Extract `reply` field (if present) to show as TARS response bubble. If `error` is present, show error state instead.

---

### WakeEvent (from tars-core)

```python
# From packages/tars-core/src/tars/contracts/v1/wake.py
from pydantic import BaseModel, ConfigDict

class WakeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    
    message_id: str
    detected: bool
    score: float | None = None
    wake_word: str | None = None
    timestamp: float
```

**Display Usage**: Check `detected` field. If `True`, transition to LISTENING mode and clear previous conversation.

---

## Configuration Model

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class DisplayConfig:
    """Service configuration from environment"""
    # MQTT connection
    mqtt_host: str
    mqtt_port: int = 1883
    mqtt_url: Optional[str] = None
    
    # Display behavior
    timeout_sec: float = 45.0
    log_level: str = "INFO"
    
    # Hardware paths (optional overrides)
    pythonpath: Optional[str] = None
    font_path: str = "/usr/share/fonts/truetype/dejavu"
    
    @classmethod
    def from_env(cls) -> "DisplayConfig":
        """Load configuration from environment variables"""
        import os
        
        return cls(
            mqtt_host=os.environ["MQTT_HOST"],
            mqtt_port=int(os.environ.get("MQTT_PORT", "1883")),
            mqtt_url=os.environ.get("MQTT_URL"),
            timeout_sec=float(os.environ.get("DISPLAY_TIMEOUT_SEC", "45.0")),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            pythonpath=os.environ.get("PYTHONPATH"),
            font_path=os.environ.get("FONT_PATH", "/usr/share/fonts/truetype/dejavu"),
        )
```

**Validation**:
- `mqtt_host` is required (raises KeyError if missing)
- Other fields have reasonable defaults
- Fail fast on startup if configuration is invalid

---

## Relationships & Data Flow

```
┌─────────────────┐
│  MQTT Messages  │
│  (External)     │
└────────┬────────┘
         │
         │ Parsed to contracts (FinalTranscript, LLMResponse, WakeEvent)
         │
         ▼
┌─────────────────┐
│  MQTT Handler   │──┐
└─────────────────┘  │
                     │ Updates
                     ▼
┌─────────────────────────┐
│  DisplayState           │  (Internal state machine)
│  - mode                 │
│  - user_message         │
│  - tars_response        │
└──────────┬──────────────┘
           │
           │ Triggers rendering
           ▼
┌─────────────────────────┐
│  MessageFormatter       │
│  Formats text into      │
│  MessageBubble objects  │
└──────────┬──────────────┘
           │
           │ Bubbles
           ▼
┌─────────────────────────┐
│  DisplayManager         │
│  Renders PIL Image      │
│  Updates e-ink display  │
└─────────────────────────┘
```

**Key Points**:
1. MQTT messages are validated against contracts at the boundary
2. DisplayState is the single source of truth for current mode
3. MessageFormatter handles text layout logic
4. DisplayManager handles hardware interaction
5. No data persistence - all state is in-memory

---

## Validation & Constraints

### Text Constraints

- **Max input per message**: ~150 characters (approximate)
- **Max display capacity**: ~6 lines × 22 chars = 132 characters total
- **Priority rule**: If user + TARS exceeds capacity, show TARS only
- **Truncation**: Use "..." for text that exceeds limits

### State Constraints

- Only one active conversation at a time (new wake event clears previous)
- Timeout resets on new wake event
- Display state survives MQTT disconnection (shows last good state + error indicator)
- Display does not persist across service restarts (returns to STANDBY)

### Hardware Constraints

- Display refresh time: 1-2 seconds (cannot be improved)
- SPI communication: Blocking (must run in thread pool)
- GPIO access: Requires permissions (root or gpio group)

---

## Testing Strategy

### Unit Tests

**DisplayState**:
- Test state transitions (valid and invalid)
- Test message assignment in appropriate modes
- Test timestamp updates

**MessageBubble**:
- Test character and line counting
- Test bounding box calculation
- Test alignment enforcement

**MessageFormatter**:
- Test text wrapping at character limits
- Test truncation with ellipsis
- Test multi-line formatting
- Test layout constraints enforcement

**DisplayConfig**:
- Test environment variable parsing
- Test default values
- Test required field validation (MQTT_HOST)

### Integration Tests

**MQTT → Display State**:
- Test wake event → LISTENING transition
- Test STT final → PROCESSING with user message
- Test LLM response → CONVERSATION with TARS response
- Test timeout → STANDBY
- Test error handling (invalid payloads)

**State → Display**:
- Test each mode renders correctly
- Test message bubble layout (mocked display)
- Test text truncation in practice
- Test priority rules (TARS only when too long)

### Contract Tests

**MQTT Payload Validation**:
- Test FinalTranscript parsing (valid and invalid)
- Test LLMResponse parsing (valid and invalid)
- Test WakeEvent parsing (valid and invalid)
- Test handling of extra fields (should fail with `extra="forbid"`)

---

## Summary

**New Models Created** (Internal):
- `DisplayState` - State machine for display modes
- `MessageBubble` - Formatted message for rendering
- `LayoutConstraints` - Display physical limits
- `DisplayConfig` - Environment configuration

**Existing Models Used** (from tars-core):
- `FinalTranscript` - User speech from STT
- `LLMResponse` - TARS response from LLM
- `WakeEvent` - Wake word detection

**No New MQTT Contracts**: Service consumes existing topics and contracts only.

**No Data Persistence**: All state is ephemeral and in-memory.
