# Migration Guide: MQTT Topic Standardization

**Target Audience**: Developers updating services to use standardized MQTT contracts  
**Status**: Active  
**Version**: 1.0.0  
**Created**: 2025-10-16

## Overview

This guide walks through migrating a service from using string literals and raw dict parsing to using standardized MQTT topic constants and Pydantic contracts from `tars-core`.

## Prerequisites

- Service already uses `tars-core` package as dependency
- Basic understanding of Pydantic v2
- Familiarity with MQTT QoS levels

## Step-by-Step Migration

### Step 1: Import Topic Constants

**Before** (string literals):
```python
# Bad - hardcoded strings
await publisher.publish("stt/final", payload, qos=1)
await subscriber.subscribe("llm/request")
```

**After** (constants):
```python
# Good - use constants from tars-core
from tars.contracts.v1.stt import TOPIC_STT_FINAL
from tars.contracts.v1.llm import TOPIC_LLM_REQUEST

await publisher.publish(TOPIC_STT_FINAL, payload, qos=1)
await subscriber.subscribe(TOPIC_LLM_REQUEST)
```

**Benefits**:
- Type checking catches typos at compile time
- Refactoring tools can update all usages
- Single source of truth in `tars-core`

---

### Step 2: Import Contract Models

**Before** (raw dicts):
```python
# Bad - manual dict construction
message = {
    "text": transcript,
    "lang": "en",
    "confidence": 0.95,
    "timestamp": time.time()
}
payload = json.dumps(message)
```

**After** (Pydantic models):
```python
# Good - use typed contracts
from tars.contracts.v1.stt import FinalTranscript

message = FinalTranscript(
    text=transcript,
    lang="en",
    confidence=0.95,
)
payload = message.model_dump_json()
```

**Benefits**:
- Validation catches errors before publishing
- IDE autocomplete for fields
- Self-documenting code
- Default values handled automatically

---

### Step 3: Validate Incoming Messages

**Before** (manual validation):
```python
# Bad - manual parsing and validation
data = json.loads(payload)
if "text" not in data:
    logger.error("Missing 'text' field")
    return
text = data["text"]
```

**After** (Pydantic validation):
```python
# Good - automatic validation
from pydantic import ValidationError
from tars.contracts.v1.llm import LLMRequest

try:
    request = LLMRequest.model_validate_json(payload)
    text = request.text  # Guaranteed to exist
except ValidationError as e:
    logger.error(f"Invalid message: {e}")
    return
```

**Benefits**:
- Type safety
- Extra fields rejected (catches typos)
- Constraint validation (e.g., speed 0.1-1.0)
- Clear error messages

---

### Step 4: Add Correlation IDs

**Before** (no correlation):
```python
# Bad - no way to trace requests
request = LLMRequest(text="Hello")
```

**After** (with correlation):
```python
# Good - track requests across services
request = LLMRequest(
    id=uuid.uuid4().hex,  # Request ID
    text="Hello",
)

# Later, in response
response = LLMResponse(
    id=request.id,  # Same ID for correlation
    reply="Hi there!",
)
```

For conversation flows (STT → LLM → TTS):
```python
# STT generates utt_id
final = FinalTranscript(
    utt_id=uuid.uuid4().hex,
    text="What's the weather?",
)

# LLM propagates utt_id
llm_request = LLMRequest(
    id=uuid.uuid4().hex,
    text=final.text,
    # Note: LLMRequest doesn't have utt_id, use 'id' field
)

# TTS receives utt_id in TtsSay
tts_request = TtsSay(
    text="It's sunny!",
    utt_id=final.utt_id,  # Propagate from original
)
```

---

### Step 5: Update Logging

**Before** (basic logging):
```python
# Bad - hard to trace
logger.info("Processing LLM request")
```

**After** (structured logging):
```python
# Good - includes correlation fields
logger.info(
    "Processing LLM request",
    extra={
        "request_id": request.id,
        "utt_id": request.utt_id,
        "service": "llm-worker",
    }
)
```

**Benefits**:
- Trace requests across services
- Search logs by correlation ID
- Better debugging

---

### Step 6: Set Correct QoS Levels

Per constitution standards:

```python
# Health topics (QoS 1, retained)
await publisher.publish(
    f"{TOPIC_SYSTEM_HEALTH_PREFIX}stt",
    health_msg.model_dump_json(),
    qos=1,
    retain=True,
)

# Commands/requests (QoS 1, not retained)
await publisher.publish(
    TOPIC_LLM_REQUEST,
    request.model_dump_json(),
    qos=1,
    retain=False,
)

# Responses (QoS 1, not retained)
await publisher.publish(
    TOPIC_LLM_RESPONSE,
    response.model_dump_json(),
    qos=1,
    retain=False,
)

# Streaming/partials (QoS 0, not retained)
await publisher.publish(
    TOPIC_STT_PARTIAL,
    partial.model_dump_json(),
    qos=0,
    retain=False,
)
```

---

### Step 7: Update Tests

**Before** (manual mocking):
```python
# Bad - manually construct test messages
test_payload = '{"text": "hello", "lang": "en"}'
```

