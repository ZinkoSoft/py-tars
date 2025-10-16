# MQTT Topic Inventory

**Status**: Phase 1 - Initial Audit  
**Created**: 2025-10-16  
**Last Updated**: 2025-10-16

This document inventories all MQTT topics currently used in py-tars, identifies gaps, and tracks standardization progress.

## Summary Statistics

- **Total Topics Identified**: 28
- **Topics with Constants**: 8 (movement domain only)
- **Topics with Contracts**: 28 (all have Pydantic models)
- **Topics Missing Constants**: 20
- **Non-Standard Naming**: 0 (all follow `<domain>/<action>` pattern)
- **QoS/Retention Gaps**: To be determined in Phase 2

## Topics by Domain

### System Topics

| Topic | Publisher | Subscriber | QoS | Retained | Contract | Constants | Status |
|-------|-----------|------------|-----|----------|----------|-----------|---------|
| `system/health/<service>` | All services | Health monitor | 1 | Yes | `health.HealthPing` | ❌ | ⚠️ Missing constant |
| `system/character/current` | memory-worker | Router, UI | 1 | Yes | `memory.CharacterSnapshot` | ❌ | ⚠️ Missing constant |

**Findings**:
- Health topics use dynamic pattern `system/health/<service>` - convention established but no constant
- Character current uses existing contract but no dedicated constant

**Actions Needed**:
- Add `TOPIC_SYSTEM_HEALTH_PREFIX = "system/health/"` constant
- Add `TOPIC_SYSTEM_CHARACTER_CURRENT` constant  
- Verify QoS=1 and retained=True is used in all health publications

---

### STT (Speech-to-Text) Topics

| Topic | Publisher | Subscriber | QoS | Retained | Contract | Constants | Status |
|-------|-----------|------------|-----|----------|----------|-----------|---------|
| `stt/final` | stt-worker | Router | 1 | No | `stt.FinalTranscript` | ❌ | ⚠️ Missing constant |
| `stt/partial` | stt-worker | UI | 0 | No | `stt.PartialTranscript` | ❌ | ⚠️ Missing constant |

**Findings**:
- Both contracts exist and are complete with correlation fields
- Using legacy event type constants (`EVENT_TYPE_STT_FINAL`) instead of topic constants
- Contracts have `utt_id` for conversation tracking ✅
- Need to verify QoS levels in actual implementation

**Actions Needed**:
- Add `TOPIC_STT_FINAL = "stt/final"` constant
- Add `TOPIC_STT_PARTIAL = "stt/partial"` constant
- Verify stt-worker uses QoS=1 for final, QoS=0 for partial
- Update stt-worker to import topic constants

---

### TTS (Text-to-Speech) Topics

| Topic | Publisher | Subscriber | QoS | Retained | Contract | Constants | Status |
|-------|-----------|------------|-----|----------|----------|-----------|---------|
| `tts/say` | Router | tts-worker | 1 | No | `tts.TtsSay` | ❌ | ⚠️ Missing constant |
| `tts/status` | tts-worker | Router, UI | 0 | No | `tts.TtsStatus` | ❌ | ⚠️ Missing constant |

**Findings**:
- Both contracts exist with good field coverage
- `TtsSay` has `utt_id` for conversation tracking ✅
- `TtsStatus` has `utt_id` for correlation ✅
- Using event type constants instead of topic constants

**Actions Needed**:
- Add `TOPIC_TTS_SAY = "tts/say"` constant
- Add `TOPIC_TTS_STATUS = "tts/status"` constant
- Verify QoS levels match standards
- Update services to use topic constants

---

### LLM (Language Model) Topics

| Topic | Publisher | Subscriber | QoS | Retained | Contract | Constants | Status |
|-------|-----------|------------|-----|----------|----------|-----------|---------|
| `llm/request` | Router | llm-worker | 1 | No | `llm.LLMRequest` | ❌ | ⚠️ Missing constant |
| `llm/response` | llm-worker | Router | 1 | No | `llm.LLMResponse` | ❌ | ⚠️ Missing constant |
| `llm/stream` | llm-worker | Router | 0 | No | `llm.LLMStreamDelta` | ❌ | ⚠️ Missing constant |
| `llm/cancel` | Router | llm-worker | 1 | No | `llm.LLMCancel` | ❌ | ⚠️ Missing constant |
| `llm/tools/registry` | mcp-bridge | llm-worker | 1 | Yes | `llm.ToolsRegistry` | ❌ | ⚠️ Missing constant, verify retained |
| `llm/tool.call.request` | llm-worker | mcp-bridge | 1 | No | `llm.ToolCallRequest` | ❌ | ⚠️ Missing constant |
| `llm/tool.call.result` | mcp-bridge | llm-worker | 1 | No | `llm.ToolCallResult` | ❌ | ⚠️ Missing constant |

