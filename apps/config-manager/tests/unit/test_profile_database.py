"""
Unit tests for profile database methods.

Tests save_profile, list_profiles, get_profile, delete_profile, and load_profile.
"""

import pytest
from datetime import datetime, timezone
import orjson

from tars.config.models import ConfigProfile, ServiceConfig
from tars.config.database import ConfigDatabase


@pytest.fixture
def sample_profile():
    """Create a sample profile for testing."""
    return ConfigProfile(
        profile_name="Test Profile",
        description="A test configuration profile",
        config_snapshot={
            "stt-worker": {
                "whisper_model": "base.en",
                "vad_threshold": 0.5
            },
            "tts-worker": {
                "piper_voice": "en_US-lessac-medium",
                "volume_percent": 100
            }
        },
        created_at=datetime(2025, 10, 18, 12, 0, 0, tzinfo=timezone.utc),
        created_by="test_user",
        updated_at=datetime(2025, 10, 18, 12, 0, 0, tzinfo=timezone.utc),
        updated_by="test_user"
    )


class TestSaveProfile:
    """Test database.save_profile()."""

    async def test_save_new_profile(self, db: ConfigDatabase, sample_profile: ConfigProfile):
        """Test saving a new profile."""
        await db.save_profile(sample_profile)
        
        # Verify saved
        saved = await db.get_profile("Test Profile")
        assert saved is not None
        assert saved.profile_name == "Test Profile"
        assert saved.description == "A test configuration profile"
        assert saved.config_snapshot["stt-worker"]["whisper_model"] == "base.en"
        assert saved.created_by == "test_user"

    async def test_save_profile_update_preserves_created_at(
        self,
        db: ConfigDatabase,
        sample_profile: ConfigProfile
    ):
        """Test that updating a profile preserves created_at and created_by."""
        # Save initial profile
        await db.save_profile(sample_profile)
        
        # Get saved profile
        saved = await db.get_profile("Test Profile")
        original_created_at = saved.created_at
        original_created_by = saved.created_by
        
        # Update profile
        updated_profile = ConfigProfile(
            profile_name="Test Profile",
            description="Updated description",
            config_snapshot={
                "stt-worker": {
                    "whisper_model": "small.en",  # Changed
                    "vad_threshold": 0.7  # Changed
                }
            },
            created_at=datetime.now(timezone.utc),  # New timestamp (should be ignored)
            created_by="different_user",  # Different user (should be ignored)
            updated_at=datetime.now(timezone.utc),
            updated_by="updater_user"
        )
        await db.save_profile(updated_profile)
        
        # Verify created_at and created_by preserved
        final = await db.get_profile("Test Profile")
        assert final.created_at == original_created_at
        assert final.created_by == original_created_by
        assert final.updated_by == "updater_user"
        assert final.description == "Updated description"
        assert final.config_snapshot["stt-worker"]["whisper_model"] == "small.en"

    async def test_save_profile_with_special_chars(self, db: ConfigDatabase):
        """Test saving profile with special characters in name."""
        profile = ConfigProfile(
            profile_name="Test-Profile_2025 (Production)",
            description="Profile with special chars",
            config_snapshot={"test": {"key": "value"}},
            created_at=datetime.now(timezone.utc),
            created_by="test",
            updated_at=datetime.now(timezone.utc),
            updated_by="test"
        )
        
        await db.save_profile(profile)
        saved = await db.get_profile("Test-Profile_2025 (Production)")
        assert saved is not None
        assert saved.profile_name == "Test-Profile_2025 (Production)"

    async def test_save_profile_large_snapshot(self, db: ConfigDatabase):
        """Test saving profile with large config snapshot."""
        large_snapshot = {
            f"service-{i}": {
                f"key-{j}": f"value-{j}"
                for j in range(50)
            }
            for i in range(10)
        }
        
        profile = ConfigProfile(
            profile_name="Large Profile",
            description="Profile with many services",
            config_snapshot=large_snapshot,
            created_at=datetime.now(timezone.utc),
            created_by="test",
            updated_at=datetime.now(timezone.utc),
            updated_by="test"
        )
        
        await db.save_profile(profile)
        saved = await db.get_profile("Large Profile")
        assert saved is not None
        assert len(saved.config_snapshot) == 10
        assert len(saved.config_snapshot["service-0"]) == 50


