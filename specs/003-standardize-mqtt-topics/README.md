# Spec 003: Standardize MQTT Topics

**Status**: In Progress  
**Created**: 2025-10-16  
**Owner**: Infrastructure Team

## Quick Links

- **[Plan](plan.md)**: High-level phases and objectives
- **[Specification](spec.md)**: Detailed technical standards
- **[Tasks](tasks.md)**: Breakdown of 122 implementation tasks
- **[Topic Inventory](topic-inventory.md)**: Complete audit of all MQTT topics
- **[Migration Guide](migration-guide.md)**: Step-by-step service migration

## Overview

This specification establishes and enforces standardized MQTT topic naming conventions, message contracts, and communication patterns across all py-tars services, implementing the Event-Driven Architecture principles from the constitution.

## Goals

1. **Standardize Topic Naming**: All topics follow `<domain>/<action>` pattern
2. **Complete Contract Coverage**: 100% of topics have Pydantic v2 models in tars-core
3. **Document Topic Registry**: Single source of truth for all MQTT topics
4. **Enforce QoS Standards**: Apply constitutional QoS/retention policies
5. **Enable Observability**: Correlation IDs and structured logging throughout

## Progress

### ✅ Completed

- [x] Phase 1: Audit current MQTT topics (28 topics inventoried)
- [x] Phase 2A: Add topic constants to existing contracts (22 constants added)
- [x] Phase 2B: Create camera contracts (3 models, 24 tests passing)
- [x] Update tars-core exports for all new constants

### 🚧 In Progress

- [ ] Phase 3: Update services to use topic constants
  - [ ] Router (priority 1 - core service)
  - [ ] stt-worker, tts-worker, llm-worker (priority 1)
  - [ ] wake-activation, memory-worker, camera-service, mcp-bridge (priority 2)
  - [ ] ui, ui-web (priority 3)

### 📋 Pending

- [ ] Phase 4: Integration testing and documentation
  - [ ] Cross-service integration tests
  - [ ] QoS verification
  - [ ] Service README updates
  - [ ] Completion report

## Key Decisions

### Topic Naming Convention

**Pattern**: `<domain>/<action_or_event>`

Examples:
- Commands: `tts/say`, `llm/request`, `memory/query`
- Events: `stt/final`, `wake/event`, `tts/status`
- System: `system/health/<service>`, `system/character/current`

### QoS & Retention

Per constitution:
- **Health**: QoS 1, retained
- **Commands/Requests**: QoS 1, not retained
- **Responses**: QoS 1, not retained
- **Streaming/Partials**: QoS 0, not retained

### Correlation Strategy

- `message_id`: Unique ID for this message (all messages)
- `request_id`: Links response to request (request/response pairs)
- `utt_id`: Utterance ID for conversations (STT → LLM → TTS flow)

## Impact Summary

### Before Standardization

- Topics hardcoded as strings throughout codebase
- Some contracts missing or incomplete
- Inconsistent QoS levels
- Limited correlation ID usage
- Hard to discover available topics

### After Standardization

- All topics defined as constants in tars-core
- 100% contract coverage with validation
- Constitutional QoS standards enforced
- Full correlation ID support
- Complete topic registry documentation

## Files in This Spec

| File | Purpose | Status |
|------|---------|--------|
| [README.md](README.md) | This file - overview and navigation | ✅ Complete |
| [plan.md](plan.md) | High-level phases, goals, success criteria | ✅ Complete |
| [spec.md](spec.md) | Detailed technical specifications | ✅ Complete |
| [tasks.md](tasks.md) | 122 implementation tasks by phase | ✅ Complete |
| [topic-inventory.md](topic-inventory.md) | Complete topic audit and gap analysis | ✅ Complete |
| [migration-guide.md](migration-guide.md) | Step-by-step migration instructions | ✅ Complete |
| COMPLETION_REPORT.md | Final report (created at Phase 4 completion) | 📋 Pending |

## Quick Start for Developers

### For New Services

When creating a new service:

1. Use topic constants from tars-core:
   ```python
   from tars.contracts.v1.stt import TOPIC_STT_FINAL, FinalTranscript
   ```

2. Validate all incoming messages:
   ```python
   try:
       msg = FinalTranscript.model_validate_json(payload)
   except ValidationError as e:
       logger.error(f"Invalid message: {e}")
       return
   ```

3. Add correlation IDs to all messages
4. Use constitutional QoS levels
5. Include structured logging with correlation fields

See [migration-guide.md](migration-guide.md) for complete examples.

### For Migrating Existing Services

Follow the [migration-guide.md](migration-guide.md) checklist:

1. Import topic constants (replace string literals)
2. Import contract models (replace dict parsing)
3. Add correlation IDs
4. Update logging
5. Set correct QoS
6. Update tests
7. Run `make check`

## Reference Implementation

The **movement domain** is fully standardized and serves as the reference:

- ✅ All topics have constants in `movement.py`
- ✅ All contracts complete with validation
- ✅ Comprehensive tests (42/42 passing)
- ✅ Dual architecture documented (frame-based + command-based)
- ✅ QoS levels per constitution
- ✅ Full correlation ID support

See: `/packages/tars-core/src/tars/contracts/v1/movement.py`

## Architecture Context

This spec implements:

- **Constitution Section I**: Event-Driven Architecture (NON-NEGOTIABLE)
- **Constitution Section II**: Typed Contracts (NON-NEGOTIABLE)
- **Constitution "MQTT Contract Standards"**: Topic design, QoS, retention, idempotency

All changes maintain backward compatibility during migration.

## Timeline

- **Week 1** (Phase 1): Audit and documentation ✅ COMPLETE
- **Week 2** (Phase 2): Contract completion ✅ COMPLETE
- **Week 3** (Phase 3): Service updates 🚧 IN PROGRESS
- **Week 4** (Phase 4): Integration tests and docs 📋 PENDING

## Questions?

- Review the [specification](spec.md) for technical details
- Check the [topic inventory](topic-inventory.md) for current state
- Follow the [migration guide](migration-guide.md) for implementation
- See the constitution for architectural principles

## Version History

- **1.0.0** (2025-10-16): Initial specification structure created
- **1.1.0** (2025-10-16): Phase 1 audit complete, Phase 2 contracts complete
