# Data Model: Remote Microphone Interface

**Feature**: 006-remote-mic | **Date**: 2025-11-02

## Overview

This feature is a **deployment configuration** change, not a data modeling change. It reuses existing MQTT message contracts without modification. This document captures the relevant entities and their relationships for completeness.

---

## Entities

### Remote Microphone Device

**Description**: Physical Radxa Zero 3W device running wake-activation and stt-worker services

**Attributes**:
- `device_hostname`: string - Hostname of the Radxa Zero 3W (for identification in logs)
- `mqtt_host`: string - IP address or hostname of main TARS system (configured in .env)
- `mqtt_port`: int - Port of MQTT broker on main system (default: 1883)
- `audio_device`: string - ALSA device identifier for USB-C microphone (optional, auto-detected)
- `deployment_type`: enum["main", "remote"] - Identifies deployment configuration

**Relationships**:
- Connects to → MQTT Broker (on main TARS system)
- Captures audio via → USB-C Microphone
- Publishes → Wake Events, Speech Transcriptions, Health Status

**State Transitions**:
```
[Stopped] → [Starting] → [Connected] → [Active]
                ↓             ↓           ↓
           [Failed]    [Disconnected] → [Reconnecting] → [Connected]
```

**Validation Rules**:
- `mqtt_host` must be valid IPv4 address or resolvable hostname
- `mqtt_port` must be in range 1-65535
- `audio_device` if specified must exist in system's audio device list

---

### MQTT Broker Connection

**Description**: Network connection between remote device and main TARS MQTT broker

**Attributes**:
- `broker_url`: string - Full MQTT URL (e.g., "mqtt://192.168.1.100:1883")
- `connection_state`: enum["disconnected", "connecting", "connected", "reconnecting"]
- `last_connected`: datetime - Timestamp of last successful connection
- `retry_count`: int - Number of reconnection attempts
- `retry_backoff`: float - Current backoff delay in seconds (5, 10, 30)

**Relationships**:
- Used by → wake-activation service, stt-worker service
- Connects to → Main TARS System MQTT Broker

**State Transitions**:
```
[Disconnected] → [Connecting] → [Connected]
      ↑              ↓               ↓
      └──[Reconnecting]←[Connection Lost]
```

**Validation Rules**:
- Connection timeout: 10 seconds
- Max retry backoff: 30 seconds
- Reconnection: Indefinite retries with exponential backoff

---

### Audio Fanout Socket

**Description**: Unix domain socket for sharing audio stream between services

**Attributes**:
- `socket_path`: string - Path to socket (default: "/tmp/tars/audio-fanout.sock")
- `owner_service`: enum["stt-worker"] - Service that creates the socket
- `consumer_services`: list[enum] - Services reading from socket (["wake-activation"])
- `sample_rate`: int - Audio sample rate in Hz (16000)
- `channels`: int - Number of audio channels (1 = mono)
- `format`: enum["int16"] - Audio sample format

**Relationships**:
- Created by → stt-worker service
- Consumed by → wake-activation service
- Located in → shared Docker volume (wake-cache)

**State Transitions**:
```
[Not Created] → [Creating] → [Ready] → [Active]
                    ↓           ↓         ↓
                [Failed]    [Failed]  [Closed] → [Not Created]
```

**Validation Rules**:
- Socket must be readable/writable by both services (shared volume permissions)
- Socket must exist before wake-activation starts (validated by healthcheck)
- If socket is removed, stt-worker recreates it on next audio frame

---

## MQTT Message Contracts

**Note**: No new contracts for this feature. All messages use existing schemas from `tars-core` package.

### WakeEvent

**Topic**: `wake/event`  
**Publisher**: wake-activation (on remote device)  
**Subscriber**: router (on main system)  
**QoS**: 1  
**Retained**: No

**Schema** (from `tars.contracts.v1.WakeEvent`):
```python
{
  "message_id": str,      # Auto-generated UUID
  "detected": bool,       # True when wake word detected
  "score": float | None,  # Confidence score (0.0-1.0)
  "wake_word": str | None, # Which wake word (e.g., "hey_tars")
  "timestamp": float      # Unix timestamp
}
```

**Example**:
```json
{
  "message_id": "wake-abc123",
  "detected": true,
  "score": 0.87,
  "wake_word": "hey_tars",
  "timestamp": 1730572800.5
}
```

---

### FinalTranscript