class TestListProfiles:
    """Test database.list_profiles()."""

    async def test_list_profiles_empty(self, db: ConfigDatabase):
        """Test listing profiles when none exist."""
        profiles = await db.list_profiles()
        assert profiles == []

    async def test_list_profiles_single(self, db: ConfigDatabase, sample_profile: ConfigProfile):
        """Test listing profiles with one profile."""
        await db.save_profile(sample_profile)
        
        profiles = await db.list_profiles()
        assert len(profiles) == 1
        assert profiles[0].profile_name == "Test Profile"
        
        # Config snapshot should be empty (performance optimization)
        assert profiles[0].config_snapshot == {}

    async def test_list_profiles_multiple(self, db: ConfigDatabase):
        """Test listing multiple profiles."""
        profiles_to_save = [
            ConfigProfile(
                profile_name=f"Profile {i}",
                description=f"Description {i}",
                config_snapshot={"service": {"key": f"value-{i}"}},
                created_at=datetime(2025, 10, 18, 12, i, 0, tzinfo=timezone.utc),
                created_by="test",
                updated_at=datetime(2025, 10, 18, 12, i, 0, tzinfo=timezone.utc),
                updated_by="test"
            )
            for i in range(5)
        ]
        
        for profile in profiles_to_save:
            await db.save_profile(profile)
        
        profiles = await db.list_profiles()
        assert len(profiles) == 5
        
        # Should be sorted by updated_at DESC (most recent first)
        assert profiles[0].profile_name == "Profile 4"
        assert profiles[-1].profile_name == "Profile 0"
        
        # All should have empty snapshots
        assert all(p.config_snapshot == {} for p in profiles)

    async def test_list_profiles_ordering(self, db: ConfigDatabase):
        """Test that profiles are ordered by updated_at DESC."""
        import asyncio
        
        # Create profiles with delays to ensure different timestamps
        profile1 = ConfigProfile(
            profile_name="First",
            description="Created first",
            config_snapshot={"s": {"k": "v"}},
            created_at=datetime.now(timezone.utc),
            created_by="test",
            updated_at=datetime.now(timezone.utc),
            updated_by="test"
        )
        await db.save_profile(profile1)
        await asyncio.sleep(0.05)  # 50ms delay
        
        profile2 = ConfigProfile(
            profile_name="Second",
            description="Created second",
            config_snapshot={"s": {"k": "v"}},
            created_at=datetime.now(timezone.utc),
            created_by="test",
            updated_at=datetime.now(timezone.utc),
            updated_by="test"
        )
        await db.save_profile(profile2)
        await asyncio.sleep(0.05)  # 50ms delay
        
        profile3 = ConfigProfile(
            profile_name="Third",
            description="Created third",
            config_snapshot={"s": {"k": "v"}},
            created_at=datetime.now(timezone.utc),
            created_by="test",
            updated_at=datetime.now(timezone.utc),
            updated_by="test"
        )
        await db.save_profile(profile3)
        
        profiles = await db.list_profiles()
        assert len(profiles) == 3
        
        # Should be in reverse creation order (most recent first)
        assert profiles[0].profile_name == "Third"
        assert profiles[1].profile_name == "Second"
        assert profiles[2].profile_name == "First"


class TestGetProfile:
    """Test database.get_profile()."""

    async def test_get_profile_exists(self, db: ConfigDatabase, sample_profile: ConfigProfile):
        """Test getting an existing profile."""
        await db.save_profile(sample_profile)
        
        profile = await db.get_profile("Test Profile")
        assert profile is not None
        assert profile.profile_name == "Test Profile"
        assert profile.description == "A test configuration profile"
        
        # Full snapshot should be included
        assert profile.config_snapshot != {}
        assert profile.config_snapshot["stt-worker"]["whisper_model"] == "base.en"

    async def test_get_profile_not_found(self, db: ConfigDatabase):
        """Test getting non-existent profile."""
        profile = await db.get_profile("Nonexistent")
        assert profile is None

    async def test_get_profile_case_sensitive(self, db: ConfigDatabase, sample_profile: ConfigProfile):
        """Test that profile names are case-sensitive."""
        await db.save_profile(sample_profile)
        
        # Exact match works
        assert await db.get_profile("Test Profile") is not None
        
        # Wrong case doesn't match
        assert await db.get_profile("test profile") is None
        assert await db.get_profile("TEST PROFILE") is None

    async def test_get_profile_with_spaces(self, db: ConfigDatabase):
        """Test getting profile with spaces in name."""
        profile = ConfigProfile(
            profile_name="My Production Config",
            description="Config with spaces",
            config_snapshot={"test": {"key": "value"}},
            created_at=datetime.now(timezone.utc),
            created_by="test",
            updated_at=datetime.now(timezone.utc),
            updated_by="test"
        )
        
        await db.save_profile(profile)
        saved = await db.get_profile("My Production Config")
        assert saved is not None
        assert saved.profile_name == "My Production Config"


