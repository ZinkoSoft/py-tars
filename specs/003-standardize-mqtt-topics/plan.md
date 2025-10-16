# Spec 003: Standardize MQTT Topics

**Status**: Active  
**Created**: 2025-10-16  
**Owner**: Infrastructure Team  
**Priority**: High

## Executive Summary

Establish and enforce standardized MQTT topic naming conventions, message contracts, and communication patterns across all py-tars services. This specification ensures consistent, type-safe, and maintainable message-based communication following the constitution's Event-Driven Architecture principles.

## Problem Statement

### Current State Issues

1. **Inconsistent Topic Naming**: Some topics use `snake_case`, others use different patterns
2. **Missing Topic Constants**: Not all topics have constants defined in tars-core contracts
3. **Incomplete Documentation**: Topic ownership and message schemas not fully documented
4. **QoS Inconsistency**: QoS levels and retention policies not consistently applied
5. **Missing Contracts**: Some MQTT messages lack Pydantic v2 models with validation

### Impact

- Difficult to discover available topics and their purposes
- Type safety violations when contracts are missing
- Inconsistent behavior across services
- Hard to evolve message formats without breaking changes
- Debugging challenges without standardized correlation IDs

## Goals

### Primary Objectives

1. **Standardize Topic Naming**: Define and enforce consistent naming patterns
2. **Complete Contract Coverage**: All topics have Pydantic v2 models in tars-core
3. **Document Topic Registry**: Single source of truth for all MQTT topics
4. **Enforce QoS Standards**: Apply constitutional QoS/retention policies
5. **Enable Observability**: Correlation IDs and structured logging

### Success Criteria

- ✅ All topics follow `<domain>/<action>` or `<domain>/<event>` pattern
- ✅ 100% of topics have Pydantic v2 contracts in tars-core
- ✅ Topic registry documents all publishers/subscribers
- ✅ QoS levels match constitutional standards
- ✅ All messages include correlation IDs for tracing
- ✅ Breaking change policy documented and enforced

## Current Topic Inventory

### System Topics

| Topic | Publisher | Subscriber | QoS | Retained | Contract |
|-------|-----------|------------|-----|----------|----------|
| `system/health/*` | All services | Health monitor | 1 | Yes | health.HealthPing |
| `system/character/current` | memory-worker | Router, UI | 1 | Yes | TBD |

### STT (Speech-to-Text) Topics

| Topic | Publisher | Subscriber | QoS | Retained | Contract |
|-------|-----------|------------|-----|----------|----------|
| `stt/final` | stt-worker | Router | 1 | No | stt.STTFinalTranscript |
| `stt/partial` | stt-worker | UI | 0 | No | stt.STTPartialTranscript |

### LLM (Language Model) Topics

| Topic | Publisher | Subscriber | QoS | Retained | Contract |
|-------|-----------|------------|-----|----------|----------|
| `llm/request` | Router | llm-worker | 1 | No | llm.LLMRequest |
| `llm/response` | llm-worker | Router | 1 | No | llm.LLMResponse |
| `llm/stream` | llm-worker | Router | 0 | No | llm.LLMStreamDelta |
| `llm/cancel` | Router | llm-worker | 1 | No | llm.LLMCancel |

### TTS (Text-to-Speech) Topics

| Topic | Publisher | Subscriber | QoS | Retained | Contract |
|-------|-----------|------------|-----|----------|----------|
| `tts/say` | Router | tts-worker | 1 | No | tts.TTSSayRequest |
| `tts/status` | tts-worker | Router, UI | 0 | No | tts.TTSStatusUpdate |

### Wake Word Topics

| Topic | Publisher | Subscriber | QoS | Retained | Contract |
|-------|-----------|------------|-----|----------|----------|
| `wake/event` | wake-activation | Router | 1 | No | wake.WakeEvent |

### Memory Topics

| Topic | Publisher | Subscriber | QoS | Retained | Contract |
|-------|-----------|------------|-----|----------|----------|
| `memory/query` | Router | memory-worker | 1 | No | memory.MemoryQuery |
| `memory/results` | memory-worker | Router | 1 | No | memory.MemoryResults |

### Movement Topics

| Topic | Publisher | Subscriber | QoS | Retained | Contract |
|-------|-----------|------------|-----|----------|----------|
| `movement/command` | External | movement-service | 1 | No | movement.MovementCommand |
| `movement/frame` | movement-service | ESP32 | 1 | No | movement.MovementFrame |
| `movement/state` | movement-service | External | 0 | No | movement.MovementState |
| `movement/test` | Router | ESP32 | 1 | No | movement.TestMovementRequest |
| `movement/stop` | Router | ESP32 | 1 | No | movement.EmergencyStopCommand |
| `movement/status` | ESP32 | Router, UI | 0 | No | movement.MovementStatusUpdate |

### Camera Topics

| Topic | Publisher | Subscriber | QoS | Retained | Contract |
|-------|-----------|------------|-----|----------|----------|
| `camera/image` | camera-service | MCP bridge | 1 | No | TBD |
| `camera/capture` | MCP bridge | camera-service | 1 | No | TBD |

### MCP (Model Context Protocol) Topics

| Topic | Publisher | Subscriber | QoS | Retained | Contract |
|-------|-----------|------------|-----|----------|----------|
| `mcp/request` | llm-worker | mcp-bridge | 1 | No | mcp.MCPRequest |
| `mcp/response` | mcp-bridge | llm-worker | 1 | No | mcp.MCPResponse |

