# Implementation Plan: Unified Configuration Management System

**Branch**: `005-unified-configuration-management` | **Date**: 2025-10-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-unified-configuration-management/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build a centralized configuration management system with SQLite storage, HMAC-signed caching for fallback, web UI for configuration management, and MQTT-based runtime updates. All configuration logic will be centralized in the tars-core package with Pydantic v2 models for type safety. Services will read from the database at startup and subscribe to Ed25519-signed MQTT updates for runtime changes. The system provides read-only fallback mode using an HMAC-verified last-known-good cache when the database is unavailable.

## Technical Context

**Language/Version**: Python 3.11+ (required for TaskGroup, better async)  
**Primary Dependencies**: 
- FastAPI (existing in ui-web for REST API and WebUI)
- Pydantic v2 (for configuration models and validation)
- SQLite with WAL mode (configuration database)
- aiosqlite (async SQLite access)
- orjson (JSON serialization)
- cryptography (AES-256-GCM encryption, Ed25519 signing, HMAC-SHA256)
- asyncio-mqtt / paho-mqtt (MQTT communication)

**Storage**: 
- SQLite in WAL mode for configuration database (dual table: service_configs + config_items)
- HMAC-signed JSON cache file (config.lkg.json) for read-only fallback
- .env files for secrets and encryption keys
- S3/MinIO via Litestream for continuous backups

**Testing**: pytest + pytest-asyncio (unit, integration, contract tests)

**Target Platform**: Linux server (Orange Pi 5 Max primary target)

**Project Type**: Web application (FastAPI backend + Vue.js frontend already in ui-web)

**Performance Goals**: 
- Configuration reads <50ms (library API)
- Database startup load <1 second
- MQTT update signature verification <1ms
- LKG cache HMAC verification <50ms
- Web UI loads all configs <2 seconds
- Search/filter results <300ms

**Constraints**: 
- <200ms p95 for config retrieval
- Database <10MB even with extensive history
- Read-only fallback with zero downtime
- Event loop non-blocking (CPU work via asyncio.to_thread)

**Scale/Scope**: 
- 100+ configuration entries across 10+ services
- Schema version tracking via model hash
- Encryption key rotation support
- Multi-role access control (config.read/config.write)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Event-Driven Architecture ✅
- **Compliant**: Configuration updates published to `system/config/<service>` with QoS 1 + retained
- **Compliant**: Services subscribe to MQTT for runtime updates; no direct service-to-service calls
- **Compliant**: All payloads use Pydantic v2 models with `ConfigDict(extra="forbid")`
- **Compliant**: orjson for all JSON serialization/deserialization
- **Action**: Define typed models for all MQTT payloads in Phase 1

### II. Typed Contracts ✅
- **Compliant**: All configuration models use Pydantic v2 with full type annotations
- **Compliant**: No `Any` types; explicit typing for all configuration fields
- **Compliant**: Round-trip serialization tests required for all models
- **Action**: Create comprehensive Pydantic models in Phase 1 data-model.md

### III. Async-First Concurrency ✅
- **Compliant**: Database operations via aiosqlite (async SQLite)
- **Compliant**: Encryption/decryption offloaded via `asyncio.to_thread()` (CPU-bound)
- **Compliant**: MQTT subscriptions use asyncio-mqtt with persistent subscriptions
- **Compliant**: Request-response uses Futures (no polling)
- **Compliant**: Timeout handling with `asyncio.wait_for()` for all operations
- **Action**: Ensure all DB and crypto operations properly async in Phase 2

### IV. Test-First Development ✅
- **Compliant**: Will write contract tests for MQTT schemas
- **Compliant**: Integration tests for database + MQTT + LKG cache
- **Compliant**: Unit tests for encryption, validation, precedence logic
- **Action**: Create test suite in Phase 1 before implementation

### V. Configuration via Environment ✅
- **Compliant**: Encryption keys (CONFIG_MASTER_KEY_BASE64, LKG_HMAC_KEY_BASE64) from .env
- **Compliant**: Signature keys (CONFIG_SIGNATURE_PRIVATE_KEY, CONFIG_SIGNATURE_PUBLIC_KEY) from .env
- **Compliant**: Database path, backup config from environment
- **Compliant**: Secrets redacted in logs
- **Compliant**: Fail fast with clear errors for missing required config
- **Action**: Document all env vars in .env.example in Phase 1

