# Specification: Standardize MQTT Topics

**Version**: 1.0.0  
**Status**: Active  
**Created**: 2025-10-16  
**Last Updated**: 2025-10-16

## Overview

This specification defines the standards for MQTT topic naming, message contracts, and communication patterns across all py-tars services. It implements the Event-Driven Architecture principles from the constitution.

## Topic Naming Standards

### Pattern

All topics MUST follow the pattern: `<domain>/<action_or_event>`

Where:
- **domain**: Service or feature area (lowercase, underscore-separated)
- **action_or_event**: Command, request, or state change

### Examples

**Commands** (imperative verbs):
- `tts/say` - Command to speak text
- `llm/request` - Request LLM generation
- `memory/query` - Query memory store
- `movement/test` - Test movement command

**Events** (past tense or nouns):
- `stt/final` - Final transcription event
- `wake/event` - Wake word detected event
- `tts/status` - TTS status update
- `movement/status` - Movement execution status

### Reserved Patterns

**System topics** use 3-level hierarchy:
- `system/health/<service>` - Health monitoring (retained)
- `system/character/current` - Current character state (retained)

### Anti-Patterns

❌ **Avoid**:
- Inconsistent casing: `STT/Final`, `tts/Say`
- Versioning in topics: `llm/request/v2` (use schema evolution instead)
- Deep hierarchies: `domain/subdomain/action/type`
- Ambiguous names: `service/do`, `app/data`

## Message Contract Standards

### Pydantic Model Requirements

All MQTT message payloads MUST have Pydantic v2 models with:

```python
from pydantic import BaseModel, Field, ConfigDict
import time

class ExampleMessage(BaseModel):
    """
    Brief description of message purpose.
    
    Published to: example/topic
    Consumed by: example-service
    """
    model_config = ConfigDict(extra="forbid")  # ← REQUIRED
    
    # Correlation fields
    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    request_id: str | None = None  # Links to originating request
    utt_id: str | None = None      # Utterance ID for conversation tracking
    
    # Timestamp
    timestamp: float = Field(default_factory=time.time)
    
    # Message-specific fields
    # ... with type annotations and validation constraints
```

### Required Fields

Every message MUST include:

1. **`message_id`**: Unique identifier (UUID) for this message
2. **`timestamp`**: Unix timestamp when message created
3. **Message-specific fields**: Validated with appropriate constraints

### Optional Correlation Fields

Include when relevant for tracing:

1. **`request_id`**: Links response to originating request
2. **`utt_id`**: Utterance ID for conversation flow (STT → LLM → TTS)
3. **`correlation_id`**: Generic correlation for other flows

### Validation Constraints

Use Pydantic validators for:

- **Ranges**: `Field(ge=0.1, le=1.0)` for speed/volume
- **String patterns**: `Field(pattern=r"^[a-z]+$")` for commands
- **Enum values**: Use `str, Enum` for fixed vocabularies
- **Lists/dicts**: Typed collections with element validation

### Example Contracts

```python
# Command message
class TTSSayRequest(BaseModel):
    """Request to synthesize and speak text."""
    model_config = ConfigDict(extra="forbid")
    
    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    utt_id: str | None = None
    timestamp: float = Field(default_factory=time.time)
    
    text: str = Field(min_length=1, max_length=5000)
    voice: str | None = None
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    volume: float = Field(default=1.0, ge=0.0, le=1.0)

# Event message
class TTSStatusUpdate(BaseModel):
    """Status update from TTS worker."""
    model_config = ConfigDict(extra="forbid")
    
    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    request_id: str  # Required - links to TTSSayRequest
    timestamp: float = Field(default_factory=time.time)
    
    event: Literal["started", "speaking", "completed", "failed"]
    detail: str | None = None
    progress: float | None = Field(default=None, ge=0.0, le=1.0)
```

## QoS and Retention Standards

### QoS Levels

Per constitution, apply these QoS levels:

| Topic Type | QoS | Rationale |
|------------|-----|-----------|
| **Health** (`system/health/*`) | 1 | Ensure status updates delivered |
| **Commands** (`*/request`, `*/say`, `*/query`) | 1 | Ensure commands not lost |
| **Responses** (`*/response`, `*/results`) | 1 | Ensure replies delivered |
| **Streaming** (`*/stream`, `*/partial`) | 0 | Speed over reliability |
| **Status** (`*/status`, `*/event`) | 0 or 1 | Depends on criticality |

### Retention Policy

| Topic Type | Retained | Rationale |
|------------|----------|-----------|
| **Health** (`system/health/*`) | Yes | Latest status available to new subscribers |
| **Character state** (`system/character/current`) | Yes | Current character persists across restarts |
| **All others** | No | Avoid stale messages |

