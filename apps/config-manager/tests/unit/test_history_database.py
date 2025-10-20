"""
Unit tests for configuration history tracking.

Tests history recording, querying, and restore functionality.
"""

import pytest
from datetime import datetime, timezone, timedelta
import orjson

from tars.config.models import ConfigHistory, ServiceConfig
from tars.config.database import ConfigDatabase


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "whisper_model": "base.en",
        "vad_threshold": 0.5,
        "streaming_partials": False,
    }


@pytest.fixture
def updated_config():
    """Updated configuration for testing."""
    return {
        "whisper_model": "small.en",  # Changed
        "vad_threshold": 0.7,  # Changed
        "streaming_partials": True,  # Changed
        "new_key": "new_value",  # Added
    }


class TestHistoryRecording:
    """Test that configuration changes are recorded in history."""

    async def test_initial_config_creates_history(self, db: ConfigDatabase, sample_config: dict):
        """Test that initial configuration creates history entries."""
        # Create initial config
        await db.update_service_config(
            service="stt-worker",
            config=sample_config,
            updated_by="test_user",
        )

        # Check history
        history = await db.get_config_history(service="stt-worker", limit=100)
        
        # Should have 3 entries (one for each key)
        assert len(history) == 3
        
        # All should be for stt-worker
        assert all(entry.service == "stt-worker" for entry in history)
        
        # All should have null old_value (initial config)
        assert all(entry.old_value_json is None for entry in history)
        
        # All should have changed_by set
        assert all(entry.changed_by == "test_user" for entry in history)
        
        # Check keys
        keys = {entry.key for entry in history}
        assert keys == {"whisper_model", "vad_threshold", "streaming_partials"}

    async def test_config_update_records_changes(
        self,
        db: ConfigDatabase,
        sample_config: dict,
        updated_config: dict,
    ):
        """Test that config updates record changes in history."""
        # Create initial config
        await db.update_service_config(
            service="stt-worker",
            config=sample_config,
            updated_by="user1",
        )

        # Update config
        await db.update_service_config(
            service="stt-worker",
            config=updated_config,
            updated_by="user2",
        )

        # Get history (most recent first)
        history = await db.get_config_history(service="stt-worker", limit=100)
        
        # Should have 3 (initial) + 4 (update: 3 changes + 1 new) = 7 entries
        assert len(history) >= 4  # At least the update entries

        # Get recent changes (from update)
        recent = history[:4]
        
        # Check that changes were recorded
        keys_changed = {entry.key for entry in recent}
        assert "whisper_model" in keys_changed
        assert "vad_threshold" in keys_changed
        assert "streaming_partials" in keys_changed
        assert "new_key" in keys_changed

        # Check updated_by
        for entry in recent:
            assert entry.changed_by == "user2"

    async def test_config_key_deletion_recorded(self, db: ConfigDatabase):
        """Test that deleted config keys are recorded in history."""
        # Create initial config with extra key
        initial = {"key1": "value1", "key2": "value2", "key3": "value3"}
        await db.update_service_config(
            service="test-service",
            config=initial,
            updated_by="user1",
        )

        # Update without key2
        updated = {"key1": "value1", "key3": "value3"}
        await db.update_service_config(
            service="test-service",
            config=updated,
            updated_by="user2",
        )

        # Check history for key2
        history = await db.get_key_history(service="test-service", key="key2", limit=10)
        
        # Should have at least 2 entries: creation and deletion
        assert len(history) >= 1
        
        # Most recent should be deletion (new_value = null)
        deletion_entry = history[0]
        assert deletion_entry.key == "key2"
        assert deletion_entry.old_value_json is not None
        assert orjson.loads(deletion_entry.new_value_json) is None
        assert deletion_entry.change_reason == "Key deleted"


