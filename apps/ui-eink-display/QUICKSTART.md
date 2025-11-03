# UI E-Ink Display - Quick Deploy Guide

## 🚀 Quick Start

### 1. Set Environment Variables
```bash
cd /data/git/py-tars/ops
cp .env.example .env
# Edit .env and set MQTT_HOST to your main TARS system IP
```

### 2. Build and Deploy
```bash
cd /data/git/py-tars
docker compose -f ops/compose.remote-mic.yml up --build ui-eink-display
```

### 3. Test with Mock Display (No Hardware)
```bash
cd /data/git/py-tars/ops
cat >> .env << EOF
MOCK_DISPLAY=1
LOG_LEVEL=DEBUG
EOF

docker compose -f ops/compose.remote-mic.yml up ui-eink-display
```

## 🧪 Testing

### Run All Tests
```bash
cd /data/git/py-tars/apps/ui-eink-display

# In Docker (recommended)
docker compose -f ../../ops/compose.remote-mic.yml run --rm ui-eink-display pytest

# Local (requires dependencies)
python -m pytest tests/ -v
```

### Run Specific Test Suites
```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests only
pytest tests/integration/ -v

# Contract tests only
pytest tests/contract/ -v
```

### Quick Validation
```bash
cd /data/git/py-tars/apps/ui-eink-display
python validate.py
```

## 📊 Monitor Logs

```bash
# Follow logs
docker compose -f ops/compose.remote-mic.yml logs -f ui-eink-display

# View recent logs
docker compose -f ops/compose.remote-mic.yml logs --tail=50 ui-eink-display
```

## 🔧 Troubleshooting

### Display Not Initializing
```bash
# Check SPI device exists
ls -la /dev/spidev*

# Check GPIO access
ls -la /dev/gpiomem

# Run with mock display
MOCK_DISPLAY=1 docker compose -f ops/compose.remote-mic.yml up ui-eink-display
```

### MQTT Connection Issues
```bash
# Test MQTT broker connectivity
ping $MQTT_HOST

# Check MQTT port
nc -zv $MQTT_HOST 1883

# View MQTT messages
docker exec -it tars-mosquitto mosquitto_sub -t '#' -v
```

### Check Service Health
```bash
# Check if service is running
docker compose -f ops/compose.remote-mic.yml ps ui-eink-display

# Check health status
docker compose -f ops/compose.remote-mic.yml exec ui-eink-display pgrep -fa python
```

## 🧩 Test MQTT Flow Manually

### 1. Subscribe to Health
```bash
docker exec -it tars-mosquitto mosquitto_sub -t 'system/health/ui-eink-display' -v
```

### 2. Trigger Wake Event
```bash
docker exec -it tars-mosquitto mosquitto_pub -t 'wake/event' -m '{
  "type": "wake",
  "confidence": 0.85
}'
```

### 3. Send STT Final
```bash
docker exec -it tars-mosquitto mosquitto_pub -t 'stt/final' -m '{
  "text": "What is the weather today?",
  "confidence": 0.92
}'
```

### 4. Send LLM Response
```bash
docker exec -it tars-mosquitto mosquitto_pub -t 'llm/response' -m '{
  "id": "test123",
  "reply": "The weather is sunny with a high of 75 degrees."
}'
```

## 📦 Development Workflow

### 1. Make Code Changes
Edit files in `apps/ui-eink-display/src/ui_eink_display/`

### 2. Restart Service (Volume-Mounted)
```bash
docker compose -f ops/compose.remote-mic.yml restart ui-eink-display
```

### 3. Run Tests
```bash
docker compose -f ops/compose.remote-mic.yml run --rm ui-eink-display pytest
```

### 4. Check Logs
```bash
docker compose -f ops/compose.remote-mic.yml logs -f ui-eink-display
```

## 🎯 Configuration Reference

### Required
- `MQTT_HOST` - Main TARS system IP address

### Optional
- `MQTT_PORT` (default: 1883)
- `DISPLAY_TIMEOUT_SEC` (default: 45)
- `MOCK_DISPLAY` (default: 0, set to 1 for testing)
- `LOG_LEVEL` (default: INFO)
- `HEALTH_CHECK_INTERVAL_SEC` (default: 30)

### Example .env
```bash
MQTT_HOST=192.168.1.100
MQTT_PORT=1883
DISPLAY_TIMEOUT_SEC=45
MOCK_DISPLAY=0
LOG_LEVEL=INFO
```

## 📋 Pre-Deployment Checklist

- [ ] Main TARS system MQTT broker accessible
- [ ] Network connectivity between devices
- [ ] SPI enabled on Radxa Zero 3W
- [ ] GPIO permissions configured
- [ ] Waveshare display connected to GPIO pins
- [ ] .env file configured with MQTT_HOST
- [ ] Docker and Docker Compose installed

## 🔗 Related Documentation

- Full README: `apps/ui-eink-display/README.md`
- Implementation Status: `apps/ui-eink-display/IMPLEMENTATION_STATUS.md`
- Feature Spec: `specs/007-eink-display/spec.md`
- Technical Plan: `specs/007-eink-display/plan.md`
- Research: `specs/007-eink-display/research.md`
