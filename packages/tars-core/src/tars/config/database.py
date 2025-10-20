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
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite
import orjson
from pydantic import BaseModel

from tars.config.crypto import decrypt_secret_async, encrypt_secret_async
from tars.config.models import ConfigEpochMetadata, ConfigHistory, ConfigItem, ConfigProfile, SchemaVersion, ServiceConfig
from tars.config.types import ConfigType

logger = logging.getLogger(__name__)


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
    examples TEXT,
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

-- Configuration profiles (named snapshots for quick switching)
CREATE TABLE IF NOT EXISTS config_profiles (
    profile_name TEXT PRIMARY KEY,
    description TEXT,
    config_snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT,
    updated_at TEXT NOT NULL,
    updated_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_config_profiles_created ON config_profiles(created_at);

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
        
        # Migration: Add examples column if it doesn't exist
        await self._migrate_add_examples_column()

    async def _migrate_add_examples_column(self) -> None:
        """Add examples column to config_items if it doesn't exist."""
        if not self._conn:
            raise RuntimeError("Database not connected")
        
        # Check if examples column exists
        async with self._conn.execute("PRAGMA table_info(config_items)") as cursor:
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if "examples" not in column_names:
                logger.info("Migrating database: adding examples column to config_items")
                await self._conn.execute("ALTER TABLE config_items ADD COLUMN examples TEXT")
                await self._conn.commit()
                logger.info("Migration complete: examples column added")

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
            (new_version, new_hash, datetime.now(UTC).isoformat()),
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
        config_epoch = epoch_data.config_epoch if epoch_data else await self.create_epoch()

        # Check version if expected_version is specified
        if expected_version is not None:
            if current and current.version != expected_version:
                raise ValueError(
                    f"Version conflict: expected {expected_version}, got {current.version}"
                )

        # Calculate new version
        new_version = (current.version + 1) if current else 1
        config_json = orjson.dumps(config).decode()
        updated_at = datetime.now(UTC).isoformat()

        # Record history: compare old and new config
        if current:
            # Track changes for history
            old_config = current.config
            for key, new_value in config.items():
                old_value = old_config.get(key)
                if old_value != new_value:
                    # Record change in history
                    await self._conn.execute(
                        """
                        INSERT INTO config_history (service, key, old_value_json, new_value_json, changed_at, changed_by, change_reason)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            service,
                            key,
                            orjson.dumps(old_value).decode() if old_value is not None else None,
                            orjson.dumps(new_value).decode(),
                            updated_at,
                            updated_by,
                            None,  # change_reason - can be added to API later
                        ),
                    )
            
            # Check for deleted keys
            for key in old_config:
                if key not in config:
                    await self._conn.execute(
                        """
                        INSERT INTO config_history (service, key, old_value_json, new_value_json, changed_at, changed_by, change_reason)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            service,
                            key,
                            orjson.dumps(old_config[key]).decode(),
                            orjson.dumps(None).decode(),
                            updated_at,
                            updated_by,
                            "Key deleted",
                        ),
                    )
        else:
            # New service config - record all keys as new
            for key, value in config.items():
                await self._conn.execute(
                    """
                    INSERT INTO config_history (service, key, old_value_json, new_value_json, changed_at, changed_by, change_reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        service,
                        key,
                        None,
                        orjson.dumps(value).decode(),
                        updated_at,
                        updated_by,
                        "Initial configuration",
                    ),
                )

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
            examples_json = orjson.dumps(meta.get("examples", [])).decode() if meta.get("examples") else None
            await self._conn.execute(
                """
                INSERT INTO config_items (service, key, value_json, type, complexity, description, help_text, examples, is_secret, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    service,
                    key,
                    value_json,
                    meta.get("type", ConfigType.STRING.value),
                    meta.get("complexity", "simple"),
                    meta.get("description", ""),
                    meta.get("help_text", ""),
                    examples_json,
                    1 if meta.get("is_secret", False) else 0,
                    datetime.now(UTC).isoformat(),
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

        sql = "SELECT id, service, key, value_json, type, complexity, description, help_text, examples, is_secret, updated_at, updated_by FROM config_items WHERE 1=1"
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
                    examples=orjson.loads(row[8]) if row[8] else [],
                    is_secret=bool(row[9]),
                    updated_at=datetime.fromisoformat(row[10]),
                    updated_by=row[11],
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
        now = datetime.now(UTC).isoformat()

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

    # ===== Configuration Profiles (Named Snapshots) =====

    async def save_profile(self, profile: ConfigProfile) -> None:
        """Save or update a configuration profile.

        Args:
            profile: Profile to save with complete config snapshot
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        now = datetime.now(UTC).isoformat()
        config_json = orjson.dumps(profile.config_snapshot).decode()

        await self._conn.execute(
            """
            INSERT OR REPLACE INTO config_profiles 
            (profile_name, description, config_snapshot_json, created_at, created_by, updated_at, updated_by)
            VALUES (?, ?, ?, 
                    COALESCE((SELECT created_at FROM config_profiles WHERE profile_name = ?), ?),
                    COALESCE((SELECT created_by FROM config_profiles WHERE profile_name = ?), ?),
                    ?, ?)
            """,
            (
                profile.profile_name,
                profile.description,
                config_json,
                profile.profile_name,  # For COALESCE created_at
                now,  # Default created_at if new
                profile.profile_name,  # For COALESCE created_by
                profile.created_by,  # Default created_by if new
                now,  # updated_at (always current time)
                profile.updated_by,
            ),
        )
        await self._conn.commit()

    async def list_profiles(self) -> list[ConfigProfile]:
        """List all saved configuration profiles.

        Returns:
            List of ConfigProfile objects (without full config snapshot for performance)
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        async with self._conn.execute(
            """
            SELECT profile_name, description, created_at, created_by, updated_at, updated_by
            FROM config_profiles 
            ORDER BY updated_at DESC
            """
        ) as cursor:
            rows = await cursor.fetchall()
            profiles = []
            for row in rows:
                profiles.append(
                    ConfigProfile(
                        profile_name=row[0],
                        description=row[1],
                        config_snapshot={},  # Empty for list view
                        created_at=datetime.fromisoformat(row[2]),
                        created_by=row[3],
                        updated_at=datetime.fromisoformat(row[4]),
                        updated_by=row[5],
                    )
                )
            return profiles

    async def get_profile(self, profile_name: str) -> ConfigProfile | None:
        """Get a specific configuration profile by name.

        Args:
            profile_name: Name of the profile to retrieve

        Returns:
            ConfigProfile with full config snapshot or None if not found
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        async with self._conn.execute(
            """
            SELECT profile_name, description, config_snapshot_json, 
                   created_at, created_by, updated_at, updated_by
            FROM config_profiles 
            WHERE profile_name = ?
            """,
            (profile_name,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                config_snapshot = orjson.loads(row[2])
                return ConfigProfile(
                    profile_name=row[0],
                    description=row[1],
                    config_snapshot=config_snapshot,
                    created_at=datetime.fromisoformat(row[3]),
                    created_by=row[4],
                    updated_at=datetime.fromisoformat(row[5]),
                    updated_by=row[6],
                )
            return None

    async def delete_profile(self, profile_name: str) -> bool:
        """Delete a configuration profile.

        Args:
            profile_name: Name of the profile to delete

        Returns:
            True if profile was deleted, False if it didn't exist
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        cursor = await self._conn.execute(
            "DELETE FROM config_profiles WHERE profile_name = ?", (profile_name,)
        )
        await self._conn.commit()
        return cursor.rowcount > 0

    async def load_profile(self, profile_name: str, epoch: str, loaded_by: str | None = None) -> dict[str, ServiceConfig]:
        """Load a profile and convert to ServiceConfig objects ready for activation.

        Args:
            profile_name: Name of the profile to load
            epoch: Current config epoch to assign to loaded configs
            loaded_by: User identifier for audit trail

        Returns:
            Dictionary mapping service name to ServiceConfig

        Raises:
            ValueError: If profile not found
        """
        profile = await self.get_profile(profile_name)
        if not profile:
            raise ValueError(f"Profile '{profile_name}' not found")

        service_configs = {}
        for service, config in profile.config_snapshot.items():
            service_configs[service] = ServiceConfig(
                service=service,
                config=config,
                version=1,  # Will be updated when applied
                updated_at=datetime.now(UTC),
                config_epoch=epoch,
            )

        return service_configs

    # ===== Configuration History =====

    async def get_config_history(
        self,
        service: str | None = None,
        key: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[ConfigHistory]:
        """Get configuration change history with optional filters.

        Args:
            service: Filter by service name (optional)
            key: Filter by configuration key (optional)
            start_date: Filter by changes after this date (optional)
            end_date: Filter by changes before this date (optional)
            limit: Maximum number of history entries to return (default 100)

        Returns:
            List of ConfigHistory entries, most recent first
        """
        if not self._conn:
            raise RuntimeError("Database not connected")

        # Build query dynamically based on filters
        conditions = []
        params = []

        if service:
            conditions.append("service = ?")
            params.append(service)
        
        if key:
            conditions.append("key = ?")
            params.append(key)
        
        if start_date:
            conditions.append("changed_at >= ?")
            params.append(start_date.isoformat())
        
        if end_date:
            conditions.append("changed_at <= ?")
            params.append(end_date.isoformat())

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        query = f"""
            SELECT id, service, key, old_value_json, new_value_json, changed_at, changed_by, change_reason
            FROM config_history
            {where_clause}
            ORDER BY changed_at DESC, id DESC
            LIMIT ?
        """

        async with self._conn.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [
                ConfigHistory(
                    id=row[0],
                    service=row[1],
                    key=row[2],
                    old_value_json=row[3],
                    new_value_json=row[4],
                    changed_at=datetime.fromisoformat(row[5]),
                    changed_by=row[6],
                    change_reason=row[7],
                )
                for row in rows
            ]

    async def get_service_history(
        self,
        service: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[ConfigHistory]:
        """Get change history for a specific service.

        Args:
            service: Service name
            start_date: Filter by changes after this date (optional)
            end_date: Filter by changes before this date (optional)
            limit: Maximum number of history entries to return

        Returns:
            List of ConfigHistory entries for the service
        """
        return await self.get_config_history(
            service=service,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    async def get_key_history(
        self,
        service: str,
        key: str,
        limit: int = 50,
    ) -> list[ConfigHistory]:
        """Get change history for a specific configuration key.

        Args:
            service: Service name
            key: Configuration key
            limit: Maximum number of history entries to return

        Returns:
            List of ConfigHistory entries for the key
        """
        return await self.get_config_history(
            service=service,
            key=key,
            limit=limit,
        )
