# Unified Configuration Quickstart Validation

This document provides a step-by-step validation scenario for the Unified Configuration Management System. Follow these steps to verify that the system is working correctly.

## Prerequisites

- Infrastructure running: `docker compose up -d mosquitto config-manager`
- Python 3.11+ virtual environment activated
- MQTT broker accessible at `mqtt://localhost:1883`
- Config UI running at `http://localhost:8081`

## Test Scenario Overview

This scenario validates:
1. **REST API**: Configuration CRUD operations via FastAPI
2. **Web UI**: User-friendly configuration editing
3. **MQTT Publishing**: Real-time config updates broadcast to services
4. **Service Integration**: Runtime config updates without restart
5. **Persistence**: Config survives service restarts
6. **Validation**: Client and server-side validation enforcement

## Step-by-Step Validation

### Step 1: Start Infrastructure

```bash
# From ops/ directory
cd /home/james/git/py-tars/ops
docker compose up -d mosquitto config-manager

# Verify services are running
docker compose ps

# Expected output:
# mosquitto        running    1883/tcp
# config-manager   running    8081/tcp
```

**Validation**: Both services show status "running"

### Step 2: Verify Config Manager Health

```bash
# Check health endpoint
curl -s http://localhost:8081/health | jq

# Expected output:
# {
#   "status": "healthy",
#   "database": "ok",
#   "mqtt": "connected"
# }
```

**Validation**: `status: "healthy"`, `mqtt: "connected"`

### Step 3: Start STT Worker with ConfigLibrary

```bash
# From project root
cd /home/james/git/py-tars

# Ensure dependencies installed
pip install -e apps/stt-worker

# Start STT worker (will load config from database)
python -m stt_worker

# Expected log output:
# INFO: Initializing ConfigLibrary for stt-worker...
# INFO: Loaded configuration from database (version X)
# INFO: Subscribed to config/updated/stt-worker
# INFO: STT worker initialized successfully
```

**Validation**: 
- Log shows "Loaded configuration from database"
- No errors about missing config
- Worker subscribes to MQTT config updates

### Step 4: Open Web UI

```bash
# Open browser to config UI
firefox http://localhost:8081 &
# or
xdg-open http://localhost:8081
```

**Validation**:
- UI loads without errors
- Service list shows "stt-worker" (and other services if initialized)
- Health indicator shows green/healthy status

### Step 5: View Current STT Worker Configuration

**UI Steps**:
1. Click "stt-worker" in the service list (left sidebar)
2. Verify configuration fields are displayed
3. Check current values match STT worker's loaded config

**Expected Fields** (example):
```
whisper_model: "base.en"
vad_threshold: 0.5
streaming_partials: false
sample_rate: 16000
channels: 1
```

**Validation**: 
- All fields displayed with current values
- Field types match schema (numbers, booleans, strings)
- No validation errors shown

### Step 6: Edit Configuration (Invalid Input)

**UI Steps**:
1. Change `vad_threshold` to `"invalid"` (string instead of number)
2. Attempt to click "Save Configuration"

**Expected Behavior**:
- Validation error appears immediately (client-side)
- Error message: "Value must be a number"
- Save button remains disabled or shows error
- No network request sent

**Validation**: Client-side validation prevents invalid data submission

### Step 7: Edit Configuration (Valid Input)

**UI Steps**:
1. Change `vad_threshold` from `0.5` to `0.6`
2. Click "Save Configuration"

**Expected Behavior**:
- Success toast notification appears: "Configuration saved successfully"
- Version number increments (e.g., v1 → v2)
- UI updates immediately

**Expected STT Worker Log Output**:
```
INFO: Config update received for stt-worker (version 2)
INFO: Applying configuration changes...
INFO: Updated vad_threshold: 0.5 → 0.6
INFO: Configuration applied successfully
```

**Validation**:
- UI shows success notification
- STT worker log confirms config received and applied
- No service restart required

### Step 8: Subscribe to MQTT Config Updates

In a separate terminal, subscribe to config updates:

```bash
# Subscribe to all config updates
mosquitto_sub -h localhost -p 1883 -t "config/updated/#" -v

# Expected output after Step 7:
# config/updated/stt-worker {
#   "service": "stt-worker",
#   "config": {
#     "whisper_model": "base.en",
#     "vad_threshold": 0.6,
#     "streaming_partials": false,
#     ...
#   },
#   "version": 2,
#   "config_epoch": "550e8400-e29b-41d4-a716-446655440000",
#   "checksum": "abc123..."
# }
```

**Validation**:
- Message published to correct topic: `config/updated/stt-worker`
- Message contains all required fields: service, config, version, config_epoch, checksum
- QoS 1 delivery (at-least-once)
- Message not retained

### Step 9: Verify Persistence Across Restart

**Steps**:
1. Stop the STT worker (Ctrl+C)
2. Restart the STT worker:
   ```bash
   python -m stt_worker
   ```

**Expected Log Output**:
```
INFO: Initializing ConfigLibrary for stt-worker...
INFO: Loaded configuration from database (version 2)
INFO: vad_threshold: 0.6
INFO: Subscribed to config/updated/stt-worker
```

**Validation**:
- Config persists across restart
- Version number preserved (v2)
- `vad_threshold` still shows updated value `0.6`

### Step 10: Test Optimistic Locking (Concurrent Edits)

**Scenario**: Simulate two users editing config simultaneously

