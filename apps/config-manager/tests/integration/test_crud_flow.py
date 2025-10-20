"""Integration tests for config-manager CRUD operations.

Tests end-to-end flows: database operations, optimistic locking, error handling,
and service lifecycle behaviors.
"""

import asyncio
import json
import pytest
from pathlib import Path
from typing import AsyncGenerator

from tars.config.database import ConfigDatabase
from tars.config.models import ServiceConfig, ConfigComplexity
from tars.config.types import ConfigType


@pytest.fixture
async def test_db(tmp_path: Path) -> AsyncGenerator[ConfigDatabase, None]:
    """Create a temporary test database."""
    db_path = tmp_path / "test_config.db"
    db = ConfigDatabase(db_path)
    await db.connect()
    await db.initialize_schema()
    yield db
    await db.close()


@pytest.fixture
def sample_service_config() -> dict:
    """Sample configuration for testing."""
    return {
        "service": "test-service",
        "config": {
            "test_string": "hello",
            "test_int": 42,
            "test_float": 3.14,
            "test_bool": True,
            "test_enum": "option1",
        },
    }


@pytest.mark.asyncio
class TestCRUDFlow:
    """Test complete CRUD lifecycle for service configurations."""

    async def test_create_and_read_service_config(
        self, test_db: ConfigDatabase, sample_service_config: dict
    ):
        """Test creating and reading a service configuration."""
        service_name = sample_service_config["service"]
        config_data = sample_service_config["config"]

        # Create
        await test_db.upsert_service_config(
            service=service_name,
            config=config_data,
            expected_version=None,  # First write
        )

        # Read
        result = await test_db.get_service_config(service_name)

        assert result is not None
        assert result.service == service_name
        assert result.config == config_data
        assert result.version == 1
        assert result.config_epoch is not None

    async def test_update_service_config_success(
        self, test_db: ConfigDatabase, sample_service_config: dict
    ):
        """Test successful configuration update with correct version."""
        service_name = sample_service_config["service"]
        initial_config = sample_service_config["config"]

        # Create initial
        await test_db.upsert_service_config(
            service=service_name,
            config=initial_config,
            expected_version=None,
        )

        # Update with correct version
        updated_config = {**initial_config, "test_string": "world"}
        await test_db.upsert_service_config(
            service=service_name,
            config=updated_config,
            expected_version=1,  # Correct version
        )

        # Verify update
        result = await test_db.get_service_config(service_name)
        assert result is not None
        assert result.config["test_string"] == "world"
        assert result.version == 2  # Version incremented

    async def test_update_with_stale_version_fails(
        self, test_db: ConfigDatabase, sample_service_config: dict
    ):
        """Test that update with stale version raises OptimisticLockError."""
        from tars.config.database import OptimisticLockError

        service_name = sample_service_config["service"]
        config_data = sample_service_config["config"]

        # Create initial
        await test_db.upsert_service_config(
            service=service_name,
            config=config_data,
            expected_version=None,
        )

        # First update (version 1 → 2)
        await test_db.upsert_service_config(
            service=service_name,
            config={**config_data, "test_string": "update1"},
            expected_version=1,
        )

        # Try to update with stale version (should fail)
        with pytest.raises(OptimisticLockError) as exc_info:
            await test_db.upsert_service_config(
                service=service_name,
                config={**config_data, "test_string": "update2"},
                expected_version=1,  # Stale! Current is 2
            )

        assert "version mismatch" in str(exc_info.value).lower()

    async def test_create_multiple_services(self, test_db: ConfigDatabase):
        """Test creating multiple service configurations."""
        services = [
            ("stt-worker", {"whisper_model": "base.en"}),
            ("tts-worker", {"piper_voice": "en_US-lessac"}),
            ("llm-worker", {"llm_provider": "openai"}),
        ]

        # Create all services
        for service_name, config in services:
            await test_db.upsert_service_config(
                service=service_name,
                config=config,
                expected_version=None,
            )

        # Verify all exist
        for service_name, expected_config in services:
            result = await test_db.get_service_config(service_name)
            assert result is not None
            assert result.service == service_name
            assert result.config == expected_config

    async def test_list_all_services(self, test_db: ConfigDatabase):
        """Test listing all service names."""
        services = ["stt-worker", "tts-worker", "llm-worker"]

        # Create services
        for service_name in services:
            await test_db.upsert_service_config(
                service=service_name,
                config={"dummy": "config"},
                expected_version=None,
            )

        # List all
        result = await test_db.list_services()

        assert set(result) == set(services)

    async def test_nonexistent_service_returns_none(self, test_db: ConfigDatabase):
        """Test that reading nonexistent service returns None."""
        result = await test_db.get_service_config("nonexistent-service")
        assert result is None

    async def test_config_persistence_across_connections(
        self, tmp_path: Path, sample_service_config: dict
    ):
        """Test that config persists across database connections."""
        db_path = tmp_path / "persistent_config.db"
        service_name = sample_service_config["service"]
        config_data = sample_service_config["config"]

        # First connection: create config
        db1 = ConfigDatabase(db_path)
        await db1.connect()
        await db1.initialize_schema()
        await db1.upsert_service_config(
            service=service_name,
            config=config_data,
            expected_version=None,
        )
        await db1.close()

        # Second connection: verify config persisted
        db2 = ConfigDatabase(db_path)
        await db2.connect()
        result = await db2.get_service_config(service_name)
        await db2.close()

        assert result is not None
        assert result.config == config_data

    async def test_concurrent_updates_with_optimistic_locking(
        self, test_db: ConfigDatabase, sample_service_config: dict
    ):
        """Test that concurrent updates are serialized via optimistic locking."""
        from tars.config.database import OptimisticLockError

        service_name = sample_service_config["service"]
        config_data = sample_service_config["config"]

        # Create initial
        await test_db.upsert_service_config(
            service=service_name,
            config=config_data,
            expected_version=None,
        )

        # Simulate two concurrent clients reading version 1
        client1_config = {**config_data, "test_string": "client1"}
        client2_config = {**config_data, "test_string": "client2"}

        # Client 1 updates first (succeeds)
        await test_db.upsert_service_config(
            service=service_name,
            config=client1_config,
            expected_version=1,
        )

        # Client 2 tries to update with same version (fails)
        with pytest.raises(OptimisticLockError):
            await test_db.upsert_service_config(
                service=service_name,
                config=client2_config,
                expected_version=1,  # Stale!
            )

        # Verify Client 1's update won
        result = await test_db.get_service_config(service_name)
        assert result is not None
        assert result.config["test_string"] == "client1"
        assert result.version == 2

    async def test_empty_config_allowed(self, test_db: ConfigDatabase):
        """Test that empty configuration is valid."""
        service_name = "empty-service"

        await test_db.upsert_service_config(
            service=service_name,
            config={},
            expected_version=None,
        )

        result = await test_db.get_service_config(service_name)
        assert result is not None
        assert result.config == {}

    async def test_large_config_values(self, test_db: ConfigDatabase):
        """Test that large configuration values are handled correctly."""
        service_name = "large-config-service"
        large_value = "x" * 10000  # 10KB string

        await test_db.upsert_service_config(
            service=service_name,
            config={"large_field": large_value},
            expected_version=None,
        )

        result = await test_db.get_service_config(service_name)
        assert result is not None
        assert result.config["large_field"] == large_value

    async def test_special_characters_in_values(self, test_db: ConfigDatabase):
        """Test that special characters in config values are preserved."""
        service_name = "special-chars-service"
        special_config = {
            "quotes": 'He said "Hello"',
            "newlines": "Line1\nLine2\nLine3",
            "unicode": "Hello 世界 🌍",
            "json": '{"nested": "value"}',
        }

        await test_db.upsert_service_config(
            service=service_name,
            config=special_config,
            expected_version=None,
        )

        result = await test_db.get_service_config(service_name)
        assert result is not None
        assert result.config == special_config