### Implementation

```python
# Publishing with QoS
await publisher.publish(
    topic="llm/request",
    payload=request.model_dump_json(),
    qos=1,      # At least once delivery
    retain=False  # Do not retain
)

# Health with retention
await publisher.publish(
    topic="system/health/router",
    payload=health.model_dump_json(),
    qos=1,
    retain=True  # Latest status persists
)
```

## Topic Constants

### Location

All topic constants MUST be defined in:
```
/packages/tars-core/src/tars/contracts/v1/<domain>.py
```

### Naming Convention

```python
TOPIC_<DOMAIN>_<ACTION> = "domain/action"
```

Examples:
```python
# STT domain
TOPIC_STT_FINAL = "stt/final"
TOPIC_STT_PARTIAL = "stt/partial"

# LLM domain
TOPIC_LLM_REQUEST = "llm/request"
TOPIC_LLM_RESPONSE = "llm/response"
TOPIC_LLM_STREAM = "llm/stream"
TOPIC_LLM_CANCEL = "llm/cancel"

# System domain
TOPIC_SYSTEM_HEALTH_PREFIX = "system/health/"  # Append service name
TOPIC_SYSTEM_CHARACTER_CURRENT = "system/character/current"
```

### Usage in Services

❌ **Never** use string literals:
```python
# BAD
await publisher.publish("stt/final", payload, qos=1)
```

✅ **Always** use constants:
```python
# GOOD
from tars.contracts.v1.stt import TOPIC_STT_FINAL

await publisher.publish(TOPIC_STT_FINAL, payload, qos=1)
```

## Correlation ID Strategy

### Request-Response Pattern

For request-response flows:

1. **Requester** generates `request_id`
2. **Responder** includes same `request_id` in response
3. **Requester** correlates via `request_id`

```python
# Request
request = LLMRequest(
    request_id=uuid.uuid4().hex,  # Generate new ID
    prompt="Hello"
)
await pub.publish(TOPIC_LLM_REQUEST, request.model_dump_json(), qos=1)

# Response
response = LLMResponse(
    request_id=request.request_id,  # Echo same ID
    content="Hi there!"
)
await pub.publish(TOPIC_LLM_RESPONSE, response.model_dump_json(), qos=1)
```

### Conversation Flow Pattern

For multi-service flows (STT → Router → LLM → TTS):

1. **STT** generates `utt_id` (utterance ID)
2. **Router** propagates `utt_id` to LLM request
3. **LLM** echoes `utt_id` in response
4. **Router** propagates `utt_id` to TTS request
5. **TTS** echoes `utt_id` in status updates

```python
# STT generates utterance ID
final = STTFinalTranscript(
    utt_id=uuid.uuid4().hex,  # New conversation
    text="What's the weather?"
)

# Router propagates to LLM
llm_request = LLMRequest(
    request_id=uuid.uuid4().hex,
    utt_id=final.utt_id,  # ← Propagate
    prompt=final.text
)

# LLM echoes back
llm_response = LLMResponse(
    request_id=llm_request.request_id,
    utt_id=llm_request.utt_id,  # ← Echo
    content="It's sunny!"
)

# Router propagates to TTS
tts_request = TTSSayRequest(
    request_id=uuid.uuid4().hex,
    utt_id=llm_response.utt_id,  # ← Propagate
    text=llm_response.content
)
```

### Logging with Correlation IDs

All log messages MUST include correlation fields:

```python
logger.info(
    "Processing LLM request",
    extra={
        "request_id": request.request_id,
        "utt_id": request.utt_id,
        "service": "llm-worker"
    }
)
```

This enables tracing requests across services in log aggregation tools.

## Schema Evolution

### Adding Fields (Backward Compatible)

✅ **Allowed**: Add optional fields with defaults

```python
# Version 1
class TTSSayRequest(BaseModel):
    text: str

# Version 2 (backward compatible)
class TTSSayRequest(BaseModel):
    text: str
    voice: str | None = None  # ← New optional field
```

Old publishers work with new subscribers (field defaults to None).

### Removing Fields (Breaking)

❌ **Requires migration**: Remove fields breaks old publishers

**Process**:
1. Mark field as optional with deprecation notice
2. Update all publishers to stop using field
3. After grace period, remove field
4. Update all subscribers

### Changing Field Types (Breaking)

❌ **Requires migration**: Type changes break validation

**Process**:
1. Add new field with new type
2. Deprecate old field
3. Update publishers to use new field
4. After grace period, remove old field

