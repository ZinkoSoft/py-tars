# Research: Remote Microphone Interface

**Feature**: 006-remote-mic | **Date**: 2025-11-02

## Overview

This document captures research decisions for deploying wake-activation and stt-worker services on a remote Radxa Zero 3W device that connects to the main TARS system via MQTT.

## Research Questions & Decisions

### 1. Docker Compose Profiles vs Separate Compose File

**Question**: Should remote microphone deployment use Docker Compose profiles or a separate compose file?

**Decision**: **Separate compose file** (`compose.remote-mic.yml`)

**Rationale**:
- **Clarity**: Separate file makes it obvious this is a different deployment target
- **Independence**: Remote device doesn't need the full compose.yml with 10+ unused services
- **Configuration isolation**: Remote device can have its own .env without conflicting with main system
- **Simpler mental model**: `docker compose -f ops/compose.remote-mic.yml up` is clearer than managing profiles
- **Precedent**: Project already uses this pattern with `compose.npu.yml` for NPU overrides

**Alternatives Considered**:
- Docker Compose profiles: More complex to document; requires understanding profile system; harder to isolate configs
- Single compose file with all services: Remote device would need to explicitly exclude 10+ services; wasteful

**References**:
- Existing pattern in `ops/compose.yml` and `ops/compose.npu.yml`
- Docker Compose best practices for multi-environment deployments

---

### 2. MQTT Broker Network Configuration

**Question**: How should the MQTT broker be configured to accept remote connections while maintaining security?

**Decision**: **Bind to 0.0.0.0:1883 with anonymous authentication initially**

**Rationale**:
- **Immediate functionality**: Anonymous auth removes authentication barrier for MVP
- **Network exposure**: Binding to 0.0.0.0 allows LAN connections (already in current mosquitto.conf)
- **Incremental security**: Future enhancement can add username/password or TLS without breaking contract
- **Alignment with spec**: Spec explicitly states "anonymous authentication is sufficient for initial implementation"
- **Existing pattern**: Current `ops/mosquitto.conf` already uses `allow_anonymous true`

**Implementation**:
- Verify `ops/mosquitto.conf` listener is `0.0.0.0:1883` (current: `listener 1883 0.0.0.0` ✓)
- Document security consideration in deployment guide
- Add to "Out of Scope": Authentication is future enhancement

**Alternatives Considered**:
- Username/password auth: Adds complexity to MVP; requires credential management; can be added later
- TLS/mTLS: Overkill for local network; significant setup complexity; future enhancement
- IP whitelisting: Fragile (DHCP changes); adds configuration burden

**Security Implications**:
- Risk: Any device on LAN can connect to MQTT broker
- Mitigation: Deployment is local network only (per spec); physical network security assumed
- Future: Add authentication as separate feature when multi-user scenarios arise

---

### 3. Audio Fanout Socket Sharing

**Question**: How do wake-activation and stt-worker share audio data on the remote device?

**Decision**: **Reuse existing audio fanout socket mechanism** (`/tmp/tars/audio-fanout.sock`)

**Rationale**:
- **No code changes**: Both services already implement this pattern
- **Proven solution**: Works in main deployment; tested and reliable
- **Minimal overhead**: Unix domain socket is efficient for local IPC
- **Dependency ordering**: docker-compose `depends_on` with healthcheck ensures socket exists before wake-activation starts

**Implementation**:
- Mount shared volume `wake-cache:/tmp/tars` on both containers
- STT service creates socket via healthcheck validation
- Wake-activation waits for STT to be healthy before starting
- Same pattern as main `ops/compose.yml`

**Alternatives Considered**:
- Separate audio capture in each service: Duplicates resource usage; 2x CPU for audio capture; hardware conflicts
- Network streaming (RTP/WebRTC): Massive overkill; adds latency; requires new code
- Named pipes: Less flexible than Unix socket; no bidirectional communication if needed later

---

### 4. Environment Variable Strategy

**Question**: What environment variables need remote-specific values?

**Decision**: **Override MQTT_HOST and MQTT_PORT; inherit others from .env**

