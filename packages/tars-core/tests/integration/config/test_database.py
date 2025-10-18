"""Integration tests for database operations."""

import tempfile
from pathlib import Path

import pytest

from tars.config.crypto import generate_master_key
from tars.config.database import ConfigDatabase
from tars.config.models import SchemaVersion, ServiceConfig, STTWorkerConfig


@pytest.fixture
async def db() -> ConfigDatabase:
    """Create temporary test database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        database = ConfigDatabase(db_path)
        await database.connect()
        await database.initialize_schema()
        yield database
        await database.close()


@pytest.mark.asyncio
class TestDatabaseOperations:
    """Test async database operations."""

    async def test_schema_initialization(self, db: ConfigDatabase) -> None:
        """Test that schema tables are created."""
        # Schema should be initialized by fixture
        version = await db.get_schema_version()
        # New database has no version yet
        assert version is None

    async def test_service_config_crud(self, db: ConfigDatabase) -> None:
        """Test create, read, update service configuration."""
        epoch = await db.create_epoch()
        service = "stt-worker"
        config_data = {"whisper_model": "base.en", "vad_threshold": 0.5}

        # Create
        success = await db.update_service_config(
            service=service,
            config=config_data,
            version=0,  # Initial version
            config_epoch=epoch,
        )
        assert success

        # Read
        service_config = await db.get_service_config(service)
        assert service_config is not None
        assert service_config.service == service
        assert service_config.config == config_data
        assert service_config.version == 1

        # Update
        updated_config = {"whisper_model": "small.en", "vad_threshold": 0.6}
        success = await db.update_service_config(
            service=service,
            config=updated_config,
            version=1,
            config_epoch=epoch,
        )
        assert success

        # Verify update
        service_config = await db.get_service_config(service)
        assert service_config is not None
        assert service_config.config == updated_config
        assert service_config.version == 2

    async def test_optimistic_locking(self, db: ConfigDatabase) -> None:
        """Test that version conflicts are detected."""
        epoch = await db.create_epoch()
        service = "test-service"
        config_data = {"key": "value"}

        # Create initial config
        await db.update_service_config(service, config_data, version=0, config_epoch=epoch)

        # Try to update with wrong version
        success = await db.update_service_config(
            service, {"key": "new"}, version=0, config_epoch=epoch
        )
        assert not success  # Should fail due to version conflict

        # Update with correct version
        success = await db.update_service_config(
            service, {"key": "new"}, version=1, config_epoch=epoch
        )
        assert success

    async def test_list_services(self, db: ConfigDatabase) -> None:
        """Test listing all services."""
        epoch = await db.create_epoch()

        # Add multiple services
        services = ["service1", "service2", "service3"]
        for svc in services:
            await db.update_service_config(svc, {"key": "val"}, version=0, config_epoch=epoch)

        # List services
        listed = await db.list_services()
        assert sorted(listed) == sorted(services)

    async def test_encrypted_secrets(self, db: ConfigDatabase) -> None:
        """Test storing and retrieving encrypted secrets."""
        master_key, key_id = generate_master_key()
        service = "test-service"
        secret_key = "api_token"
        plaintext = "super-secret-value"

        # Store encrypted secret
        await db.store_encrypted_secret(service, secret_key, plaintext, master_key, key_id)

        # Retrieve and verify
        retrieved = await db.retrieve_encrypted_secret(service, secret_key, master_key)
        assert retrieved == plaintext

    async def test_search_config_items(self, db: ConfigDatabase) -> None:
        """Test searching configuration items."""
        epoch = await db.create_epoch()
        service = "stt-worker"
        config = {"whisper_model": "base.en", "vad_threshold": 0.5}
        metadata = {
            "whisper_model": {
                "type": "string",
                "complexity": "simple",
                "description": "Whisper model size",
            },
            "vad_threshold": {
                "type": "float",
                "complexity": "advanced",
                "description": "Voice activity detection threshold",
            },
        }

        # Create service config
        await db.update_service_config(service, config, version=0, config_epoch=epoch)

        # Sync config items
        await db.sync_config_items(service, config, metadata)

        # Search by query
        results = await db.search_config_items(query="whisper")
        assert len(results) == 1
        assert results[0].key == "whisper_model"

        # Search by service
        results = await db.search_config_items(service_filter=service)
        assert len(results) == 2

        # Search by complexity
        results = await db.search_config_items(complexity_filter="simple")
        assert len(results) == 1
        assert results[0].complexity == "simple"

    async def test_schema_version_tracking(self, db: ConfigDatabase) -> None:
        """Test schema version hash tracking."""
        # Compute hash for models
        model_hash = await db.compute_model_hash(STTWorkerConfig, ServiceConfig)
        assert len(model_hash) == 64  # SHA256 hex string

        # Increment schema version
        version = await db.increment_schema_version(model_hash)
        assert version == 1

        # Get schema version
        schema_version = await db.get_schema_version()
        assert schema_version is not None
        assert schema_version.version == 1
        assert schema_version.model_hash == model_hash

        # Validate schema
        is_valid = await db.validate_schema_version(model_hash)
        assert is_valid

        # Invalid hash should fail
        is_valid = await db.validate_schema_version("0" * 64)
        assert not is_valid
