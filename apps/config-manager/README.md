# Config Manager Service

Centralized configuration management service for TARS with SQLite storage, HMAC-signed caching for fallback, web UI for configuration management, and MQTT-based runtime updates.

## Overview

The config-manager service provides:
- Centralized SQLite database for all service configurations
- Web UI for viewing and editing configurations
- MQTT-based runtime configuration updates (Ed25519 signed)
- Read-only fallback mode using HMAC-verified last-known-good cache
- Continuous backups via Litestream to S3/MinIO
- Access control with API tokens
- Configuration change history and audit trail

## MQTT Topics

### Published

- **`system/config/<service>`** (QoS 1, retained) - Configuration updates for specific service
  - Payload: `ConfigUpdatePayload` (see contracts/mqtt-config-update.json)
  - Signed with Ed25519 for authentication
  - Published after every configuration change via REST API

- **`system/health/config-manager`** (QoS 1, retained) - Health status
  - Payload: `ConfigHealthPayload` (see contracts/mqtt-health-status.json)
  - Includes database status, operational mode, schema version
  - Updated on state transitions (normal ↔ read-only-fallback ↔ rebuilding)

### Subscribed

- None (config-manager is a source, not a consumer)

## Environment Variables

See `.env.example` for complete list. Key variables:

- **CONFIG_DB_PATH** - Path to SQLite database (default: `/data/config/config.db`)
- **CONFIG_MASTER_KEY_BASE64** - AES-256 encryption key for secrets (auto-generated)
- **CONFIG_SIGNATURE_PRIVATE_KEY** - Ed25519 private key for signing MQTT messages (auto-generated)
- **MQTT_URL** - MQTT broker connection string
- **CONFIG_MANAGER_PORT** - HTTP port for REST API (default: 8081)
- **CONFIG_API_TOKENS** - API tokens for access control (format: `token:role,token:role`)
- **ALLOW_AUTO_REBUILD** - Enable automatic database rebuild on corruption (0=disabled, 1=enabled)

## Development Workflow

### Setup

```bash
# Install dependencies
make install

# Copy environment template
cp .env.example .env

# Edit .env with your configuration (keys will be auto-generated on first run)
```

### Running Locally

```bash
# Run the service
python -m config_manager

# Or via Docker
docker compose up config-manager
```

### Testing

```bash
# Run all tests
make test

# Run specific test types
pytest -m unit           # Unit tests only
pytest -m integration    # Integration tests (require MQTT + DB)
pytest -m contract       # Contract tests (MQTT schema validation)
```

### Linting and Formatting

```bash
# Format code
make fmt

# Lint code
make lint

# Run all checks (CI gate)
make check
```

## REST API Endpoints

### Health

- **GET /api/config/health** - Service health status

### Configuration CRUD

- **GET /api/config/services** - List all services
- **GET /api/config/services/{service}** - Get service configuration
- **PUT /api/config/services/{service}** - Update service configuration (requires `config.write` role)

### Search

- **POST /api/config/search** - Search configurations by keyword

### History

- **GET /api/config/history** - Get configuration change history
- **POST /api/config/history/restore** - Restore configuration to specific point in time

### Profiles

- **GET /api/config/profiles** - List saved configuration profiles
- **POST /api/config/profiles** - Save current configuration as profile
- **PUT /api/config/profiles/{name}/activate** - Activate saved profile
- **DELETE /api/config/profiles/{name}** - Delete profile

### Rebuild

- **POST /api/config/rebuild** - Manually trigger database rebuild (requires `REBUILD_TOKEN`)

## Architecture

```
┌─────────────────┐
│   Web UI        │
│  (ui-web)       │
└────────┬────────┘
         │ REST API
         ▼
┌─────────────────┐      MQTT (signed)      ┌─────────────────┐
│ Config Manager  │───────────────────────▶ │   Services      │
│   (FastAPI)     │                         │ (STT, TTS, etc) │
└────────┬────────┘                         └─────────────────┘
         │
         ▼
┌─────────────────┐      Replicate         ┌─────────────────┐
│  SQLite (WAL)   │───────────────────────▶│  Litestream     │
│   config.db     │                         │  (S3 backup)    │
└────────┬────────┘                         └─────────────────┘
         │
         ▼
┌─────────────────┐
│  LKG Cache      │
│ (HMAC signed)   │
└─────────────────┘
```

## Operational Modes

### Normal

- Database healthy and writable
- All CRUD operations available
- Configuration updates published via MQTT
- LKG cache updated on every successful read

### Read-Only Fallback

- Database unavailable or corrupted
- Services read from LKG cache (HMAC verified)
- REST API returns read-only errors for write operations
- Automatic recovery when database becomes healthy

### Rebuilding

- Database being reconstructed from scratch
- All services use LKG cache
- New config_epoch assigned after rebuild
- Tombstone file created with rebuild metadata

## Security

### Encryption

- **AES-256-GCM** for database secrets (user-created secrets only, not .env secrets)
- **Ed25519** signatures for MQTT message authentication
- **HMAC-SHA256** for LKG cache integrity verification

### Access Control

- API token authentication via `X-API-Token` header
- Role-based access: `config.read` (view) and `config.write` (modify)
- Audit logging for all configuration changes
- Secret reveal logging (when secrets displayed in UI)

### Key Rotation

- Master key rotation supported via dual-key grace window
- Re-encryption job runs automatically on key ID change
- Ed25519 keypair rotation requires manual coordination (public key distribution)

## Troubleshooting

### Database Locked

If you see "database is locked" errors:
1. Verify WAL mode is enabled: `PRAGMA journal_mode;` should return `wal`
2. Check for long-running transactions
3. Ensure Litestream isn't holding exclusive lock during backup

### Schema Mismatch

If service enters read-only fallback with schema errors:
1. Check if Pydantic models changed in recent update
2. Either update models to match DB or rebuild database
3. Set `ALLOW_AUTO_REBUILD=1` for automatic rebuild on mismatch

### MQTT Signature Failures

If services log "invalid signature" errors:
1. Verify `CONFIG_SIGNATURE_PUBLIC_KEY` matches across all services
2. Check system clock sync (signatures include timestamp)
3. Ensure Ed25519 keys are valid PEM format

## License

Same as main TARS project.