**Topic**: `stt/final`  
**Publisher**: stt-worker (on remote device)  
**Subscriber**: router (on main system)  
**QoS**: 1  
**Retained**: No

**Schema** (from `tars.contracts.v1.FinalTranscript`):
```python
{
  "message_id": str,       # Auto-generated UUID
  "text": str,             # Transcribed text
  "lang": str,             # Language code (default: "en")
  "confidence": float | None, # Confidence score
  "utt_id": str | None,    # Utterance ID for correlation
  "ts": float,             # Unix timestamp
  "is_final": bool         # Always true for final transcripts
}
```

**Example**:
```json
{
  "message_id": "stt-def456",
  "text": "turn on the lights",
  "lang": "en",
  "confidence": 0.95,
  "utt_id": "utt-789",
  "ts": 1730572802.3,
  "is_final": true
}
```

---

### HealthPing

**Topic**: `system/health/wake-activation`, `system/health/stt`  
**Publisher**: wake-activation, stt-worker (on remote device)  
**Subscriber**: monitoring systems (on main system)  
**QoS**: 1  
**Retained**: Yes

**Schema** (from `tars.contracts.v1.HealthPing`):
```python
{
  "ok": bool,         # Service is healthy
  "event": str        # "ready", "running", "error", etc.
}
```

**Examples**:
```json
{
  "ok": true,
  "event": "ready"
}
```

```json
{
  "ok": false,
  "event": "mqtt_disconnected"
}
```

---

### WakeMicCommand

**Topic**: `wake/mic`  
**Publisher**: router (on main system)  
**Subscriber**: wake-activation (on remote device)  
**QoS**: 1  
**Retained**: No

**Schema** (from `tars.contracts.v1.WakeMicCommand`):
```python
{
  "message_id": str,  # Auto-generated UUID
  "action": str       # "start", "stop", "pause", "resume"
}
```

**Example**:
```json
{
  "message_id": "mic-cmd-123",
  "action": "pause"
}
```

**Note**: Remote wake-activation service subscribes to this topic to coordinate with TTS playback on main system (pause listening during speech output).

---

### TtsStatus

**Topic**: `tts/status`  
**Publisher**: tts-worker (on main system)  
**Subscriber**: wake-activation (on remote device)  
**QoS**: 1  
**Retained**: No

**Schema** (from `tars.contracts.v1.TtsStatus`):
```python
{
  "message_id": str,    # Auto-generated UUID
  "event": str,         # "speaking_start", "speaking_end", "paused", "resumed", "stopped"
  "text": str,          # Text being spoken
  "timestamp": float,   # Unix timestamp
  "utt_id": str | None, # Utterance ID
  "reason": str | None, # For "stopped" events
  "wake_ack": bool | None,
  "system_announce": bool | None
}
```

**Example**:
```json
{
  "message_id": "tts-status-abc",
  "event": "speaking_start",
  "text": "Turning on the lights",
  "timestamp": 1730572803.0,
  "utt_id": "utt-789"
}
```

**Note**: Remote wake-activation service subscribes to coordinate listening state (typically pauses wake detection during TTS output).

---

## Configuration Model

### Environment Variables (.env)

**Remote-Specific Configuration**:
```bash
# Required: Main TARS system connection
MQTT_HOST=192.168.1.100              # IP or hostname of main TARS system
MQTT_PORT=1883                       # MQTT broker port

# Optional: Audio device selection
AUDIO_DEVICE_NAME=                   # Empty = auto-detect; specify for USB-C mic
```

**Inherited from Main System** (same values as main .env):
```bash
# Logging
LOG_LEVEL=INFO

# Audio Processing
SAMPLE_RATE=16000
CHUNK_DURATION_MS=20
VAD_AGGRESSIVENESS=3

# Wake Detection
WAKE_AUDIO_FANOUT=/tmp/tars/audio-fanout.sock
WAKE_MODEL_PATH=/models/openwakeword/hey_tars.tflite
WAKE_DETECTION_THRESHOLD=0.35
WAKE_MIN_RETRIGGER_SEC=0.8

# STT Processing
WHISPER_MODEL=small
SILENCE_THRESHOLD_MS=600
```

**Validation**:
- `MQTT_HOST` required, non-empty
- `MQTT_PORT` must be integer 1-65535
- All other variables optional with sensible defaults

---

## Docker Compose Configuration Model