**After** (use contracts):
```python
# Good - use contracts in tests
from tars.contracts.v1.stt import FinalTranscript

test_msg = FinalTranscript(text="hello", lang="en")
test_payload = test_msg.model_dump_json()

# Verify received message
received = FinalTranscript.model_validate_json(received_payload)
assert received.text == "hello"
```

---

## Example: Complete Service Migration

Here's a complete before/after for a simplified STT worker:

### Before

```python
# stt_worker.py (OLD)
import json
import time
from mqtt_client import MQTTClient

async def publish_transcript(text, confidence):
    # Manual dict construction
    message = {
        "text": text,
        "lang": "en",
        "confidence": confidence,
        "timestamp": time.time(),
        "is_final": True,
    }
    
    # Hardcoded topic string
    await mqtt_client.publish(
        "stt/final",
        json.dumps(message),
        qos=1
    )
    
    logger.info(f"Published transcript: {text}")
```

### After

```python
# stt_worker.py (NEW)
from tars.contracts.v1.stt import FinalTranscript, TOPIC_STT_FINAL
from pydantic import ValidationError

async def publish_transcript(text, confidence, utt_id=None):
    try:
        # Use Pydantic contract
        message = FinalTranscript(
            text=text,
            lang="en",
            confidence=confidence,
            utt_id=utt_id,
        )
        
        # Use topic constant
        await mqtt_client.publish(
            TOPIC_STT_FINAL,
            message.model_dump_json(),
            qos=1,
        )
        
        # Structured logging with correlation
        logger.info(
            "Published transcript",
            extra={
                "message_id": message.message_id,
                "utt_id": message.utt_id,
                "text_length": len(text),
                "service": "stt-worker",
            }
        )
        
    except ValidationError as e:
        logger.error(f"Invalid transcript message: {e}")
        raise
```

---

## Common Pitfalls

### 1. Forgetting `model_dump_json()` for serialization

❌ **Wrong**:
```python
await publisher.publish(topic, message)  # Publishing Pydantic object
```

✅ **Correct**:
```python
await publisher.publish(topic, message.model_dump_json())
```

### 2. Using `dict()` instead of `model_dump()`

❌ **Wrong** (deprecated):
```python
data = message.dict()  # Old Pydantic v1 API
```

✅ **Correct**:
```python
data = message.model_dump()  # Pydantic v2 API
```

### 3. Not handling `ValidationError`

❌ **Wrong**:
```python
message = Contract.model_validate_json(payload)  # Uncaught exception
```

✅ **Correct**:
```python
try:
    message = Contract.model_validate_json(payload)
except ValidationError as e:
    logger.error(f"Invalid message: {e}")
    return
```

### 4. Missing correlation ID propagation

❌ **Wrong**:
```python
# STT generates utt_id
final = FinalTranscript(utt_id=uuid.uuid4().hex, text="hello")

# LLM doesn't propagate utt_id
llm_request = LLMRequest(id=uuid.uuid4().hex, text=final.text)
# Lost correlation!
```

✅ **Correct**:
```python
# STT generates utt_id
final = FinalTranscript(utt_id=uuid.uuid4().hex, text="hello")

# Router tracks utt_id and passes to TTS
tts_request = TtsSay(text="response", utt_id=final.utt_id)
# Correlation maintained
```

---

## Testing Your Migration

After migration, verify:

### 1. Unit Tests Pass
```bash
cd apps/<your-service>
make test
```

### 2. Lint Checks Pass
```bash
make lint
```

### 3. Type Checks Pass
```bash
make type-check
```

### 4. Integration Tests
```bash
# Start MQTT broker
docker run -d -p 1883:1883 eclipse-mosquitto

# Start your service
python -m <your_service>

# Publish test message
mosquitto_pub -t stt/final -m '{"text":"test","lang":"en"}'
```

### 5. Manual Verification
- Check logs include correlation IDs
- Verify messages validate correctly
- Test with malformed messages (should log errors, not crash)

---

## Checklist

Use this checklist for each service migration:

- [ ] Import topic constants from `tars.contracts.v1.<domain>`
- [ ] Replace all topic string literals with constants
- [ ] Import contract models
- [ ] Replace dict construction with Pydantic models
- [ ] Use `model_validate_json()` for parsing
- [ ] Use `model_dump_json()` for serialization
- [ ] Add correlation ID fields to messages
- [ ] Update logging to include correlation IDs
- [ ] Set correct QoS levels (per constitution)
- [ ] Set correct retention policy (per constitution)
- [ ] Add `ValidationError` handling
- [ ] Update tests to use contracts
- [ ] Run `make check`
- [ ] Update service README with:
  - Topics published (with constants)
  - Topics subscribed (with constants)
  - Correlation ID strategy
- [ ] Test integration with MQTT broker

---

## Getting Help

If you encounter issues:

1. **Check the spec**: `specs/003-standardize-mqtt-topics/spec.md`
2. **Review topic inventory**: `specs/003-standardize-mqtt-topics/topic-inventory.md`
3. **See movement contracts** as reference (fully standardized)
4. **Ask in team channels**: #py-tars or #architecture

---

## Version History

- **1.0.0** (2025-10-16): Initial migration guide
