"""Database layer for configuration management.

Provides:
- SQLite schema initialization with WAL mode
- Async CRUD operations for configurations
- Schema version tracking
- Config epoch management
- Encrypted secrets management
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite
import orjson
from pydantic import BaseModel

from tars.config.crypto import decrypt_secret_async, encrypt_secret_async
from tars.config.models import ConfigEpochMetadata, ConfigItem, SchemaVersion, ServiceConfig
from tars.config.types import ConfigType


# SQL Schema Definitions

SCHEMA_SQL = """
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
    config_json TEXT NOT NULL,
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
    encrypted_value TEXT NOT NULL,
    key_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(service, key)
);
CREATE INDEX IF NOT EXISTS idx_encrypted_secrets_key_id ON encrypted_secrets(key_id);

-- Access control audit log
CREATE TABLE IF NOT EXISTS access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    action TEXT NOT NULL,
    service TEXT,
    key TEXT,
    success INTEGER NOT NULL,
    reason TEXT,
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_access_log_time ON access_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_access_log_user ON access_log(user_id);
"""


class ConfigDatabase:
    """Async database interface for configuration management."""

    def __init__(self, db_path: str | Path):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Connect to database and enable WAL mode."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(self.db_path))
        # Enable WAL mode for concurrent reads
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.execute("PRAGMA busy_timeout=5000")
        await self._conn.execute("PRAGMA wal_autocheckpoint=1000")

    async def initialize_schema(self) -> None:
        """Create tables if they don't exist."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        await self._conn.executescript(SCHEMA_SQL)
        await self._conn.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    # ===== Schema Version Tracking =====

    async def get_schema_version(self) -> SchemaVersion | None:
        """Get current schema version."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        async with self._conn.execute("SELECT version, model_hash, updated_at FROM schema_version WHERE id = 1") as cursor:
            row = await cursor.fetchone()
            if row:
                return SchemaVersion(
                    id=1,
                    version=row[0],
                    model_hash=row[1],
                    updated_at=datetime.fromisoformat(row[2]),
                )
            return None

    async def compute_model_hash(self, *models: type[BaseModel]) -> str:
        """Compute SHA256 hash of Pydantic model schemas.

        Args:
            models: Pydantic model classes to hash

        Returns:
            Hex-encoded SHA256 hash
        """
        schemas = []
        for model in models:
            schema = model.model_json_schema()
            schemas.append(orjson.dumps(schema, option=orjson.OPT_SORT_KEYS))

        combined = b"".join(schemas)
        return hashlib.sha256(combined).hexdigest()

    async def validate_schema_version(self, expected_hash: str) -> bool:
        """Validate schema version matches expected hash.

        Args:
            expected_hash: Expected model hash

        Returns:
            True if schema is compatible
        """
        current = await self.get_schema_version()
        if not current:
            return False
        return current.model_hash == expected_hash

    async def increment_schema_version(self, new_hash: str) -> int:
        """Increment schema version after model changes.

        Args:
            new_hash: New model hash

        Returns:
            New version number
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        current = await self.get_schema_version()
        new_version = (current.version + 1) if current else 1

        await self._conn.execute(
            """
            INSERT OR REPLACE INTO schema_version (id, version, model_hash, updated_at)
            VALUES (1, ?, ?, ?)
            """,
            (new_version, new_hash, datetime.utcnow().isoformat()),
        )
        await self._conn.commit()
        return new_version

    # ===== Config Epoch Management =====

    async def create_epoch(self) -> str:
        """Create new config epoch (UUID).

        Returns:
            New epoch UUID
        """
        return str(uuid.uuid4())

    async def get_config_epoch(self) -> ConfigEpochMetadata | None:
        """Get current config epoch metadata.

        Returns:
            ConfigEpochMetadata if any service config exists, None otherwise
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        # Get epoch from any service config (all should have the same epoch)
        async with self._conn.execute(
            "SELECT config_epoch, updated_at FROM service_configs LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None

            return ConfigEpochMetadata(
                config_epoch=row[0],
                schema_version=1,  # TODO: Get from schema_version table
                created_at=datetime.fromisoformat(row[1]),
            )

    async def validate_epoch(self, epoch: str) -> bool:
        """Validate epoch exists in database.

        Args:
            epoch: Epoch UUID to validate

        Returns:
            True if epoch is current
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        async with self._conn.execute(
            "SELECT COUNT(*) FROM service_configs WHERE config_epoch = ?", (epoch,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] > 0 if row else False

    # ===== Service Configuration CRUD =====

    async def get_service_config(self, service: str) -> ServiceConfig | None:
        """Get configuration for a service.

        Args:
            service: Service name

        Returns:
            ServiceConfig if found, None otherwise
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        async with self._conn.execute(
            "SELECT config_json, version, config_epoch, updated_at FROM service_configs WHERE service = ?",
            (service,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                config_data = orjson.loads(row[0])
                return ServiceConfig(
                    service=service,
                    config=config_data,
                    version=row[1],
                    config_epoch=row[2],
                    updated_at=datetime.fromisoformat(row[3]),
                )
            return None

    async def update_service_config(
        self,
        service: str,
        config: dict[str, Any],
        expected_version: int | None = None,
        updated_by: str | None = None,
    ) -> int:
        """Update service configuration with optional optimistic locking.

        Args:
            service: Service name
            config: New configuration values
            expected_version: Expected current version for optimistic locking.
                            If None, creates or updates without version checking.
            updated_by: User identifier

        Returns:
            New version number after update

        Raises:
            ValueError: If version conflict occurs (expected_version doesn't match current)
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        # Get current config and epoch
        current = await self.get_service_config(service)
        epoch_data = await self.get_config_epoch()
        config_epoch = epoch_data.epoch_id if epoch_data else await self.create_epoch()

        # Check version if expected_version is specified
        if expected_version is not None:
            if current and current.version != expected_version:
                raise ValueError(
                    f"Version conflict: expected {expected_version}, got {current.version}"
                )

        # Calculate new version
        new_version = (current.version + 1) if current else 1
        config_json = orjson.dumps(config).decode()
        updated_at = datetime.utcnow().isoformat()

        await self._conn.execute(
            """
            INSERT OR REPLACE INTO service_configs (service, config_json, version, config_epoch, updated_at, updated_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (service, config_json, new_version, config_epoch, updated_at, updated_by),
        )
        await self._conn.commit()
        return new_version

    async def list_services(self) -> list[str]:
        """List all services with configurations.

        Returns:
            List of service names
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        async with self._conn.execute("SELECT service FROM service_configs ORDER BY service") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    # ===== Configuration Items (for search/history) =====

    async def sync_config_items(
        self, service: str, config: dict[str, Any], metadata: dict[str, dict[str, Any]]
    ) -> None:
        """Sync config_items table from service config.

        Args:
            service: Service name
            config: Configuration values
            metadata: Field metadata (key -> {type, complexity, description, ...})
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        # Delete existing items for this service
        await self._conn.execute("DELETE FROM config_items WHERE service = ?", (service,))

        # Insert new items
        for key, value in config.items():
            meta = metadata.get(key, {})
            value_json = orjson.dumps(value).decode()
            await self._conn.execute(
                """
                INSERT INTO config_items (service, key, value_json, type, complexity, description, help_text, is_secret, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    service,
                    key,
                    value_json,
                    meta.get("type", ConfigType.STRING.value),
                    meta.get("complexity", "simple"),
                    meta.get("description", ""),
                    meta.get("help_text", ""),
                    1 if meta.get("is_secret", False) else 0,
                    datetime.utcnow().isoformat(),
                ),
            )

        await self._conn.commit()

    async def search_config_items(
        self,
        query: str = "",
        service_filter: str | None = None,
        complexity_filter: str | None = None,
        type_filter: str | None = None,
    ) -> list[ConfigItem]:
        """Search configuration items.

        Args:
            query: Search text (matches service, key, description)
            service_filter: Filter by service name
            complexity_filter: Filter by complexity (simple/advanced)
            type_filter: Filter by type

        Returns:
            List of matching ConfigItem objects
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        sql = "SELECT id, service, key, value_json, type, complexity, description, help_text, is_secret, updated_at, updated_by FROM config_items WHERE 1=1"
        params: list[Any] = []

        if query:
            sql += " AND (service LIKE ? OR key LIKE ? OR description LIKE ?)"
            pattern = f"%{query}%"
            params.extend([pattern, pattern, pattern])

        if service_filter:
            sql += " AND service = ?"
            params.append(service_filter)

        if complexity_filter:
            sql += " AND complexity = ?"
            params.append(complexity_filter)

        if type_filter:
            sql += " AND type = ?"
            params.append(type_filter)

        sql += " ORDER BY service, key"

        async with self._conn.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            return [
                ConfigItem(
                    id=row[0],
                    service=row[1],
                    key=row[2],
                    value_json=row[3],
                    type=ConfigType(row[4]),
                    complexity=row[5],  # type: ignore
                    description=row[6],
                    help_text=row[7] or "",
                    is_secret=bool(row[8]),
                    updated_at=datetime.fromisoformat(row[9]),
                    updated_by=row[10],
                )
                for row in rows
            ]

    # ===== Encrypted Secrets =====

    async def store_encrypted_secret(
        self,
        service: str,
        key: str,
        plaintext: str,
        master_key_base64: str,
        key_id: str,
    ) -> None:
        """Store encrypted secret in database.

        Args:
            service: Service name
            key: Secret key
            plaintext: Secret value (will be encrypted)
            master_key_base64: Master encryption key
            key_id: Key ID for rotation tracking
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        encrypted_value = await encrypt_secret_async(plaintext, master_key_base64)
        now = datetime.utcnow().isoformat()

        await self._conn.execute(
            """
            INSERT OR REPLACE INTO encrypted_secrets (service, key, encrypted_value, key_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (service, key, encrypted_value, key_id, now, now),
        )
        await self._conn.commit()

    async def retrieve_encrypted_secret(
        self, service: str, key: str, master_key_base64: str
    ) -> str | None:
        """Retrieve and decrypt secret from database.

        Args:
            service: Service name
            key: Secret key
            master_key_base64: Master encryption key

        Returns:
            Decrypted secret or None if not found
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        async with self._conn.execute(
            "SELECT encrypted_value FROM encrypted_secrets WHERE service = ? AND key = ?",
            (service, key),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return await decrypt_secret_async(row[0], master_key_base64)
            return None

    async def list_secrets_by_key_id(self, key_id: str) -> list[tuple[str, str]]:
        """List all secrets encrypted with a specific key ID.

        Args:
            key_id: Encryption key ID

        Returns:
            List of (service, key) tuples
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        async with self._conn.execute(
            "SELECT service, key FROM encrypted_secrets WHERE key_id = ?", (key_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [(row[0], row[1]) for row in rows]
