"""Tests for authentication and authorization."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest

from config_manager.auth import (
    Role,
    Permission,
    APIToken,
    TokenStore,
    has_permission,
    require_permission,
    ROLE_PERMISSIONS,
)


class TestRolePermissions:
    """Tests for role and permission mappings."""

    def test_admin_has_all_permissions(self):
        """Test that admin role has all permissions."""
        admin_perms = ROLE_PERMISSIONS[Role.ADMIN]
        assert Permission.CONFIG_READ in admin_perms
        assert Permission.CONFIG_WRITE in admin_perms
        assert Permission.CONFIG_DELETE in admin_perms
        assert Permission.USER_MANAGE in admin_perms

    def test_write_role_permissions(self):
        """Test that write role has read and write permissions."""
        write_perms = ROLE_PERMISSIONS[Role.WRITE]
        assert Permission.CONFIG_READ in write_perms
        assert Permission.CONFIG_WRITE in write_perms
        assert Permission.CONFIG_DELETE not in write_perms
        assert Permission.USER_MANAGE not in write_perms

    def test_read_role_permissions(self):
        """Test that read role has only read permission."""
        read_perms = ROLE_PERMISSIONS[Role.READ]
        assert Permission.CONFIG_READ in read_perms
        assert Permission.CONFIG_WRITE not in read_perms
        assert Permission.CONFIG_DELETE not in read_perms
        assert Permission.USER_MANAGE not in read_perms


class TestAPIToken:
    """Tests for APIToken model."""

    def test_create_token(self):
        """Test creating an API token."""
        token = APIToken(
            token_id="test-id",
            token_hash="abc123hash",
            name="test-token",
            role=Role.WRITE,
        )
        
        assert token.token_id == "test-id"
        assert token.name == "test-token"
        assert token.role == Role.WRITE
        assert token.is_active is True

    def test_token_expiration(self):
        """Test token with expiration."""
        expires = datetime.now(UTC) + timedelta(days=30)
        token = APIToken(
            token_id="test-id",
            token_hash="abc123hash",
            name="test-token",
            role=Role.READ,
            expires_at=expires,
        )
        
        assert token.expires_at == expires


class TestTokenStore:
    """Tests for TokenStore."""

    @pytest.fixture(autouse=True)
    def clear_env(self):
        """Clear API_TOKENS env var before each test."""
        if "API_TOKENS" in os.environ:
            del os.environ["API_TOKENS"]

    def test_create_token(self):
        """Test creating a token."""
        store = TokenStore()
        
        token = store.create_token(
            token="my-secret-token",
            name="test-token",
            role=Role.WRITE,
        )
        
        assert token.name == "test-token"
        assert token.role == Role.WRITE
        assert token.is_active is True

    def test_validate_token_success(self):
        """Test validating a valid token."""
        store = TokenStore()
        
        # Create token
        store.create_token(
            token="my-secret-token",
            name="test-token",
            role=Role.WRITE,
        )
        
        # Validate it
        validated = store.validate_token("my-secret-token")
        assert validated is not None
        assert validated.name == "test-token"
        assert validated.role == Role.WRITE

    def test_validate_token_invalid(self):
        """Test validating an invalid token."""
        store = TokenStore()
        
        # Try to validate non-existent token
        validated = store.validate_token("invalid-token")
        assert validated is None

    def test_validate_inactive_token(self):
        """Test validating an inactive token."""
        store = TokenStore()
        
        # Create and revoke token
        token = store.create_token(
            token="my-token",
            name="test",
            role=Role.READ,
        )
        token.is_active = False
        
        # Should fail validation
        validated = store.validate_token("my-token")
        assert validated is None

    def test_validate_expired_token(self):
        """Test validating an expired token."""
        store = TokenStore()
        
        # Create token that expired yesterday
        store.create_token(
            token="my-token",
            name="test",
            role=Role.READ,
            expires_in_days=-1,
        )
        
        # Should fail validation
        validated = store.validate_token("my-token")
        assert validated is None

    def test_revoke_token(self):
        """Test revoking a token."""
        store = TokenStore()
        
        # Create token
        token = store.create_token(
            token="my-token",
            name="test",
            role=Role.WRITE,
        )
        
        # Revoke it
        result = store.revoke_token(token.token_id)
        assert result is True
        
        # Should fail validation now
        validated = store.validate_token("my-token")
        assert validated is None

    def test_revoke_nonexistent_token(self):
        """Test revoking a non-existent token."""
        store = TokenStore()
        result = store.revoke_token("nonexistent-id")
        assert result is False

    def test_list_tokens(self):
        """Test listing all tokens."""
        store = TokenStore()
        
        # Initially should have the default dev token
        initial_tokens = store.list_tokens()
        initial_count = len(initial_tokens)
        
        # Create more tokens
        store.create_token("token1", "Test 1", Role.READ)
        store.create_token("token2", "Test 2", Role.WRITE)
        
        tokens = store.list_tokens()
        assert len(tokens) == initial_count + 2

    def test_initialize_from_env(self):
        """Test initializing tokens from environment."""
        os.environ["API_TOKENS"] = "token1:admin-token:admin,token2:readonly:config.read"
        
        store = TokenStore()
        
        # Should have loaded both tokens
        token1 = store.validate_token("token1")
        assert token1 is not None
        assert token1.name == "admin-token"
        assert token1.role == Role.ADMIN
        
        token2 = store.validate_token("token2")
        assert token2 is not None
        assert token2.name == "readonly"
        assert token2.role == Role.READ

    def test_initialize_from_env_invalid_format(self, monkeypatch, caplog):
        """Test that invalid token formats are skipped."""
        monkeypatch.setenv("API_TOKENS", "invalid:format")
        
        # Creating TokenStore will call _initialize_from_env internally
        store = TokenStore()
        
        tokens = store.list_tokens()
        # Invalid format should be skipped (no tokens created)
        assert len(tokens) == 0
        # Should have logged an error about invalid format
        assert any("Invalid token spec" in record.message for record in caplog.records)

    def test_token_hash_consistency(self):
        """Test that token hashing is consistent."""
        store = TokenStore()
        
        hash1 = store._hash_token("my-token")
        hash2 = store._hash_token("my-token")
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex length


class TestPermissionChecking:
    """Tests for permission checking functions."""

    def test_has_permission_admin(self):
        """Test that admin has all permissions."""
        token = APIToken(
            token_id="test",
            token_hash="hash",
            name="admin",
            role=Role.ADMIN,
        )
        
        assert has_permission(token, Permission.CONFIG_READ) is True
        assert has_permission(token, Permission.CONFIG_WRITE) is True
        assert has_permission(token, Permission.CONFIG_DELETE) is True
        assert has_permission(token, Permission.USER_MANAGE) is True

    def test_has_permission_write(self):
        """Test write role permissions."""
        token = APIToken(
            token_id="test",
            token_hash="hash",
            name="writer",
            role=Role.WRITE,
        )
        
        assert has_permission(token, Permission.CONFIG_READ) is True
        assert has_permission(token, Permission.CONFIG_WRITE) is True
        assert has_permission(token, Permission.CONFIG_DELETE) is False
        assert has_permission(token, Permission.USER_MANAGE) is False

    def test_has_permission_read(self):
        """Test read role permissions."""
        token = APIToken(
            token_id="test",
            token_hash="hash",
            name="reader",
            role=Role.READ,
        )
        
        assert has_permission(token, Permission.CONFIG_READ) is True
        assert has_permission(token, Permission.CONFIG_WRITE) is False
        assert has_permission(token, Permission.CONFIG_DELETE) is False
        assert has_permission(token, Permission.USER_MANAGE) is False

    def test_has_permission_no_token(self):
        """Test that None token has no permissions."""
        assert has_permission(None, Permission.CONFIG_READ) is False
        assert has_permission(None, Permission.CONFIG_WRITE) is False

    def test_require_permission_success(self):
        """Test require_permission with valid permission."""
        token = APIToken(
            token_id="test",
            token_hash="hash",
            name="admin",
            role=Role.ADMIN,
        )
        
        # Should not raise
        require_permission(token, Permission.CONFIG_WRITE)

    def test_require_permission_failure(self):
        """Test require_permission with missing permission."""
        token = APIToken(
            token_id="test",
            token_hash="hash",
            name="reader",
            role=Role.READ,
        )
        
        # Should raise PermissionError
        with pytest.raises(PermissionError) as exc_info:
            require_permission(token, Permission.CONFIG_WRITE)
        
        assert "config.write" in str(exc_info.value)

    def test_require_permission_no_token(self):
        """Test require_permission with no token."""
        with pytest.raises(PermissionError):
            require_permission(None, Permission.CONFIG_READ)


class TestTokenStoreIntegration:
    """Integration tests for TokenStore."""

    @pytest.fixture(autouse=True)
    def clear_env(self):
        """Clear API_TOKENS env var before each test."""
        if "API_TOKENS" in os.environ:
            del os.environ["API_TOKENS"]

    def test_full_token_lifecycle(self):
        """Test complete token lifecycle."""
        store = TokenStore()
        
        # Create token
        token = store.create_token(
            token="lifecycle-token",
            name="Lifecycle Test",
            role=Role.WRITE,
            expires_in_days=30,
        )
        
        assert token.is_active is True
        
        # Validate token
        validated = store.validate_token("lifecycle-token")
        assert validated is not None
        assert validated.name == "Lifecycle Test"
        
        # Last used should be updated
        assert validated.last_used is not None
        
        # Revoke token
        revoked = store.revoke_token(token.token_id)
        assert revoked is True
        
        # Should no longer validate
        revalidated = store.validate_token("lifecycle-token")
        assert revalidated is None

    def test_multiple_tokens_different_roles(self):
        """Test managing multiple tokens with different roles."""
        store = TokenStore()
        
        # Create tokens with different roles
        admin_token = store.create_token("admin-key", "Admin", Role.ADMIN)
        write_token = store.create_token("write-key", "Writer", Role.WRITE)
        read_token = store.create_token("read-key", "Reader", Role.READ)
        
        # Validate admin can do everything
        admin = store.validate_token("admin-key")
        assert has_permission(admin, Permission.CONFIG_READ)
        assert has_permission(admin, Permission.CONFIG_WRITE)
        assert has_permission(admin, Permission.USER_MANAGE)
        
        # Validate writer can read and write
        writer = store.validate_token("write-key")
        assert has_permission(writer, Permission.CONFIG_READ)
        assert has_permission(writer, Permission.CONFIG_WRITE)
        assert not has_permission(writer, Permission.USER_MANAGE)
        
        # Validate reader can only read
        reader = store.validate_token("read-key")
        assert has_permission(reader, Permission.CONFIG_READ)
        assert not has_permission(reader, Permission.CONFIG_WRITE)
        assert not has_permission(reader, Permission.USER_MANAGE)