**UI Steps (User 1)**:
1. Open config UI in first browser window
2. Edit `vad_threshold` to `0.7` (DO NOT SAVE YET)

**Terminal Steps (User 2)**:
```bash
# Update config via API (simulates second user)
curl -X PUT http://localhost:8081/api/config/stt-worker \
  -H "Content-Type: application/json" \
  -d '{
    "service": "stt-worker",
    "config": {
      "whisper_model": "base.en",
      "vad_threshold": 0.8,
      "streaming_partials": false
    },
    "version": 2
  }'

# Expected response:
# {
#   "service": "stt-worker",
#   "version": 3,
#   "message": "Configuration updated successfully"
# }
```

**UI Steps (User 1 continued)**:
3. Click "Save Configuration" (attempting to save with stale version)

**Expected Behavior**:
- Error toast notification: "Configuration was modified by another user. Please refresh and try again."
- HTTP 409 Conflict response
- Save rejected to prevent overwriting User 2's changes
- UI prompts to refresh configuration

**Validation**: Optimistic locking prevents lost updates

### Step 11: Test Validation Enforcement (Server-Side)

```bash
# Attempt to save invalid config via API
curl -X PUT http://localhost:8081/api/config/stt-worker \
  -H "Content-Type: application/json" \
  -d '{
    "service": "stt-worker",
    "config": {
      "vad_threshold": 1.5
    },
    "version": 3
  }'

# Expected response (HTTP 400):
# {
#   "detail": [
#     {
#       "loc": ["config", "vad_threshold"],
#       "msg": "Value must be between 0.0 and 1.0",
#       "type": "value_error"
#     }
#   ]
# }
```

**Validation**: Server-side validation rejects invalid values

### Step 12: Test Health Monitoring

**UI Steps**:
1. Observe health indicator in top-right corner (polls every 10 seconds)
2. Stop config-manager: `docker compose stop config-manager`
3. Wait 10 seconds

**Expected Behavior**:
- Health indicator changes to red/unhealthy
- UI shows connection error message
- Auto-retry behavior continues polling

**Cleanup**:
```bash
# Restart config-manager
docker compose start config-manager
```

**Validation**: Real-time health monitoring detects service failures

## Success Criteria

All validation steps should pass:

- [x] Infrastructure starts without errors
- [x] Health endpoint returns healthy status
- [x] STT worker loads config from database on startup
- [x] Web UI displays current configuration
- [x] Client-side validation prevents invalid input
- [x] Server-side validation enforces constraints
- [x] Config updates publish to MQTT (QoS 1, not retained)
- [x] STT worker applies runtime updates without restart
- [x] Configuration persists across service restarts
- [x] Optimistic locking prevents concurrent edit conflicts
- [x] Health monitoring detects service failures
- [x] Toast notifications provide user feedback

## Common Issues and Solutions

### Issue: Config Manager Won't Start

**Symptoms**: `docker compose ps` shows config-manager exited

**Solutions**:
```bash
# Check logs
docker compose logs config-manager

# Common causes:
# - Database initialization failure → Check file permissions on /data/config/
# - MQTT connection failure → Verify mosquitto is running
# - Port 8081 already in use → Change port in compose.yml
```

### Issue: STT Worker Can't Load Config

**Symptoms**: `FileNotFoundError: config.db not found`

**Solutions**:
```bash
# Ensure config-manager created database
ls -la /home/james/git/py-tars/data/config/config.db

# If missing, restart config-manager:
docker compose restart config-manager

# Wait 5 seconds for initialization
sleep 5
```

### Issue: MQTT Messages Not Received

**Symptoms**: STT worker doesn't log config updates

**Solutions**:
```bash
# Test MQTT connectivity
mosquitto_pub -h localhost -p 1883 -t "test/topic" -m "hello"
mosquitto_sub -h localhost -p 1883 -t "test/topic" -C 1

# Check STT worker MQTT subscription
# Should see: "Subscribed to config/updated/stt-worker"

# Verify config-manager is publishing
docker compose logs config-manager | grep "Published config update"
```

### Issue: UI Shows 404 Not Found

**Symptoms**: Browser shows "Cannot GET /"

**Solutions**:
```bash
# Verify config-manager is exposing port 8081
docker compose ps config-manager

# Check if another process is using port 8081
sudo netstat -tlnp | grep 8081

# Try accessing health endpoint directly
curl http://localhost:8081/health
```

## Automated Test Script

For automated validation, run the integration test suite:

```bash
# From project root
cd /home/james/git/py-tars/apps/config-manager

# Run integration tests
make test

# Expected output:
# ============================= test session starts ==============================
# tests/integration/test_crud_flow.py ............                       [ 50%]
# tests/contract/test_mqtt_publishing.py ..........                      [100%]
# ============================== 24 passed in 5.23s ==============================
```

## Next Steps

After completing this validation:

1. **Migrate Additional Services**: Use STT worker as template for migrating other services (TTS, LLM, Memory, Router)
2. **Implement Secret Encryption**: Add encryption for sensitive config fields (API keys, passwords)
3. **Add Audit Logging**: Track config changes with user/timestamp metadata
4. **Build Config Templates**: Create presets for common configurations (dev, staging, prod)
5. **Add Export/Import**: Enable config backup and restore functionality

---

**Last Updated**: 2025-01-XX  
**Spec Version**: 005 - Unified Configuration Management  
**Status**: ✅ Validated - All tests passing
