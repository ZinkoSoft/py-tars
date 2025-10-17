# MQTT Contracts Documentation

This document provides a comprehensive reference for all MQTT topics and message contracts used in the TARS system.

## Overview

TARS uses **strongly-typed Pydantic v2 contracts** for all MQTT messages, ensuring type safety and validation at all edges. All contracts are defined in `packages/tars-core/src/tars/contracts/v1/` and are the single source of truth for message schemas.

### Contract Principles

1. **Single Source of Truth**: All message schemas defined in `tars-core`
2. **Strict Validation**: All models use `extra="forbid"` to prevent typos
3. **JSON Serialization**: Via `orjson` for performance
4. **Correlation IDs**: message_id for tracing, request_id for correlation
5. **Backward Compatible**: Message formats don't break existing services

---

## Table of Contents

- [Speech-to-Text (STT)](#speech-to-text-stt)
- [Text-to-Speech (TTS)](#text-to-speech-tts)
- [LLM (Language Model)](#llm-language-model)
- [Wake Detection](#wake-detection)
- [Movement](#movement)
- [Memory](#memory)
- [MCP (Model Context Protocol)](#mcp-model-context-protocol)
- [Health](#health)

---

## Speech-to-Text (STT)

### Topics

| Topic | Direction | Publisher | Subscriber | QoS | Retained |
|-------|-----------|-----------|------------|-----|----------|
| `stt/final` | Service→Router | stt-worker | router | 1 | No |
| `stt/partial` | Service→Router | stt-worker | router (optional) | 0 | No |

### Contracts

#### FinalTranscript

Published when STT completes transcription of an utterance.

```python
from tars.contracts.v1 import FinalTranscript

FinalTranscript(
    message_id: str,  # Auto-generated UUID
    text: str,  # Transcribed text
    lang: str = "en",  # Language code
    confidence: float | None = None,  # 0.0-1.0
    utt_id: str | None = None,  # Utterance ID for correlation
    ts: float,  # Auto-generated timestamp
    is_final: bool = True
)
```

**Example:**
```json
{
  "message_id": "abc123",
  "text": "Hey TARS, tell me a joke",
  "lang": "en",
  "confidence": 0.95,
  "utt_id": "utt-456",
  "ts": 1696281234.5,
  "is_final": true
}
```

#### PartialTranscript

Published during streaming transcription (optional).

```python
from tars.contracts.v1 import PartialTranscript

PartialTranscript(
    message_id: str,  # Auto-generated UUID
    text: str,  # Partial transcribed text
    lang: str = "en",
    confidence: float | None = None,
    utt_id: str | None = None,
    ts: float,  # Auto-generated timestamp
    is_final: bool = False
)
```

---

## Text-to-Speech (TTS)

### Topics

| Topic | Direction | Publisher | Subscriber | QoS | Retained |
|-------|-----------|-----------|------------|-----|----------|
| `tts/say` | Router→Service | router, llm-worker | tts-worker | 1 | No |
| `tts/status` | Service→Router | tts-worker | router | 1 | No |

### Contracts

#### TtsSay

Command to speak text.

```python
from tars.contracts.v1 import TtsSay

TtsSay(
    message_id: str,  # Auto-generated UUID
    text: str,  # Text to speak
    voice: str | None = None,  # Voice name
    lang: str | None = None,  # Language code
    utt_id: str | None = None,  # Utterance ID for correlation
    style: str | None = None,  # Speaking style
    stt_ts: float | None = None,  # STT timestamp for latency tracking
    wake_ack: bool | None = None,  # Wake acknowledgment
    system_announce: bool | None = None  # System announcement flag
)
```

**Example:**
```json
{
  "message_id": "msg-789",
  "text": "Sure, here's a joke for you!",
  "voice": "en_US-amy-medium",
  "lang": "en",
  "utt_id": "utt-456"
}
```

#### TtsStatus

Status updates from TTS worker.

```python
from tars.contracts.v1 import TtsStatus

TtsStatus(
    message_id: str,  # Auto-generated UUID
    event: Literal["speaking_start", "speaking_end", "paused", "resumed", "stopped"],
    text: str = "",  # Text being spoken
    timestamp: float,  # Auto-generated
    utt_id: str | None = None,
    reason: str | None = None,  # For stopped events
    wake_ack: bool | None = None,
    system_announce: bool | None = None
)
```

**Example:**
```json
{
  "message_id": "status-abc",
  "event": "speaking_start",
  "text": "Sure, here's a joke for you!",
  "timestamp": 1696281235.0,
  "utt_id": "utt-456"
}
```

---

## LLM (Language Model)

### Topics

| Topic | Direction | Publisher | Subscriber | QoS | Retained |
|-------|-----------|-----------|------------|-----|----------|
| `llm/request` | Router→Service | router | llm-worker | 1 | No |
| `llm/response` | Service→Router | llm-worker | router | 1 | No |
| `llm/stream` | Service→Router | llm-worker | router | 0 | No |
| `llm/cancel` | Router→Service | router | llm-worker | 1 | No |
| `llm/tools/registry` | Service→Service | mcp-bridge | llm-worker | 1 | Yes |
| `llm/tool/call/request` | Service→Service | llm-worker | mcp-bridge | 1 | No |
| `llm/tool/call/result` | Service→Service | mcp-bridge | llm-worker | 1 | No |

### Contracts

#### LLMRequest

Request LLM to generate a response.

```python
from tars.contracts.v1 import LLMRequest, ConversationMessage

LLMRequest(
    message_id: str,  # Auto-generated UUID
    id: str,  # Request ID for correlation
    text: str,  # User prompt
    stream: bool = True,  # Stream response
    use_rag: bool | None = None,  # Use RAG
    rag_k: int | None = None,  # Number of RAG results
    system: str | None = None,  # System prompt override
    params: dict | None = None,  # Model parameters
    conversation_history: List[ConversationMessage] | None = None
)
```

#### LLMResponse

Complete LLM response (non-streaming or final).

```python
from tars.contracts.v1 import LLMResponse

LLMResponse(
    message_id: str,  # Auto-generated UUID
    id: str,  # Matches LLMRequest.id
    reply: str | None = None,  # Generated text
    error: str | None = None,  # Error message if failed
    provider: str | None = None,  # "ollama", "openai", etc.
    model: str | None = None,  # Model name
    tokens: dict | None = None  # Token usage stats
)
```

#### LLMStreamDelta

Streaming chunk of LLM response.

```python
from tars.contracts.v1 import LLMStreamDelta

LLMStreamDelta(
    message_id: str,  # Auto-generated UUID
    id: str,  # Matches LLMRequest.id
    seq: int | None = None,  # Sequence number
    delta: str | None = None,  # Text chunk
    done: bool = False,  # True on final chunk
    provider: str | None = None,
    model: str | None = None
)
```

#### ToolCallRequest / ToolCallResult

MCP tool calls (see [MCP section](#mcp-model-context-protocol)).

---

## Wake Detection

### Topics

| Topic | Direction | Publisher | Subscriber | QoS | Retained |
|-------|-----------|-----------|------------|-----|----------|
| `wake/event` | Service→Router | wake-activation | router | 1 | No |
| `wake/mic` | Router→Service | router | wake-activation | 1 | No |

### Contracts

#### WakeEvent

Published when wake word is detected.

```python
from tars.contracts.v1 import WakeEvent

WakeEvent(
    message_id: str,  # Auto-generated UUID
    detected: bool,  # Wake word detected
    score: float | None = None,  # Confidence score
    wake_word: str | None = None,  # Which wake word
    timestamp: float  # Auto-generated
)
```

**Example:**
```json
{
  "message_id": "wake-123",
  "detected": true,
  "score": 0.92,
  "wake_word": "hey_tars",
  "timestamp": 1696281234.0
}
```

#### WakeMicCommand

Control microphone listening.

```python
from tars.contracts.v1 import WakeMicCommand

WakeMicCommand(
    message_id: str,  # Auto-generated UUID
    action: Literal["start", "stop", "pause", "resume"]
)
```

---

## Movement

Movement has **two architectures**: frame-based (movement-service) and command-based (ESP32 autonomous).

### Topics

| Topic | Direction | Publisher | Subscriber | Architecture | QoS | Retained |
|-------|-----------|-----------|------------|--------------|-----|----------|
| `movement/command` | External→Service | router, external | movement-service | Frame-based | 1 | No |
| `movement/frame` | Service→ESP32 | movement-service | ESP32 (future) | Frame-based | 1 | No |
| `movement/state` | Service→External | movement-service | router, UI | Frame-based | 0 | No |
| `movement/test` | External→ESP32 | router, external | ESP32 | Command-based | 1 | No |
| `movement/stop` | External→ESP32 | router, external | ESP32, movement-service | Both | 1 | No |
| `movement/status` | ESP32→External | ESP32 | router, UI | Command-based | 0 | No |

### Contracts

#### Frame-Based Architecture

##### MovementCommand

Request movement-service to execute a movement.

```python
from tars.contracts.v1 import MovementCommand, MovementAction

MovementCommand(
    message_id: str,  # Auto-generated UUID
    timestamp: float,  # Auto-generated
    id: str,  # Auto-generated UUID for correlation
    command: MovementAction,  # Movement type
    params: dict[str, Any] = {}  # Movement parameters
)
```

**MovementAction enum:**
- `reset`, `disable`
- `step_forward`, `step_backward`, `turn_left`, `turn_right`
- `balance`, `laugh`, `swing_legs`, `pose`, `bow`

**Example:**
```json
{
  "message_id": "msg-abc",
  "timestamp": 1696281234.5,
  "id": "cmd-123",
  "command": "step_forward",
  "params": {}
}
```

##### MovementFrame

Servo frame calculated by movement-service.

```python
from tars.contracts.v1 import MovementFrame

MovementFrame(
    message_id: str,  # Auto-generated UUID
    timestamp: float,  # Auto-generated
    id: str,  # Links to MovementCommand.id
    seq: int,  # Frame sequence number
    total: int,  # Total frames in sequence
    duration_ms: int,  # Frame duration
    hold_ms: int,  # Hold time after frame
    channels: dict[int, int],  # channel -> pulse_width_us
    disable_after: bool = False,  # Disable servos after frame
    done: bool = False  # Last frame in sequence
)
```

**Example:**
```json
{
  "message_id": "frame-abc",
  "timestamp": 1696281235.0,
  "id": "cmd-123",
  "seq": 0,
  "total": 5,
  "duration_ms": 400,
  "hold_ms": 0,
  "channels": {0: 1500, 1: 1500, 2: 1500},
  "disable_after": false,
  "done": false
}
```

##### MovementState

State update from movement-service.

```python
from tars.contracts.v1 import MovementState, MovementStateEvent

MovementState(
    message_id: str,  # Auto-generated UUID
    timestamp: float,  # Auto-generated
    id: str,  # Links to MovementCommand.id
    event: MovementStateEvent,  # State change
    seq: int | None = None,  # Frame sequence number
    detail: str | None = None  # Additional details
)
```

**MovementStateEvent enum:**
- `started`, `frame_sent`, `completed`, `failed`, `cancelled`

**Example:**
```json
{
  "message_id": "state-abc",
  "timestamp": 1696281235.1,
  "id": "cmd-123",
  "event": "frame_sent",
  "seq": 0
}
```

#### Command-Based Architecture

##### TestMovementRequest

Request ESP32 to autonomously execute a movement.

```python
from tars.contracts.v1 import TestMovementRequest, TestMovementCommand

TestMovementRequest(
    message_id: str,  # Auto-generated UUID
    timestamp: float,  # Auto-generated
    command: TestMovementCommand,  # Movement type
    speed: float = 1.0,  # 0.1-1.0 (slow to normal)
    params: dict[str, Any] = {},  # Movement parameters
    request_id: str | None = None  # Optional correlation ID
)
```

**TestMovementCommand enum:**
- Basic: `reset`, `step_forward`, `step_backward`, `turn_left`, `turn_right`
- Expressive: `wave`, `laugh`, `swing_legs`, `pezz`, `pezz_dispenser`, `now`, `balance`, `mic_drop`, `monster`, `pose`, `bow`
- Control: `disable`, `stop`
- Manual: `move_legs`, `move_arm`

**Example:**
```json
{
  "message_id": "msg-xyz",
  "timestamp": 1696281234.5,
  "command": "wave",
  "speed": 0.8,
  "request_id": "req-abc123"
}
```

##### MovementStatusUpdate

Status update from ESP32.

```python
from tars.contracts.v1 import MovementStatusUpdate, MovementStatusEvent

MovementStatusUpdate(
    message_id: str,  # Auto-generated UUID
    timestamp: float,  # Auto-generated
    event: MovementStatusEvent,  # Status change
    command: str | None = None,  # Which command triggered this
    detail: str | None = None,  # Additional details
    request_id: str | None = None  # Links to TestMovementRequest
)
```

**MovementStatusEvent enum:**
- `connected`, `disconnected`
- `command_started`, `command_completed`, `command_failed`
- `emergency_stop`, `stop_cleared`
- `queue_full`, `battery_low`

**Example:**
```json
{
  "message_id": "status-def",
  "timestamp": 1696281235.0,
  "event": "command_started",
  "command": "wave",
  "request_id": "req-abc123"
}
```

##### EmergencyStopCommand

Emergency stop all movement.

```python
from tars.contracts.v1 import EmergencyStopCommand

EmergencyStopCommand(
    message_id: str,  # Auto-generated UUID
    timestamp: float,  # Auto-generated
    reason: str | None = None  # Why stop was triggered
)
```

**Example:**
```json
{
  "message_id": "stop-urgent",
  "timestamp": 1696281240.0,
  "reason": "user_requested"
}
```

---

## Memory

### Topics

| Topic | Direction | Publisher | Subscriber | QoS | Retained |
|-------|-----------|-----------|------------|-----|----------|
| `memory/query` | Router→Service | router | memory-worker | 1 | No |
| `memory/results` | Service→Router | memory-worker | router | 1 | No |
| `character/get` | Service→Service | llm-worker | memory-worker | 1 | No |
| `character/result` | Service→Service | memory-worker | llm-worker | 1 | No |
| `system/character/current` | Service→All | memory-worker | All services | 1 | Yes |

### Contracts

#### MemoryQuery

Query vector memory for RAG.

```python
from tars.contracts.v1 import MemoryQuery

MemoryQuery(
    message_id: str,  # Auto-generated UUID
    id: str,  # Query ID for correlation
    query: str,  # Query text
    k: int = 5,  # Number of results
    character_id: str | None = None  # Filter by character
)
```

#### MemoryResults

Results from vector memory query.

```python
from tars.contracts.v1 import MemoryResults, MemoryResult

MemoryResults(
    message_id: str,  # Auto-generated UUID
    id: str,  # Matches MemoryQuery.id
    results: List[MemoryResult],  # Retrieved chunks
    k: int  # Number of results requested
)
```

#### CharacterSnapshot

Current character state (retained).

```python
from tars.contracts.v1 import CharacterSnapshot, CharacterSection

CharacterSnapshot(
    message_id: str,  # Auto-generated UUID
    character_id: str,  # Character identifier
    sections: List[CharacterSection],  # Character data sections
    timestamp: float  # Auto-generated
)
```

---

## MCP (Model Context Protocol)

### Topics

| Topic | Direction | Publisher | Subscriber | QoS | Retained |
|-------|-----------|-----------|------------|-----|----------|
| `llm/tools/registry` | Service→Service | mcp-bridge | llm-worker | 1 | Yes |
| `llm/tool/call/request` | Service→Service | llm-worker | mcp-bridge | 1 | No |
| `llm/tool/call/result` | Service→Service | mcp-bridge | llm-worker | 1 | No |

### Contracts

#### ToolsRegistry

Registry of available MCP tools (retained).

```python
from tars.contracts.v1 import ToolsRegistry, ToolSpec

ToolsRegistry(
    message_id: str,  # Auto-generated UUID
    tools: List[ToolSpec]  # Available tools
)
```

#### ToolCallRequest

Request to execute an MCP tool.

```python
from tars.contracts.v1 import ToolCallRequest

ToolCallRequest(
    message_id: str,  # Auto-generated UUID
    call_id: str,  # Call ID for correlation
    name: str,  # "mcp:server:tool_name"
    arguments: dict  # Tool arguments
)
```

#### ToolCallResult

Result from MCP tool execution.

```python
from tars.contracts.v1 import ToolCallResult

ToolCallResult(
    message_id: str,  # Auto-generated UUID
    call_id: str,  # Matches ToolCallRequest.call_id
    result: dict | None = None,  # Tool result
    error: str | None = None  # Error message if failed
)
```

---

## Health

### Topics

| Topic | Direction | Publisher | Subscriber | QoS | Retained |
|-------|-----------|-----------|------------|-----|----------|
| `system/health/router` | Service→Monitor | router | monitoring | 1 | Yes |
| `system/health/stt` | Service→Monitor | stt-worker | router, monitoring | 1 | Yes |
| `system/health/tts` | Service→Monitor | tts-worker | router, monitoring | 1 | Yes |
| `system/health/llm` | Service→Monitor | llm-worker | monitoring | 1 | Yes |
| `system/health/memory` | Service→Monitor | memory-worker | monitoring | 1 | Yes |
| `system/health/wake` | Service→Monitor | wake-activation | monitoring | 1 | Yes |
| `system/health/movement` | Service→Monitor | movement-service | monitoring | 1 | Yes |
| `system/health/movement-controller` | Service→Monitor | ESP32 | monitoring | 1 | Yes |

### Contracts

#### HealthPing

Health status update (retained).

```python
from tars.contracts.v1 import HealthPing

HealthPing(
    ok: bool,  # Service is healthy
    event: str  # "ready", "running", "error", etc.
)
```

**Example:**
```json
{
  "ok": true,
  "event": "ready"
}
```

---

## Message Flow Examples

### Example 1: Voice Command to Movement

```
1. User: "Hey TARS, wave"
2. wake-activation → wake/event: WakeEvent(detected=true)
3. stt-worker → stt/final: FinalTranscript(text="wave")
4. router → llm/request: LLMRequest(text="wave", use_rag=true)
5. llm-worker → llm/response: LLMResponse(reply="*waves*")
6. router → tts/say: TtsSay(text="Sure!")
7. router → movement/test: TestMovementRequest(command="wave")
8. ESP32 → movement/status: MovementStatusUpdate(event="command_started")
9. ESP32 → movement/status: MovementStatusUpdate(event="command_completed")
10. tts-worker → tts/status: TtsStatus(event="speaking_start")
11. tts-worker → tts/status: TtsStatus(event="speaking_end")
```

### Example 2: Emergency Stop

```
1. User: "Stop!"
2. stt-worker → stt/final: FinalTranscript(text="stop")
3. router → movement/stop: EmergencyStopCommand(reason="user_requested")
4. ESP32 → movement/status: MovementStatusUpdate(event="emergency_stop")
5. movement-service (if running) stops frame publishing
```

### Example 3: RAG-Enhanced Response

```
1. router → memory/query: MemoryQuery(query="Tell me about yourself", k=5)
2. memory-worker → memory/results: MemoryResults(results=[...])
3. router → llm/request: LLMRequest(text="Tell me about yourself", use_rag=true)
4. llm-worker uses RAG context from memory
5. llm-worker → llm/stream: LLMStreamDelta(delta="I am TARS...")
6. llm-worker → llm/response: LLMResponse(reply="I am TARS...")
```

---

## Validation Patterns

### Python (tars-core)

```python
from tars.contracts.v1 import TestMovementRequest, TestMovementCommand
from pydantic import ValidationError

# Valid
try:
    msg = TestMovementRequest(command=TestMovementCommand.WAVE, speed=0.8)
    assert msg.command == TestMovementCommand.WAVE
    assert msg.speed == 0.8
except ValidationError as e:
    print(f"Validation failed: {e}")

# Invalid - speed out of range
try:
    msg = TestMovementRequest(command=TestMovementCommand.WAVE, speed=1.5)
except ValidationError as e:
    print(f"Speed must be 0.1-1.0: {e}")

# Invalid - extra field
try:
    TestMovementRequest(command=TestMovementCommand.WAVE, extra_field="oops")
except ValidationError as e:
    print(f"Extra inputs not permitted: {e}")
```

### MicroPython (ESP32)

```python
from lib.validation import validate_test_movement, ValidationError

# Valid
data = {"command": "wave", "speed": 0.8}
try:
    validated = validate_test_movement(data)
    assert validated["command"] == "wave"
    assert validated["speed"] == 0.8
except ValidationError as e:
    print(f"Validation failed: {e}")

# Invalid - missing command
try:
    validate_test_movement({"speed": 0.8})
except ValidationError as e:
    print(f"Missing required field: {e}")
```

---

## Topic Naming Conventions

1. **Service Topics**: `<service>/<action>` (e.g., `stt/final`, `tts/say`)
2. **System Topics**: `system/<category>/<service>` (e.g., `system/health/router`)
3. **Hierarchical Topics**: Use `/` for hierarchy (e.g., `llm/tool/call/request`)
4. **Event Types**: Use event_type field in envelope, not in topic name

---

## QoS Guidelines

- **QoS 0**: Fire-and-forget (status updates, streaming deltas)
- **QoS 1**: At-least-once delivery (commands, requests, final results)
- **Retained**: Last Will & Testament, health pings, configuration

---

## Best Practices

1. **Always validate**: Use Pydantic models on Python services, validation helpers on ESP32
2. **Use correlation IDs**: message_id for tracing, request_id/id for correlation
3. **Handle errors gracefully**: Check for ValidationError and log/publish errors
4. **Document message flows**: Update this doc when adding new topics
5. **Test contracts**: Write unit tests for all message models
6. **Version carefully**: When changing contracts, ensure backward compatibility

---

## Adding New Contracts

1. **Define in tars-core**: `packages/tars-core/src/tars/contracts/v1/<service>.py`
2. **Export from __init__.py**: Add to `packages/tars-core/src/tars/contracts/v1/__init__.py`
3. **Add tests**: `packages/tars-core/tests/test_<service>_contracts.py`
4. **Document here**: Add topic and contract to this file
5. **Update services**: Import from tars-core in consuming services

---

## References

- **Pydantic V2 Docs**: https://docs.pydantic.dev/latest/
- **MQTT Specification**: https://mqtt.org/mqtt-specification/
- **tars-core README**: `/packages/tars-core/README.md`
- **Movement Contracts Plan**: `/plan/mqtt-contracts-refactor.md`