**Required Overrides** (remote-specific):
```bash
MQTT_HOST=192.168.1.100          # Main TARS system IP
MQTT_PORT=1883                   # MQTT broker port
```

**Inherited from .env** (same as main system):
```bash
LOG_LEVEL=INFO
AUDIO_DEVICE_NAME=                        # Auto-detect or specify USB-C mic
WAKE_AUDIO_FANOUT=/tmp/tars/audio-fanout.sock
WAKE_MODEL_PATH=/models/openwakeword/hey_tars.tflite
WAKE_DETECTION_THRESHOLD=0.35
WHISPER_MODEL=small
SAMPLE_RATE=16000
# ... all other audio/processing settings
```

**Rationale**:
- **Minimal configuration**: Only network connection details differ
- **Consistency**: Audio processing settings should match main system for identical behavior
- **Simplicity**: Operator only needs to edit 2 variables (host + port)
- **Maintainability**: Audio tuning changes propagate from main .env.example

**Implementation**:
- Create `ops/.env.remote-mic.example` with MQTT_HOST/PORT placeholders + comments
- Document: Copy .env.remote-mic.example to .env, edit MQTT_HOST to main system IP

---

### 5. Service Dependencies and Startup Order

**Question**: What is the correct startup sequence for remote services?

**Decision**: **STT starts first → becomes healthy → wake-activation starts**

**Sequence**:
1. Docker Compose brings up both services
2. STT worker starts, initializes audio device, creates fanout socket
3. STT healthcheck validates socket exists and is connectable
4. Wake-activation starts only after STT is healthy (`depends_on: stt: condition: service_healthy`)
5. Wake-activation connects to audio fanout socket
6. Both services connect to remote MQTT broker (with retry/reconnect)

**Rationale**:
- **Audio fanout dependency**: Wake-activation consumes STT's audio stream; socket must exist first
- **Proven pattern**: Matches existing `ops/compose.yml` startup sequence
- **Graceful degradation**: If STT fails, wake-activation never starts (fail-fast)
- **Healthcheck validation**: Docker confirms socket is ready before starting consumer

**Implementation**:
- STT service defines healthcheck testing socket connectivity
- Wake-activation `depends_on` STT with `condition: service_healthy`
- Both services implement MQTT reconnection logic (already exists)

**Alternatives Considered**:
- Parallel startup with retry: Race conditions; wake-activation crashes before STT ready
- Startup script coordination: More complex; doesn't leverage Docker's built-in orchestration
- External orchestrator (k8s, systemd): Overkill for 2-service deployment

---

### 6. Network Disconnection Handling

**Question**: What specific behaviors are needed for network loss scenarios?

**Decision**: **Drop in-progress work, reconnect automatically, resume from clean state**

**Behaviors**:

| Scenario | Behavior |
|----------|----------|
| MQTT disconnect during idle | Log warning, attempt reconnect with exponential backoff (5s, 10s, 30s) |
| MQTT disconnect during wake detection | Drop current detection frame, reconnect, resume listening |
| MQTT disconnect during transcription | Drop partial transcription, reconnect, wait for next wake word |
| MQTT broker restart | Both services detect disconnect, reconnect automatically within 5s |
| Network partition | Services log repeated connection failures, continue retrying indefinitely |

**Rationale**:
- **Simplicity**: No queuing or buffering logic; clean failure semantics
- **Data integrity**: Prevents partial/corrupted events from reaching router
- **User experience**: User simply retries command after connectivity restores
- **Existing implementation**: Services already implement this pattern (per spec clarification)

**Implementation**:
- No code changes needed; existing asyncio-mqtt reconnection handles this
- Verify reconnection timeout is 5s (configurable via env if needed)
- Add logging for disconnect/reconnect events (already required per FR-015)

---

### 7. Deployment Verification Approach

**Question**: How does operator verify successful deployment?

**Decision**: **Use `docker compose ps` for service health + test with voice**