class TestDeleteProfile:
    """Test database.delete_profile()."""

    async def test_delete_profile_success(self, db: ConfigDatabase, sample_profile: ConfigProfile):
        """Test deleting an existing profile."""
        await db.save_profile(sample_profile)
        
        # Verify exists
        assert await db.get_profile("Test Profile") is not None
        
        # Delete
        result = await db.delete_profile("Test Profile")
        assert result is True
        
        # Verify deleted
        assert await db.get_profile("Test Profile") is None

    async def test_delete_profile_not_found(self, db: ConfigDatabase):
        """Test deleting non-existent profile."""
        result = await db.delete_profile("Nonexistent")
        assert result is False

    async def test_delete_profile_multiple_exists(self, db: ConfigDatabase):
        """Test deleting one profile doesn't affect others."""
        profile1 = ConfigProfile(
            profile_name="Profile 1",
            description="First",
            config_snapshot={"s": {"k": "v1"}},
            created_at=datetime.now(timezone.utc),
            created_by="test",
            updated_at=datetime.now(timezone.utc),
            updated_by="test"
        )
        
        profile2 = ConfigProfile(
            profile_name="Profile 2",
            description="Second",
            config_snapshot={"s": {"k": "v2"}},
            created_at=datetime.now(timezone.utc),
            created_by="test",
            updated_at=datetime.now(timezone.utc),
            updated_by="test"
        )
        
        await db.save_profile(profile1)
        await db.save_profile(profile2)
        
        # Delete first
        assert await db.delete_profile("Profile 1") is True
        
        # Verify first deleted, second remains
        assert await db.get_profile("Profile 1") is None
        assert await db.get_profile("Profile 2") is not None

    async def test_delete_and_recreate(self, db: ConfigDatabase, sample_profile: ConfigProfile):
        """Test deleting and recreating a profile."""
        await db.save_profile(sample_profile)
        await db.delete_profile("Test Profile")
        
        # Recreate with different data
        new_profile = ConfigProfile(
            profile_name="Test Profile",  # Same name
            description="Recreated profile",  # Different description
            config_snapshot={"new": {"data": "value"}},
            created_at=datetime.now(timezone.utc),
            created_by="new_user",
            updated_at=datetime.now(timezone.utc),
            updated_by="new_user"
        )
        await db.save_profile(new_profile)
        
        # Verify recreated with new data
        saved = await db.get_profile("Test Profile")
        assert saved is not None
        assert saved.description == "Recreated profile"
        assert saved.created_by == "new_user"


class TestLoadProfile:
    """Test database.load_profile()."""

    async def test_load_profile_success(self, db: ConfigDatabase, sample_profile: ConfigProfile):
        """Test loading a profile into ServiceConfig objects."""
        await db.save_profile(sample_profile)
        
        epoch = "test-epoch-123"
        loaded_by = "test_loader"
        
        configs = await db.load_profile("Test Profile", epoch, loaded_by)
        
        # Should return dict of service_name -> ServiceConfig
        assert isinstance(configs, dict)
        assert "stt-worker" in configs
        assert "tts-worker" in configs
        
        # Check stt-worker config
        stt_config = configs["stt-worker"]
        assert isinstance(stt_config, ServiceConfig)
        assert stt_config.service == "stt-worker"
        assert stt_config.config_epoch == epoch
        assert stt_config.config["whisper_model"] == "base.en"
        assert stt_config.config["vad_threshold"] == 0.5
        
        # Check tts-worker config
        tts_config = configs["tts-worker"]
        assert isinstance(tts_config, ServiceConfig)
        assert tts_config.service == "tts-worker"
        assert tts_config.config_epoch == epoch
        assert tts_config.config["piper_voice"] == "en_US-lessac-medium"

    async def test_load_profile_not_found(self, db: ConfigDatabase):
        """Test loading non-existent profile."""
        with pytest.raises(ValueError, match="not found"):
            await db.load_profile("Nonexistent", "epoch", "user")

    async def test_load_profile_empty_snapshot(self, db: ConfigDatabase):
        """Test loading profile with empty snapshot."""
        profile = ConfigProfile(
            profile_name="Empty Profile",
            description="No services",
            config_snapshot={},  # Empty
            created_at=datetime.now(timezone.utc),
            created_by="test",
            updated_at=datetime.now(timezone.utc),
            updated_by="test"
        )
        await db.save_profile(profile)
        
        configs = await db.load_profile("Empty Profile", "epoch", "user")
        assert configs == {}

    async def test_load_profile_multiple_services(self, db: ConfigDatabase):
        """Test loading profile with multiple services."""
        profile = ConfigProfile(
            profile_name="Multi Service",
            description="Multiple services",
            config_snapshot={
                "service-1": {"key1": "value1"},
                "service-2": {"key2": "value2"},
                "service-3": {"key3": "value3"}
            },
            created_at=datetime.now(timezone.utc),
            created_by="test",
            updated_at=datetime.now(timezone.utc),
            updated_by="test"
        )
        await db.save_profile(profile)
        
        configs = await db.load_profile("Multi Service", "epoch-123", "loader")
        
        assert len(configs) == 3
        assert all(isinstance(c, ServiceConfig) for c in configs.values())
        assert all(c.config_epoch == "epoch-123" for c in configs.values())
        assert configs["service-1"].config["key1"] == "value1"
        assert configs["service-2"].config["key2"] == "value2"
        assert configs["service-3"].config["key3"] == "value3"

    async def test_load_profile_timestamps(self, db: ConfigDatabase, sample_profile: ConfigProfile):
        """Test that loaded configs have proper timestamps."""
        await db.save_profile(sample_profile)
        
        configs = await db.load_profile("Test Profile", "epoch", "user")
        
        # All configs should have timestamps
        for config in configs.values():
            assert config.updated_at is not None
            # Timestamp should be a datetime object
            assert isinstance(config.updated_at, datetime)


