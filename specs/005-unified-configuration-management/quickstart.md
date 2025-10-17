# Quickstart: Unified Configuration Management

**Date**: 2025-10-17  
**Feature**: 005-unified-configuration-management  
**Purpose**: Setup guide for developers and operators

## Prerequisites

- Python 3.11+
- Docker & Docker Compose (for Litestream sidecar)
- MQTT broker (Mosquitto)
- S3-compatible storage (AWS S3 or MinIO) for backups

## Environment Variables

Create or update `.env` file with the following variables:

```bash
# ===== Configuration Database =====
CONFIG_DB_PATH=/data/config/config.db
CONFIG_LKG_CACHE_PATH=/data/config/config.lkg.json
CONFIG_EPOCH_PATH=/data/config/health+epoch.json

# ===== Encryption Keys (auto-generated on first run if missing) =====
# Master key for AES-256-GCM encryption of database secrets (32 bytes base64)
CONFIG_MASTER_KEY_BASE64=CHANGEME_base64_encoded_32_bytes
CONFIG_MASTER_KEY_ID=00000000-0000-0000-0000-000000000000

# HMAC key for signing LKG cache (32 bytes base64)
LKG_HMAC_KEY_BASE64=CHANGEME_base64_encoded_32_bytes
LKG_HMAC_KEY_ID=00000000-0000-0000-0000-000000000000

# ===== Ed25519 Signature Keys (auto-generated on first run if missing) =====
# For signing MQTT configuration update messages
CONFIG_SIGNATURE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nCHANGEME\n-----END PRIVATE KEY-----"
CONFIG_SIGNATURE_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\nCHANGEME\n-----END PUBLIC KEY-----"

# ===== Recovery & Rebuild =====
# Allow automatic database rebuild on corruption (0=disabled, 1=enabled)
ALLOW_AUTO_REBUILD=0

# Token required for manual rebuild trigger via API (generate secure random string)
REBUILD_TOKEN=CHANGEME_secure_random_token

# ===== Litestream Backup =====
# S3-compatible storage for continuous backups
LITESTREAM_S3_ENDPOINT=https://s3.amazonaws.com
LITESTREAM_S3_BUCKET=tars-config-backups
LITESTREAM_S3_PATH=config-db
LITESTREAM_ACCESS_KEY_ID=CHANGEME
LITESTREAM_SECRET_ACCESS_KEY=CHANGEME
LITESTREAM_RETENTION_HOURS=168  # 7 days

# ===== MQTT =====
MQTT_URL=mqtt://user:password@localhost:1883

# ===== Config Manager Service =====
CONFIG_MANAGER_HOST=0.0.0.0
CONFIG_MANAGER_PORT=8081
CONFIG_MANAGER_LOG_LEVEL=INFO

# ===== Access Control =====
# API tokens for REST endpoints (comma-separated: token:role)
# Roles: config.read (view configs), config.write (modify configs)
CONFIG_API_TOKENS="readonly-token:config.read,admin-token:config.write"
```

## Initial Setup

### 1. Generate Encryption Keys (First Run)

If you don't have encryption keys yet, the config-manager service will auto-generate them on first run:

```bash
# Start the service - it will print keys to stdout if .env is unwritable
docker compose up config-manager

# If .env is writable, keys are automatically added
# If not, copy the printed keys to your .env file manually
```

**Manual key generation** (if needed):

```python
import os
import base64
import uuid
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# Generate AES master key (32 bytes for AES-256)
master_key = os.urandom(32)
print(f"CONFIG_MASTER_KEY_BASE64={base64.b64encode(master_key).decode()}")
print(f"CONFIG_MASTER_KEY_ID={uuid.uuid4()}")

# Generate HMAC key (32 bytes)
hmac_key = os.urandom(32)
print(f"LKG_HMAC_KEY_BASE64={base64.b64encode(hmac_key).decode()}")
print(f"LKG_HMAC_KEY_ID={uuid.uuid4()}")

# Generate Ed25519 keypair
private_key = ed25519.Ed25519PrivateKey.generate()
public_key = private_key.public_key()

private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
).decode()

public_pem = public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
).decode()

print(f"CONFIG_SIGNATURE_PRIVATE_KEY=\"{private_pem.strip()}\"")
print(f"CONFIG_SIGNATURE_PUBLIC_KEY=\"{public_pem.strip()}\"")
```

### 2. Start Services

```bash
# Start all services including config-manager
docker compose up -d

# Check config-manager health
curl http://localhost:8081/api/config/health
```

Expected response:
```json
{
  "ok": true,
  "database_status": "healthy",
  "operational_mode": "normal",
  "config_epoch": "550e8400-e29b-41d4-a716-446655440000",
  "schema_version": 1,
  "lkg_cache_valid": true,
  "litestream_status": "healthy",
  "last_backup": "2025-10-17T12:00:00Z"
}
```

### 3. Verify MQTT Integration

```bash
# Subscribe to configuration updates (use your MQTT credentials)
mosquitto_sub -h localhost -u user -P password -t 'system/config/#' -v

# Subscribe to health status
mosquitto_sub -h localhost -u user -P password -t 'system/health/config-manager' -v
```

### 4. Access Web UI

Open browser to: `http://localhost:8080` (ui-web service)

Navigate to the configuration management section via the settings cog icon or service tabs.

## Using the Configuration Library (Services)

### 1. Add Dependency

In your service's `pyproject.toml`:

```toml
[project]
dependencies = [
    "tars-core",  # Already includes config library
    # ... other deps
]
```

### 2. Define Service Configuration Model

Create your service's config model in `tars-core`:

```python
# packages/tars-core/src/tars/config/models.py

from pydantic import BaseModel, Field, ConfigDict

class MyServiceConfig(BaseModel):
    """Configuration for my-service."""
    model_config = ConfigDict(extra="forbid")
    
    some_setting: str = Field(default="default_value")
    another_setting: int = Field(default=100, ge=0, le=1000)
    enable_feature: bool = Field(default=False)
```

### 3. Use Configuration in Service

```python
# apps/my-service/src/my_service/service.py

import asyncio
from tars.config.library import ConfigLibrary, ConfigUpdateCallback
from tars.config.models import MyServiceConfig

class MyService:
    def __init__(self):
        self.config_lib = ConfigLibrary(service_name="my-service")
        self.config: MyServiceConfig | None = None
    
    async def start(self) -> None:
        # Load configuration from database
        self.config = await self.config_lib.get_config(MyServiceConfig)
        
        # Subscribe to runtime updates
        await self.config_lib.subscribe_updates(self._on_config_update)
        
        print(f"Loaded config: {self.config}")
    
    async def _on_config_update(self, new_config: MyServiceConfig) -> None:
        """Called when configuration changes via MQTT."""
        print(f"Config updated: {new_config}")
        self.config = new_config
        # Apply changes as needed (some settings may require restart)
    
    async def shutdown(self) -> None:
        await self.config_lib.close()

# Usage
async def main():
    service = MyService()
    await service.start()
    # ... run service
    await service.shutdown()
```

## REST API Usage

### List All Services

```bash
curl -H "X-API-Token: readonly-token" \
  http://localhost:8081/api/config/services
```

### Get Service Configuration

```bash
curl -H "X-API-Token: readonly-token" \
  http://localhost:8081/api/config/services/stt-worker
```

### Update Service Configuration

```bash
curl -X PUT \
  -H "X-API-Token: admin-token" \
  -H "Content-Type: application/json" \
  -d '{
    "service": "stt-worker",
    "config": {
      "whisper_model": "small.en",
      "vad_threshold": 0.6
    },
    "version": 1
  }' \
  http://localhost:8081/api/config/services/stt-worker
```

### Search Configurations

```bash
curl -X POST \
  -H "X-API-Token: readonly-token" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "whisper",
    "complexity_filter": "simple"
  }' \
  http://localhost:8081/api/config/search
```

## Database Management

### Backup & Restore

**Litestream handles backups automatically.** To manually restore:

```bash
# Stop config-manager
docker compose stop config-manager

# Restore from specific timestamp
docker compose run --rm litestream restore \
  -o /data/config/config.db \
  -timestamp 2025-10-17T12:00:00Z \
  /data/config/config.db

# Or restore latest
docker compose run --rm litestream restore \
  -o /data/config/config.db \
  /data/config/config.db

# Restart config-manager
docker compose start config-manager
```

### Manual Rebuild (Emergency)

If database is corrupted and auto-rebuild is disabled:

```bash
# Trigger rebuild via API (requires REBUILD_TOKEN)
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"token": "your-rebuild-token-from-env"}' \
  http://localhost:8081/api/config/rebuild
```

**Warning**: Rebuild creates a new database with defaults. User-created secrets will be lost and must be re-entered.

### Encryption Key Rotation

When rotating CONFIG_MASTER_KEY_BASE64:

1. Generate new key with new ID
2. Add both old and new keys to .env (grace window)
3. Restart config-manager
4. Re-encryption job runs automatically
5. After completion, remove old key from .env

```bash
# In .env during rotation
CONFIG_MASTER_KEY_BASE64=new_key_here
CONFIG_MASTER_KEY_ID=new_uuid_here
CONFIG_MASTER_KEY_OLD_BASE64=old_key_here
CONFIG_MASTER_KEY_OLD_ID=old_uuid_here
CONFIG_KEY_ROTATION_GRACE_MINUTES=60
```

## Troubleshooting

### Database Locked

**Symptom**: `database is locked` errors

**Solution**: System automatically falls back to LKG cache. Check:
1. WAL mode enabled: `PRAGMA journal_mode;` should return `wal`
2. No long-running transactions blocking
3. Litestream not holding lock during backup

### Schema Mismatch

**Symptom**: Read-only fallback mode, logs show schema incompatibility

**Solution**:
1. Check Pydantic model changes in recent updates
2. Either update models to match DB or rebuild with `ALLOW_AUTO_REBUILD=1`
3. Verify schema_version table: `SELECT * FROM schema_version;`

### MQTT Signature Verification Failures

**Symptom**: Services log "invalid signature" when receiving config updates

**Solution**:
1. Verify CONFIG_SIGNATURE_PUBLIC_KEY matches in all service .env files
2. Check clock sync across services (signature includes timestamp)
3. Ensure ed25519 keys are valid PEM format

### LKG Cache Invalid

**Symptom**: Health shows `lkg_cache_valid: false`

**Solution**:
1. Check LKG_HMAC_KEY_BASE64 is correct and not changed
2. Cache regenerates automatically on next successful DB read
3. If persistent, delete cache file and restart: `rm /data/config/config.lkg.json`

## Development Workflow

1. **Update Pydantic model** in `packages/tars-core/src/tars/config/models.py`
2. **Write tests** for validation and defaults
3. **Run migrations** (schema version auto-increments)
4. **Update UI** to display new fields if user-facing
5. **Deploy** config-manager service
6. **Update services** to use new fields

## Next Steps

- Explore Web UI configuration editor
- Set up Litestream backups to production S3
- Configure access control tokens for your team
- Customize service configuration models

For implementation details, see [data-model.md](./data-model.md) and [contracts/](./contracts/).
