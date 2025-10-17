# Data Models: Unified Configuration Management System

**Date**: 2025-10-17  
**Feature**: 005-unified-configuration-management  
**Purpose**: Define Pydantic v2 models and database schema

## Pydantic Models

### Core Configuration Models

```python
from __future__ import annotations
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Literal, Any
from datetime import datetime
from enum import Enum

class ConfigComplexity(str, Enum):
    """Configuration complexity level for UI filtering."""
    SIMPLE = "simple"      # Commonly used, shown by default
    ADVANCED = "advanced"  # Technical, hidden unless expanded

class ConfigType(str, Enum):
    """Configuration value types."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ENUM = "enum"
    PATH = "path"
    SECRET = "secret"

class ConfigSource(str, Enum):
    """Where configuration value comes from."""
    ENV = "env"           # .env file (immutable)
    DATABASE = "database" # SQLite database (mutable)
    DEFAULT = "default"   # Hardcoded default

class ConfigFieldMetadata(BaseModel):
    """Metadata for a single configuration field."""
    model_config = ConfigDict(extra="forbid")
    
    key: str = Field(..., description="Unique config key (e.g., 'stt.whisper_model')")
    service: str = Field(..., description="Service name (e.g., 'stt-worker')")
    type: ConfigType = Field(..., description="Value type")
    complexity: ConfigComplexity = Field(default=ConfigComplexity.SIMPLE)
    description: str = Field(..., description="User-facing explanation")
    help_text: str = Field(default="", description="Detailed documentation")
    is_secret: bool = Field(default=False, description="Whether value should be masked")
    secret_source: ConfigSource | None = Field(None, description="Secret source (env/database)")
    validation_min: int | float | None = Field(None, description="Min value for numeric types")
    validation_max: int | float | None = Field(None, description="Max value for numeric types")
    validation_pattern: str | None = Field(None, description="Regex pattern for string types")
    validation_allowed: list[str] | None = Field(None, description="Allowed values for enum types")

class ServiceConfig(BaseModel):
    """Complete configuration for a single service."""
    model_config = ConfigDict(extra="forbid")
    
    service: str = Field(..., description="Service name")
    config: dict[str, Any] = Field(..., description="Configuration key-value pairs")
    version: int = Field(default=1, description="Config version for optimistic locking")
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    config_epoch: str = Field(..., description="Database epoch identifier")

class ConfigItem(BaseModel):
    """Individual configuration key-value for search/history."""
    model_config = ConfigDict(extra="forbid")
    
    id: int | None = Field(None, description="Auto-increment primary key")
    service: str = Field(..., description="Service name")
    key: str = Field(..., description="Configuration key")
    value_json: str = Field(..., description="Value as JSON string")
    type: ConfigType = Field(..., description="Value type")
    complexity: ConfigComplexity = Field(...)
    description: str = Field(...)
    help_text: str = Field(default="")
    is_secret: bool = Field(default=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: str | None = Field(None, description="User identifier")

class SchemaVersion(BaseModel):
    """Schema version tracking for compatibility."""
    model_config = ConfigDict(extra="forbid")
    
    id: Literal[1] = 1  # Singleton record
    version: int = Field(..., description="Schema version number")
    model_hash: str = Field(..., description="SHA256 hash of Pydantic model schemas")
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ConfigEpochMetadata(BaseModel):
    """Database epoch for split-brain prevention."""
    model_config = ConfigDict(extra="forbid")
    
    config_epoch: str = Field(..., description="Unique epoch identifier (UUID)")
    schema_version: int = Field(..., description="Current schema version")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_rebuild: datetime | None = Field(None, description="Last rebuild timestamp")

class LKGCache(BaseModel):
    """Last-known-good cache structure."""
    model_config = ConfigDict(extra="forbid")
    
    payload: dict[str, dict[str, Any]] = Field(..., description="Service -> config mapping")
    config_epoch: str = Field(..., description="Epoch at cache generation")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    signature: str = Field(..., description="HMAC-SHA256 signature")
    algorithm: Literal["hmac-sha256"] = "hmac-sha256"
```

### Service-Specific Configuration Models

