# MQTTClient Configuration Guide

Complete reference for configuring the centralized MQTT client via environment variables.

**Module**: `tars.adapters.mqtt_client`  
**Configuration Method**: Environment variables (12-factor app)

---

## Table of Contents

- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
  - [Required Variables](#required-variables)
  - [Optional Variables](#optional-variables)
- [Configuration Examples](#configuration-examples)
- [Validation Rules](#validation-rules)
- [Default Values](#default-values)

---

## Quick Start

### Minimal Configuration

```bash
# .env file
MQTT_URL=mqtt://localhost:1883
MQTT_CLIENT_ID=my-service
```

```python
from tars.adapters.mqtt_client import MQTTClient

# Load from environment
client = MQTTClient.from_env()
await client.connect()
```

### Production Configuration

```bash
# .env file
MQTT_URL=mqtt://user:password@mqtt.example.com:1883
MQTT_CLIENT_ID=my-service-prod
MQTT_SOURCE_NAME=my-service
MQTT_ENABLE_HEALTH=true
MQTT_ENABLE_HEARTBEAT=true
MQTT_HEARTBEAT_INTERVAL=30.0
MQTT_DEDUPE_TTL=5.0
MQTT_DEDUPE_MAX_ENTRIES=1000
MQTT_RECONNECT_MIN_DELAY=1.0
MQTT_RECONNECT_MAX_DELAY=5.0
```

---

## Environment Variables

### Required Variables

#### MQTT_URL

**Type**: `str`  
**Required**: Yes  
**Format**: `mqtt://[user:pass@]host[:port]`  
**Description**: MQTT broker connection URL

**Examples**:

```bash
# Local broker (no auth)
MQTT_URL=mqtt://localhost:1883

# Remote broker with credentials
MQTT_URL=mqtt://admin:secret@mqtt.example.com:1883

# Custom port
MQTT_URL=mqtt://192.168.1.100:8883
```

**Notes**:

- Protocol must be `mqtt://` (TLS not currently supported)
- Default port is 1883 if not specified
- URL-encode special characters in username/password

#### MQTT_CLIENT_ID

**Type**: `str`  
**Required**: Yes  
**Description**: Unique client identifier for MQTT connection

**Examples**:

```bash
# Service name
MQTT_CLIENT_ID=stt-worker

# Service with instance ID
MQTT_CLIENT_ID=llm-worker-1

# Hostname-based
MQTT_CLIENT_ID=tars-pi-main
```

**Notes**:

- Must be unique across all connected clients
- Duplicate client IDs cause disconnections
- Used in health topic: `system/health/{client_id}`
- Used in heartbeat topic: `system/keepalive/{client_id}`

---

### Optional Variables

#### MQTT_SOURCE_NAME

**Type**: `str`  
**Required**: No  
**Default**: Same as `MQTT_CLIENT_ID`  
**Description**: Source name for envelope metadata

**Example**:

```bash
MQTT_CLIENT_ID=stt-worker-1
MQTT_SOURCE_NAME=stt-worker  # Logical service name
```

**Notes**:

- Appears in `envelope.source` field
- Use for logical service name when `client_id` includes instance suffix

#### MQTT_ENABLE_HEALTH

**Type**: `bool` (string: `"true"` / `"false"`)  
**Required**: No  
**Default**: `false`  
**Description**: Enable health status publishing to `system/health/{client_id}`

**Example**:

```bash
MQTT_ENABLE_HEALTH=true
```

**Behavior when enabled**:

- Publishes health status on connect: `{ok: true, event: "connected"}`
- Publishes health status on shutdown: `{ok: false, event: "shutdown"}`
- Manual updates via `publish_health()`
- QoS 1 (at-least-once)
- Retained (latest status always available)

#### MQTT_ENABLE_HEARTBEAT

**Type**: `bool` (string: `"true"` / `"false"`)  
**Required**: No  
**Default**: `false`  
**Description**: Enable periodic heartbeat publishing

**Example**:

```bash
MQTT_ENABLE_HEARTBEAT=true
MQTT_HEARTBEAT_INTERVAL=30.0
```

**Behavior when enabled**:

- Publishes to `system/keepalive/{client_id}` at configured interval
- Payload: `{ok: true, event: "heartbeat", timestamp: <unix_ts>}`
- Watchdog detects stale connections (3x interval)
- QoS 0 (best-effort)
- Not retained

#### MQTT_HEARTBEAT_INTERVAL

**Type**: `float`  
**Required**: No  
**Default**: `30.0`  
**Minimum**: `1.0`  
**Unit**: Seconds  
**Description**: Interval between heartbeat publishes

**Example**:

```bash
MQTT_HEARTBEAT_INTERVAL=60.0  # Heartbeat every minute
```

**Notes**:

- Only used when `MQTT_ENABLE_HEARTBEAT=true`
- Watchdog triggers at 3x this interval
- Lower values = more frequent heartbeats = more MQTT traffic

#### MQTT_DEDUPE_TTL

**Type**: `float`  
**Required**: No  
**Default**: `0.0` (deduplication disabled)  
**Minimum**: `0.0`  
**Unit**: Seconds  
**Description**: Message deduplication time-to-live

**Example**:

```bash
MQTT_DEDUPE_TTL=5.0
MQTT_DEDUPE_MAX_ENTRIES=1000
```

**Behavior when enabled (`> 0`)**:

- Deduplicates messages by envelope ID
- Messages with same ID within TTL window are skipped
- Requires `MQTT_DEDUPE_MAX_ENTRIES > 0`

**Use cases**:

- Prevent duplicate message processing
- Handle MQTT reconnection duplicates (QoS 1)
- Idempotency for critical handlers

#### MQTT_DEDUPE_MAX_ENTRIES

**Type**: `int`  
**Required**: No (required when `MQTT_DEDUPE_TTL > 0`)  
**Default**: `0`  
**Minimum**: `0`  
**Description**: Maximum deduplication cache entries (LRU)

**Example**:

```bash
MQTT_DEDUPE_TTL=5.0
MQTT_DEDUPE_MAX_ENTRIES=1000
```

**Notes**:

- Must be `> 0` when `MQTT_DEDUPE_TTL > 0` (validation error otherwise)
- Older entries are evicted when cache is full (LRU)
- Higher values = more memory, better deduplication coverage
- Recommended: `1000` for most services

#### MQTT_RECONNECT_MIN_DELAY

**Type**: `float`  
**Required**: No  
**Default**: `1.0`  
**Minimum**: `0.1`  
**Unit**: Seconds  
**Description**: Minimum reconnection delay (exponential backoff starts here)

**Example**:

```bash
MQTT_RECONNECT_MIN_DELAY=0.5  # Fast reconnection
MQTT_RECONNECT_MAX_DELAY=10.0
```

**Notes**:

- First reconnection attempt waits this long
- Subsequent attempts use exponential backoff
- Must be ≤ `MQTT_RECONNECT_MAX_DELAY`

#### MQTT_RECONNECT_MAX_DELAY

**Type**: `float`  
**Required**: No  
**Default**: `5.0`  
**Minimum**: `0.5`  
**Unit**: Seconds  
**Description**: Maximum reconnection delay (exponential backoff cap)

**Example**:

```bash
MQTT_RECONNECT_MIN_DELAY=1.0
MQTT_RECONNECT_MAX_DELAY=30.0  # Max 30s between retries
```

**Notes**:

- Exponential backoff caps at this value
- Must be ≥ `MQTT_RECONNECT_MIN_DELAY`
- Higher values reduce reconnection attempt frequency

---

## Configuration Examples

### Development (Minimal)

```bash
MQTT_URL=mqtt://localhost:1883
MQTT_CLIENT_ID=dev-service
```

### Production Service

```bash
MQTT_URL=mqtt://mqtt_user:mqtt_pass@mqtt.prod.example.com:1883
MQTT_CLIENT_ID=stt-worker-prod-1
MQTT_SOURCE_NAME=stt-worker
MQTT_ENABLE_HEALTH=true
MQTT_ENABLE_HEARTBEAT=true
MQTT_HEARTBEAT_INTERVAL=30.0
MQTT_DEDUPE_TTL=5.0
MQTT_DEDUPE_MAX_ENTRIES=1000
MQTT_RECONNECT_MIN_DELAY=1.0
MQTT_RECONNECT_MAX_DELAY=10.0
```

### High-Availability Service

```bash
MQTT_URL=mqtt://ha-user:ha-pass@mqtt-ha.example.com:1883
MQTT_CLIENT_ID=critical-service-ha-1
MQTT_ENABLE_HEALTH=true
MQTT_ENABLE_HEARTBEAT=true
MQTT_HEARTBEAT_INTERVAL=10.0  # Faster heartbeat
MQTT_DEDUPE_TTL=10.0           # Longer dedup window
MQTT_DEDUPE_MAX_ENTRIES=5000   # Larger cache
MQTT_RECONNECT_MIN_DELAY=0.5   # Fast reconnection
MQTT_RECONNECT_MAX_DELAY=5.0
```

### Testing/CI Environment

```bash
MQTT_URL=mqtt://localhost:1883
MQTT_CLIENT_ID=test-client-${RANDOM}  # Unique per test run
MQTT_ENABLE_HEALTH=false               # Skip health for tests
MQTT_ENABLE_HEARTBEAT=false            # Skip heartbeat for tests
MQTT_DEDUPE_TTL=0.0                    # No deduplication for tests
MQTT_RECONNECT_MIN_DELAY=0.1           # Fast reconnection for tests
MQTT_RECONNECT_MAX_DELAY=1.0
```

---

## Validation Rules

The following validation rules are enforced when loading configuration:

### Cross-Field Validation

#### Reconnection Delays

```python
MQTT_RECONNECT_MAX_DELAY >= MQTT_RECONNECT_MIN_DELAY
```

**Error if violated**:

```
ValueError: reconnect_max_delay (2.0) must be >= reconnect_min_delay (5.0)
```

#### Deduplication Cache

```python
if MQTT_DEDUPE_TTL > 0:
    assert MQTT_DEDUPE_MAX_ENTRIES > 0
```

**Error if violated**:

```
ValueError: dedupe_max_entries must be > 0 when dedupe_ttl=5.0
(deduplication requires cache size limit)
```

### Field Constraints

- `MQTT_HEARTBEAT_INTERVAL` ≥ 1.0 (minimum 1 second)
- `MQTT_DEDUPE_TTL` ≥ 0.0 (cannot be negative)
- `MQTT_RECONNECT_MIN_DELAY` ≥ 0.1 (minimum 100ms)
- `MQTT_RECONNECT_MAX_DELAY` ≥ 0.5 (minimum 500ms)

---

## Default Values

| Variable | Default Value | Notes |
|----------|---------------|-------|
| `MQTT_URL` | *(required)* | No default |
| `MQTT_CLIENT_ID` | *(required)* | No default |
| `MQTT_SOURCE_NAME` | `MQTT_CLIENT_ID` | Defaults to client ID |
| `MQTT_ENABLE_HEALTH` | `false` | Disabled by default |
| `MQTT_ENABLE_HEARTBEAT` | `false` | Disabled by default |
| `MQTT_HEARTBEAT_INTERVAL` | `30.0` | 30 seconds |
| `MQTT_DEDUPE_TTL` | `0.0` | Deduplication disabled |
| `MQTT_DEDUPE_MAX_ENTRIES` | `0` | No cache |
| `MQTT_RECONNECT_MIN_DELAY` | `1.0` | 1 second |
| `MQTT_RECONNECT_MAX_DELAY` | `5.0` | 5 seconds |

---

## Loading Configuration

### From Environment

```python
from tars.adapters.mqtt_client import MQTTClient

# Automatically loads all MQTT_* environment variables
client = MQTTClient.from_env()
```

### Manual Configuration (without environment)

```python
from tars.adapters.mqtt_client import MQTTClient

# Bypass environment variables
client = MQTTClient(
    mqtt_url="mqtt://localhost:1883",
    client_id="manual-client",
    source_name="manual-service",
    enable_health=True,
    enable_heartbeat=True,
    heartbeat_interval=30.0,
    dedupe_ttl=5.0,
    dedupe_max_entries=1000,
    reconnect_min_delay=1.0,
    reconnect_max_delay=5.0,
)
```

### Config Object

```python
from tars.adapters.mqtt_client import MQTTClientConfig

# Load config separately
config = MQTTClientConfig.from_env()

# Inspect config
print(f"Client ID: {config.client_id}")
print(f"Health enabled: {config.enable_health}")

# Pass to client
client = MQTTClient(
    mqtt_url=config.mqtt_url,
    client_id=config.client_id,
    # ... other config fields
)
```

---

## Debugging Configuration

### Print Loaded Configuration

```python
from tars.adapters.mqtt_client import MQTTClientConfig

config = MQTTClientConfig.from_env()
print(config.model_dump())
```

### Check Required Variables

```python
import os

required = ["MQTT_URL", "MQTT_CLIENT_ID"]
missing = [var for var in required if var not in os.environ]

if missing:
    raise ValueError(f"Missing required environment variables: {missing}")
```

### Validate Before Loading

```python
import os
from pydantic import ValidationError
from tars.adapters.mqtt_client import MQTTClientConfig

try:
    config = MQTTClientConfig.from_env()
except ValidationError as e:
    print("Configuration errors:")
    for error in e.errors():
        print(f"  - {error['loc']}: {error['msg']}")
    raise
```

---

## Security Considerations

### Credentials in MQTT_URL

**Warning**: Environment variables may be logged or exposed. For production:

1. **Use secrets management**: Inject credentials at runtime from Vault, AWS Secrets Manager, etc.
2. **Restrict access**: Limit who can view environment variables
3. **Rotate credentials**: Regular password rotation

**Example with secrets**:

```python
import os
from my_secrets import get_secret

# Inject credentials at runtime
mqtt_user = get_secret("mqtt_username")
mqtt_pass = get_secret("mqtt_password")
os.environ["MQTT_URL"] = f"mqtt://{mqtt_user}:{mqtt_pass}@mqtt.example.com:1883"

client = MQTTClient.from_env()
```

### URL Encoding

Special characters in username/password must be URL-encoded:

```python
from urllib.parse import quote

username = "user@example.com"
password = "p@ssw0rd!"

encoded_user = quote(username, safe="")  # user%40example.com
encoded_pass = quote(password, safe="")  # p%40ssw0rd%21

mqtt_url = f"mqtt://{encoded_user}:{encoded_pass}@mqtt.example.com:1883"
```

---

## Common Issues

### "Missing required environment variable: MQTT_URL"

**Cause**: `MQTT_URL` not set  
**Fix**: Set `MQTT_URL` in `.env` file or environment

```bash
export MQTT_URL=mqtt://localhost:1883
```

### "reconnect_max_delay must be >= reconnect_min_delay"

**Cause**: Max delay is less than min delay  
**Fix**: Ensure `MQTT_RECONNECT_MAX_DELAY ≥ MQTT_RECONNECT_MIN_DELAY`

```bash
MQTT_RECONNECT_MIN_DELAY=1.0
MQTT_RECONNECT_MAX_DELAY=5.0  # Must be >= 1.0
```

### "dedupe_max_entries must be > 0 when dedupe_ttl > 0"

**Cause**: Deduplication enabled without cache size  
**Fix**: Set `MQTT_DEDUPE_MAX_ENTRIES > 0` when using deduplication

```bash
MQTT_DEDUPE_TTL=5.0
MQTT_DEDUPE_MAX_ENTRIES=1000  # Required
```

---

## See Also

- [API Reference](API.md): Complete MQTTClient API documentation
- [Migration Guide](MIGRATION_GUIDE.md): Migrating from custom MQTT wrappers
- [Quickstart](../specs/004-centralize-mqtt-client/quickstart.md): Usage patterns and examples
