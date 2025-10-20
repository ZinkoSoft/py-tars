"""Configuration for config-manager service."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


def _load_signature_private_key() -> Optional[str]:
    """Load signature private key from file or environment.
    
    Tries in order:
    1. /run/secrets/signature_private_key.pem (Docker secret mount)
    2. /etc/tars/secrets/signature_private_key.pem (volume mount)
    3. CONFIG_SIGNATURE_PRIVATE_KEY_B64 (base64-encoded env var)
    4. CONFIG_SIGNATURE_PRIVATE_KEY (plain PEM env var)
    """
    # Try Docker secrets mount
    secret_path = Path("/run/secrets/signature_private_key.pem")
    if secret_path.exists():
        return secret_path.read_text()
    
    # Try volume mount
    volume_path = Path("/etc/tars/secrets/signature_private_key.pem")
    if volume_path.exists():
        return volume_path.read_text()
    
    # Try base64-encoded env var
    b64_key = os.getenv("CONFIG_SIGNATURE_PRIVATE_KEY_B64")
    if b64_key:
        try:
            return base64.b64decode(b64_key).decode("utf-8")
        except Exception:
            pass
    
    # Fall back to plain PEM env var
    return os.getenv("CONFIG_SIGNATURE_PRIVATE_KEY")


def _load_signature_public_key() -> Optional[str]:
    """Load signature public key from file or environment.
    
    Tries in order:
    1. /run/secrets/signature_public_key.pem (Docker secret mount)
    2. /etc/tars/secrets/signature_public_key.pem (volume mount)
    3. CONFIG_SIGNATURE_PUBLIC_KEY_B64 (base64-encoded env var)
    4. CONFIG_SIGNATURE_PUBLIC_KEY (plain PEM env var)
    """
    # Try Docker secrets mount
    secret_path = Path("/run/secrets/signature_public_key.pem")
    if secret_path.exists():
        return secret_path.read_text()
    
    # Try volume mount
    volume_path = Path("/etc/tars/secrets/signature_public_key.pem")
    if volume_path.exists():
        return volume_path.read_text()
    
    # Try base64-encoded env var
    b64_key = os.getenv("CONFIG_SIGNATURE_PUBLIC_KEY_B64")
    if b64_key:
        try:
            return base64.b64decode(b64_key).decode("utf-8")
        except Exception:
            pass
    
    # Fall back to plain PEM env var
    return os.getenv("CONFIG_SIGNATURE_PUBLIC_KEY")


class ConfigManagerConfig(BaseModel):
    """Configuration for config-manager service."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Database
    db_path: Path = Field(
        default_factory=lambda: Path(
            os.getenv("CONFIG_DB_PATH", "/data/config/config.db")
        ),
        description="Path to SQLite configuration database",
    )
    lkg_cache_path: Path = Field(
        default_factory=lambda: Path(
            os.getenv("CONFIG_LKG_CACHE_PATH", "/data/config/config.lkg.json")
        ),
        description="Path to last-known-good configuration cache",
    )

    # Encryption keys
    master_key_base64: Optional[str] = Field(
        default_factory=lambda: os.getenv("CONFIG_MASTER_KEY_BASE64"),
        description="Base64-encoded AES-256 master key for secret encryption",
    )
    master_key_id: str = Field(
        default_factory=lambda: os.getenv("CONFIG_MASTER_KEY_ID", "default"),
        description="Master key identifier for key rotation",
    )
    hmac_key_base64: Optional[str] = Field(
        default_factory=lambda: os.getenv("LKG_HMAC_KEY_BASE64"),
        description="Base64-encoded HMAC key for cache signing",
    )

    # Ed25519 signing keys
    signature_private_key: Optional[str] = Field(
        default_factory=_load_signature_private_key,
        description="PEM-encoded Ed25519 private key for MQTT message signing",
    )
    signature_public_key: Optional[str] = Field(
        default_factory=_load_signature_public_key,
        description="PEM-encoded Ed25519 public key for signature verification",
    )

    # MQTT
    mqtt_url: str = Field(
        default_factory=lambda: os.getenv(
            "MQTT_URL", "mqtt://tars:tars@localhost:1883"
        ),
        description="MQTT broker URL",
    )
    mqtt_config_update_topic: str = Field(
        default="config/update", description="Topic for configuration updates"
    )
    mqtt_health_topic: str = Field(
        default="system/health/config-manager",
        description="Topic for health status (retained)",
    )

    # REST API
    api_host: str = Field(
        default_factory=lambda: os.getenv("CONFIG_MANAGER_HOST", "0.0.0.0"),
        description="API server host",
    )
    api_port: int = Field(
        default_factory=lambda: int(os.getenv("CONFIG_MANAGER_PORT", "8081")),
        description="API server port",
    )
    api_reload: bool = Field(
        default_factory=lambda: os.getenv("CONFIG_MANAGER_API_RELOAD", "0") == "1",
        description="Enable API auto-reload (dev only)",
    )

    # Security
    allow_auto_rebuild: bool = Field(
        default_factory=lambda: os.getenv("ALLOW_AUTO_REBUILD", "0") == "1",
        description="Allow automatic database rebuild from LKG cache",
    )
    api_token_enabled: bool = Field(
        default_factory=lambda: os.getenv("CONFIG_API_TOKEN_ENABLED", "0") == "1",
        description="Enable API token authentication",
    )
    api_token: Optional[str] = Field(
        default_factory=lambda: os.getenv("CONFIG_API_TOKEN"),
        description="API bearer token for authentication",
    )

    # Operational
    log_level: str = Field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"),
        description="Logging level",
    )
    enable_access_log: bool = Field(
        default_factory=lambda: os.getenv("ENABLE_ACCESS_LOG", "1") == "1",
        description="Enable configuration access logging to database",
    )


def load_config() -> ConfigManagerConfig:
    """Load configuration from environment variables."""
    return ConfigManagerConfig()