```python
# Example: STT Worker Configuration
class STTWorkerConfig(BaseModel):
    """Configuration for STT Worker service."""
    model_config = ConfigDict(extra="forbid")
    
    whisper_model: str = Field(default="base.en", description="Whisper model size")
    stt_backend: Literal["whisper", "ws"] = Field(default="whisper")
    ws_url: str | None = Field(None, description="WebSocket backend URL")
    streaming_partials: bool = Field(default=False)
    vad_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    vad_speech_pad_ms: int = Field(default=300, ge=0, le=1000)
    vad_silence_duration_ms: int = Field(default=500, ge=0, le=2000)
    sample_rate: int = Field(default=16000, gt=0)
    channels: int = Field(default=1, ge=1, le=2)

# Example: TTS Worker Configuration
class TTSWorkerConfig(BaseModel):
    """Configuration for TTS Worker service."""
    model_config = ConfigDict(extra="forbid")
    
    piper_voice: str = Field(default="en_US-lessac-medium")
    tts_streaming: bool = Field(default=False)
    tts_pipeline: bool = Field(default=True)
    tts_aggregate_by_utt: bool = Field(default=True)
    tts_aggregate_timeout_sec: float = Field(default=2.0, ge=0.0, le=10.0)
    volume_percent: int = Field(default=100, ge=0, le=200)

# Example: Router Configuration
class RouterConfig(BaseModel):
    """Configuration for Router service."""
    model_config = ConfigDict(extra="forbid")
    
    router_llm_tts_stream: bool = Field(default=True)
    router_stream_min_chars: int = Field(default=30, ge=1)
    router_stream_max_chars: int = Field(default=200, ge=1)
    router_stream_boundary_only: bool = Field(default=True)
    router_stream_boundary_regex: str = Field(default=r"[.!?…]+[\"')\\]]?\\s")

# Add similar models for: LLMWorkerConfig, MemoryWorkerConfig, etc.
```

### MQTT Message Models

```python
class ConfigUpdatePayload(BaseModel):
    """MQTT payload for system/config/<service> topic."""
    model_config = ConfigDict(extra="forbid")
    
    version: int = Field(..., description="Message format version")
    service: str = Field(..., description="Target service")
    config: dict[str, Any] = Field(..., description="Complete service configuration")
    checksum: str = Field(..., description="SHA256 of config JSON")
    config_epoch: str = Field(..., description="Database epoch")
    issued_at: datetime = Field(default_factory=datetime.utcnow)
    signature: str = Field(..., description="Ed25519 signature (base64)")

class ConfigHealthPayload(BaseModel):
    """Health status for config-manager service."""
    model_config = ConfigDict(extra="forbid")
    
    ok: bool = Field(..., description="Overall health status")
    database_status: Literal["healthy", "locked", "corrupted", "schema-mismatch"] = Field(...)
    operational_mode: Literal["normal", "read-only-fallback", "rebuilding"] = Field(...)
    config_epoch: str = Field(..., description="Current database epoch")
    schema_version: int = Field(..., description="Current schema version")
    lkg_cache_valid: bool = Field(..., description="LKG cache HMAC valid")
    litestream_status: Literal["healthy", "error", "disabled"] = Field(...)
    last_backup: datetime | None = Field(None)
    event: str | None = Field(None, description="Event description")
    err: str | None = Field(None, description="Error message if unhealthy")
```

### REST API Models

```python
class ConfigReadRequest(BaseModel):
    """Request to read service configuration."""
    model_config = ConfigDict(extra="forbid")
    
    service: str = Field(..., description="Service name to retrieve")

class ConfigReadResponse(BaseModel):
    """Response with service configuration."""
    model_config = ConfigDict(extra="forbid")
    
    service: str
    config: dict[str, Any]
    metadata: dict[str, Any] = Field(..., description="version, updated_at, etc.")

class ConfigUpdateRequest(BaseModel):
    """Request to update service configuration."""
    model_config = ConfigDict(extra="forbid")
    
    service: str
    config: dict[str, Any]
    version: int = Field(..., description="For optimistic locking")

class ConfigUpdateResponse(BaseModel):
    """Response after configuration update."""
    model_config = ConfigDict(extra="forbid")
    
    success: bool
    new_version: int | None = None
    error: str | None = None

class ConfigSearchRequest(BaseModel):
    """Search configuration items."""
    model_config = ConfigDict(extra="forbid")
    
    query: str = Field(default="", description="Search text")
    service_filter: str | None = Field(None)
    complexity_filter: ConfigComplexity | None = Field(None)
    type_filter: ConfigType | None = Field(None)

class ConfigSearchResponse(BaseModel):
    """Search results."""
    model_config = ConfigDict(extra="forbid")
    
    results: list[ConfigItem]
    total: int
```

## Database Schema

### SQLite Tables

