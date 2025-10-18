"""Authentication and authorization for configuration management."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class Role(str, Enum):
    """User roles for configuration management."""
    
    ADMIN = "admin"  # Full access (read + write + manage users)
    WRITE = "config.write"  # Can read and write configuration
    READ = "config.read"  # Can only read configuration


class Permission(str, Enum):
    """Granular permissions."""
    
    CONFIG_READ = "config.read"
    CONFIG_WRITE = "config.write"
    CONFIG_DELETE = "config.delete"
    USER_MANAGE = "user.manage"


# Role to permissions mapping
ROLE_PERMISSIONS: dict[Role, list[Permission]] = {
    Role.ADMIN: [
        Permission.CONFIG_READ,
        Permission.CONFIG_WRITE,
        Permission.CONFIG_DELETE,
        Permission.USER_MANAGE,
    ],
    Role.WRITE: [
        Permission.CONFIG_READ,
        Permission.CONFIG_WRITE,
    ],
    Role.READ: [
        Permission.CONFIG_READ,
    ],
}


class APIToken(BaseModel):
    """API token model."""
    
    model_config = ConfigDict(extra="forbid")
    
    token_id: str = Field(description="Unique token identifier")
    token_hash: str = Field(description="SHA256 hash of the token")
    name: str = Field(description="Human-readable token name")
    role: Role = Field(description="Token role")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = Field(None, description="Token expiration")
    last_used: Optional[datetime] = Field(None, description="Last usage timestamp")
    is_active: bool = Field(default=True, description="Whether token is active")


class TokenStore:
    """In-memory token store.
    
    In production, this should be replaced with a database-backed store.
    For the MVP, we use environment variables for simple token management.
    """
    
    def __init__(self):
        """Initialize token store."""
        self._tokens: dict[str, APIToken] = {}
        self._initialize_from_env()
    
    def _initialize_from_env(self) -> None:
        """Initialize tokens from environment variables.
        
        Expected format:
        API_TOKENS='token1:name1:role1,token2:name2:role2'
        
        Example:
        API_TOKENS='abc123:admin-token:admin,def456:readonly:config.read'
        """
        import os
        
        tokens_str = os.environ.get("API_TOKENS", "")
        if not tokens_str:
            logger.warning("No API_TOKENS configured - using MQTT password as admin token")
            
            # Try to get MQTT password from environment
            mqtt_password = os.environ.get("MQTT_PASS") or os.environ.get("MQTT_PASSWORD")
            
            # If not found, try to extract from MQTT_URL
            if not mqtt_password:
                mqtt_url = os.environ.get("MQTT_URL", "")
                if "@" in mqtt_url and ":" in mqtt_url:
                    try:
                        # Extract password from mqtt://user:pass@host:port
                        auth_part = mqtt_url.split("@")[0].split("//")[1]
                        if ":" in auth_part:
                            mqtt_password = auth_part.split(":")[1]
                    except Exception as e:
                        logger.warning(f"Failed to extract MQTT password from URL: {e}")
            
            # Use MQTT password as token if found
            if mqtt_password:
                logger.warning(
                    f"=================================================================\n"
                    f"Created admin API token from MQTT password.\n"
                    f"Use X-API-Token header with value: {mqtt_password}\n"
                    f"================================================================="
                )
                self.create_token(mqtt_password, "mqtt-admin", Role.ADMIN)
            else:
                # Fallback to random token
                default_token = "dev-admin-token-" + secrets.token_urlsafe(16)
                logger.warning(
                    f"Development mode: No MQTT password found.\n"
                    f"Creating random admin token: {default_token}"
                )
                self.create_token(default_token, "dev-admin", Role.ADMIN)
            
            return
        
        for token_spec in tokens_str.split(","):
            parts = token_spec.strip().split(":")
            if len(parts) != 3:
                logger.error(f"Invalid token spec: {token_spec}")
                continue
            
            token, name, role_str = parts
            try:
                role = Role(role_str)
                self.create_token(token, name, role)
                logger.info(f"Loaded API token: {name} (role={role.value})")
            except ValueError:
                logger.error(f"Invalid role '{role_str}' for token {name}")
    
    def create_token(
        self,
        token: str,
        name: str,
        role: Role,
        expires_in_days: Optional[int] = None,
    ) -> APIToken:
        """Create a new API token.
        
        Args:
            token: The actual token string (plain text)
            name: Human-readable name
            role: Token role
            expires_in_days: Optional expiration in days
        
        Returns:
            Created APIToken
        """
        token_id = secrets.token_urlsafe(16)
        token_hash = self._hash_token(token)
        
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)
        
        api_token = APIToken(
            token_id=token_id,
            token_hash=token_hash,
            name=name,
            role=role,
            expires_at=expires_at,
        )
        
        self._tokens[token_hash] = api_token
        return api_token
    
    def validate_token(self, token: str) -> Optional[APIToken]:
        """Validate a token and return its details.
        
        Args:
            token: The token to validate
        
        Returns:
            APIToken if valid, None otherwise
        """
        token_hash = self._hash_token(token)
        api_token = self._tokens.get(token_hash)
        
        if not api_token:
            logger.warning(f"Invalid token attempt: {token[:8]}...")
            return None
        
        if not api_token.is_active:
            logger.warning(f"Inactive token used: {api_token.name}")
            return None
        
        if api_token.expires_at and datetime.now(UTC) > api_token.expires_at:
            logger.warning(f"Expired token used: {api_token.name}")
            return None
        
        # Update last used
        api_token.last_used = datetime.now(UTC)
        
        return api_token
    
    def revoke_token(self, token_id: str) -> bool:
        """Revoke a token by ID.
        
        Args:
            token_id: Token ID to revoke
        
        Returns:
            True if revoked, False if not found
        """
        for api_token in self._tokens.values():
            if api_token.token_id == token_id:
                api_token.is_active = False
                logger.info(f"Revoked token: {api_token.name}")
                return True
        
        return False
    
    def list_tokens(self) -> list[APIToken]:
        """List all tokens (for admin use).
        
        Returns:
            List of all APITokens
        """
        return list(self._tokens.values())
    
    @staticmethod
    def _hash_token(token: str) -> str:
        """Hash a token for storage.
        
        Args:
            token: Plain text token
        
        Returns:
            SHA256 hash of the token
        """
        return hashlib.sha256(token.encode()).hexdigest()


def has_permission(token: Optional[APIToken], permission: Permission) -> bool:
    """Check if a token has a specific permission.
    
    Args:
        token: API token to check
        permission: Required permission
    
    Returns:
        True if token has permission, False otherwise
    """
    if not token:
        return False
    
    role_permissions = ROLE_PERMISSIONS.get(token.role, [])
    return permission in role_permissions


def require_permission(token: Optional[APIToken], permission: Permission) -> None:
    """Require a token to have a specific permission.
    
    Args:
        token: API token to check
        permission: Required permission
    
    Raises:
        PermissionError: If token doesn't have permission
    """
    if not has_permission(token, permission):
        role_name = token.role.value if token else "none"
        raise PermissionError(
            f"Insufficient permissions. Role '{role_name}' lacks {permission.value}"
        )


# Global token store instance
_token_store: Optional[TokenStore] = None


def get_token_store() -> TokenStore:
    """Get the global token store instance.
    
    Returns:
        TokenStore instance
    """
    global _token_store
    if _token_store is None:
        _token_store = TokenStore()
    return _token_store


def initialize_token_store() -> TokenStore:
    """Initialize the global token store.
    
    Returns:
        Initialized TokenStore
    """
    global _token_store
    _token_store = TokenStore()
    return _token_store