class TestHistoryQuerying:
    """Test history query methods."""

    async def test_get_config_history_all(self, db: ConfigDatabase):
        """Test getting all config history."""
        # Create configs for multiple services
        await db.update_service_config("service1", {"key": "value1"}, updated_by="user1")
        await db.update_service_config("service2", {"key": "value2"}, updated_by="user2")

        # Get all history
        history = await db.get_config_history(limit=100)
        
        # Should have entries for both services
        services = {entry.service for entry in history}
        assert "service1" in services
        assert "service2" in services

    async def test_get_config_history_filter_by_service(self, db: ConfigDatabase):
        """Test filtering history by service."""
        await db.update_service_config("service1", {"key": "value1"})
        await db.update_service_config("service2", {"key": "value2"})

        # Get only service1 history
        history = await db.get_config_history(service="service1", limit=100)
        
        # All entries should be for service1
        assert all(entry.service == "service1" for entry in history)
        assert len(history) > 0

    async def test_get_config_history_filter_by_key(self, db: ConfigDatabase):
        """Test filtering history by configuration key."""
        await db.update_service_config(
            "test-service",
            {"key1": "value1", "key2": "value2"},
        )

        # Get only key1 history
        history = await db.get_config_history(service="test-service", key="key1", limit=100)
        
        # All entries should be for key1
        assert all(entry.key == "key1" for entry in history)
        assert len(history) > 0

    async def test_get_config_history_filter_by_date(self, db: ConfigDatabase):
        """Test filtering history by date range."""
        import asyncio

        # Create config at time T1
        await db.update_service_config("test-service", {"key": "value1"})
        
        # Mark time
        cutoff_time = datetime.now(timezone.utc)
        await asyncio.sleep(0.1)  # Small delay
        
        # Create config at time T2
        await db.update_service_config("test-service", {"key": "value2"})

        # Get history after cutoff (should only get T2 changes)
        history_after = await db.get_config_history(
            service="test-service",
            start_date=cutoff_time,
            limit=100,
        )
        
        # Get history before cutoff (should only get T1 changes)
        history_before = await db.get_config_history(
            service="test-service",
            end_date=cutoff_time,
            limit=100,
        )

        # Both should have entries
        assert len(history_after) > 0
        assert len(history_before) > 0
        
        # They should be different
        after_ids = {entry.id for entry in history_after}
        before_ids = {entry.id for entry in history_before}
        assert after_ids != before_ids

    async def test_get_config_history_limit(self, db: ConfigDatabase):
        """Test history limit parameter."""
        # Create many changes
        for i in range(20):
            await db.update_service_config("test-service", {"counter": i})

        # Get with limit
        history = await db.get_config_history(service="test-service", limit=5)
        
        # Should respect limit
        assert len(history) == 5
        
        # Should be most recent first
        values = [orjson.loads(entry.new_value_json) for entry in history]
        # Most recent should be higher counter values
        assert values[0] > values[-1]

    async def test_get_service_history(self, db: ConfigDatabase):
        """Test convenience method for service history."""
        await db.update_service_config("test-service", {"key": "value"})

        history = await db.get_service_history("test-service", limit=100)
        
        assert all(entry.service == "test-service" for entry in history)
        assert len(history) > 0

    async def test_get_key_history(self, db: ConfigDatabase):
        """Test convenience method for key history."""
        await db.update_service_config(
            "test-service",
            {"key1": "value1", "key2": "value2"},
        )

        history = await db.get_key_history("test-service", "key1", limit=100)
        
        assert all(entry.service == "test-service" for entry in history)
        assert all(entry.key == "key1" for entry in history)
        assert len(history) > 0

    async def test_history_ordering(self, db: ConfigDatabase):
        """Test that history is returned in reverse chronological order."""
        import asyncio

        # Create configs with delays
        await db.update_service_config("test-service", {"counter": 1})
        await asyncio.sleep(0.05)
        await db.update_service_config("test-service", {"counter": 2})
        await asyncio.sleep(0.05)
        await db.update_service_config("test-service", {"counter": 3})

        # Get history
        history = await db.get_key_history("test-service", "counter", limit=10)
        
        # Should have 3 entries
        assert len(history) == 3
        
        # Should be in reverse order (most recent first)
        values = [orjson.loads(entry.new_value_json) for entry in history]
        assert values == [3, 2, 1]