```sql
-- Schema version tracking (singleton table)
CREATE TABLE IF NOT EXISTS schema_version (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL,
    model_hash TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Canonical service configuration snapshots (JSON blobs for atomicity)
CREATE TABLE IF NOT EXISTS service_configs (
    service TEXT PRIMARY KEY,
    config_json TEXT NOT NULL,  -- Complete ServiceConfig as JSON
    version INTEGER NOT NULL DEFAULT 1,
    config_epoch TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_service_configs_epoch ON service_configs(config_epoch);

-- Derived configuration items (for search/filter/history without JSON parsing)
CREATE TABLE IF NOT EXISTS config_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    key TEXT NOT NULL,
    value_json TEXT NOT NULL,
    type TEXT NOT NULL,
    complexity TEXT NOT NULL,
    description TEXT NOT NULL,
    help_text TEXT,
    is_secret INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    updated_by TEXT,
    UNIQUE(service, key)
);
CREATE INDEX IF NOT EXISTS idx_config_items_service ON config_items(service);
CREATE INDEX IF NOT EXISTS idx_config_items_complexity ON config_items(complexity);
CREATE INDEX IF NOT EXISTS idx_config_items_key ON config_items(key);
CREATE INDEX IF NOT EXISTS idx_config_items_search ON config_items(service, key, description);

-- Configuration change history (audit trail)
CREATE TABLE IF NOT EXISTS config_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    key TEXT NOT NULL,
    old_value_json TEXT,
    new_value_json TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    changed_by TEXT,
    change_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_config_history_service ON config_history(service);
CREATE INDEX IF NOT EXISTS idx_config_history_time ON config_history(changed_at);

-- Encrypted secrets (user-created, separate from .env secrets)
CREATE TABLE IF NOT EXISTS encrypted_secrets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    key TEXT NOT NULL,
    encrypted_value TEXT NOT NULL,  -- AES-256-GCM encrypted, base64-encoded
    key_id TEXT NOT NULL,            -- CONFIG_MASTER_KEY_ID for rotation tracking
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(service, key)
);
CREATE INDEX IF NOT EXISTS idx_encrypted_secrets_key_id ON encrypted_secrets(key_id);

-- Access control audit log
CREATE TABLE IF NOT EXISTS access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    action TEXT NOT NULL,  -- 'read', 'write', 'reveal_secret', 'unauthorized'
    service TEXT,
    key TEXT,
    success INTEGER NOT NULL,
    reason TEXT,
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_access_log_time ON access_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_access_log_user ON access_log(user_id);
```

## Entity Relationships

```
service_configs (1) ──── (N) config_items
     │                         │
     │                         │
     └─────────────────────────┴──── (N) config_history
     
service_configs (1) ──── (N) encrypted_secrets

schema_version (1 singleton)

access_log (audit trail, no relations)
```

## Validation Rules

### Field Constraints

1. **service**: Must match `^[a-z][a-z0-9-]*$` (lowercase, hyphens allowed)
2. **key**: Must match `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$` (dotted notation)
3. **version**: Positive integer, increments on every update (optimistic locking)
4. **config_epoch**: UUID v4 format
5. **model_hash**: 64-character hex string (SHA256)

### State Transitions

```
Database Health States:
  healthy → locked (temporary, auto-recover)
  healthy → corrupted (requires intervention)
  healthy → schema-mismatch (requires rebuild or schema fix)
  corrupted → rebuilding → healthy (with new epoch)
  schema-mismatch → read-only-fallback → healthy (after schema update)

Operational Modes:
  normal → read-only-fallback (on DB failure)
  normal → rebuilding (on opt-in auto-rebuild)
  read-only-fallback → normal (after DB recovery)
  rebuilding → normal (after rebuild complete)
```

### Encryption Metadata

```python
class EncryptionMetadata(BaseModel):
    """Track encryption key rotation."""
    model_config = ConfigDict(extra="forbid")
    
    master_key_id: str = Field(..., description="CONFIG_MASTER_KEY_ID from .env")
    hmac_key_id: str = Field(..., description="LKG_HMAC_KEY_ID from .env")
    signature_public_key_hash: str = Field(..., description="SHA256 of public key")
    rotation_status: Literal["idle", "in-progress", "completed"] = "idle"
    grace_window_until: datetime | None = None
```

## Summary

All entity models defined with:
- ✅ Pydantic v2 models for type safety
- ✅ SQLite schema with indexes for performance
- ✅ Validation rules and constraints
- ✅ State transition documentation
- ✅ MQTT message contracts
- ✅ REST API contracts

**Next Steps**: Generate OpenAPI/JSON schemas in contracts/ directory