**Findings**:
- Contracts exist in llm.py with comprehensive coverage
- Tool-related topics may need review for proper hierarchical naming
- Using event type constants but topic constants missing
- Request/response flow uses `id` field for correlation ✅
- Streaming uses `seq` field for ordering ✅

**Actions Needed**:
- Add all topic constants (`TOPIC_LLM_REQUEST`, etc.)
- Consider renaming `llm/tool.call.*` to `llm/tool/call/*` for consistency
- Verify tools registry should be retained (likely yes for new LLM worker instances)
- Update services to use topic constants

---

### Wake Word Topics

| Topic | Publisher | Subscriber | QoS | Retained | Contract | Constants | Status |
|-------|-----------|------------|-----|----------|----------|-----------|---------|
| `wake/event` | wake-activation | Router | 1 | No | `wake.WakeEvent` | ❌ | ⚠️ Missing constant |
| `wake/mic` | wake-activation | stt-worker | 1 | No | `wake.WakeMicCommand` | ❌ | ⚠️ Missing constant |

**Findings**:
- Both contracts exist with appropriate fields
- `WakeEvent` has correlation fields (`tts_id`, `ts`) ✅
- Mic command pattern for coordinating wake/STT interaction

**Actions Needed**:
- Add `TOPIC_WAKE_EVENT = "wake/event"` constant
- Add `TOPIC_WAKE_MIC = "wake/mic"` constant
- Verify QoS=1 for both (wake events are important)

---

### Memory Topics

| Topic | Publisher | Subscriber | QoS | Retained | Contract | Constants | Status |
|-------|-----------|------------|-----|----------|----------|-----------|---------|
| `memory/query` | Router | memory-worker | 1 | No | `memory.MemoryQuery` | ❌ | ⚠️ Missing constant |
| `memory/results` | memory-worker | Router | 1 | No | `memory.MemoryResults` | ❌ | ⚠️ Missing constant |
| `character/get` | Router/UI | memory-worker | 1 | No | `memory.CharacterGetRequest` | ❌ | ⚠️ Missing constant |
| `character/result` | memory-worker | Router/UI | 1 | No | `memory.CharacterSnapshot` or `CharacterSection` | ❌ | ⚠️ Missing constant |
| `character/update` | UI/Router | memory-worker | 1 | No | `memory.CharacterTraitUpdate` or `CharacterResetTraits` | ❌ | ⚠️ Missing constant |

**Findings**:
- Comprehensive memory contracts exist
- Character management has multiple contract types
- All have `message_id` for correlation ✅
- Memory query has sophisticated options (RAG, context window, etc.)

**Actions Needed**:
- Add all topic constants
- Clarify character/result contract selection (snapshot vs section)
- Verify QoS=1 appropriate for all

---

### Movement Topics

| Topic | Publisher | Subscriber | QoS | Retained | Contract | Constants | Status |
|-------|-----------|------------|-----|----------|----------|-----------|---------|
| `movement/command` | External | movement-service | 1 | No | `movement.MovementCommand` | ✅ | ✅ Complete |
| `movement/frame` | movement-service | ESP32 | 1 | No | `movement.MovementFrame` | ✅ | ✅ Complete |
| `movement/state` | movement-service | External | 0 | No | `movement.MovementState` | ✅ | ✅ Complete |
| `movement/test` | Router | ESP32 | 1 | No | `movement.TestMovementRequest` | ✅ | ✅ Complete |
| `movement/stop` | Router | ESP32 | 1 | No | `movement.EmergencyStopCommand` | ✅ | ✅ Complete |
| `movement/status` | ESP32 | Router, UI | 0 | No | `movement.MovementStatusUpdate` | ✅ | ✅ Complete |
| `system/health/movement` | movement-service | Health monitor | 1 | Yes | `health.HealthPing` | ✅ | ✅ Complete |
| `system/health/movement-controller` | ESP32 | Health monitor | 1 | Yes | `health.HealthPing` | ✅ | ✅ Complete |

**Findings**:
- Movement domain is FULLY STANDARDIZED ✅
- All topics have constants in `movement.py`
- All contracts complete with correlation fields
- Dual architecture (frame-based + command-based) well documented
- QoS levels appropriate for each topic type

**Actions Needed**:
- None - use as reference for other domains

---

### Camera Topics

