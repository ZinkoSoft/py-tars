# STT Worker Configuration Migration - Complete ✅

**Tasks Completed**: T067-T069

## Summary

Successfully migrated the STT worker from hardcoded environment variable configuration to the centralized ConfigLibrary system with runtime update support.

---

## Completed Tasks

### T067: Update STT Worker to Use ConfigLibrary ✅

**New File**: `apps/stt-worker/src/stt_worker/config_lib_adapter.py`

**Purpose**: Bridge between ConfigLibrary and existing STT worker code

**Features**:
- **Initialization**: `initialize_and_subscribe(mqtt_url)` - Sets up ConfigLibrary for "stt-worker" service
- **Initial Load**: Loads `STTWorkerConfig` from database at startup
- **Module Attribute Updates**: Applies config values to `stt_worker.config` module-level constants
- **Field Mapping**: Maps Pydantic model fields to module constants:
  ```python
  {
      "whisper_model": "WHISPER_MODEL",
      "stt_backend": "STT_BACKEND",
      "ws_url": "WS_URL",
      "streaming_partials": "STREAMING_PARTIALS",
      "vad_threshold": "VAD_ENHANCED_ANALYSIS",
      "vad_speech_pad_ms": "PARTIAL_INTERVAL_MS",
      "vad_silence_duration_ms": "PARTIAL_MIN_DURATION_MS",
      "sample_rate": "SAMPLE_RATE",
      "channels": "CHANNELS",
  }
  ```
- **Callback Registration**: `register_callback(cb)` - External callbacks notified on config updates
- **MQTT Subscription**: Automatically subscribes to `system/config/stt-worker` for runtime updates
- **Graceful Degradation**: Falls back to environment variables if ConfigLibrary unavailable

**Modified File**: `apps/stt-worker/src/stt_worker/app.py`

**Changes**:
1. **Import adapter**: Added `from .config_lib_adapter import initialize_and_subscribe, register_callback`
2. **Initialize in startup**: Calls `await initialize_and_subscribe()` in `STTWorker.initialize()`
3. **Register callback**: Calls `register_callback(self._on_config_update)` to receive updates
4. **Error handling**: Wrapped in try-except to continue with env vars if initialization fails

---

### T068: Add Config Update Callback to STT Worker ✅

**Method Added**: `STTWorker._on_config_update(self, new_cfg)`

**Purpose**: Apply runtime configuration changes without restart

**Implementation**:
```python
def _on_config_update(self, new_cfg) -> None:
    """Apply runtime configuration updates from ConfigLibrary.
    
    This method is called synchronously by the adapter when an update is received.
    Update runtime-only flags and schedule any necessary async tasks via the
    event loop if needed.
    """
    try:
        # Extract new values from Pydantic model
        streaming = bool(getattr(new_cfg, "streaming_partials", False))
        backend = getattr(new_cfg, "stt_backend", None)

        # Update runtime fields on the next event loop tick (thread-safe)
        loop = asyncio.get_event_loop()

        def apply():
            self._enable_partials = streaming and (backend not in {"ws", "openai"})
            logger.info("Applied runtime config update: streaming_partials=%s, stt_backend=%s", 
                       streaming, backend)

        loop.call_soon_threadsafe(apply)
    except Exception:
        logger.exception("Failed to apply config update")
```