## Standardization Requirements

### Topic Naming Convention

**Pattern**: `<domain>/<action_or_event>`

- **Domain**: Service/feature area (e.g., `stt`, `tts`, `llm`, `movement`)
- **Action**: Command/request (e.g., `say`, `request`, `query`)
- **Event**: State change/notification (e.g., `final`, `status`, `event`)

**Rules**:
- Use lowercase with underscores for multi-word domains
- Keep topic depth to 2 levels (domain/action) for simplicity
- Exception: `system/*` topics may have 3 levels (e.g., `system/health/router`)
- Avoid versioning in topic names; use schema evolution instead

### Message Contract Requirements

All MQTT messages MUST have Pydantic v2 models with:
- `ConfigDict(extra="forbid")` to reject unknown fields
- Complete type annotations (no `Any` without justification)
- Correlation ID fields: `message_id`, `request_id`, `utt_id` as appropriate
- Timestamp field with default factory
- Field validation constraints where applicable
- Docstrings explaining purpose and usage

### QoS and Retention Standards

Per constitution section "MQTT Contract Standards":

1. **Health topics** (`system/health/*`):
   - QoS: 1 (at least once delivery)
   - Retained: Yes (latest status persists)

2. **Commands/Requests**:
   - QoS: 1 (at least once delivery)
   - Retained: No

3. **Responses**:
   - QoS: 1 (at least once delivery)
   - Retained: No

4. **Streaming/Partials**:
   - QoS: 0 (best effort)
   - Retained: No

### Correlation ID Strategy

Every message MUST include appropriate correlation fields:

- **`message_id`**: Unique identifier for this specific message (UUID)
- **`request_id`**: Links response to originating request
- **`utt_id`**: Utterance ID for conversation tracking (STT → LLM → TTS flow)

## Implementation Phases

### Phase 1: Audit and Documentation (Week 1)

1. ✅ Inventory all existing MQTT topics across codebase
2. ✅ Document current publishers and subscribers
3. ✅ Identify topics missing contracts
4. ✅ Identify topics with non-standard naming
5. ✅ Identify QoS/retention mismatches

### Phase 2: Contract Completion (Week 2)

1. Add missing topic constants to tars-core contracts
2. Create Pydantic models for topics lacking contracts
3. Add validation tests for all contracts
4. Update services to use topic constants (not string literals)
5. Add correlation ID fields where missing

### Phase 3: Service Updates (Week 3)

1. Update all services to import contracts from tars-core
2. Standardize QoS levels per constitution
3. Add correlation ID tracking in all message handlers
4. Update logging to include correlation IDs
5. Ensure proper error handling for validation failures

### Phase 4: Documentation and Testing (Week 4)

1. Create comprehensive topic registry
2. Document breaking change policy
3. Add integration tests for cross-service flows
4. Update service READMEs with topic documentation
5. Create migration guide for future topic changes

## Breaking Change Policy

When topic changes are unavoidable:

1. **Create parallel topic** (e.g., `llm/request/v2`)
2. **Document migration plan** in spec directory
3. **Set deprecation timeline** (minimum 2 sprint cycles)
4. **Update all services** before removing old topic
5. **Announce in team channels** with migration guide

Prefer schema evolution over breaking changes:
- Add optional fields (backward compatible)
- Use discriminated unions for variants
- Version message schemas internally, not in topics

## Migration Strategy

### Backward Compatibility

All changes must be non-breaking:
- Existing topics continue to work
- New contracts are additive
- Services adopt gradually
- Validation errors logged but not fatal initially

### Rollout Plan

1. **Week 1**: Complete audit and create missing contracts
2. **Week 2**: Update core services (router, stt, tts, llm)
3. **Week 3**: Update remaining services (memory, movement, camera, mcp)
4. **Week 4**: Enable strict validation and finalize docs

### Rollback Strategy

If issues arise:
- Contracts are opt-in via imports
- Services can temporarily use raw dict parsing
- Validation can be disabled via environment variable
- Easy to revert individual service updates

## Testing Strategy

### Contract Tests

- Test all Pydantic models (valid/invalid cases)
- Test JSON serialization round-trips
- Test field constraints and validation
- Test extra field rejection

### Integration Tests

- Test cross-service message flows (e.g., STT → Router → LLM → TTS)
- Test correlation ID propagation
- Test error handling for malformed messages
- Test QoS delivery guarantees

### Regression Tests

- Ensure existing functionality unchanged
- Test backward compatibility
- Verify no message loss during migration

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing services | HIGH | Phased rollout, backward compatibility |
| Performance impact from validation | LOW | Pydantic is fast; benchmark before/after |
| Contract versioning complexity | MEDIUM | Prefer schema evolution over versioning |
| Team adoption challenges | MEDIUM | Clear documentation, examples, support |

## Success Metrics

- ✅ 100% of topics have documented contracts
- ✅ 100% of topics follow naming convention
- ✅ 100% of messages include correlation IDs
- ✅ Zero breaking changes to existing services
- ✅ All integration tests passing
- ✅ Topic registry complete and accurate

## References

- Constitution: `/.specify/memory/constitution.md`
- MQTT Contracts Plan: `/plan/mqtt-contracts-refactor.md`
- MQTT Contracts Complete: `/plan/mqtt-contracts-refactor-COMPLETE.md`
- tars-core Contracts: `/packages/tars-core/src/tars/contracts/v1/`

## Version History

- **1.0.0** (2025-10-16): Initial specification
