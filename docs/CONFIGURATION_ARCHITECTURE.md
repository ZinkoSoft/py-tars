# Configuration Architecture

## Overview

TARS uses a **two-tier configuration system** that separates infrastructure config from application config.

## Configuration Tiers

### 1. Infrastructure Config (.env files)

**Location**: `.env` and `ops/.env`

**Purpose**: System-level configuration that is the same across all environments and rarely changes.

**What Goes Here**:
- ✅ **MQTT broker connection** (host, port, credentials, URL)
- ✅ **Database paths** (CONFIG_DB_PATH, CONFIG_LKG_CACHE_PATH)
- ✅ **Encryption keys** (CONFIG_MASTER_KEY_BASE64, LKG_HMAC_KEY_BASE64)
- ✅ **Service discovery** (hostnames, ports)
- ✅ **Audio hardware** (PulseAudio paths, device names)
- ✅ **Model paths** (WHISPER_MODEL location)
- ✅ **Log levels** (LOG_LEVEL)

**Why .env**:
- Used by **all services** (router, STT, TTS, LLM, memory, wake-activation)
- Part of deployment infrastructure (Docker Compose, systemd)
- Changes require service restart anyway
- Security-sensitive (credentials, keys)
- Not user-facing configuration

**Examples**:
```bash
# MQTT Broker (NEVER in unified config)
MQTT_USER=tars
MQTT_PASS=change_me
MQTT_HOST=127.0.0.1
MQTT_PORT=1883
MQTT_URL=mqtt://tars:change_me@127.0.0.1:1883

# Database
CONFIG_DB_PATH=/data/config/config.db
CONFIG_LKG_CACHE_PATH=/data/config/config.lkg.json

# Encryption
CONFIG_MASTER_KEY_BASE64=...
LKG_HMAC_KEY_BASE64=...

# Audio
PULSE_SERVER=unix:/run/user/1000/pulse/native
AUDIO_DEVICE_NAME=AIRHUG 21

# Logging
LOG_LEVEL=INFO
```

### 2. Application Config (Unified Config System)

**Location**: SQLite database (`/data/config/config.db`)

**Purpose**: Service-specific, user-tunable settings that can change at runtime.

**What Goes Here**:
- ✅ **STT settings** (model size, VAD thresholds, streaming, suppression)
- ✅ **TTS settings** (provider, voice, streaming, caching, ElevenLabs API)
- ✅ **Router settings** (wake window, acknowledgments, live mode, streaming)
- ✅ **LLM settings** (provider, model, temperature, max tokens, RAG)
- ✅ **Memory settings** (strategy, embedding model, top-k)
- ✅ **Wake settings** (threshold, model, acknowledgments)

**Why Unified Config**:
- User-facing settings (exposed in web UI)
- Can be changed without restart (MQTT live updates)
- Cryptographically signed for security
- Version controlled (LKG cache + checksum)
- Service-specific (each service has its own config model)

**Examples**:
```yaml
# STT Worker Config
whisper_model: "base"  # small, medium, large
vad_aggressiveness: 3
streaming_partials: true
stt_backend: "whisper"

# TTS Worker Config
tts_provider: "piper"  # or "elevenlabs"
piper_voice: "/voices/TARS.onnx"
tts_streaming: false
eleven_api_key: "sk_..."
eleven_voice_id: "pr2LENmoMj8ou32Umqvg"

# Router Config
router_wake_window_sec: 20.0
router_wake_ack_enabled: true
router_stream_min_chars: 60
```

## Decision Matrix

When adding a new configuration option, use this matrix:

| Question | .env | Unified Config |
|----------|------|----------------|
| Used by multiple services? | ✅ | ❌ |
| Infrastructure/deployment level? | ✅ | ❌ |
| Contains credentials/secrets? | ✅ | ❌ (except API keys) |
| Requires restart to apply? | ✅ | ❌ |
| User wants to change in UI? | ❌ | ✅ |
| Service-specific behavior? | ❌ | ✅ |
| Changes frequently? | ❌ | ✅ |
| Needs versioning/rollback? | ❌ | ✅ |

