# Research: Unified Configuration Management System

**Date**: 2025-10-17  
**Feature**: 005-unified-configuration-management  
**Purpose**: Resolve technical unknowns and establish implementation patterns

## Research Tasks

### 1. SQLite WAL Mode Best Practices

**Question**: How to configure SQLite for optimal concurrent read performance while maintaining data integrity?

**Decision**: Use SQLite in WAL (Write-Ahead Logging) mode with explicit configuration

**Rationale**:
- WAL mode allows multiple concurrent readers without blocking writers
- `PRAGMA journal_mode=WAL` enables WAL mode
- `PRAGMA synchronous=NORMAL` provides good balance of safety and performance
- `PRAGMA busy_timeout=5000` prevents immediate lock failures
- WAL checkpoint configuration: `PRAGMA wal_autocheckpoint=1000`

**Alternatives Considered**:
- DELETE mode (default) → rejected due to reader/writer blocking
- TRUNCATE mode → rejected, no significant advantage over WAL
- MEMORY mode → rejected due to data loss risk

**Implementation Pattern**:
```python
import aiosqlite

async def init_database(db_path: str) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(db_path)
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA synchronous=NORMAL")
    await conn.execute("PRAGMA busy_timeout=5000")
    await conn.execute("PRAGMA wal_autocheckpoint=1000")
    return conn
```

### 2. AES-256-GCM Encryption in Python

**Question**: Which Python library provides secure AES-256-GCM encryption with proper key management?

**Decision**: Use `cryptography` library (PyCA) for AES-256-GCM encryption

**Rationale**:
- Industry-standard library maintained by Python Cryptographic Authority
- Hardware-accelerated AES when available
- Automatic nonce generation and IV handling
- Built-in authentication tag for integrity verification
- FIPS 140-2 validated cryptographic modules

**Alternatives Considered**:
- PyCrypto → rejected (unmaintained, security vulnerabilities)
- pycryptodome → rejected (less ecosystem support than PyCA)
- Manual OpenSSL bindings → rejected (complexity, error-prone)

**Implementation Pattern**:
```python
import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def encrypt_secret(plaintext: str, key_base64: str) -> str:
    """Encrypt secret using AES-256-GCM."""
    key = base64.b64decode(key_base64)
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    # Return base64(nonce + ciphertext)
    return base64.b64encode(nonce + ciphertext).decode()

def decrypt_secret(encrypted_base64: str, key_base64: str) -> str:
    """Decrypt secret using AES-256-GCM."""
    key = base64.b64decode(key_base64)
    aesgcm = AESGCM(key)
    encrypted = base64.b64decode(encrypted_base64)
    nonce = encrypted[:12]
    ciphertext = encrypted[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode()
```

### 3. Ed25519 Signature Verification

**Question**: How to implement Ed25519 signing for MQTT message authentication?

**Decision**: Use `cryptography.hazmat.primitives.asymmetric.ed25519` for Ed25519 signatures

**Rationale**:
- Fast verification (<1ms per message)
- Small signature size (64 bytes)
- Strong security guarantees (128-bit security level)
- Deterministic signatures prevent side-channel attacks
- Native support in cryptography library

**Alternatives Considered**:
- RSA signatures → rejected (slower, larger signatures)
- ECDSA → rejected (non-deterministic, timing attack risks)
- HMAC → rejected (symmetric key distribution problem)

**Implementation Pattern**:
```python
import base64
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

def generate_ed25519_keypair() -> tuple[str, str]:
    """Generate Ed25519 keypair for MQTT signing."""
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    return private_pem.decode(), public_pem.decode()

def sign_message(message: bytes, private_key_pem: str) -> str:
    """Sign message with Ed25519 private key."""
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode(), password=None
    )
    signature = private_key.sign(message)
    return base64.b64encode(signature).decode()

def verify_signature(message: bytes, signature_b64: str, public_key_pem: str) -> bool:
    """Verify Ed25519 signature."""
    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode())
        signature = base64.b64decode(signature_b64)
        public_key.verify(signature, message)
        return True
    except Exception:
        return False
```

### 4. HMAC-SHA256 for LKG Cache Integrity

**Question**: How to implement tamper-proof caching with HMAC signatures?

**Decision**: Use `hmac` stdlib module with SHA256 for cache signing

**Rationale**:
- Fast computation (<50ms for typical config files)
- Standard library (no external dependencies)
- Strong collision resistance (256-bit output)
- Simple key management (single symmetric key)

**Alternatives Considered**:
- SHA256 hash only → rejected (no authentication, vulnerable to tampering)
- SHA512 → rejected (overkill for config files, slower)
- Encryption + hash → rejected (unnecessary complexity for read-only cache)

**Implementation Pattern**:
```python
import hmac
import hashlib
import base64
import orjson

def sign_cache(data: dict, hmac_key_base64: str) -> dict:
    """Sign LKG cache with HMAC-SHA256."""
    key = base64.b64decode(hmac_key_base64)
    payload = orjson.dumps(data, option=orjson.OPT_SORT_KEYS)
    signature = hmac.new(key, payload, hashlib.sha256).hexdigest()
    return {
        "payload": data,
        "signature": signature,
        "algorithm": "hmac-sha256"
    }

def verify_cache(signed_data: dict, hmac_key_base64: str) -> dict | None:
    """Verify and extract LKG cache data."""
    key = base64.b64decode(hmac_key_base64)
    payload = orjson.dumps(signed_data["payload"], option=orjson.OPT_SORT_KEYS)
    expected_sig = hmac.new(key, payload, hashlib.sha256).hexdigest()
    if hmac.compare_digest(expected_sig, signed_data["signature"]):
        return signed_data["payload"]
    return None  # Tampered cache
```