### Parallel Topics for Major Changes

For incompatible changes, create parallel topic:

```python
# Old topic (deprecated)
TOPIC_LLM_REQUEST_V1 = "llm/request"  # Deprecated 2025-11-01

# New topic (current)
TOPIC_LLM_REQUEST = "llm/request/v2"
```

**Timeline**:
1. Deploy new topic alongside old
2. Update publishers to new topic
3. Update subscribers to new topic
4. Deprecate old topic (announce timeline)
5. Remove old topic after grace period (minimum 2 sprints)

## Error Handling

### Validation Errors

Services MUST handle validation errors gracefully:

```python
try:
    request = LLMRequest.model_validate_json(payload)
except ValidationError as e:
    logger.error(
        "Invalid message received",
        extra={
            "topic": topic,
            "error": str(e),
            "payload": payload[:200]  # Truncate for logging
        }
    )
    # Optionally publish error to monitoring topic
    return
```

### Missing Required Fields

Pydantic raises `ValidationError` for missing required fields:

```python
{
  "type": "missing",
  "loc": ["request_id"],
  "msg": "Field required"
}
```

### Extra Fields

With `extra="forbid"`, unknown fields cause validation errors:

```python
{
  "type": "extra_forbidden",
  "loc": ["unknown_field"],
  "msg": "Extra inputs are not permitted"
}
```

This catches typos and schema drift early.

## Testing Standards

### Contract Tests

Every contract file MUST have comprehensive tests:

```python
# packages/tars-core/tests/test_<domain>_contracts.py

def test_valid_request():
    """Test valid message validates."""
    msg = TTSSayRequest(text="Hello")
    assert msg.text == "Hello"
    assert msg.speed == 1.0  # Default

def test_invalid_speed():
    """Test speed validation."""
    with pytest.raises(ValidationError) as exc:
        TTSSayRequest(text="Hello", speed=3.0)  # > 2.0
    assert "less than or equal to 2.0" in str(exc.value)

def test_extra_fields_forbidden():
    """Test extra fields rejected."""
    with pytest.raises(ValidationError) as exc:
        TTSSayRequest(text="Hello", typo="oops")
    assert "Extra inputs are not permitted" in str(exc.value)

def test_json_round_trip():
    """Test JSON serialization."""
    msg = TTSSayRequest(text="Hello")
    json_str = msg.model_dump_json()
    msg2 = TTSSayRequest.model_validate_json(json_str)
    assert msg == msg2
```

### Integration Tests

Test cross-service flows:

```python
# tests/integration/test_mqtt_flows.py

async def test_stt_to_tts_flow(mqtt_broker):
    """Test complete STT → Router → LLM → TTS flow."""
    utt_id = uuid.uuid4().hex
    
    # Publish STT final
    stt_msg = STTFinalTranscript(utt_id=utt_id, text="Hello")
    await publish(TOPIC_STT_FINAL, stt_msg)
    
    # Expect LLM request with same utt_id
    llm_req = await receive(TOPIC_LLM_REQUEST)
    assert llm_req.utt_id == utt_id
    
    # Publish LLM response
    llm_resp = LLMResponse(
        request_id=llm_req.request_id,
        utt_id=utt_id,
        content="Hi!"
    )
    await publish(TOPIC_LLM_RESPONSE, llm_resp)
    
    # Expect TTS request with same utt_id
    tts_req = await receive(TOPIC_TTS_SAY)
    assert tts_req.utt_id == utt_id
    assert tts_req.text == "Hi!"
```

## Migration Checklist

For each service migrating to standardized contracts:

- [ ] Import contracts from `tars.contracts.v1.<domain>`
- [ ] Replace topic string literals with `TOPIC_*` constants
- [ ] Use `model_validate()` or `model_validate_json()` for parsing
- [ ] Use `model_dump()` or `model_dump_json()` for serialization
- [ ] Add correlation ID fields to all messages
- [ ] Update logging to include correlation IDs
- [ ] Set QoS levels per standards
- [ ] Set retention policy per standards
- [ ] Add error handling for `ValidationError`
- [ ] Update tests to use contracts
- [ ] Update README with topic documentation
- [ ] Run `make check` to verify

## References

- **Constitution**: `/.specify/memory/constitution.md`
- **Event-Driven Architecture**: Constitution Section I
- **Typed Contracts**: Constitution Section II
- **MQTT Standards**: Constitution Section "MQTT Contract Standards"
- **tars-core Contracts**: `/packages/tars-core/src/tars/contracts/v1/`

## Version History

- **1.0.0** (2025-10-16): Initial specification