### VI. Observability & Health Monitoring ✅
- **Compliant**: Health status includes database state, schema version, encryption status
- **Compliant**: Structured JSON logs with correlation IDs (config_epoch, request_id)
- **Compliant**: Metrics for config reads, writes, fallback events, signature failures
- **Compliant**: Audit logs for secret reveals, config changes, access violations
- **Action**: Define health payload structure in Phase 1 contracts

### VII. Simplicity & YAGNI ⚠️ **JUSTIFICATION REQUIRED**
- **Complexity**: This feature introduces significant complexity (SQLite, encryption, MQTT signing, LKG cache, schema versioning)
- **Justification**: Current configuration spread across .env files in 10+ services is unmaintainable; no way to update configs without service restarts; no validation or audit trail; no user-friendly management interface
- **Simpler Alternative Rejected**: 
  - Continuing with .env-only → rejected because requires file editing + container rebuilds + no validation
  - Shared .env file → rejected because no encryption for user secrets, no runtime updates
  - etcd/Consul → rejected as over-engineering for single-node deployment
- **Decision**: Proceed with centralized config system; complexity justified by operational benefits

**GATE RESULT**: ✅ **PASS** (with complexity justification documented above)

---

## Constitution Check (Post-Design Re-evaluation)

*Re-checked after Phase 1 design completion*

### I. Event-Driven Architecture ✅
- ✅ Contracts defined: `mqtt-config-update.json`, `mqtt-health-status.json`
- ✅ All payloads use Pydantic v2 models with strict validation
- ✅ No direct service-to-service calls in design
- ✅ QoS and retention policies documented

### II. Typed Contracts ✅
- ✅ Comprehensive Pydantic models in `data-model.md`
- ✅ OpenAPI schema in `contracts/rest-api.json`
- ✅ All MQTT schemas in JSON Schema format
- ✅ No `Any` types; all fields explicitly typed

### III. Async-First Concurrency ✅
- ✅ Database layer uses `aiosqlite` (async)
- ✅ Encryption offloaded via `asyncio.to_thread()` pattern documented
- ✅ MQTT subscriptions persistent (no per-request overhead)
- ✅ Request-response uses Futures (documented in research.md)

### IV. Test-First Development ✅
- ✅ Contract tests required for all MQTT schemas
- ✅ Integration tests for DB + MQTT + cache flows
- ✅ Unit tests for crypto, validation, precedence
- ✅ Test structure defined in project layout

### V. Configuration via Environment ✅
- ✅ All keys and secrets from .env (documented in quickstart.md)
- ✅ Auto-generation with fail-fast on unwritable .env
- ✅ Secrets redaction in logs (design requirement)
- ✅ Complete .env.example provided

### VI. Observability & Health Monitoring ✅
- ✅ Health payload schema defined (`mqtt-health-status.json`)
- ✅ Structured logging with correlation IDs (config_epoch, request_id)
- ✅ Metrics defined (DB ops, signature failures, fallback events)
- ✅ Audit log table for access control violations

### VII. Simplicity & YAGNI ✅
- ✅ Complexity justified in Complexity Tracking table
- ✅ No premature abstractions (SQLite chosen over etcd/Consul)
- ✅ Dual table structure justified (atomic + search performance)
- ✅ Three-key crypto system justified (separate security models)

**POST-DESIGN GATE RESULT**: ✅ **PASS** - All constitution principles satisfied, complexity justified

## Project Structure

### Documentation (this feature)