### 5. Litestream Integration

**Question**: How to configure Litestream for continuous SQLite backups to S3/MinIO?

**Decision**: Run Litestream as sidecar container with volume sharing

**Rationale**:
- Continuous replication with <5s lag
- Point-in-time recovery via S3 versioning
- No application code changes required
- Works with any S3-compatible storage
- Automatic WAL file cleanup

**Alternatives Considered**:
- Manual cron backups → rejected (too slow, large recovery window)
- Application-level backups → rejected (complexity, coupling)
- SQLite BACKUP API → rejected (requires downtime)

**Configuration Pattern** (`litestream.yml`):
```yaml
dbs:
  - path: /data/config/config.db
    replicas:
      - type: s3
        bucket: tars-config-backups
        path: config-db
        endpoint: https://minio.example.com
        access-key-id: ${LITESTREAM_ACCESS_KEY_ID}
        secret-access-key: ${LITESTREAM_SECRET_ACCESS_KEY}
        retention: 168h  # 7 days
        sync-interval: 1s
        snapshot-interval: 24h
```

**Docker Compose Integration**:
```yaml
services:
  config-manager:
    # ... main service config
    volumes:
      - config-db:/data/config

  litestream:
    image: litestream/litestream:latest
    volumes:
      - config-db:/data/config
      - ./litestream.yml:/etc/litestream.yml:ro
    env_file:
      - .env
    command: replicate
    restart: unless-stopped

volumes:
  config-db:
```

### 6. Pydantic Model Hash for Schema Versioning

**Question**: How to detect schema incompatibility across Pydantic model changes?

**Decision**: Generate SHA256 hash of all Pydantic model JSON schemas

**Rationale**:
- Detects field additions, removals, type changes
- Fast computation (milliseconds for all models)
- Deterministic (same models always produce same hash)
- Works with Pydantic v2's `model_json_schema()`

**Alternatives Considered**:
- Manual version numbers → rejected (error-prone, requires discipline)
- Model source code hash → rejected (detects cosmetic changes like comments)
- Pickle hash → rejected (not deterministic across Python versions)

**Implementation Pattern**:
```python
import hashlib
import orjson
from typing import Type
from pydantic import BaseModel

def compute_schema_hash(*models: Type[BaseModel]) -> str:
    """Compute SHA256 hash of Pydantic model schemas."""
    schemas = []
    for model in models:
        schema = model.model_json_schema()
        # Sort keys for deterministic hashing
        schemas.append(orjson.dumps(schema, option=orjson.OPT_SORT_KEYS))
    
    combined = b"".join(schemas)
    return hashlib.sha256(combined).hexdigest()
```

### 7. Async Database Operations with aiosqlite

**Question**: How to perform non-blocking SQLite operations in async context?

**Decision**: Use `aiosqlite` for async database access

**Rationale**:
- Runs SQLite operations in thread pool (non-blocking)
- Compatible with asyncio event loop
- Same API as sqlite3 stdlib module
- Handles connection pooling internally

**Alternatives Considered**:
- `asyncio.to_thread(sqlite3.*)` → rejected (manual connection management complexity)
- sync sqlite3 → rejected (blocks event loop)
- databases library → rejected (overkill for single database)

**Implementation Pattern**:
```python
import aiosqlite
from contextlib import asynccontextmanager

class ConfigDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None
    
    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.db_path)
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
    
    async def get_config(self, service: str) -> dict | None:
        async with self._conn.execute(
            "SELECT config_json FROM service_configs WHERE service = ?",
            (service,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return orjson.loads(row[0])
            return None
    
    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
```

### 8. Vue.js Component Architecture for Config UI

**Question**: How to structure Vue.js components for configuration management?

**Decision**: Use composition API with TypeScript for type-safe config editing

**Rationale**:
- Composition API provides better code organization
- TypeScript ensures type safety between backend and frontend
- Reusable composables for config CRUD operations
- Existing ui-web already uses Vue.js

**Alternatives Considered**:
- Options API → rejected (less flexible for complex state management)
- React → rejected (would require rewriting existing ui-web)
- Plain HTML/JS → rejected (poor maintainability)

**Component Structure**:
```
frontend/src/
├── components/
│   ├── ConfigEditor.vue         # Main editor with field types
│   ├── ConfigField.vue          # Single field editor (string/int/bool/secret)
│   ├── ConfigSearch.vue         # Search and filter controls
│   ├── ConfigTabs.vue           # Service tabs navigation
│   ├── GlobalSettings.vue       # Cross-service settings panel
│   └── HealthIndicator.vue      # Service health status
├── composables/
│   ├── useConfig.ts             # Config CRUD operations
│   ├── useConfigWebSocket.ts   # Real-time config updates via WS
│   └── useConfigValidation.ts  # Client-side validation
└── types/
    └── config.ts                # TypeScript types for configs
```

## Summary

All technical unknowns resolved with concrete implementation decisions:

1. ✅ SQLite WAL mode configuration
2. ✅ AES-256-GCM encryption via cryptography library
3. ✅ Ed25519 signing for MQTT authentication
4. ✅ HMAC-SHA256 for cache integrity
5. ✅ Litestream sidecar for continuous backups
6. ✅ Pydantic schema hashing for version tracking
7. ✅ aiosqlite for async database operations
8. ✅ Vue.js composition API for config UI

**Next Steps**: Proceed to Phase 1 (data models and contracts)
