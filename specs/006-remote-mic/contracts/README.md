# MQTT Contracts: Remote Microphone Interface

**Feature**: 006-remote-mic | **Date**: 2025-11-02

## Overview

This feature **does not introduce new MQTT contracts**. It reuses existing contracts from `tars-core` package. This document lists the contracts relevant to remote microphone operation for reference.

---

## Contracts Used

All contracts are defined in `packages/tars-core/src/tars/contracts/v1/` and imported by services.

### Published by Remote Services

#### 1. WakeEvent
- **Topic**: `wake/event`
- **Publisher**: wake-activation (remote)
- **Contract**: `tars.contracts.v1.WakeEvent`
- **File**: `packages/tars-core/src/tars/contracts/v1/wake.py`
- **No changes needed**

#### 2. FinalTranscript
- **Topic**: `stt/final`
- **Publisher**: stt-worker (remote)
- **Contract**: `tars.contracts.v1.FinalTranscript`
- **File**: `packages/tars-core/src/tars/contracts/v1/stt.py`
- **No changes needed**

#### 3. HealthPing
- **Topics**: `system/health/wake-activation`, `system/health/stt`
- **Publishers**: wake-activation, stt-worker (remote)
- **Contract**: `tars.contracts.v1.HealthPing`
- **File**: `packages/tars-core/src/tars/contracts/v1/health.py`
- **No changes needed**

### Subscribed by Remote Services

#### 4. WakeMicCommand
- **Topic**: `wake/mic`
- **Subscriber**: wake-activation (remote)
- **Publisher**: router (main system)
- **Contract**: `tars.contracts.v1.WakeMicCommand`
- **File**: `packages/tars-core/src/tars/contracts/v1/wake.py`
- **No changes needed**

#### 5. TtsStatus
- **Topic**: `tts/status`
- **Subscriber**: wake-activation (remote)
- **Publisher**: tts-worker (main system)
- **Contract**: `tars.contracts.v1.TtsStatus`
- **File**: `packages/tars-core/src/tars/contracts/v1/tts.py`
- **No changes needed**

---

## Contract Testing

### Existing Tests

All contracts have existing tests in `packages/tars-core/tests/`:
- Serialization/deserialization round-trip tests
- Validation tests (required fields, type checking, extra fields forbidden)
- Example message tests

### New Tests Required

Add integration tests in `tests/remote-mic/`:

1. **test_mqtt_connection.py**: Verify remote services can connect to main MQTT broker
2. **test_remote_contracts.py**: Validate messages published from remote match expected schemas
3. **test_reconnection.py**: Verify reconnection behavior preserves contract compliance

---

## Contract Compatibility

**Critical**: Remote device MUST run same version of `tars-core` as main system to ensure contract compatibility.

**Deployment Process**:
1. Update main TARS system to latest version
2. Git pull on remote device to match version
3. Rebuild remote containers: `docker compose -f ops/compose.remote-mic.yml build`
4. Restart remote services: `docker compose -f ops/compose.remote-mic.yml up -d`

**Version Mismatch Handling**:
- Pydantic validation will catch schema mismatches and log errors
- Services will fail fast on invalid messages (per constitution)
- Operator should check logs for validation errors after updates

---

## No New Contracts Justification

This feature does not require new MQTT contracts because:

1. **Wake detection**: Remote wake-activation publishes same WakeEvent as local deployment
2. **Transcription**: Remote stt-worker publishes same FinalTranscript as local deployment
3. **Health monitoring**: Both services use existing HealthPing contract
4. **Coordination**: Remote wake-activation subscribes to existing WakeMicCommand and TtsStatus

The remote/local distinction is a **deployment detail**, not a semantic difference requiring different message schemas.

---

## References

- **Contract Definitions**: `packages/tars-core/src/tars/contracts/v1/`
- **Contract Documentation**: `docs/mqtt-contracts.md`
- **Contract Tests**: `packages/tars-core/tests/`
- **Constitution**: `.specify/memory/constitution.md` (Section II: Typed Contracts)