### Service Definition (compose.remote-mic.yml)

**Services**:
1. **stt-worker**: Captures audio, runs VAD, performs transcription, publishes to MQTT
2. **wake-activation**: Consumes audio fanout, detects wake word, publishes to MQTT

**Shared Resources**:
- **Volume**: `wake-cache` → `/tmp/tars` (for audio fanout socket)
- **Network**: Default bridge network (no special networking needed)
- **Environment**: Loaded from `.env` file

**Dependencies**:
```
stt-worker (healthy) → wake-activation
   ↓
Audio Device → Audio Fanout Socket → Wake Detection
   ↓                    ↓
STT Processing    Wake Events → MQTT → Main TARS System
```

---

## Entity Relationship Diagram

```
┌─────────────────────┐
│  Radxa Zero 3W      │
│  (Remote Device)    │
└──────────┬──────────┘
           │
           │ USB-C
           ↓
┌─────────────────────┐
│  USB-C Microphone   │
└──────────┬──────────┘
           │
           │ ALSA
           ↓
┌─────────────────────┐       ┌──────────────────────┐
│   stt-worker        │──────→│  Audio Fanout Socket │
│   (Docker)          │create │  /tmp/tars/*.sock    │
└──────────┬──────────┘       └──────────┬───────────┘
           │                              │
           │ MQTT                         │ consume
           │ (network)                    ↓
           │                  ┌──────────────────────┐
           │                  │  wake-activation     │
           │                  │  (Docker)            │
           │                  └──────────┬───────────┘
           │                             │
           │                             │ MQTT
           │                             │ (network)
           ↓                             ↓
┌─────────────────────────────────────────────────────┐
│  Main TARS System                                   │
│                                                     │
│  ┌──────────────┐   ┌──────────────┐              │
│  │ MQTT Broker  │←──│   Router     │              │
│  └──────────────┘   └──────────────┘              │
│         ↓                  ↑                        │
│  ┌──────────────┐   ┌──────────────┐              │
│  │  TTS Worker  │   │  LLM Worker  │              │
│  └──────────────┘   └──────────────┘              │
└─────────────────────────────────────────────────────┘
```

---

## Data Flow

### Wake Word Detection Flow

1. **Audio Capture**: USB-C microphone → PyAudio → stt-worker
2. **Audio Sharing**: stt-worker → fanout socket → wake-activation
3. **Detection**: wake-activation processes audio frames, detects wake word
4. **Event Publishing**: wake-activation → MQTT (wake/event) → main TARS router
5. **Health Status**: Both services → MQTT (system/health/*) → monitoring

### Speech Transcription Flow

1. **Wake Detection**: Wake word detected (see above)
2. **Mic Control**: Router → MQTT (wake/mic "start") → wake-activation (mutes wake detection)
3. **Audio Capture**: USB-C microphone → PyAudio → stt-worker (continues capture)
4. **VAD**: stt-worker applies voice activity detection
5. **Transcription**: stt-worker runs Whisper on audio buffer
6. **Publishing**: stt-worker → MQTT (stt/final) → main TARS router
7. **Processing**: Router forwards to LLM, gets response, triggers TTS
8. **Coordination**: TTS worker → MQTT (tts/status "speaking_start") → wake-activation (keeps wake detection muted)
9. **Resume**: TTS worker → MQTT (tts/status "speaking_end") → wake-activation (unmutes wake detection)

### Network Disconnection Flow

1. **Detection**: asyncio-mqtt detects connection loss
2. **Logging**: Both services log WARNING "Disconnected from MQTT broker"
3. **State Change**: Health status flips to unhealthy
4. **Transcription Handling**: If transcription in progress, drop it (no partial data sent)
5. **Reconnection**: Services attempt reconnect with exponential backoff (5s, 10s, 30s)
6. **Recovery**: On successful reconnect, log INFO "Reconnected", flip health to healthy
7. **Resume**: Both services resume normal operation (wake-activation listening, stt-worker ready)

---

## Summary

This feature involves **zero new data models** - it's purely a deployment configuration change. All MQTT contracts, audio processing, and service logic remain unchanged. The only new "entities" are:

1. Remote microphone device (physical hardware + deployment config)
2. MQTT connection configuration (host/port in .env)
3. Docker Compose service definitions (compose.remote-mic.yml)

All message schemas, validation rules, and data flows already exist and are tested in the main TARS deployment.
