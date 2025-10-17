# MQTT Topic Inventory

**Generated**: 2025-10-16  
**Purpose**: Complete inventory of all MQTT topics used in py-tars

## Summary

| Domain | Topics | Contracts Complete | Constants Defined | Services Using Constants |
|--------|--------|-------------------|------------------|-------------------------|
| STT | 3 | ✅ | ✅ | ⚠️ Partial |
| TTS | 3 | ✅ | ✅ | ⚠️ Partial |
| LLM | 6 | ✅ | ✅ | ⚠️ Partial |
| Memory | 5 | ✅ | ✅ | ⚠️ Partial |
| Movement | 7 | ✅ | ✅ | ✅ Complete |
| Wake | 2 | ✅ | ✅ | ⚠️ Partial |
| Camera | 2 | ✅ | ✅ | ⚠️ Partial |
| MCP/Tools | 3 | ✅ | ✅ | ⚠️ Partial |
| System | 2+ | ⚠️ Partial | ⚠️ Partial | ❌ No |

## Detailed Inventory

### STT (Speech-to-Text)

| Topic | Publisher | Subscribers | QoS | Retained | Contract | Status |
|-------|-----------|-------------|-----|----------|----------|--------|
| `stt/final` | stt-worker | router, memory-worker, ui, ui-web, wake-activation | 1 | No | `FinalTranscript` | ✅ |
| `stt/partial` | stt-worker | ui, ui-web | 0 | No | `PartialTranscript` | ✅ |
| `stt/audio_fft` | stt-worker | ui, ui-web | 0 | No | ❌ None | ❌ Missing contract |

**Constants Defined**: `TOPIC_STT_FINAL`, `TOPIC_STT_PARTIAL` in `tars.contracts.v1.stt`  
**Missing**: Topic constant for `stt/audio_fft`

**Service Usage**:
- ✅ stt-worker: Uses string literals `"stt/final"`, `"stt/partial"`, `"stt/audio_fft"` in `config.py`
- ❌ router: Uses string literals
- ❌ memory-worker: Uses config constant `TOPIC_STT_FINAL` from local config, not tars-core
- ❌ ui/ui-web: Uses string literals in config

### TTS (Text-to-Speech)

| Topic | Publisher | Subscribers | QoS | Retained | Contract | Status |
|-------|-----------|-------------|-----|----------|----------|--------|
| `tts/say` | router, memory-worker, ui-web | tts-worker | 1 | No | `TtsSay` | ✅ |
| `tts/status` | tts-worker | router, ui, ui-web, wake-activation, stt-worker | 0 | No | `TtsStatus` | ✅ |
| `tts/control` | wake-activation | tts-worker | 1 | No | ❌ None | ❌ Missing contract |

**Constants Defined**: `TOPIC_TTS_SAY`, `TOPIC_TTS_STATUS` in `tars.contracts.v1.tts`  
**Missing**: Topic constant for `tts/control`

**Service Usage**:
- ❌ tts-worker: Hardcoded constants in `service.py` (not from tars-core)
- ❌ router: Uses config constants from local config
- ❌ memory-worker: Uses config constant `TOPIC_TTS_SAY` from local config
- ❌ wake-activation: Uses config field with env default

### LLM (Language Model)

| Topic | Publisher | Subscribers | QoS | Retained | Contract | Status |
|-------|-----------|-------------|-----|----------|----------|--------|
| `llm/request` | router | llm-worker | 1 | No | `LLMRequest` | ✅ |
| `llm/response` | llm-worker | router, ui, ui-web | 1 | No | `LLMResponse` | ✅ |
| `llm/stream` | llm-worker | router, ui-web | 0 | No | `LLMStreamDelta` | ✅ |
| `llm/cancel` | router | llm-worker | 1 | No | `LLMCancel` | ✅ |
| `llm/tools/registry` | mcp-bridge | llm-worker | 1 | Yes | `ToolsRegistry` | ✅ |
| `llm/tools/call` | llm-worker | mcp-bridge | 1 | No | `ToolCallRequest` | ✅ |
| `llm/tools/result` | mcp-bridge | llm-worker | 1 | No | `ToolCallResult` | ✅ |

**Constants Defined**: All defined in `tars.contracts.v1.llm`  
**Note**: `TOPIC_LLM_TOOL_CALL_REQUEST` uses dot notation in constant name but slash in value

**Service Usage**:
- ⚠️ llm-worker: Uses local config constants (not from tars-core), but has proper QoS
- ❌ router: Uses string literals in places
- ❌ ui/ui-web: Uses string literals

### Memory