```
specs/005-unified-configuration-management/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (crypto libraries, SQLite WAL, Litestream)
├── data-model.md        # Phase 1 output (Pydantic models, database schema)
├── quickstart.md        # Phase 1 output (setup guide, env vars)
├── contracts/           # Phase 1 output (MQTT message schemas)
│   ├── config-update.json    # system/config/<service> payload
│   ├── health-status.json    # system/health/config-manager payload
│   └── api-endpoints.json    # REST API contracts
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```
# Configuration Library (tars-core package)
packages/tars-core/
├── src/tars/
│   ├── config/                    # NEW: Configuration management module
│   │   ├── __init__.py
│   │   ├── models.py              # Pydantic models for all services
│   │   ├── database.py            # SQLite database access layer
│   │   ├── cache.py               # LKG cache management with HMAC
│   │   ├── crypto.py              # AES-256-GCM encryption, Ed25519 signing
│   │   ├── library.py             # Public API (get_config, subscribe_updates)
│   │   ├── precedence.py          # .env → database → defaults resolution
│   │   ├── schema_version.py     # Pydantic model hash tracking
│   │   └── types.py               # Shared types and enums
│   └── domain/                    # Existing domain services
└── tests/
    ├── unit/
    │   └── config/                # Config library unit tests
    ├── integration/
    │   └── config/                # DB + MQTT integration tests
    └── contract/
        └── config/                # MQTT payload validation tests

# Configuration Manager Service (NEW)
apps/config-manager/
├── src/config_manager/
│   ├── __init__.py
│   ├── __main__.py                # Entry point
│   ├── config.py                  # Service-specific config (from env)
│   ├── service.py                 # Core service logic
│   ├── api.py                     # REST API endpoints (FastAPI)
│   ├── mqtt_handler.py            # MQTT message signing & publishing
│   └── backup.py                  # Litestream integration
├── tests/
│   ├── unit/
│   ├── integration/
│   └── contract/
├── pyproject.toml
├── Makefile
├── README.md
└── .env.example

# Web UI Enhancement (existing ui-web)
apps/ui-web/
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── ConfigEditor.vue       # NEW: Config editor component
│       │   ├── ConfigSearch.vue       # NEW: Search/filter
│       │   ├── ConfigTabs.vue         # NEW: Service tabs navigation
│       │   └── GlobalSettings.vue     # NEW: Cross-service settings
│       └── views/
│           └── ConfigView.vue         # NEW: Main config management view
└── src/ui_web/
    └── api.py                         # NEW: Config REST endpoints

# Database and Cache (data directory)
data/
├── config/
│   ├── config.db                      # SQLite database (WAL mode)
│   ├── config.db-wal                  # SQLite WAL file
│   ├── config.db-shm                  # SQLite shared memory
│   ├── config.lkg.json                # HMAC-signed LKG cache
│   ├── health+epoch.json              # Database epoch metadata
│   └── rebuild.info                   # Tombstone file (if rebuilt)
└── backups/                           # Litestream backups (local fallback)

# Docker Configuration
docker/
└── specialized/
    └── config-manager.Dockerfile      # NEW: Config manager container

ops/
├── compose.yml                        # Updated: add config-manager service
└── compose.npu.yml                    # Updated: add config-manager service
```

**Structure Decision**: Web application with backend (config-manager service) + frontend (ui-web enhancement). Configuration library centralized in tars-core package for use by all services. Follows existing monorepo patterns with apps/ for services and packages/ for shared code.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| New config-manager service (13th service) | Centralized configuration logic requires dedicated service for database management, API endpoints, MQTT signing, and Litestream backup coordination | Distributing logic across existing services → rejected because creates tight coupling and no clear ownership of database/backup/API responsibilities |
| SQLite + dual table structure | Atomic service configuration snapshots (service_configs JSON) + fast search/history (config_items per-key) | Single table with JSON → rejected because every search requires parsing all JSON blobs; separate tables → rejected because loses atomic update guarantees |
| Three separate cryptographic keys (master, HMAC, signature) | CONFIG_MASTER_KEY_BASE64 for AES-256-GCM encryption; LKG_HMAC_KEY_BASE64 for cache signing; Ed25519 keypair for MQTT signatures | Single key for all → rejected due to cryptographic cross-protocol attack risk; two keys → rejected because cache signing and MQTT signing serve different security models |
| Schema version tracking via model hash | Detects Pydantic model incompatibility across deployments; prevents reading corrupted configs | Version number only → rejected because doesn't catch field type changes or validation rule updates; no tracking → rejected because silent failures on schema drift |
| Read-only fallback + LKG cache | Zero-downtime degradation when database unavailable | Fail completely → rejected because breaks entire system on DB lock; retry loop → rejected because adds latency and complexity |
| Litestream continuous backup | Point-in-time recovery for configuration database | Manual backups → rejected because requires operator discipline and loses recent changes; no backups → rejected due to data loss risk |