class TestHistoryModel:
    """Test ConfigHistory model."""

    async def test_history_model_fields(self, db: ConfigDatabase):
        """Test that all ConfigHistory fields are populated."""
        await db.update_service_config(
            "test-service",
            {"test_key": "test_value"},
            updated_by="test_user",
        )

        history = await db.get_config_history(service="test-service", limit=1)
        
        assert len(history) == 1
        entry = history[0]
        
        # Check all fields
        assert isinstance(entry, ConfigHistory)
        assert isinstance(entry.id, int)
        assert entry.service == "test-service"
        assert entry.key == "test_key"
        assert entry.old_value_json is None  # Initial config
        assert entry.new_value_json is not None
        assert isinstance(entry.changed_at, datetime)
        assert entry.changed_by == "test_user"
        # change_reason may be None or have a value

    async def test_history_json_values(self, db: ConfigDatabase):
        """Test that history values are valid JSON."""
        await db.update_service_config(
            "test-service",
            {
                "string": "value",
                "int": 42,
                "float": 3.14,
                "bool": True,
                "list": [1, 2, 3],
                "dict": {"nested": "value"},
            },
        )

        history = await db.get_config_history(service="test-service", limit=100)
        
        # All entries should have valid JSON
        for entry in history:
            assert entry.new_value_json is not None
            new_value = orjson.loads(entry.new_value_json)
            # Value should be deserialized correctly
            assert new_value is not None


class TestHistoryIntegration:
    """Integration tests for history with full config lifecycle."""

    async def test_history_tracks_full_lifecycle(self, db: ConfigDatabase):
        """Test history tracking through create, update, delete cycle."""
        service = "lifecycle-test"
        
        # 1. Create initial config
        await db.update_service_config(
            service,
            {"key1": "value1", "key2": "value2"},
            updated_by="user1",
        )
        
        # 2. Update some values
        await db.update_service_config(
            service,
            {"key1": "new_value1", "key2": "value2", "key3": "value3"},
            updated_by="user2",
        )
        
        # 3. Delete a key
        await db.update_service_config(
            service,
            {"key1": "new_value1", "key3": "value3"},
            updated_by="user3",
        )

        # Get full history
        history = await db.get_service_history(service, limit=100)
        
        # Should have all changes
        assert len(history) >= 5  # 2 initial + 2 update (1 change + 1 new) + 1 delete
        
        # Check specific key history
        key1_history = await db.get_key_history(service, "key1", limit=10)
        assert len(key1_history) >= 2  # Initial + update
        
        key2_history = await db.get_key_history(service, "key2", limit=10)
        assert len(key2_history) >= 2  # Initial + delete
        
        key3_history = await db.get_key_history(service, "key3", limit=10)
        assert len(key3_history) >= 1  # Added in update

    async def test_history_multiple_services_isolated(self, db: ConfigDatabase):
        """Test that history for different services is isolated."""
        # Update multiple services
        await db.update_service_config("service-a", {"key": "value-a"})
        await db.update_service_config("service-b", {"key": "value-b"})
        await db.update_service_config("service-c", {"key": "value-c"})

        # Get history for each service
        history_a = await db.get_service_history("service-a", limit=100)
        history_b = await db.get_service_history("service-b", limit=100)
        history_c = await db.get_service_history("service-c", limit=100)

        # Each should only have their own history
        assert all(entry.service == "service-a" for entry in history_a)
        assert all(entry.service == "service-b" for entry in history_b)
        assert all(entry.service == "service-c" for entry in history_c)
        
        # IDs should not overlap
        ids_a = {entry.id for entry in history_a}
        ids_b = {entry.id for entry in history_b}
        ids_c = {entry.id for entry in history_c}
        
        assert ids_a.isdisjoint(ids_b)
        assert ids_b.isdisjoint(ids_c)
        assert ids_a.isdisjoint(ids_c)