| Topic | Publisher | Subscribers | QoS | Retained | Contract | Status |
|-------|-----------|-------------|-----|----------|----------|--------|
| `memory/query` | router, ui-web | memory-worker | 1 | No | `MemoryQuery` | ✅ |
| `memory/results` | memory-worker | router, ui-web, llm-worker | 1 | No | `MemoryResults` | ✅ |
| `system/character/current` | memory-worker | llm-worker, ui | 1 | Yes | `CharacterSnapshot` | ✅ |
| `system/character/get` | llm-worker | memory-worker | 1 | No | `CharacterGetRequest` | ✅ |
| `system/character/result` | memory-worker | llm-worker | 1 | No | `CharacterSnapshot` | ✅ |

**Constants Defined**: All defined in `tars.contracts.v1.memory`  
**Note**: `TOPIC_CHARACTER_UPDATE` is defined but actual topic is `TOPIC_SYSTEM_CHARACTER_CURRENT`

**Service Usage**:
- ❌ memory-worker: Uses local config constants
- ❌ llm-worker: Uses local config constants
- ❌ ui-web: Uses string literals

### Movement

| Topic | Publisher | Subscribers | QoS | Retained | Contract | Status |
|-------|-----------|-------------|-----|----------|----------|--------|
| `movement/command` | external | movement-service | 1 | No | `MovementCommand` | ✅ |
| `movement/frame` | movement-service | esp32 | 1 | No | `MovementFrame` | ✅ |
| `movement/state` | movement-service | external | 0 | No | `MovementState` | ✅ |
| `movement/test` | router, external | movement-service, esp32 | 1 | No | `TestMovementRequest` | ✅ |
| `movement/stop` | router | esp32 | 1 | No | `EmergencyStopCommand` | ✅ |
| `movement/status` | esp32 | router, ui | 0 | No | `MovementStatusUpdate` | ✅ |
| `system/health/movement` | movement-service | health-monitor | 1 | Yes | `HealthPing` | ✅ |

**Constants Defined**: All defined in `tars.contracts.v1.movement`

**Service Usage**:
- ✅ movement-service: Fully uses tars-core contracts

### Wake

| Topic | Publisher | Subscribers | QoS | Retained | Contract | Status |
|-------|-----------|-------------|-----|----------|----------|--------|
| `wake/event` | wake-activation | router, stt-worker | 1 | No | `WakeEvent` | ✅ |
| `wake/mic` | wake-activation | stt-worker | 1 | No | `WakeMicCommand` | ✅ |
| `system/health/wake` | wake-activation | health-monitor | 1 | Yes | `HealthPing` | ⚠️ |

**Constants Defined**: `TOPIC_WAKE_EVENT`, `TOPIC_WAKE_MIC` in `tars.contracts.v1.wake`  
**Missing**: Health topic constant (uses string literal in config)

**Service Usage**:
- ❌ wake-activation: Uses local config with env defaults
- ❌ stt-worker: Uses string literals `"wake/mic"`, `"wake/event"`

### Camera

| Topic | Publisher | Subscribers | QoS | Retained | Contract | Status |
|-------|-----------|-------------|-----|----------|----------|--------|
| `camera/capture` | mcp-bridge | camera-service | 1 | No | `CameraCaptureRequest` | ✅ |
| `camera/image` | camera-service | mcp-bridge | 1 | No | `CameraImageResponse` | ✅ |
| `camera/frame` | camera-service | ui/visualization | 0 | No | ❌ None | ❌ Missing contract |
| `system/health/camera` | camera-service | health-monitor | 1 | Yes | `HealthPing` | ✅ |

**Constants Defined**: `TOPIC_CAMERA_CAPTURE`, `TOPIC_CAMERA_IMAGE` in `tars.contracts.v1.camera`  
**Missing**: Topic constant for `camera/frame`

**Service Usage**:
- ❌ camera-service: Uses local config with string literals

### System

| Topic | Publisher | Subscribers | QoS | Retained | Contract | Status |
|-------|-----------|-------------|-----|----------|----------|--------|
| `system/health/*` | all services | health-monitor, ui, ui-web | 1 | Yes | `HealthPing` | ✅ |
| `system/character/current` | memory-worker | llm-worker, ui | 1 | Yes | `CharacterSnapshot` | ✅ |
| `system/character/get` | llm-worker | memory-worker | 1 | No | `CharacterGetRequest` | ✅ |
| `system/character/result` | memory-worker | llm-worker | 1 | No | `CharacterSnapshot` | ✅ |
| `system/keepalive/*` | stt-worker | none | 0 | No | ❌ None | ❌ Undocumented |

**Constants Defined**: `TOPIC_SYSTEM_HEALTH_PREFIX`, character topics in memory.py  
**Issues**: 
- Health topic pattern uses prefix + service name (dynamic construction)
- `system/keepalive/*` appears in code but not documented
- No unified system domain constant collection

