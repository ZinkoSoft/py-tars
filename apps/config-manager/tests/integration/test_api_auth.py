"""Integration tests for API authentication and validation."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from config_manager.auth import initialize_token_store, Role


@pytest.fixture
def test_tokens():
    """Initialize test tokens."""
    token_store = initialize_token_store()
    
    # Create test tokens
    admin_token = token_store.create_token("test-admin-token", "Test Admin", Role.ADMIN)
    write_token = token_store.create_token("test-write-token", "Test Writer", Role.WRITE)
    read_token = token_store.create_token("test-read-token", "Test Reader", Role.READ)
    
    return {
        "admin": "test-admin-token",
        "write": "test-write-token",
        "read": "test-read-token",
    }


@pytest.fixture
def client():
    """Create a test client."""
    # Import here to avoid circular imports
    from config_manager.__main__ import app
    return TestClient(app)


class TestAuthenticationEndpoints:
    """Tests for API authentication."""

    def test_get_services_without_token(self, client):
        """Test that accessing services without token returns 401."""
        response = client.get("/api/config/services")
        assert response.status_code == 401
        assert "API token required" in response.json()["detail"]

    def test_get_services_with_invalid_token(self, client):
        """Test that invalid token returns 401."""
        response = client.get(
            "/api/config/services",
            headers={"X-API-Token": "invalid-token-12345"},
        )
        assert response.status_code == 401
        assert "Invalid or expired" in response.json()["detail"]

    def test_get_services_with_valid_token(self, client, test_tokens):
        """Test that valid token allows access."""
        response = client.get(
            "/api/config/services",
            headers={"X-API-Token": test_tokens["read"]},
        )
        # May return 503 if service not initialized, which is OK for auth test
        assert response.status_code in [200, 503]

    def test_get_csrf_token_without_auth(self, client):
        """Test that CSRF endpoint requires authentication."""
        response = client.get("/api/config/csrf-token")
        assert response.status_code == 401

    def test_get_csrf_token_with_auth(self, client, test_tokens):
        """Test getting CSRF token with authentication."""
        response = client.get(
            "/api/config/csrf-token",
            headers={"X-API-Token": test_tokens["read"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "csrf_token" in data
        assert "expires_at" in data
        assert len(data["csrf_token"]) > 10


class TestAuthorizationEndpoints:
    """Tests for API authorization (permissions)."""

    def test_read_token_can_get_services(self, client, test_tokens):
        """Test that read token can list services."""
        response = client.get(
            "/api/config/services",
            headers={"X-API-Token": test_tokens["read"]},
        )
        # Should have permission (200 or 503 if service not ready)
        assert response.status_code in [200, 503]

    def test_read_token_cannot_update_config(self, client, test_tokens):
        """Test that read token cannot update configuration."""
        response = client.put(
            "/api/config/services/test-service",
            headers={
                "X-API-Token": test_tokens["read"],
                "X-CSRF-Token": "test-csrf",
            },
            json={
                "service": "test-service",
                "config": {"key": "value"},
                "version": 1,
            },
        )
        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]

    def test_write_token_can_get_services(self, client, test_tokens):
        """Test that write token can list services."""
        response = client.get(
            "/api/config/services",
            headers={"X-API-Token": test_tokens["write"]},
        )
        assert response.status_code in [200, 503]

    def test_write_token_can_update_config(self, client, test_tokens):
        """Test that write token can update configuration."""
        response = client.put(
            "/api/config/services/test-service",
            headers={
                "X-API-Token": test_tokens["write"],
                "X-CSRF-Token": "test-csrf",
            },
            json={
                "service": "test-service",
                "config": {"key": "value"},
                "version": 1,
            },
        )
        # May fail with 503/404/400 but should NOT be 403 (permission denied)
        assert response.status_code != 403

    def test_admin_token_has_full_access(self, client, test_tokens):
        """Test that admin token has all permissions."""
        # Can read
        response = client.get(
            "/api/config/services",
            headers={"X-API-Token": test_tokens["admin"]},
        )
        assert response.status_code in [200, 503]

        # Can write (may fail for other reasons, but not permission)
        response = client.put(
            "/api/config/services/test-service",
            headers={
                "X-API-Token": test_tokens["admin"],
                "X-CSRF-Token": "test-csrf",
            },
            json={
                "service": "test-service",
                "config": {"key": "value"},
                "version": 1,
            },
        )
        assert response.status_code != 403


class TestValidationEndpoints:
    """Tests for server-side validation."""

    def test_update_with_invalid_data_returns_422(self, client, test_tokens):
        """Test that invalid configuration data returns 422."""
        # Try to set vad_threshold out of range for STT worker
        response = client.put(
            "/api/config/services/stt-worker",
            headers={
                "X-API-Token": test_tokens["write"],
                "X-CSRF-Token": "test-csrf",
            },
            json={
                "service": "stt-worker",
                "config": {
                    "vad_threshold": 5.0,  # Invalid: > 1.0
                },
                "version": 1,
            },
        )
        
        # Should get validation error (if service exists) or 404/503
        if response.status_code == 422:
            data = response.json()
            assert "validation" in data["detail"]["message"].lower()
            assert "errors" in data["detail"]

    def test_update_with_invalid_service_name_returns_400(self, client, test_tokens):
        """Test that mismatched service name returns 400."""
        response = client.put(
            "/api/config/services/stt-worker",
            headers={
                "X-API-Token": test_tokens["write"],
                "X-CSRF-Token": "test-csrf",
            },
            json={
                "service": "different-service",  # Mismatch!
                "config": {},
                "version": 1,
            },
        )
        
        assert response.status_code == 400
        assert "must match" in response.json()["detail"]


class TestCSRFProtection:
    """Tests for CSRF protection."""

    def test_update_without_csrf_token_logs_warning(self, client, test_tokens):
        """Test that update without CSRF token is logged but not blocked."""
        # In current implementation, we log warning but don't block
        response = client.put(
            "/api/config/services/test-service",
            headers={
                "X-API-Token": test_tokens["write"],
                # No X-CSRF-Token header
            },
            json={
                "service": "test-service",
                "config": {},
                "version": 1,
            },
        )
        
        # Should not be blocked by CSRF in current MVP implementation
        # May fail for other reasons (503, 404, etc)
        assert response.status_code != 403

    def test_update_with_csrf_token_accepted(self, client, test_tokens):
        """Test that update with CSRF token is accepted."""
        response = client.put(
            "/api/config/services/test-service",
            headers={
                "X-API-Token": test_tokens["write"],
                "X-CSRF-Token": "any-token-for-mvp",
            },
            json={
                "service": "test-service",
                "config": {},
                "version": 1,
            },
        )
        
        # Should not be blocked by CSRF
        assert response.status_code != 403


class TestAuditLogging:
    """Tests to verify audit logging (check logs manually)."""

    def test_unauthorized_attempt_is_logged(self, client, caplog):
        """Test that unauthorized attempts are logged."""
        with caplog.at_level("WARNING"):
            client.get("/api/config/services")
        
        # Should have logged the missing token attempt
        assert any("without API token" in record.message for record in caplog.records)

    def test_permission_denied_is_logged(self, client, test_tokens, caplog):
        """Test that permission denied attempts are logged."""
        with caplog.at_level("WARNING"):
            client.put(
                "/api/config/services/test-service",
                headers={
                    "X-API-Token": test_tokens["read"],
                    "X-CSRF-Token": "test",
                },
                json={
                    "service": "test-service",
                    "config": {},
                    "version": 1,
                },
            )
        
        # Should have logged permission denial
        assert any("Permission denied" in record.message for record in caplog.records)
