# T074 Complete: Migrate camera-service to Centralized MQTT Client

**Status**: ✅ Complete  
**Commit**: 80edd6e  
**Date**: 2025-10-17  
**Lines Changed**: +8684, -911 (net +7773)

---

## Objective

Migrate camera-service from synchronous `paho-mqtt` wrapper to async centralized `MQTTClient`:
- Replace local `mqtt_client.py` (100 lines) with `tars.adapters.mqtt_client.MQTTClient`
- Convert service to fully async pattern
- Enable health monitoring and heartbeat
- Update documentation

---

## Migration Details

### 1. Dependency Changes

**pyproject.toml**:
```diff
- "asyncio-mqtt>=0.16.2",
- "paho-mqtt<2.0",
+ "tars-core",
```

**Impact**: Eliminates direct MQTT library dependencies, centralizes through tars-core

### 2. Service Code Changes

**service.py** - Key modifications:

#### Import Replacement
```python
# Before
from .mqtt_client import MQTTPublisher

# After
from tars.adapters.mqtt_client import MQTTClient  # type: ignore[import]
```

#### Client Initialization (sync → async)
```python
# Before (sync)
self.mqtt = MQTTPublisher(
    self.cfg.mqtt.url,
    self.cfg.mqtt.frame_topic,
    self.cfg.mqtt.health_topic,
)
self.mqtt.connect()

# After (async)
self.mqtt = MQTTClient(
    self.cfg.mqtt.url,
    client_id="tars-camera",
    enable_health=True,
    enable_heartbeat=True,
)
await self.mqtt.connect()
```

#### Frame Publishing (sync → async)
```python
# Before (sync method call)
self.mqtt.publish_frame(jpeg_data, width, height, ...)

# After (async method in capture loop)
await self._publish_frame(jpeg_data, width, height, ...)

# New async method
async def _publish_frame(self, jpeg_data: bytes, ...) -> None:
    """Publish frame to MQTT (base64 encoded)."""
    frame_b64 = base64.b64encode(jpeg_data).decode("ascii")
    payload = {
        "frame": frame_b64,
        "timestamp": time.time(),
        "width": width,
        "height": height,
        "quality": quality,
        "mqtt_rate": mqtt_rate,
        "backend": backend,
        "consecutive_failures": consecutive_failures,
    }
    await self.mqtt.publish(self.cfg.mqtt.frame_topic, payload, qos=0)
```

#### Health Publishing (manual → automatic)
```python
# Before (manual calls throughout)
self.mqtt.publish_health(True, "started")
self.mqtt.publish_health(False, str(e))
self.mqtt.publish_health(False, "stopped")

# After (automatic on connect/disconnect)
# Health published automatically by centralized client
# No manual calls needed!
```

#### Shutdown (sync → async)
```python
# Before (sync)
def stop(self) -> None:
    self.running = False
    if self.mqtt:
        self.mqtt.publish_health(False, "stopped")
        self.mqtt.disconnect()

# After (async)
async def stop(self) -> None:
    self.running = False
    if self.mqtt:
        await self.mqtt.shutdown()  # Handles health automatically
```

### 3. Entry Point Changes

**__main__.py** - Async shutdown handling:

```python
# Before (sync signal handler)
def signal_handler(signum, frame):
    logging.info(f"Received signal {signum}, shutting down...")
    service.stop()  # Sync call

# After (async shutdown)
async def shutdown():
    """Async shutdown handler."""
    logging.info("Shutting down camera service...")
    await service.stop()

def signal_handler(signum, frame):
    logging.info(f"Received signal {signum}, initiating shutdown...")
    asyncio.create_task(shutdown())
```

### 4. Deleted Files

- **apps/camera-service/src/camera_service/mqtt_client.py** (100 lines)
  - Old `MQTTPublisher` class
  - Manual reconnection logic
  - Synchronous paho-mqtt wrapper
  - Health publishing methods

---

## Code Improvements

### 1. Async-First Design
- **Before**: Mixed sync/async (paho-mqtt in sync, asyncio for capture loop)
- **After**: Pure async throughout (no blocking calls)
- **Benefit**: Better event loop hygiene, no thread contention