@pytest.mark.asyncio
class TestConfigEpoch:
    """Test config epoch tracking for split-brain prevention."""

    async def test_config_epoch_created_on_init(self, test_db: ConfigDatabase):
        """Test that config epoch is created during schema initialization."""
        epoch = await test_db.get_config_epoch()
        assert epoch is not None
        assert len(epoch.config_epoch) == 36  # UUID format

    async def test_config_epoch_consistent_across_reads(self, test_db: ConfigDatabase):
        """Test that config epoch remains consistent."""
        epoch1 = await test_db.get_config_epoch()
        epoch2 = await test_db.get_config_epoch()

        assert epoch1 is not None
        assert epoch2 is not None
        assert epoch1.config_epoch == epoch2.config_epoch

    async def test_service_config_includes_epoch(
        self, test_db: ConfigDatabase, sample_service_config: dict
    ):
        """Test that service config includes the database epoch."""
        service_name = sample_service_config["service"]
        config_data = sample_service_config["config"]

        await test_db.upsert_service_config(
            service=service_name,
            config=config_data,
            expected_version=None,
        )

        result = await test_db.get_service_config(service_name)
        epoch = await test_db.get_config_epoch()

        assert result is not None
        assert epoch is not None
        assert result.config_epoch == epoch.config_epoch


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
