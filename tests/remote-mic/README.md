# Remote Microphone Tests

Test suite for remote microphone deployment feature (006-remote-mic).

## Test Structure

### test_remote_deployment.py
**Purpose**: Validates Docker Compose configuration for remote deployment

**Tests**:
- Compose file structure and syntax
- Service definitions (stt-worker, wake-activation)
- Volume configuration (wake-cache for audio fanout)
- Dependency ordering (wake-activation depends on stt health)
- Environment variable configuration
- Container naming conventions
- Documentation completeness

**Run**:
```bash
pytest tests/remote-mic/test_remote_deployment.py -v
```

**No prerequisites**: These are static configuration validation tests.

---

### test_mqtt_connection.py
**Purpose**: Validates MQTT connectivity from remote device to main broker

**Tests**:
- Network reachability to MQTT broker
- Anonymous authentication
- Publishing to wake/event and stt/final topics
- Subscribing to wake/mic and tts/status topics
- QoS 1 message delivery
- Reconnection behavior
- Health status publishing

**Prerequisites**:
- Running MQTT broker on main TARS system
- Set `MQTT_TEST_HOST` environment variable to broker IP

**Run**:
```bash
# Set broker IP
export MQTT_TEST_HOST=192.168.1.100

# Run tests
pytest tests/remote-mic/test_mqtt_connection.py -v
```

**Note**: These are integration tests and require actual MQTT broker access.

---

## Running All Tests

### Quick Validation (no broker needed)

```bash
pytest tests/remote-mic/test_remote_deployment.py -v
```

### Full Integration Tests (requires MQTT broker)

```bash
# On main TARS system, ensure broker is running
docker compose -f ops/compose.yml up mqtt -d

# On remote device (or any device with network access)
export MQTT_TEST_HOST=192.168.1.100  # Main TARS system IP
pytest tests/remote-mic/ -v
```

### Run from repository root

```bash
cd /path/to/py-tars
pytest tests/remote-mic/ -v
```

---

## Test Requirements

### Python Packages

Required for all tests:
```bash
pip install pytest pyyaml
```

Required for MQTT tests:
```bash
pip install paho-mqtt
```

Or install from repository requirements:
```bash
pip install -r requirements-test.txt  # If it exists
```

---

## Expected Results

### test_remote_deployment.py

All tests should **pass** if:
- `ops/compose.remote-mic.yml` is correctly structured
- `ops/.env.remote-mic.example` contains all required variables
- `docs/REMOTE_MICROPHONE_SETUP.md` exists with essential sections

### test_mqtt_connection.py

Tests are **skipped** if:
- `MQTT_TEST_HOST` environment variable not set
- `paho-mqtt` package not installed

Tests **pass** if:
- MQTT broker is running and accessible at `MQTT_TEST_HOST:1883`
- Broker allows anonymous connections (mosquitto.conf: `allow_anonymous true`)
- Broker binds to network interface (mosquitto.conf: `listener 1883 0.0.0.0`)
- Firewall allows port 1883/tcp

Tests **fail** if:
- Cannot reach broker (network issue, firewall, wrong IP)
- Authentication required (but not provided)
- Topics are restricted (ACL configuration)

---

## Troubleshooting

### "Cannot connect to MQTT broker"

1. **Check broker is running**:
   ```bash
   # On main TARS system
   docker ps | grep mqtt
   ```

2. **Check network connectivity**:
   ```bash
   # From test environment
   ping -c 4 192.168.1.100  # Replace with your MQTT_TEST_HOST
   nc -zv 192.168.1.100 1883
   ```

3. **Verify broker configuration**:
   ```bash
   # On main TARS system
   cat ops/mosquitto.conf | grep listener
   # Should show: listener 1883 0.0.0.0
   
   cat ops/mosquitto.conf | grep allow_anonymous
   # Should show: allow_anonymous true
   ```

4. **Check firewall**:
   ```bash
   # On main TARS system
   sudo ufw status
   sudo firewall-cmd --list-ports
   # Ensure 1883/tcp is allowed
   ```

### "paho-mqtt not installed"

```bash
pip install paho-mqtt
```

### "MQTT_TEST_HOST not set"

```bash
export MQTT_TEST_HOST=192.168.1.100  # Replace with your broker IP
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Remote Microphone Tests

on: [push, pull_request]

jobs:
  test-config:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install pytest pyyaml
      - name: Run deployment tests
        run: |
          pytest tests/remote-mic/test_remote_deployment.py -v

  test-mqtt-integration:
    runs-on: ubuntu-latest
    services:
      mqtt:
        image: eclipse-mosquitto:2
        ports:
          - 1883:1883
        options: >-
          --health-cmd "mosquitto_sub -t '$SYS/#' -C 1"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install pytest paho-mqtt
      - name: Run MQTT tests
        run: |
          export MQTT_TEST_HOST=localhost
          pytest tests/remote-mic/test_mqtt_connection.py -v
```

---

## Adding New Tests

### Test Checklist

When adding new tests for remote microphone features:

1. **Configuration Tests** → Add to `test_remote_deployment.py`
   - New environment variables
   - New services or volumes
   - Documentation requirements

2. **Integration Tests** → Add to `test_mqtt_connection.py`
   - New MQTT topics
   - New message contracts
   - Connection behaviors

3. **Update this README** with:
   - Test description
   - Prerequisites
   - Expected results

### Test Naming Convention

- `test_<feature>_<aspect>`: Clear, descriptive names
- Example: `test_mqtt_publish_wake_event`, `test_stt_service_configuration`

### Test Documentation

Each test function should have:
- Docstring explaining what it validates
- Clear assertion messages
- Appropriate pytest markers (skip conditions, etc.)

---

## Related Documentation

- **Feature Specification**: `specs/006-remote-mic/spec.md`
- **Implementation Plan**: `specs/006-remote-mic/plan.md`
- **Deployment Guide**: `docs/REMOTE_MICROPHONE_SETUP.md`
- **Quickstart**: `specs/006-remote-mic/quickstart.md`
- **MQTT Contracts**: `docs/mqtt-contracts.md`
