# Implementation Plan: Remote Microphone Interface

**Branch**: `006-remote-mic` | **Date**: 2025-11-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-remote-mic/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Create a separate Docker Compose configuration that deploys only wake-activation and stt-worker services on a Radxa Zero 3W device with USB-C microphone. The remote microphone connects to the main TARS system's MQTT broker over the network, enabling physical separation of audio input from processing. Configuration uses `.env` file for MQTT broker host/port. Initial implementation supports single remote device with automatic reconnection on network loss.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: asyncio-mqtt, paho-mqtt, pydantic, openwakeword, faster-whisper, pyaudio, webrtcvad  
**Storage**: N/A (stateless services forwarding events to MQTT)  
**Testing**: pytest, pytest-asyncio (contract tests for MQTT messages, integration tests for service startup/connection)  
**Target Platform**: Linux ARM64 (Radxa Zero 3W - RK3588S SoC)  
**Project Type**: Monorepo with Docker Compose deployment profile  
**Performance Goals**: 
  - Wake word detection latency within 200ms of local deployment
  - Audio processing at 16kHz sample rate with minimal CPU usage
  - Reconnection to MQTT broker within 5 seconds of network restoration  
**Constraints**: 
  - <1GB RAM total for both services (resource-constrained device)
  - <50% average CPU during normal operation
  - <10% CPU idle when no voice activity
  - Must use existing audio fanout socket mechanism (/tmp/tars/audio-fanout.sock)  
**Scale/Scope**: Single remote microphone device (1 Radxa Zero 3W), 2 services (wake-activation + stt-worker)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Event-Driven Architecture** | ✅ PASS | Services communicate exclusively via MQTT; no direct calls; reuses existing Pydantic contracts from tars-core |
| **II. Typed Contracts** | ✅ PASS | Reuses existing WakeEvent, FinalTranscript, HealthPing contracts; no new contracts needed |
| **III. Async-First Concurrency** | ✅ PASS | Both services already async-first with asyncio.to_thread() for CPU work; no changes to concurrency model |
| **IV. Test-First Development** | ✅ PASS | Will add contract tests for remote deployment scenarios; integration tests for MQTT connection/reconnection |
| **V. Configuration via Environment** | ✅ PASS | Uses .env file with MQTT_HOST/MQTT_PORT; follows 12-factor pattern |
| **VI. Observability & Health Monitoring** | ✅ PASS | Services already publish to system/health/* topics; logs MQTT connect/disconnect, audio device status, detections |
| **VII. Simplicity & YAGNI** | ✅ PASS | Minimal change: new Docker Compose file + env var overrides; no new abstractions or services |
| **MQTT Contract Standards** | ✅ PASS | No new topics or contracts; uses existing wake/event, stt/final, system/health/* |
| **Docker Build System** | ✅ PASS | Reuses existing specialized Dockerfiles (wake-activation.Dockerfile, stt-worker.Dockerfile) |

**Overall**: ✅ **PASS** - No constitution violations. Feature reuses existing services and contracts with only deployment configuration changes.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
ops/
├── compose.yml                          # [EXISTING] Main TARS stack
├── compose.npu.yml                      # [EXISTING] NPU overrides for main stack
├── compose.remote-mic.yml               # [NEW] Remote microphone deployment
└── .env.remote-mic.example              # [NEW] Example config for remote device

apps/
├── wake-activation/                     # [EXISTING] No code changes
│   ├── src/wake_activation/
│   ├── Dockerfile → docker/specialized/wake-activation.Dockerfile
│   └── pyproject.toml
└── stt-worker/                          # [EXISTING] No code changes
    ├── src/stt_worker/
    ├── Dockerfile → docker/specialized/stt-worker.Dockerfile
    └── pyproject.toml

docker/
└── specialized/
    ├── wake-activation.Dockerfile       # [EXISTING] No changes
    └── stt-worker.Dockerfile            # [EXISTING] No changes

docs/
└── REMOTE_MICROPHONE_SETUP.md           # [NEW] Deployment guide

tests/
└── remote-mic/                          # [NEW] Remote deployment tests
    ├── test_remote_deployment.py        # Compose stack validation
    └── test_mqtt_connection.py          # Remote MQTT connectivity tests
```

**Structure Decision**: This is a **deployment configuration feature**, not a new service. All code changes are in `ops/` (new compose file + env example) and `docs/` (deployment guide). Existing wake-activation and stt-worker services are reused without modification. Tests focus on deployment and connectivity validation.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

N/A - No constitution violations. This feature adds minimal complexity (one new compose file) and follows all existing patterns.