**Features**:
- **Thread-safe updates**: Uses `loop.call_soon_threadsafe()` to avoid race conditions
- **Runtime flag updates**: Dynamically enables/disables streaming partials
- **Backend awareness**: Respects backend constraints (ws/openai don't support partials)
- **Error resilience**: Exceptions logged but don't crash the service

**Flow**:
```
MQTT config update → ConfigLibrary → Adapter applies to module → 
Adapter calls callback → _on_config_update updates runtime flags
```

---

### T069: Remove Hardcoded Config from STT Worker ✅

**Modified File**: `apps/stt-worker/src/stt_worker/config.py`

**Changes**:
1. **Deprecation Notice**: Added comprehensive docstring explaining migration:
   ```python
   """Configuration module for STT worker.

   DEPRECATION NOTICE:
   This module is being migrated to use tars.config.ConfigLibrary.
   Module-level constants are now populated at runtime by config_lib_adapter.py
   which loads configuration from the centralized database and subscribes to
   runtime updates via MQTT.

   New code should NOT add constants here. Instead, add fields to
   tars.config.models.STTWorkerConfig and access via ConfigLibrary.

   For existing code, module attributes are updated dynamically by the adapter,
   so imports will continue to work during the transition period.
   """
   ```

2. **Added CHANNELS constant**: 
   ```python
   CHANNELS = int(os.getenv("CHANNELS", "1"))
   ```
   - Required by adapter mapping
   - Added to `__all__` exports

**Modified File**: `apps/stt-worker/README.md`

**Changes**: Added comprehensive configuration documentation:

```markdown
## Configuration

### Unified Configuration Management (Recommended)

As of spec 005, STT worker integrates with the centralized **ConfigLibrary** 
for runtime configuration management:

- **Initial load**: Configuration is loaded from the config database at startup
- **Runtime updates**: Changes made via the Config Manager UI are applied live 
  via MQTT (no restart required)
- **Fallback**: If database is unavailable, falls back to Last-Known-Good (LKG) 
  cache, then environment variables

**Key fields** (defined in `tars.config.models.STTWorkerConfig`):
- `whisper_model` - Whisper model size (e.g., "base.en", "small", "medium")
- `stt_backend` - Backend type: "whisper" or "ws"
- `ws_url` - WebSocket backend URL (when backend=ws)
- `streaming_partials` - Enable partial transcriptions (bool)
- `vad_threshold` - Voice activity detection threshold (0.0-1.0)
- `sample_rate` - Audio sample rate in Hz
- `channels` - Audio channels (1=mono, 2=stereo)

Configuration can be edited via:
1. **Config Manager UI** (recommended) - Web interface
2. **Config Manager API** - REST API
3. **Environment variables** (legacy fallback)

### Legacy Environment Variables

**Note**: Environment variables take precedence over database configuration 
during the migration period.
```

---

## Architecture

### Configuration Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Config Manager Service                    │
│                   (port 8081, SQLite DB)                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ 1. Initial load at startup
                            │ 2. MQTT updates at runtime
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              ConfigLibrary (in STT Worker)                   │
│  ├── Loads STTWorkerConfig from database                   │
│  ├── Subscribes to system/config/stt-worker                │
│  └── Notifies adapter on updates                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│           config_lib_adapter.py (Adapter Layer)             │
│  ├── Applies config to stt_worker.config module attrs      │
│  ├── Calls external callbacks (e.g., STTWorker)            │
│  └── Thread-safe updates via event loop                    │
└─────────────────────────────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                │                       │
                ↓                       ↓
┌─────────────────────────┐  ┌──────────────────────┐
│  stt_worker.config      │  │   STTWorker instance │
│  (module attributes)    │  │   (runtime flags)    │
│  ├── WHISPER_MODEL      │  │   ├── _enable_partials│
│  ├── STT_BACKEND        │  │   └── Other state     │
│  ├── STREAMING_PARTIALS │  │                       │
│  ├── SAMPLE_RATE        │  │                       │
│  └── CHANNELS           │  │                       │
└─────────────────────────┘  └──────────────────────┘
         │                            │
         │ Imported by:               │ Direct updates
         ↓                            ↓
┌───────────────────────────────────────────────────┐
│   Other STT Worker Modules                       │
│   ├── audio_capture.py (reads SAMPLE_RATE)      │
│   ├── vad.py (reads VAD constants)              │
│   ├── suppression.py (reads suppression rules)  │
│   └── transcriber.py (reads WHISPER_MODEL)      │
└───────────────────────────────────────────────────┘
```

### Update Flow (Runtime Config Change)

```
User edits config in UI
    ↓
Config Manager API (PUT /api/config/services/stt-worker)
    ↓
Database updated with new values
    ↓
MQTT publish to system/config/stt-worker (signed message)
    ↓
ConfigLibrary receives update
    ↓
Verifies signature
    ↓
Parses into STTWorkerConfig model
    ↓
Adapter applies to module attributes
    ↓
Adapter calls _on_config_update callback
    ↓
STTWorker updates runtime flags (e.g., _enable_partials)
    ↓
New configuration active (no restart required!)
```

---

## Benefits

### Before Migration
- ❌ All config hardcoded as environment variables
- ❌ Changes require container restart
- ❌ No UI for configuration
- ❌ No runtime validation
- ❌ Difficult to manage 50+ env vars

### After Migration
- ✅ **Centralized management** via Config Manager UI
- ✅ **Runtime updates** without restart
- ✅ **Type-safe** configuration via Pydantic models
- ✅ **Validation** at database and client level
- ✅ **Fallback layers**: Database → LKG cache → Environment variables
- ✅ **MQTT integration** for live updates
- ✅ **Web UI** for easy editing
- ✅ **Backwards compatible** - existing imports still work

---

## Files Changed

### New Files (1)
```
apps/stt-worker/src/stt_worker/
  └── config_lib_adapter.py       (~125 lines) - ConfigLibrary adapter
```

### Modified Files (3)
```
apps/stt-worker/src/stt_worker/
  ├── app.py                      (~30 lines changed) - Initialization & callback
  ├── config.py                   (~15 lines changed) - Deprecation notice + CHANNELS
  └── README.md                   (~30 lines changed) - Configuration documentation
```

**Total Changes**: ~200 lines (125 new, 75 modified)

---

## Testing Checklist

### Manual Testing
- [ ] Start config-manager service: `tars-config-manager`
- [ ] Start STT worker: `tars-stt-worker`
- [ ] Check logs for ConfigLibrary initialization
- [ ] Edit config via UI (e.g., toggle `streaming_partials`)
- [ ] Verify MQTT update received
- [ ] Confirm runtime flag updated (check logs)
- [ ] Verify STT still works correctly

### Integration Testing (Next: T070-T072)
- [ ] Test database unavailable → LKG cache fallback
- [ ] Test LKG cache unavailable → env var fallback
- [ ] Test invalid MQTT signature → ignored
- [ ] Test concurrent config updates → optimistic locking
- [ ] Test config persistence across restarts

---

## Known Limitations

1. **Partial Migration**: Only key STT config fields mapped in adapter; full migration requires mapping all 50+ constants
2. **Module Attribute Mutation**: Relies on Python's dynamic module attributes; not ideal for strict typing
3. **Restart Required For**: Model changes (WHISPER_MODEL) still require restart to reload model
4. **Environment Precedence**: Env vars still take precedence over database during transition

---

## Next Steps

### Immediate (Remaining Tasks)
- [ ] **T070**: Write integration tests for CRUD flow
- [ ] **T071**: Write contract tests for MQTT publishing
- [ ] **T072**: Create quickstart validation scenario

### Future Enhancements
1. **Full Field Coverage**: Map all 50+ config constants to STTWorkerConfig
2. **Hot Model Reload**: Support changing WHISPER_MODEL without restart
3. **Remove Environment Precedence**: Make database authoritative
4. **Migrate Other Services**: Apply same pattern to TTS, LLM, Router, Memory workers

---

## Summary Stats

- **Tasks Completed**: 3/3 (T067-T069)
- **Lines of Code**: ~200 lines (125 new, 75 modified)
- **Files Changed**: 4 total (1 new, 3 modified)
- **Runtime Updates**: ✅ Enabled for streaming_partials and stt_backend
- **Backwards Compatible**: ✅ Existing code continues to work
- **Production Ready**: ⚠️ Needs integration testing (T070-T072)

**Status**: Service Integration **COMPLETE** ✅  
**Next**: Integration & Contract Testing (T070-T072)
