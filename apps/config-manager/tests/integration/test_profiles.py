"""
Integration tests for configuration profile management.

Tests CRUD operations, profile activation, and security controls.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
import orjson
from datetime import datetime, timezone


@pytest.fixture
def mock_mqtt_publisher():
    """Mock MQTT publisher for testing."""
    publisher = AsyncMock()
    publisher.publish_config_update = AsyncMock()
    return publisher


@pytest.fixture
def mock_cache_manager():
    """Mock cache manager for testing."""
    cache = AsyncMock()
    cache.atomic_update_from_db = AsyncMock()
    return cache


@pytest.fixture
def sample_profile_data():
    """Sample profile data for testing."""
    return {
        "profile_name": "Test Profile",
        "description": "A test configuration profile",
        "config_snapshot": {
            "stt-worker": {
                "whisper_model": "base.en",
                "vad_threshold": 0.5
            },
            "tts-worker": {
                "piper_voice": "en_US-lessac-medium",
                "volume_percent": 100
            }
        }
    }


class TestProfileList:
    """Test GET /api/config/profiles - list all profiles."""

    def test_list_profiles_empty(self, client: TestClient, admin_token: str):
        """Test listing profiles when none exist."""
        response = client.get(
            "/api/config/profiles",
            headers={"X-API-Token": admin_token}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "profiles" in data
        assert isinstance(data["profiles"], list)

    def test_list_profiles_with_data(
        self,
        client: TestClient,
        admin_token: str,
        sample_profile_data: dict
    ):
        """Test listing profiles with existing profiles."""
        # Create a profile first
        from tars.config.models import ConfigProfile
        profile = ConfigProfile(
            profile_name=sample_profile_data["profile_name"],
            description=sample_profile_data["description"],
            config_snapshot=sample_profile_data["config_snapshot"],
            created_at=datetime.now(timezone.utc),
            created_by="admin",
            updated_at=datetime.now(timezone.utc),
            updated_by="admin"
        )
        
        # Access database through app state
        database = client.app.state.database
        database.save_profile(profile)
        
        # List profiles
        response = client.get(
            "/api/config/profiles",
            headers={"X-API-Token": admin_token}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["profiles"]) >= 1
        
        # Check profile structure (should not include full snapshot)
        profile_data = data["profiles"][0]
        assert profile_data["profile_name"] == "Test Profile"
        assert profile_data["description"] == "A test configuration profile"
        assert "config_snapshot" not in profile_data  # Not included in list view
        assert "created_at" in profile_data
        assert "updated_at" in profile_data

    def test_list_profiles_no_auth(self, client: TestClient):
        """Test listing profiles without authentication."""
        response = client.get("/api/config/profiles")
        assert response.status_code == 401

    def test_list_profiles_readonly_access(self, client: TestClient, readonly_token: str):
        """Test listing profiles with read-only token."""
        response = client.get(
            "/api/config/profiles",
            headers={"X-API-Token": readonly_token}
        )
        assert response.status_code == 200


class TestProfileGet:
    """Test GET /api/config/profiles/{name} - get specific profile."""

    def test_get_profile_success(
        self,
        client: TestClient,
        admin_token: str,
        sample_profile_data: dict
    ):
        """Test getting a specific profile."""
        # Create profile
        from tars.config.models import ConfigProfile
        profile = ConfigProfile(
            profile_name=sample_profile_data["profile_name"],
            description=sample_profile_data["description"],
            config_snapshot=sample_profile_data["config_snapshot"],
            created_at=datetime.now(timezone.utc),
            created_by="admin",
            updated_at=datetime.now(timezone.utc),
            updated_by="admin"
        )
        
        database = client.app.state.database
        database.save_profile(profile)
        
        # Get profile
        response = client.get(
            "/api/config/profiles/Test%20Profile",
            headers={"X-API-Token": admin_token}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["profile_name"] == "Test Profile"
        assert data["description"] == "A test configuration profile"
        assert "config_snapshot" in data  # Full snapshot included
        assert data["config_snapshot"]["stt-worker"]["whisper_model"] == "base.en"

    def test_get_profile_not_found(self, client: TestClient, admin_token: str):
        """Test getting non-existent profile."""
        response = client.get(
            "/api/config/profiles/Nonexistent",
            headers={"X-API-Token": admin_token}
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_profile_no_auth(self, client: TestClient):
        """Test getting profile without authentication."""
        response = client.get("/api/config/profiles/Test%20Profile")
        assert response.status_code == 401

    def test_get_profile_readonly_access(
        self,
        client: TestClient,
        readonly_token: str,
        sample_profile_data: dict
    ):
        """Test getting profile with read-only token."""
        # Create profile
        from tars.config.models import ConfigProfile
        profile = ConfigProfile(
            profile_name=sample_profile_data["profile_name"],
            description=sample_profile_data["description"],
            config_snapshot=sample_profile_data["config_snapshot"],
            created_at=datetime.now(timezone.utc),
            created_by="admin",
            updated_at=datetime.now(timezone.utc),
            updated_by="admin"
        )
        
        database = client.app.state.database
        database.save_profile(profile)
        
        # Read-only should be able to get profiles
        response = client.get(
            "/api/config/profiles/Test%20Profile",
            headers={"X-API-Token": readonly_token}
        )
        assert response.status_code == 200


class TestProfileSave:
    """Test POST /api/config/profiles - save current config as profile."""

    def test_save_profile_success(
        self,
        client: TestClient,
        admin_token: str,
        admin_csrf_token: str
    ):
        """Test saving current config as a profile."""
        # First, ensure we have some service configs
        database = client.app.state.database
        from tars.config.models import ServiceConfig
        
        config = ServiceConfig(
            service_name="stt-worker",
            config_epoch="epoch-test",
            items={"whisper_model": "base.en", "vad_threshold": 0.5},
            config_version=1,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        database.update_service_config(config)
        
        # Save profile
        response = client.post(
            "/api/config/profiles",
            headers={
                "X-API-Token": admin_token,
                "X-CSRF-Token": admin_csrf_token
            },
            json={
                "profile_name": "My Test Profile",
                "description": "Saved from test"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["profile_name"] == "My Test Profile"
        assert data["description"] == "Saved from test"
        assert "config_snapshot" in data
        assert "created_at" in data
        assert data["created_by"] == "admin"

    def test_save_profile_no_csrf(
        self,
        client: TestClient,
        admin_token: str
    ):
        """Test saving profile without CSRF token."""
        response = client.post(
            "/api/config/profiles",
            headers={"X-API-Token": admin_token},
            json={
                "profile_name": "Test",
                "description": "Test"
            }
        )
        assert response.status_code == 403

    def test_save_profile_readonly_denied(
        self,
        client: TestClient,
        readonly_token: str,
        readonly_csrf_token: str
    ):
        """Test saving profile with read-only token."""
        response = client.post(
            "/api/config/profiles",
            headers={
                "X-API-Token": readonly_token,
                "X-CSRF-Token": readonly_csrf_token
            },
            json={
                "profile_name": "Test",
                "description": "Test"
            }
        )
        assert response.status_code == 403

    def test_save_profile_invalid_name(
        self,
        client: TestClient,
        admin_token: str,
        admin_csrf_token: str
    ):
        """Test saving profile with invalid name."""
        response = client.post(
            "/api/config/profiles",
            headers={
                "X-API-Token": admin_token,
                "X-CSRF-Token": admin_csrf_token
            },
            json={
                "profile_name": "",  # Empty name
                "description": "Test"
            }
        )
        assert response.status_code == 422  # Validation error

    def test_save_profile_update_existing(
        self,
        client: TestClient,
        admin_token: str,
        admin_csrf_token: str
    ):
        """Test updating an existing profile preserves created_at."""
        database = client.app.state.database
        from tars.config.models import ServiceConfig, ConfigProfile
        
        # Create initial config
        config = ServiceConfig(
            service_name="stt-worker",
            config_epoch="epoch-test",
            items={"whisper_model": "base.en"},
            config_version=1,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        database.update_service_config(config)
        
        # Save profile first time
        response1 = client.post(
            "/api/config/profiles",
            headers={
                "X-API-Token": admin_token,
                "X-CSRF-Token": admin_csrf_token
            },
            json={
                "profile_name": "Update Test",
                "description": "First save"
            }
        )
        assert response1.status_code == 200
        first_created_at = response1.json()["created_at"]
        
        # Update config
        config.items["vad_threshold"] = 0.7
        config.config_version = 2
        database.update_service_config(config)
        
        # Save profile again (update)
        response2 = client.post(
            "/api/config/profiles",
            headers={
                "X-API-Token": admin_token,
                "X-CSRF-Token": admin_csrf_token
            },
            json={
                "profile_name": "Update Test",
                "description": "Second save"
            }
        )
        assert response2.status_code == 200
        second_created_at = response2.json()["created_at"]
        
        # created_at should be preserved
        assert first_created_at == second_created_at
        assert response2.json()["description"] == "Second save"


class TestProfileActivate:
    """Test PUT /api/config/profiles/{name}/activate - apply profile."""

    @patch("config_manager.api.mqtt_publisher")
    @patch("config_manager.api.cache_manager")
    def test_activate_profile_success(
        self,
        mock_cache: MagicMock,
        mock_mqtt: MagicMock,
        client: TestClient,
        admin_token: str,
        admin_csrf_token: str,
        sample_profile_data: dict
    ):
        """Test activating a profile."""
        # Setup mocks
        mock_mqtt.publish_config_update = AsyncMock()
        mock_cache.atomic_update_from_db = AsyncMock()
        
        # Create profile
        from tars.config.models import ConfigProfile
        profile = ConfigProfile(
            profile_name=sample_profile_data["profile_name"],
            description=sample_profile_data["description"],
            config_snapshot=sample_profile_data["config_snapshot"],
            created_at=datetime.now(timezone.utc),
            created_by="admin",
            updated_at=datetime.now(timezone.utc),
            updated_by="admin"
        )
        
        database = client.app.state.database
        database.save_profile(profile)
        
        # Activate profile
        response = client.put(
            "/api/config/profiles/Test%20Profile/activate",
            headers={
                "X-API-Token": admin_token,
                "X-CSRF-Token": admin_csrf_token
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "services_updated" in data
        assert "stt-worker" in data["services_updated"]
        assert "tts-worker" in data["services_updated"]
        assert "config_epoch" in data

    def test_activate_profile_not_found(
        self,
        client: TestClient,
        admin_token: str,
        admin_csrf_token: str
    ):
        """Test activating non-existent profile."""
        response = client.put(
            "/api/config/profiles/Nonexistent/activate",
            headers={
                "X-API-Token": admin_token,
                "X-CSRF-Token": admin_csrf_token
            }
        )
        assert response.status_code == 404

    def test_activate_profile_no_csrf(
        self,
        client: TestClient,
        admin_token: str
    ):
        """Test activating profile without CSRF token."""
        response = client.put(
            "/api/config/profiles/Test/activate",
            headers={"X-API-Token": admin_token}
        )
        assert response.status_code == 403

    def test_activate_profile_readonly_denied(
        self,
        client: TestClient,
        readonly_token: str,
        readonly_csrf_token: str
    ):
        """Test activating profile with read-only token."""
        response = client.put(
            "/api/config/profiles/Test/activate",
            headers={
                "X-API-Token": readonly_token,
                "X-CSRF-Token": readonly_csrf_token
            }
        )
        assert response.status_code == 403


class TestProfileDelete:
    """Test DELETE /api/config/profiles/{name} - delete profile."""

    def test_delete_profile_success(
        self,
        client: TestClient,
        admin_token: str,
        admin_csrf_token: str,
        sample_profile_data: dict
    ):
        """Test deleting a profile."""
        # Create profile
        from tars.config.models import ConfigProfile
        profile = ConfigProfile(
            profile_name=sample_profile_data["profile_name"],
            description=sample_profile_data["description"],
            config_snapshot=sample_profile_data["config_snapshot"],
            created_at=datetime.now(timezone.utc),
            created_by="admin",
            updated_at=datetime.now(timezone.utc),
            updated_by="admin"
        )
        
        database = client.app.state.database
        database.save_profile(profile)
        
        # Delete profile
        response = client.delete(
            "/api/config/profiles/Test%20Profile",
            headers={
                "X-API-Token": admin_token,
                "X-CSRF-Token": admin_csrf_token
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted" in data["message"].lower()
        
        # Verify deleted
        profile_check = database.get_profile("Test Profile")
        assert profile_check is None

    def test_delete_profile_not_found(
        self,
        client: TestClient,
        admin_token: str,
        admin_csrf_token: str
    ):
        """Test deleting non-existent profile."""
        response = client.delete(
            "/api/config/profiles/Nonexistent",
            headers={
                "X-API-Token": admin_token,
                "X-CSRF-Token": admin_csrf_token
            }
        )
        assert response.status_code == 404

    def test_delete_profile_no_csrf(
        self,
        client: TestClient,
        admin_token: str
    ):
        """Test deleting profile without CSRF token."""
        response = client.delete(
            "/api/config/profiles/Test",
            headers={"X-API-Token": admin_token}
        )
        assert response.status_code == 403

    def test_delete_profile_readonly_denied(
        self,
        client: TestClient,
        readonly_token: str,
        readonly_csrf_token: str
    ):
        """Test deleting profile with read-only token."""
        response = client.delete(
            "/api/config/profiles/Test",
            headers={
                "X-API-Token": readonly_token,
                "X-CSRF-Token": readonly_csrf_token
            }
        )
        assert response.status_code == 403


class TestProfileAuditLogging:
    """Test audit logging for profile operations."""

    def test_profile_save_audit_log(
        self,
        client: TestClient,
        admin_token: str,
        admin_csrf_token: str
    ):
        """Test that saving a profile creates audit log entry."""
        database = client.app.state.database
        from tars.config.models import ServiceConfig
        
        config = ServiceConfig(
            service_name="test-service",
            config_epoch="epoch-test",
            items={"test": "value"},
            config_version=1,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        database.update_service_config(config)
        
        # Save profile
        response = client.post(
            "/api/config/profiles",
            headers={
                "X-API-Token": admin_token,
                "X-CSRF-Token": admin_csrf_token
            },
            json={
                "profile_name": "Audit Test",
                "description": "Test audit"
            }
        )
        assert response.status_code == 200
        
        # Check audit log
        logs = database.get_access_logs(limit=1)
        assert len(logs) > 0
        latest_log = logs[0]
        assert latest_log.token_name == "admin"
        assert latest_log.endpoint == "/api/config/profiles"
        assert latest_log.method == "POST"

    def test_profile_activate_audit_log(
        self,
        client: TestClient,
        admin_token: str,
        admin_csrf_token: str,
        sample_profile_data: dict
    ):
        """Test that activating a profile creates audit log entry."""
        # Create profile
        from tars.config.models import ConfigProfile
        profile = ConfigProfile(
            profile_name=sample_profile_data["profile_name"],
            description=sample_profile_data["description"],
            config_snapshot=sample_profile_data["config_snapshot"],
            created_at=datetime.now(timezone.utc),
            created_by="admin",
            updated_at=datetime.now(timezone.utc),
            updated_by="admin"
        )
        
        database = client.app.state.database
        database.save_profile(profile)
        
        # Activate profile
        with patch("config_manager.api.mqtt_publisher"), \
             patch("config_manager.api.cache_manager"):
            response = client.put(
                "/api/config/profiles/Test%20Profile/activate",
                headers={
                    "X-API-Token": admin_token,
                    "X-CSRF-Token": admin_csrf_token
                }
            )
            assert response.status_code == 200
        
        # Check audit log
        logs = database.get_access_logs(limit=1)
        assert len(logs) > 0
        latest_log = logs[0]
        assert latest_log.token_name == "admin"
        assert "/activate" in latest_log.endpoint
        assert latest_log.method == "PUT"

    def test_profile_delete_audit_log(
        self,
        client: TestClient,
        admin_token: str,
        admin_csrf_token: str,
        sample_profile_data: dict
    ):
        """Test that deleting a profile creates audit log entry."""
        # Create profile
        from tars.config.models import ConfigProfile
        profile = ConfigProfile(
            profile_name=sample_profile_data["profile_name"],
            description=sample_profile_data["description"],
            config_snapshot=sample_profile_data["config_snapshot"],
            created_at=datetime.now(timezone.utc),
            created_by="admin",
            updated_at=datetime.now(timezone.utc),
            updated_by="admin"
        )
        
        database = client.app.state.database
        database.save_profile(profile)
        
        # Delete profile
        response = client.delete(
            "/api/config/profiles/Test%20Profile",
            headers={
                "X-API-Token": admin_token,
                "X-CSRF-Token": admin_csrf_token
            }
        )
        assert response.status_code == 200
        
        # Check audit log
        logs = database.get_access_logs(limit=1)
        assert len(logs) > 0
        latest_log = logs[0]
        assert latest_log.token_name == "admin"
        assert "Test%20Profile" in latest_log.endpoint or "Test Profile" in latest_log.endpoint
        assert latest_log.method == "DELETE"
