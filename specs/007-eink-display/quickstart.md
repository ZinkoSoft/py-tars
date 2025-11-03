# Quickstart Guide: E-Ink Display Service

**Feature**: Remote E-Ink Display for TARS Communication  
**Audience**: Developers setting up or testing the ui-eink-display service

---

## Prerequisites

### Hardware Requirements

- Radxa Zero 3W (or compatible SBC with 40-pin GPIO header)
- Waveshare 2.13" V4 e-ink display
- Display connected via SPI to GPIO pins
- MicroSD card with Linux installed
- Network connection to main TARS system

### Software Requirements

- Docker and Docker Compose installed
- SPI enabled in kernel (`/dev/spidev0.0` present)
- Waveshare epd library installed (or available in PYTHONPATH)
- Main TARS system running with MQTT broker accessible

---

## Quick Setup

### 1. Clone Repository

```bash
cd /data/git
git clone <repository-url> py-tars
cd py-tars
git checkout 007-eink-display
```

### 2. Configure Environment

Copy and edit environment configuration:

```bash
cd ops
cp .env.remote-mic.example .env
nano .env
```

Required settings:
```bash
# Main TARS system IP address
MQTT_HOST=192.168.1.100

# Optional: adjust timeout (default 45 seconds)
DISPLAY_TIMEOUT_SEC=45

# Optional: adjust log level
LOG_LEVEL=INFO
```

### 3. Verify Waveshare Library

Ensure waveshare-epd library is accessible:

```bash
# Option 1: Clone waveshare repo (if not already done)
cd /data/git
git clone https://github.com/waveshare/e-Paper
export PYTHONPATH=/data/git/e-Paper/RaspberryPi_JetsonNano/python/lib:$PYTHONPATH

# Option 2: Install via pip (if available)
pip install waveshare-epd

# Verify access
python -c "from waveshare_epd import epd2in13_V4; print('OK')"
```

### 4. Test Display Hardware

Run the standalone example to verify hardware:

```bash
cd /data/git/py-tars
python e-paper-example.py
```

You should see system information displayed on the e-ink screen. Press Ctrl+C to stop.

### 5. Start Service

```bash
cd /data/git/py-tars
docker compose -f ops/compose.remote-mic.yml up --build
```

This will start:
- `stt-worker` (speech-to-text)
- `wake-activation` (wake word detection)
- `ui-eink-display` (e-ink display) ← new service

### 6. Verify Service

Check that all services are running:

```bash
docker compose -f ops/compose.remote-mic.yml ps
```

Expected output:
```
NAME                          STATUS
tars-stt-remote               Up (healthy)
tars-wake-activation-remote   Up
tars-ui-eink-display-remote   Up
```

Check logs for ui-eink-display:

```bash
docker compose -f ops/compose.remote-mic.yml logs -f ui-eink-display
```

Look for:
```
INFO: Display initialized successfully
INFO: Connected to MQTT broker at 192.168.1.100:1883
INFO: Subscribed to stt/final, llm/response, wake/event
INFO: Display mode: STANDBY
```

### 7. Test Conversation Flow

Speak to the device:

1. **Say wake word**: "Hey TARS"
   - Display should show "● LISTENING ●"
   
2. **Ask a question**: "What time is it?"
   - Display should show your question in a right-aligned bubble
   - Then show "processing" indicator
   
3. **Wait for response**:
   - Display should show TARS response in a left-aligned bubble
   
4. **Wait ~45 seconds**:
   - Display should return to standby screen

---

## Development Setup

### Run Tests

```bash
cd /data/git/py-tars/apps/ui-eink-display

# Install dev dependencies
pip install -e .[dev]

# Run all tests
pytest tests/

# Run with coverage
pytest --cov=ui_eink_display tests/

# Run specific test types
pytest tests/unit/
pytest tests/integration/
pytest tests/contract/
```

### Run Service Locally (Outside Docker)

```bash
cd /data/git/py-tars

# Set environment variables
export MQTT_HOST=192.168.1.100
export MQTT_PORT=1883
export LOG_LEVEL=DEBUG
export DISPLAY_TIMEOUT_SEC=45
export PYTHONPATH=/data/git/e-Paper/RaspberryPi_JetsonNano/python/lib:packages/tars-core/src:apps/ui-eink-display/src

# Run service
python -m ui_eink_display
```

### Mock Display for Testing

For testing without physical hardware, set mock mode:

```bash
export MOCK_DISPLAY=1
python -m ui_eink_display
```

This will use a simulated display that logs updates instead of controlling hardware.

---

## Troubleshooting

### Display Not Initializing

**Symptom**: Error message "Failed to initialize display"

**Solutions**:
1. Check SPI is enabled: `ls /dev/spidev*`
2. Verify GPIO permissions: `groups` should include `gpio` or `spi`
3. Check display connections (refer to Waveshare wiring guide)
4. Verify waveshare-epd library: `python -c "from waveshare_epd import epd2in13_V4"`