class TestProfileIntegration:
    """Integration tests combining multiple profile operations."""

    async def test_profile_lifecycle(self, db: ConfigDatabase):
        """Test complete profile lifecycle: create, list, get, update, delete."""
        # 1. Create profile
        profile = ConfigProfile(
            profile_name="Lifecycle Test",
            description="Initial version",
            config_snapshot={"service": {"key": "v1"}},
            created_at=datetime.now(timezone.utc),
            created_by="creator",
            updated_at=datetime.now(timezone.utc),
            updated_by="creator"
        )
        await db.save_profile(profile)
        
        # 2. List profiles
        profiles = await db.list_profiles()
        assert len(profiles) == 1
        assert profiles[0].profile_name == "Lifecycle Test"
        
        # 3. Get full profile
        full = await db.get_profile("Lifecycle Test")
        assert full.description == "Initial version"
        assert full.config_snapshot["service"]["key"] == "v1"
        
        # 4. Update profile
        updated = ConfigProfile(
            profile_name="Lifecycle Test",
            description="Updated version",
            config_snapshot={"service": {"key": "v2"}},
            created_at=datetime.now(timezone.utc),
            created_by="someone_else",  # Should be ignored
            updated_at=datetime.now(timezone.utc),
            updated_by="updater"
        )
        await db.save_profile(updated)
        
        # 5. Verify update preserved created_by
        final = await db.get_profile("Lifecycle Test")
        assert final.created_by == "creator"  # Preserved
        assert final.updated_by == "updater"  # Updated
        assert final.description == "Updated version"
        assert final.config_snapshot["service"]["key"] == "v2"
        
        # 6. Load profile
        configs = await db.load_profile("Lifecycle Test", "epoch", "loader")
        assert configs["service"].config["key"] == "v2"
        
        # 7. Delete profile
        assert await db.delete_profile("Lifecycle Test") is True
        assert await db.get_profile("Lifecycle Test") is None
        assert await db.list_profiles() == []

    async def test_multiple_profiles_coexist(self, db: ConfigDatabase):
        """Test that multiple profiles can coexist without interference."""
        profiles = [
            ConfigProfile(
                profile_name=f"Profile {i}",
                description=f"Description {i}",
                config_snapshot={f"service-{i}": {"key": f"value-{i}"}},
                created_at=datetime.now(timezone.utc),
                created_by=f"user-{i}",
                updated_at=datetime.now(timezone.utc),
                updated_by=f"user-{i}"
            )
            for i in range(10)
        ]
        
        # Save all
        for profile in profiles:
            await db.save_profile(profile)
        
        # List all
        all_profiles = await db.list_profiles()
        assert len(all_profiles) == 10
        
        # Get each individually
        for i in range(10):
            p = await db.get_profile(f"Profile {i}")
            assert p is not None
            assert p.description == f"Description {i}"
        
        # Load each
        for i in range(10):
            configs = await db.load_profile(f"Profile {i}", "epoch", "user")
            assert f"service-{i}" in configs
        
        # Delete half
        for i in range(0, 10, 2):
            assert await db.delete_profile(f"Profile {i}") is True
        
        # Verify half deleted, half remain
        remaining = await db.list_profiles()
        assert len(remaining) == 5
        assert all("1" in p.profile_name or "3" in p.profile_name or 
                   "5" in p.profile_name or "7" in p.profile_name or 
                   "9" in p.profile_name for p in remaining)