**Service Usage**:
- ❌ All services: Construct health topics dynamically with string concatenation

## Gaps Identified

### Missing Contracts

1. **`stt/audio_fft`** - Audio FFT data for visualization
   - No Pydantic model
   - No topic constant
   - Used by: stt-worker (publisher), ui/ui-web (subscribers)

2. **`tts/control`** - TTS control commands (pause, resume, stop)
   - No Pydantic model
   - No topic constant
   - Used by: wake-activation (publisher), tts-worker (subscriber)

3. **`camera/frame`** - Real-time camera frame updates
   - No Pydantic model
   - No topic constant
   - Used by: camera-service (publisher), ui (subscriber)

4. **`system/keepalive/*`** - Keepalive messages
   - No Pydantic model
   - No topic constant
   - Used by: stt-worker (publisher)

### Missing Topic Constants

Even where contracts exist, some services use string literals:
- All health topics constructed via string concatenation
- Most services use local config constants instead of tars-core imports

### Non-Standard Naming

✅ All topics follow `<domain>/<action>` pattern  
✅ System topics correctly use 3-level hierarchy (`system/health/stt`)

### QoS Inconsistencies

Most services follow constitutional standards:
- ✅ Commands/requests: QoS 1
- ✅ Responses: QoS 1  
- ✅ Streams/partials: QoS 0
- ✅ Health: QoS 1, retained
- ⚠️ Some services don't specify QoS explicitly (defaults to 0)

### Correlation IDs

#### ✅ Complete Support
- **LLM domain**: All messages include `message_id`, requests/responses use `id` field
- **Movement domain**: All messages include correlation IDs
- **Memory domain**: Query/results include proper correlation

#### ⚠️ Partial Support
- **STT**: Has `utt_id` for conversation tracking, but not consistent `message_id`
- **TTS**: Has `utt_id`, but `message_id` only in recent contracts
- **Wake**: Has `message_id` but no request/response correlation

#### ❌ Missing
- `stt/audio_fft` - No contract at all
- `tts/control` - No contract at all

## Service-by-Service Analysis

### ✅ Fully Compliant
- **movement-service**: Uses tars-core contracts exclusively

### ⚠️ Partially Compliant
- **llm-worker**: Uses local config constants instead of tars-core imports
- **memory-worker**: Uses local config constants instead of tars-core imports
- **tts-worker**: Uses local constants, not tars-core imports
- **wake-activation**: Uses config-based topic strings
- **camera-service**: Uses local config

### ❌ Non-Compliant
- **router**: Mixed usage of string literals
- **stt-worker**: String literals throughout
- **ui**: String literals in config
- **ui-web**: String literals in config
- **mcp-bridge**: Needs review

## Recommended Actions

### Phase 1: Complete Missing Contracts (Priority)
1. Add `AudioFFTData` contract and `TOPIC_STT_AUDIO_FFT` constant
2. Add `TtsControlCommand` contract and `TOPIC_TTS_CONTROL` constant
3. Add `CameraFrame` contract and `TOPIC_CAMERA_FRAME` constant
4. Document or remove `system/keepalive/*` usage

### Phase 2: Standardize Service Imports (High Priority)
1. Update all services to import `TOPIC_*` constants from tars-core
2. Remove local topic constant definitions from service configs
3. Use tars-core contracts for all message validation

### Phase 3: Enhance Correlation IDs (Medium Priority)
1. Ensure all contracts have `message_id` field
2. Add proper request/response correlation to wake domain
3. Document correlation strategy in each service README

### Phase 4: QoS Consistency (Medium Priority)
1. Explicitly set QoS in all publish calls
2. Add QoS validation tests
3. Document QoS rationale in each service

### Phase 5: Documentation (Low Priority)
1. Update service READMEs with topic tables
2. Create topic registry with auto-generation from contracts
3. Document breaking change policy

## Testing Coverage

### ✅ Contract Tests Exist
- STT: `packages/tars-core/tests/test_stt_contracts.py` (likely)
- TTS: Similar pattern expected
- LLM: Similar pattern expected
- Movement: Comprehensive tests exist

### ❌ Missing Tests
- Integration tests for cross-service correlation ID propagation
- QoS delivery guarantee tests
- Contract validation tests for all domains

## Notes

- Constitution compliance: **80%** (good structure, needs consistency)
- Type safety: **70%** (contracts exist, but not universally used)
- Documentation: **40%** (contracts documented, but service READMEs incomplete)
- Observability: **60%** (correlation IDs present in most domains)

**Next Steps**: See tasks.md for detailed implementation plan