### MQTT Connection Fails

**Symptom**: Error message "Failed to connect to MQTT broker"

**Solutions**:
1. Verify MQTT_HOST is correct: `ping $MQTT_HOST`
2. Check MQTT broker is running: `docker compose -f ops/compose.yml ps | grep mosquitto`
3. Verify firewall allows port 1883: `telnet $MQTT_HOST 1883`
4. Check ops/mosquitto.conf has `listener 1883 0.0.0.0`

### Display Shows Error State

**Symptom**: Display shows "⚠ ERROR ⚠ Connection Lost"

**Solutions**:
1. Check service logs: `docker compose -f ops/compose.remote-mic.yml logs ui-eink-display`
2. Verify MQTT connection: Look for "Connected to MQTT" in logs
3. Check main TARS system is running
4. Restart service: `docker compose -f ops/compose.remote-mic.yml restart ui-eink-display`

### Text Not Readable

**Symptom**: Text appears truncated or wrapped poorly

**Solutions**:
1. Check font files exist: `ls /usr/share/fonts/truetype/dejavu/`
2. Verify font size configuration in code
3. Test with shorter messages
4. Check display orientation (should be landscape)

### Service Crashes on Startup

**Symptom**: Container exits immediately

**Solutions**:
1. Check logs: `docker compose -f ops/compose.remote-mic.yml logs ui-eink-display`
2. Verify environment variables: `docker compose -f ops/compose.remote-mic.yml config`
3. Check MQTT_HOST is set: `grep MQTT_HOST ops/.env`
4. Run locally to see full traceback (see "Run Service Locally" above)

---

## Testing Checklist

Use this checklist to verify the feature is working correctly:

- [ ] Display shows standby screen on startup
- [ ] Wake word detection transitions to "LISTENING" state
- [ ] STT final transcript shows user message (right-aligned)
- [ ] LLM response shows TARS message (left-aligned)
- [ ] Long messages are truncated or wrapped correctly
- [ ] Very long LLM responses show TARS only (skip user message)
- [ ] Display returns to standby after ~45 seconds
- [ ] New wake word clears previous conversation
- [ ] MQTT disconnect shows error state
- [ ] MQTT reconnect returns to normal operation
- [ ] Service survives display errors (logs error but doesn't crash)
- [ ] Health status published to system/health/ui-eink-display

---

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MQTT_HOST` | Yes | - | Main TARS system IP address |
| `MQTT_PORT` | No | 1883 | MQTT broker port |
| `MQTT_URL` | No | - | Alternative to HOST+PORT |
| `LOG_LEVEL` | No | INFO | Logging verbosity |
| `DISPLAY_TIMEOUT_SEC` | No | 45.0 | Seconds before returning to standby |
| `PYTHONPATH` | No | - | Path to waveshare-epd library |
| `FONT_PATH` | No | /usr/share/fonts/truetype/dejavu | Path to font files |
| `MOCK_DISPLAY` | No | 0 | Set to 1 for testing without hardware |

### Docker Compose Service Definition

```yaml
ui-eink-display:
  build:
    context: ..
    dockerfile: docker/specialized/ui-eink-display.Dockerfile
  image: tars/ui-eink-display-remote:dev
  container_name: tars-ui-eink-display-remote
  env_file: ../.env
  environment:
    MQTT_HOST: ${MQTT_HOST}
    MQTT_PORT: ${MQTT_PORT:-1883}
    LOG_LEVEL: ${LOG_LEVEL:-INFO}
    DISPLAY_TIMEOUT_SEC: ${DISPLAY_TIMEOUT_SEC:-45}
    PYTHONPATH: /workspace/apps/ui-eink-display/src:/workspace/packages/tars-core/src
  devices:
    - /dev/spidev0.0:/dev/spidev0.0  # SPI access for display
    - /dev/gpiomem:/dev/gpiomem      # GPIO access
  volumes:
    - ..:/workspace:ro
  restart: unless-stopped
  depends_on:
    stt:
      condition: service_healthy
```

---

## Next Steps

After verifying the quickstart:

1. **Customize Display**: Edit `display_manager.py` to adjust layout or styling
2. **Tune Timeout**: Adjust `DISPLAY_TIMEOUT_SEC` for your preference
3. **Add Features**: See `tasks.md` for planned enhancements
4. **Deploy**: Update `ops/compose.remote-mic.yml` and deploy to remote device

---

## Additional Resources

- **Feature Spec**: `specs/007-eink-display/spec.md`
- **Implementation Plan**: `specs/007-eink-display/plan.md`
- **Data Model**: `specs/007-eink-display/data-model.md`
- **Research Notes**: `specs/007-eink-display/research.md`
- **Waveshare Docs**: https://www.waveshare.com/wiki/2.13inch_e-Paper_HAT_(D)
- **MQTT Contracts**: `docs/mqtt-contracts.md`