| Topic | Publisher | Subscriber | QoS | Retained | Contract | Constants | Status |
|-------|-----------|------------|-----|----------|----------|-----------|---------|
| `camera/capture` | MCP bridge | camera-service | 1 | No | ❌ | ❌ | ❌ Missing contract |
| `camera/image` | camera-service | MCP bridge | 1 | No | ❌ | ❌ | ❌ Missing contract |

**Findings**:
- Camera domain has NO contracts or constants
- Topics follow standard naming pattern ✅
- Need to define message schemas for camera operations

**Actions Needed**:
- Create `camera.py` contract file
- Define `CameraCaptureRequest` contract
- Define `CameraImageResponse` contract
- Add topic constants
- Add correlation fields for request/response tracking
- Add comprehensive tests

---

## Gap Analysis

### Missing Topic Constants (Priority: High)

All domains except movement need topic constants added:

**System Domain** (2 topics):
- `TOPIC_SYSTEM_HEALTH_PREFIX`
- `TOPIC_SYSTEM_CHARACTER_CURRENT`

**STT Domain** (2 topics):
- `TOPIC_STT_FINAL`
- `TOPIC_STT_PARTIAL`

**TTS Domain** (2 topics):
- `TOPIC_TTS_SAY`
- `TOPIC_TTS_STATUS`

**LLM Domain** (7 topics):
- `TOPIC_LLM_REQUEST`
- `TOPIC_LLM_RESPONSE`
- `TOPIC_LLM_STREAM`
- `TOPIC_LLM_CANCEL`
- `TOPIC_LLM_TOOLS_REGISTRY`
- `TOPIC_LLM_TOOL_CALL_REQUEST`
- `TOPIC_LLM_TOOL_CALL_RESULT`

**Wake Domain** (2 topics):
- `TOPIC_WAKE_EVENT`
- `TOPIC_WAKE_MIC`

**Memory Domain** (5 topics):
- `TOPIC_MEMORY_QUERY`
- `TOPIC_MEMORY_RESULTS`
- `TOPIC_CHARACTER_GET`
- `TOPIC_CHARACTER_RESULT`
- `TOPIC_CHARACTER_UPDATE`

**Camera Domain** (2 topics):
- `TOPIC_CAMERA_CAPTURE`
- `TOPIC_CAMERA_IMAGE`

**Total**: 22 topic constants to add

### Missing Contracts (Priority: High)

Camera domain needs contracts created:
- `CameraCaptureRequest` - Request to capture image
- `CameraImageResponse` - Image data response

### QoS/Retention Verification Needed (Priority: Medium)

Need to verify actual QoS levels used in services:
- [ ] stt-worker: final=1, partial=0
- [ ] tts-worker: say=1, status=0
- [ ] llm-worker: request/response/cancel=1, stream=0
- [ ] wake-activation: event=1, mic=1
- [ ] memory-worker: all=1
- [ ] All services: health topics with QoS=1 and retained=True

### Topic Naming Review (Priority: Low)

Consider consistency improvements:
- `llm/tool.call.request` → `llm/tool/call/request` (use slashes not dots)
- `llm/tool.call.result` → `llm/tool/call/result`

Or keep as-is since dots indicate sub-events (existing convention)?

## Implementation Priority

### Phase 2A: Add Missing Constants (Week 2 - Days 1-2)

High priority - enables services to use constants:

1. ✅ Movement (already complete - reference)
2. System (health prefix + character current)
3. STT (final, partial)
4. TTS (say, status)
5. LLM (request, response, stream, cancel, tools)
6. Wake (event, mic)
7. Memory (query, results, character operations)
8. Camera (capture, image - with new contracts)

### Phase 2B: Create Missing Contracts (Week 2 - Days 3-4)

Camera domain only:
1. Create `camera.py` contract file
2. Define request/response models
3. Add tests
4. Export from v1/__init__.py

### Phase 3: Service Updates (Week 3)

Update services to use topic constants (no string literals):

**Priority 1 - Core Services**:
1. Router (uses all domains)
2. stt-worker
3. tts-worker
4. llm-worker

**Priority 2 - Supporting Services**:
5. wake-activation
6. memory-worker
7. camera-service
8. mcp-bridge

**Priority 3 - UI Services**:
9. ui
10. ui-web

### Phase 4: Validation (Week 4)

1. Integration tests for all flows
2. QoS verification
3. Documentation updates
4. Completion report

## Notes

- Movement domain serves as GOLD STANDARD - all other domains should match its pattern
- All existing contracts have `extra="forbid"` ✅
- Most contracts have correlation fields (message_id, request_id, utt_id) ✅
- Topic naming is already consistent ✅
- Main work is adding constants and updating service imports

## Version History

- **1.0.0** (2025-10-16): Initial audit complete