**Verification Steps**:
1. **Service health**: `docker compose ps` shows both services "running" or "healthy"
2. **Log confirmation**: `docker compose logs` shows "Connected to MQTT broker" from both services
3. **Voice test**: Speak wake word, verify logs show detection and transcription activity
4. **Optional MQTT verification**: Use mosquitto_sub to listen on wake/event topic

**Rationale**:
- **Progressive validation**: Operator can diagnose issues at each level
- **Standard Docker workflow**: Familiar to anyone using Docker Compose
- **Clear success criteria**: Service status + logs + functional test
- **No special tools required**: docker compose + voice is sufficient

**Implementation**:
- Document verification steps in REMOTE_MICROPHONE_SETUP.md
- Include example log output showing successful connection
- Provide troubleshooting section for common issues (wrong MQTT_HOST, firewall, audio device)

---

### 8. Logging Requirements

**Question**: What specific events need logging for troubleshooting?

**Decision**: **Log connection lifecycle, audio device status, detection events, errors**

**Required Log Events**:

| Event | Level | Example Message |
|-------|-------|-----------------|
| Service startup | INFO | `wake-activation starting (version 0.1.0)` |
| MQTT connection attempt | INFO | `Connecting to MQTT broker at 192.168.1.100:1883` |
| MQTT connection success | INFO | `Connected to MQTT broker at 192.168.1.100:1883` |
| MQTT connection failure | ERROR | `Failed to connect to MQTT broker: Connection refused` |
| MQTT disconnection | WARNING | `Disconnected from MQTT broker, attempting reconnect...` |
| MQTT reconnection | INFO | `Reconnected to MQTT broker after 5.2s` |
| Audio device init success | INFO | `Audio device initialized: USB Audio Device (16kHz, mono)` |
| Audio device init failure | ERROR | `Failed to initialize audio device: [Errno -9996] Invalid input device` |
| Wake word detection | INFO | `Wake word detected (score=0.87, word=hey_tars)` |
| Transcription start | DEBUG | `Starting transcription (utt_id=abc123)` |
| Transcription complete | INFO | `Transcription complete (utt_id=abc123, text="turn on the lights", duration=2.3s)` |
| Errors with context | ERROR | `Error processing audio frame: [exception details + stack trace]` |

**Rationale**:
- **Operational visibility**: Logs provide enough detail to diagnose connectivity, audio, and processing issues
- **Troubleshooting workflow**: Operator can identify whether problem is network, audio device, or service logic
- **Performance insight**: Duration logging helps identify latency issues
- **Correlation**: utt_id links wake detection to transcription across logs

**Implementation**:
- Verify existing logging meets these requirements (likely already implemented)
- Add any missing events (MQTT connection lifecycle especially)
- Ensure LOG_LEVEL=INFO captures all required events

---

## Technology Stack Summary

| Component | Technology | Version | Notes |
|-----------|-----------|---------|-------|
| **Language** | Python | 3.11 | Monorepo standard |
| **MQTT Client** | asyncio-mqtt | 0.16.2+ | Async wrapper around paho-mqtt |
| **Message Format** | JSON | - | Via orjson for performance |
| **Validation** | Pydantic | 2.6.0+ | Typed contracts |
| **Wake Detection** | OpenWakeWord | 0.5.0+ | ML wake word model |
| **Speech-to-Text** | Faster Whisper | 1.0.3+ | Local transcription |
| **Audio Capture** | PyAudio | 0.2.14+ | ALSA audio interface |
| **VAD** | WebRTC VAD | 2.0.10+ | Voice activity detection |
| **Container Runtime** | Docker | 20.10+ | Deployment via compose |
| **Orchestration** | Docker Compose | 2.0+ | Service coordination |

---

## Open Questions

None - All research questions resolved through specification clarification session and existing codebase analysis.

---

## References

- **Existing Implementation**: `ops/compose.yml`, `apps/wake-activation/`, `apps/stt-worker/`
- **Constitution**: `.specify/memory/constitution.md`
- **MQTT Contracts**: `docs/mqtt-contracts.md`
- **Feature Spec**: `specs/006-remote-mic/spec.md`
- **Clarifications**: `specs/006-remote-mic/spec.md#clarifications`