## Examples by Category

### Infrastructure (.env)

```bash
# Broker connection (used by 6+ services)
MQTT_URL=mqtt://mqtt:1883
MQTT_HOST=mqtt
MQTT_PORT=1883

# Database paths (used by config-manager + all services)
CONFIG_DB_PATH=/data/config/config.db

# Hardware (physical system config)
PULSE_SERVER=unix:/run/user/1000/pulse/native
AUDIO_DEVICE_NAME=AIRHUG 21

# Logging (operations concern)
LOG_LEVEL=INFO
```

### Application (Unified Config)

```python
# STTWorkerConfig
whisper_model: str  # User picks model size
vad_aggressiveness: int  # User tunes sensitivity
streaming_partials: bool  # User enables/disables feature

# TTSWorkerConfig
tts_provider: str  # User switches between Piper/ElevenLabs
tts_streaming: bool  # User tunes responsiveness
eleven_api_key: str  # User API key (encrypted in DB)

# RouterConfig
router_wake_window_sec: float  # User adjusts timeout
router_wake_ack_enabled: bool  # User enables/disables feature
```

## Anti-Patterns (Don't Do This)

### ❌ Don't Put MQTT in Unified Config

**Bad**:
```python
class RouterConfig(BaseModel):
    mqtt_host: str  # ❌ NO - infrastructure config
    mqtt_port: int  # ❌ NO - used by all services
```

**Why**: MQTT connection is infrastructure. Changing it in one service config would break everything.

### ❌ Don't Put User Preferences in .env

**Bad**:
```bash
# .env
WHISPER_MODEL=base  # ❌ NO - user should pick in UI
TTS_STREAMING=1     # ❌ NO - user-facing feature toggle
```

**Why**: User can't change without editing files and restarting. Should be in unified config.

### ❌ Don't Duplicate Config

**Bad**:
```bash
# .env
ROUTER_WAKE_WINDOW=20

# AND in unified config
router_wake_window_sec: 20.0
```

**Why**: Creates confusion about which value is authoritative. Pick one tier.

## Migration Path

When moving from `.env` to unified config:

1. **Add field to Pydantic model** (`packages/tars-core/src/tars/config/models.py`)
2. **Add metadata** (`ops/config-metadata.yml`)
3. **Sync database** (restart config-manager)
4. **Add config library integration** (service-specific `config_lib_adapter.py`)
5. **Test MQTT live updates** (change in UI, verify no restart needed)
6. **Remove from .env** (after confirming unified config works)

## Current Status

### Services with Unified Config ✅
- **STT Worker**: Full integration, MQTT live updates enabled
- **TTS Worker**: Full integration, MQTT live updates enabled (DNS issue pending)
- **Config Manager**: Central service, signs MQTT updates

### Services with .env Only ⏳
- **Router**: Still uses environment variables (TODO: add config library)
- **LLM Worker**: Still uses environment variables (TODO: add config library)
- **Memory Worker**: Still uses environment variables (TODO: add config library)
- **Wake Activation**: Still uses environment variables (TODO: add config library)

### Infrastructure Config (Always .env) 🔒
- **MQTT Broker**: Connection details, credentials
- **Database**: Paths, encryption keys
- **Audio**: Hardware paths, device names
- **Logging**: System-wide log level

## References

- **Copilot Instructions**: `.github/copilot-instructions.md` section 3 (Configuration)
- **Config Models**: `packages/tars-core/src/tars/config/models.py`
- **Config Metadata**: `ops/config-metadata.yml`
- **Config Library**: `packages/tars-core/src/tars/config/library.py`
- **MQTT Signature Keys**: `docs/MQTT_SIGNATURE_KEYS_IMPLEMENTATION.md`