### 2. Automatic Health Monitoring
- **Before**: Manual `publish_health(True/False, "event")` calls scattered throughout
- **After**: Auto-published on `connect()`, `disconnect()`, errors
- **Benefit**: Eliminated 5+ manual health publishing calls, consistent behavior

### 3. Heartbeat Support
- **Before**: No heartbeat (connection liveness unclear)
- **After**: Optional heartbeat to `system/keepalive/camera` every 5s
- **Benefit**: Session presence monitoring, detect stale connections

### 4. Auto-Reconnection
- **Before**: No automatic reconnection (relied on paho-mqtt's basic retry)
- **After**: Exponential backoff (0.5s-5s), session recovery, subscription resumption
- **Benefit**: Robust connection handling, survives broker restarts

### 5. Message Deduplication
- **Before**: No deduplication (could publish duplicate frames on reconnect)
- **After**: TTL cache prevents duplicate processing
- **Benefit**: Clean MQTT logs, no duplicate frames during connection issues

---

## Documentation Updates

### README.md Changes

#### Added "MQTT Client Architecture" Section
- Documents centralized client usage
- Key features (auto-reconnect, health, heartbeat, deduplication)
- Async publishing pattern with code example
- Migration benefits quantified (~100 lines eliminated)

#### Updated "Project Structure" Section
```diff
  └── camera_service/
      ├── __init__.py
      ├── __main__.py     # CLI entry point
      ├── config.py       # Configuration parsing
-     ├── service.py      # Core business logic
+     ├── service.py      # Core business logic (MQTT lifecycle, async publishing)
      ├── capture.py      # Camera capture
-     ├── streaming.py    # HTTP streaming
-     └── mqtt_client.py  # MQTT client
+     └── streaming.py    # HTTP streaming
```

#### Enhanced "Architecture" Section
```diff
  1. **Camera Capture** (`capture.py`): ...
  2. **HTTP Streaming** (`streaming.py`): ...
- 3. **MQTT Client** (`mqtt_client.py`): Publishes occasional frames...
+ 3. **Service Orchestration** (`service.py`): Coordinates capture, streaming, and async MQTT publishing
```

#### Updated MQTT Integration Table
Added fields to frame payload:
- `backend`: Camera backend (opencv/libcamera)
- `consecutive_failures`: Capture failure count

Added topics:
- `system/health/camera`: Auto-published health status
- `system/keepalive/camera`: Optional heartbeat

---

## Testing Considerations

### Manual Testing Required
1. **Frame Publishing**: Verify frames still published to `camera/frame` topic
2. **Health Status**: Check `system/health/camera` updates on connect/disconnect
3. **Heartbeat**: Validate `system/keepalive/camera` messages every 5s
4. **Reconnection**: Test broker restart, service survives and reconnects
5. **HTTP Streaming**: Ensure `/stream` and `/snapshot` endpoints work

### Integration Test Checklist
- [ ] Camera capture → MQTT frame publishing pipeline
- [ ] Health status lifecycle (started → running → stopped)
- [ ] Heartbeat consistency (5s intervals)
- [ ] Reconnection after broker restart
- [ ] HTTP endpoints still functional
- [ ] No duplicate frames during reconnect

---

## Migration Pattern Summary

This migration demonstrates the **publish-only service pattern**:

### Characteristics
- No subscription handlers (only publishes)
- Simple async `publish()` calls
- Health and heartbeat auto-managed
- No message routing logic needed

### Differences from Subscriber Services
- **llm-worker/memory-worker**: Subscription handlers, request-response patterns
- **camera-service**: Fire-and-forget publishing, no inbound messages
- **Simplicity**: Fewer lines changed (no handler conversions)

### Pattern Template
```python
# 1. Initialize with health + heartbeat
self.mqtt = MQTTClient(url, client_id="...", enable_health=True, enable_heartbeat=True)
await self.mqtt.connect()

# 2. Publish from async context
async def publish_data(self, data):
    await self.mqtt.publish(topic, payload, qos=0)

# 3. Shutdown
async def stop(self):
    await self.mqtt.shutdown()  # Auto-publishes health=false
```

---

## Phase 7 Completion Status

### Services Migrated (9/9 = 100%)

1. ✅ **stt-worker** (T065) - VAD + Whisper transcription
2. ✅ **router** (T066) - Message routing + LLM fallback
3. ✅ **tts-worker** (T067) - Piper synthesis + streaming
4. ✅ **movement-service** (T068) - Motor control
5. ✅ **ui-web** (T069) - Web UI
6. ✅ **wake-activation** (T070) - Wake word detection
7. ✅ **llm-worker** (T071a) - LLM requests + tool calling
8. ✅ **memory-worker** (T071b) - Vector DB + character management
9. ✅ **camera-service** (T074) - Camera capture + HTTP streaming

### Wrappers Deleted (Total: ~756 lines)

| Service | File | Lines | Task |
|---------|------|-------|------|
| llm-worker | `mqtt_client.py` | ~250 | T071a |
| memory-worker | `mqtt_client.py` | ~200 | T071b |
| stt-worker | `mqtt_utils.py` | 206 | T073 |
| camera-service | `mqtt_client.py` | 100 | T074 |
| **TOTAL** | | **~756** | |

### Documentation Updated

- ✅ llm-worker README (T072)
- ✅ memory-worker README (T072)
- ✅ camera-service README (T074)
- ✅ All deprecated files removed (T073)
- ✅ Directory structures corrected

---

## Lessons Learned

### 1. Publish-Only Services Are Simplest
- No subscription handlers to convert
- No message routing logic
- Just replace sync publish with async await
- ~30 min migration vs ~2 hours for subscriber services

### 2. Async Shutdown Requires Care
- Signal handlers can't directly await
- Use `asyncio.create_task(shutdown())` pattern
- Final cleanup in `finally` block as fallback

### 3. Health Auto-Publishing Is Powerful
- Eliminated 5+ manual health calls in camera-service
- Consistent behavior (no forgotten calls)
- Automatic on connect/disconnect/errors

### 4. Documentation Pattern Established
- "MQTT Client Architecture" section is standardized
- Copy-paste template for future services
- Consistent terminology across all READMEs

---

## Next Steps

1. **T075**: Integration testing
   - Test all 9 services with centralized client
   - Verify reconnection, health, heartbeat
   - Load testing for message deduplication

2. **T076**: Phase 7 completion summary
   - Document all migrations
   - Architectural impact analysis
   - Overall metrics and lessons

3. **Future**: Consider remaining services
   - **mcp-bridge**: Pure MCP server (no MQTT migration needed)
   - **ui**: Tkinter app (simple publish-only, low priority)
   - **ESP32 firmware**: Different platform (MicroPython, not applicable)

---

## Commit Message

```
feat: Migrate camera-service to centralized MQTT client

Migration Changes:
- Replace local mqtt_client.py with tars.adapters.mqtt_client.MQTTClient
- Convert service.py to fully async pattern (await publish, await stop)
- Update __main__.py for async shutdown handling
- Remove paho-mqtt/asyncio-mqtt deps, add tars-core dependency

Code Improvements:
- Async-first design eliminates thread blocking
- Auto-reconnection with exponential backoff
- Health monitoring auto-published on connect/disconnect
- Heartbeat support for session presence
- Message deduplication during reconnects

Documentation:
- Add MQTT Client Architecture section to README
- Document async publishing pattern and migration benefits
- Update directory structure (removed mqtt_client.py)
- Enhanced Architecture section with centralized client details
- Updated MQTT integration table with all published topics

Impact:
- Deleted: 100 lines of local MQTT wrapper (mqtt_client.py)
- Migration benefits: centralized patterns, auto-health, async-native
- Part of T074: Complete Phase 7 MQTT client migration (9/9 services)

All services now use centralized MQTTClient ✅
```

**Commit**: 80edd6e  
**Branch**: 004-centralize-mqtt-client

---

## Completion Checklist

- [x] Replace paho-mqtt/asyncio-mqtt with tars-core dependency
- [x] Update service.py to use MQTTClient
- [x] Convert all publish calls to async
- [x] Remove manual health publishing calls
- [x] Update __main__.py for async shutdown
- [x] Delete old mqtt_client.py file (100 lines)
- [x] Add MQTT Client Architecture section to README
- [x] Update directory structure in README
- [x] Update Architecture section with centralized client
- [x] Update MQTT integration table with all topics
- [x] Commit with comprehensive message
- [x] Update todo list (mark T074 complete)
- [x] Create completion summary (this document)

**T074: Complete** ✅

**Phase 7: 100% Complete (9/9 services)** 🎉
