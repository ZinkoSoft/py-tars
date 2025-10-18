"""MQTT message models for configuration management."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ConfigUpdatePayload(BaseModel):
    """MQTT payload for system/config/<service> topic."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(..., description="Message format version")
    service: str = Field(..., description="Target service")
    config: dict[str, Any] = Field(..., description="Complete service configuration")
    checksum: str = Field(..., description="SHA256 of config JSON")
    config_epoch: str = Field(..., description="Database epoch")
    issued_at: datetime = Field(default_factory=datetime.utcnow)
    signature: str = Field(..., description="Ed25519 signature (base64)")


class ConfigHealthPayload(BaseModel):
    """Health status for config-manager service."""

    model_config = ConfigDict(extra="forbid")

    ok: bool = Field(..., description="Overall health status")
    database_status: Literal["healthy", "locked", "corrupted", "schema-mismatch"] = Field(...)
    operational_mode: Literal["normal", "read-only-fallback", "rebuilding"] = Field(...)
    config_epoch: str = Field(..., description="Current database epoch")
    schema_version: int = Field(..., description="Current schema version")
    lkg_cache_valid: bool = Field(..., description="LKG cache HMAC valid")
    litestream_status: Literal["healthy", "error", "disabled"] = Field(...)
    last_backup: datetime | None = Field(None)
    event: str | None = Field(None, description="Event description")
    err: str | None = Field(None, description="Error message if unhealthy")


# REST API Models


class ConfigReadRequest(BaseModel):
    """Request to read service configuration."""

    model_config = ConfigDict(extra="forbid")

    service: str = Field(..., description="Service name to retrieve")


class ConfigReadResponse(BaseModel):
    """Response with service configuration."""

    model_config = ConfigDict(extra="forbid")

    service: str
    config: dict[str, Any]
    metadata: dict[str, Any] = Field(..., description="version, updated_at, etc.")


class ConfigUpdateRequest(BaseModel):
    """Request to update service configuration."""

    model_config = ConfigDict(extra="forbid")

    service: str
    config: dict[str, Any]
    version: int = Field(..., description="For optimistic locking")


class ConfigUpdateResponse(BaseModel):
    """Response after configuration update."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    new_version: int | None = None
    error: str | None = None


class ConfigSearchRequest(BaseModel):
    """Search configuration items."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(default="", description="Search text")
    service_filter: str | None = Field(None)
    complexity_filter: str | None = Field(None)
    type_filter: str | None = Field(None)


class ConfigSearchResult(BaseModel):
    """Single search result item."""

    model_config = ConfigDict(extra="forbid")

    service: str
    key: str
    value: Any
    description: str
    complexity: str
    type: str


class ConfigSearchResponse(BaseModel):
    """Search results."""

    model_config = ConfigDict(extra="forbid")

    results: list[ConfigSearchResult]
    total: int
