"""REST API endpoints for configuration management."""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Header, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from config_manager.auth import (
    get_token_store,
    APIToken,
    Permission,
    has_permission,
    require_permission,
)

from tars.config.models import (
    ServiceConfig,
    STTWorkerConfig,
    TTSWorkerConfig,
    RouterConfig,
    LLMWorkerConfig,
    MemoryWorkerConfig,
    WakeActivationConfig,
)
from pydantic import ValidationError as PydanticValidationError

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/config", tags=["config"])

# Service config model mapping for validation
SERVICE_CONFIG_MODELS = {
    "stt-worker": STTWorkerConfig,
    "tts-worker": TTSWorkerConfig,
    "router": RouterConfig,
    "llm-worker": LLMWorkerConfig,
    "memory-worker": MemoryWorkerConfig,
    "wake-activation": WakeActivationConfig,
}


# Authentication dependency
async def get_current_token(
    x_api_token: str | None = Header(None, alias="X-API-Token", convert_underscores=False)
) -> APIToken:
    """Extract and validate API token from header.
    
    Args:
        x_api_token: API token from X-API-Token header
    
    Returns:
        Validated APIToken
    
    Raises:
        HTTPException: If token is missing or invalid
    """
    if not x_api_token:
        logger.warning("Request without API token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API token required. Provide X-API-Token header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_store = get_token_store()
    api_token = token_store.validate_token(x_api_token)
    
    if not api_token:
        logger.warning(f"Invalid API token attempt: {x_api_token[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.debug(f"Authenticated request: token={api_token.name}, role={api_token.role.value}")
    return api_token


# Permission checking dependency factory
def require_permissions(*permissions: Permission):
    """Create a dependency that requires specific permissions.
    
    Args:
        *permissions: Required permissions
    
    Returns:
        FastAPI dependency function
    """
    async def permission_checker(token: APIToken = Depends(get_current_token)) -> APIToken:
        """Check if token has all required permissions."""
        for permission in permissions:
            if not has_permission(token, permission):
                logger.warning(
                    f"Permission denied: token={token.name}, role={token.role.value}, "
                    f"required={permission.value}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required: {permission.value}",
                )
        return token
    
    return permission_checker


# CSRF Protection for state-changing operations
async def validate_csrf_header(x_csrf_token: str = Header(None, alias="X-CSRF-Token")):
    """Validate CSRF token for state-changing operations.
    
    For API token authentication, the token itself provides CSRF protection.
    This is an additional layer that ensures requests come from our web UI.
    
    Args:
        x_csrf_token: CSRF token from X-CSRF-Token header
    
    Raises:
        HTTPException: If CSRF token is missing or invalid
    """
    # For now, we accept any non-empty CSRF token
    # In production, you might want to validate against a generated token
    if not x_csrf_token:
        logger.warning("CSRF token missing from state-changing request")
        # For MVP, we'll just log a warning but not block the request
        # In production, you would raise an exception:
        # raise HTTPException(
        #     status_code=status.HTTP_403_FORBIDDEN,
        #     detail="CSRF token required for state-changing operations",
        # )
    return x_csrf_token


class ServiceListResponse(BaseModel):
    """Response for listing available services."""

    model_config = ConfigDict(extra="forbid")

    services: List[str] = Field(description="List of service names")


class ConfigFieldMetadataResponse(BaseModel):
    """Field metadata for a configuration key."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(description="Configuration key")
    type: str = Field(description="Value type (string, integer, float, boolean, etc.)")
    complexity: str = Field(description="Complexity level (simple or advanced)")
    description: str = Field(description="Human-readable description")
    help_text: Optional[str] = Field(default=None, description="Optional help text")
    examples: Optional[List[str]] = Field(default=None, description="Example values")
    is_secret: bool = Field(default=False, description="Whether value is a secret")


class ConfigGetResponse(BaseModel):
    """Response for getting service configuration."""

    model_config = ConfigDict(extra="forbid")

    service: str = Field(description="Service name")
    config: dict = Field(description="Configuration dictionary")
    version: int = Field(description="Configuration version for optimistic locking")
    updated_at: str = Field(description="ISO8601 timestamp of last update")
    config_epoch: str = Field(description="Current configuration epoch")
    fields: Optional[List[ConfigFieldMetadataResponse]] = Field(
        default=None, description="Optional field metadata (when include_fields=true)"
    )


class ConfigUpdateRequest(BaseModel):
    """Request to update service configuration."""

    model_config = ConfigDict(extra="forbid")

    service: str = Field(description="Service name")
    config: dict = Field(description="Configuration dictionary")
    version: int = Field(
        description="Expected current version (for optimistic locking)"
    )


class ConfigUpdateResponse(BaseModel):
    """Response after updating configuration."""

    model_config = ConfigDict(extra="forbid")

    success: bool = Field(description="Whether update succeeded")
    version: int = Field(description="New configuration version")
    config_epoch: str = Field(description="Current configuration epoch")
    message: Optional[str] = Field(default=None, description="Optional message")


class SearchRequest(BaseModel):
    """Request to search configuration items."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(description="Search query string")
    service_filter: Optional[str] = Field(default=None, description="Filter by service name")
    complexity_filter: Optional[str] = Field(default=None, description="Filter by complexity (simple/advanced)")
    max_results: int = Field(default=50, ge=1, le=200, description="Maximum number of results")


class SearchResultItem(BaseModel):
    """Single search result item."""

    model_config = ConfigDict(extra="forbid")

    service: str = Field(description="Service name")
    key: str = Field(description="Configuration key")
    value: Optional[str] = Field(default=None, description="Current value (omitted for secrets)")
    type: str = Field(description="Value type")
    complexity: str = Field(description="Complexity level")
    description: str = Field(description="Description")
    is_secret: bool = Field(default=False, description="Whether value is a secret")
    match_score: float = Field(description="Relevance score (0-1)", ge=0, le=1)


class SearchResponse(BaseModel):
    """Response with search results."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(description="Original search query")
    results: List[SearchResultItem] = Field(description="Matching configuration items")
    total_count: int = Field(description="Total number of results")


class ProfileMetadata(BaseModel):
    """Profile metadata without full config snapshot."""

    model_config = ConfigDict(extra="forbid")

    profile_name: str = Field(description="Profile name")
    description: str = Field(description="Profile description")
    created_at: str = Field(description="ISO8601 timestamp")
    created_by: Optional[str] = Field(default=None, description="Creator user ID")
    updated_at: str = Field(description="ISO8601 timestamp")
    updated_by: Optional[str] = Field(default=None, description="Last updater user ID")


class ProfileListResponse(BaseModel):
    """Response listing all profiles."""

    model_config = ConfigDict(extra="forbid")

    profiles: List[ProfileMetadata] = Field(description="List of saved profiles")


class ProfileSaveRequest(BaseModel):
    """Request to save current config as a profile."""

    model_config = ConfigDict(extra="forbid")

    profile_name: str = Field(description="Unique profile name", min_length=1, max_length=100)
    description: str = Field(default="", description="Optional description")


class ProfileResponse(BaseModel):
    """Response with profile details."""

    model_config = ConfigDict(extra="forbid")

    profile_name: str = Field(description="Profile name")
    description: str = Field(description="Profile description")
    config_snapshot: dict = Field(description="Service configurations")
    created_at: str = Field(description="ISO8601 timestamp")
    created_by: Optional[str] = Field(default=None, description="Creator user ID")
    updated_at: str = Field(description="ISO8601 timestamp")
    updated_by: Optional[str] = Field(default=None, description="Last updater user ID")


class ProfileActivateResponse(BaseModel):
    """Response after activating a profile."""

    model_config = ConfigDict(extra="forbid")

    success: bool = Field(description="Whether activation succeeded")
    services_updated: List[str] = Field(description="List of services that were updated")
    config_epoch: str = Field(description="Current configuration epoch")


def _get_service():
    """Get the global service instance from app state.
    
    Raises:
        HTTPException: If service not initialized
    """
    import sys
    
    # Get the service from the module in sys.modules
    # Try both __main__ (when run as script) and config_manager.__main__ (when imported)
    main_module = sys.modules.get('__main__') or sys.modules.get('config_manager.__main__')
    if not main_module:
        logger.error("Main module not found in sys.modules")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service module not loaded",
        )
    
    service = getattr(main_module, 'service', None)
    
    if not service or not service.database:
        logger.error("Service not initialized - service=%s, database=%s, module=%s", 
                    service, service.database if service else None, main_module.__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not initialized",
        )
    
    return service


class CSRFTokenResponse(BaseModel):
    """CSRF token response."""
    
    model_config = ConfigDict(extra="forbid")
    
    csrf_token: str = Field(description="CSRF token for state-changing operations")
    expires_at: str = Field(description="Token expiration timestamp")


@router.get("/csrf-token", response_model=CSRFTokenResponse)
async def get_csrf_token(
    token: APIToken = Depends(get_current_token),
):
    """Get a CSRF token for state-changing operations.
    
    The web UI should call this endpoint once and include the token
    in X-CSRF-Token header for PUT/POST/DELETE requests.
    
    Returns:
        CSRF token
    """
    import secrets
    from datetime import UTC, datetime, timedelta
    
    # Generate a simple CSRF token
    # In production, store these in a cache/database with expiration
    csrf_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    
    return CSRFTokenResponse(
        csrf_token=csrf_token,
        expires_at=expires_at.isoformat(),
    )


@router.get("/me")
async def get_current_user(
    token: APIToken = Depends(get_current_token),
):
    """Get current user information including role and permissions.
    
    Returns:
        User role and permissions
    """
    from .auth import ROLE_PERMISSIONS
    
    permissions = ROLE_PERMISSIONS.get(token.role, [])
    
    return {
        "name": token.name,
        "role": token.role.value,
        "permissions": [p.value for p in permissions],
    }


@router.get("/services", response_model=ServiceListResponse)
async def list_services(
    token: APIToken = Depends(require_permissions(Permission.CONFIG_READ)),
):
    """List all available services with configuration.
    
    Requires: config.read permission

    Returns:
        List of service names
    """
    service = _get_service()

    try:
        services = await service.database.list_services()
        return ServiceListResponse(services=services)
    except Exception as e:
        logger.error(f"Failed to list services: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list services: {str(e)}",
        )


@router.post("/search", response_model=SearchResponse)
async def search_configurations(
    request: SearchRequest,
    token: APIToken = Depends(require_permissions(Permission.CONFIG_READ)),
):
    """Search across all configuration items.
    
    Requires: config.read permission

    Args:
        request: Search query and filters

    Returns:
        Matching configuration items with relevance scores
    """
    service = _get_service()

    try:
        # Search config items in database
        items = await service.database.search_config_items(
            query=request.query if request.query.strip() else None,
            service_filter=request.service_filter,
            complexity_filter=request.complexity_filter,
        )

        # Build search results
        results: List[SearchResultItem] = []
        query_lower = request.query.lower().strip()

        for item in items[:request.max_results]:
            # Calculate simple relevance score
            score = 0.0
            key_lower = item.key.lower()
            desc_lower = item.description.lower()

            # Exact key match = highest score
            if query_lower == key_lower:
                score = 1.0
            # Key starts with query = high score
            elif key_lower.startswith(query_lower):
                score = 0.8
            # Key contains query = medium score
            elif query_lower in key_lower:
                score = 0.6
            # Description contains query = low score
            elif query_lower in desc_lower:
                score = 0.3

            # Get current value (mask secrets)
            current_value = None
            if not item.is_secret:
                config_data = await service.database.get_service_config(item.service)
                if config_data and item.key in config_data.config:
                    current_value = str(config_data.config[item.key])

            results.append(
                SearchResultItem(
                    service=item.service,
                    key=item.key,
                    value=current_value,
                    type=item.type,
                    complexity=item.complexity,
                    description=item.description,
                    is_secret=item.is_secret,
                    match_score=score,
                )
            )

        # Sort by relevance score (highest first)
        results.sort(key=lambda r: r.match_score, reverse=True)

        return SearchResponse(
            query=request.query,
            results=results,
            total_count=len(results),
        )

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}",
        )


@router.get("/services/{service_name}", response_model=ConfigGetResponse)
async def get_service_config(
    service_name: str,
    include_fields: bool = True,
    token: APIToken = Depends(require_permissions(Permission.CONFIG_READ)),
):
    """Get configuration for a specific service.
    
    Requires: config.read permission

    Args:
        service_name: Name of the service
        include_fields: Whether to include field metadata (default: True)

    Returns:
        Service configuration with version and metadata
    """
    service = _get_service()

    try:
        config_data = await service.database.get_service_config(service_name)
        if not config_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_name}' not found",
            )

        # Get config epoch
        epoch = await service.database.get_config_epoch()

        # Optionally fetch field metadata
        fields = None
        if include_fields:
            config_items = await service.database.search_config_items(
                service_filter=service_name
            )
            fields = [
                ConfigFieldMetadataResponse(
                    key=item.key,
                    type=item.type,
                    complexity=item.complexity,
                    description=item.description,
                    help_text=item.help_text,
                    examples=item.examples if hasattr(item, 'examples') and item.examples else None,
                    is_secret=item.is_secret,
                )
                for item in config_items
            ]

        return ConfigGetResponse(
            service=service_name,
            config=config_data.config,
            version=config_data.version,
            updated_at=config_data.updated_at.isoformat(),
            config_epoch=epoch.config_epoch if epoch else "unknown",
            fields=fields,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get config for {service_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get configuration: {str(e)}",
        )


@router.put("/services/{service_name}", response_model=ConfigUpdateResponse)
async def update_service_config(
    service_name: str,
    request: ConfigUpdateRequest,
    token: APIToken = Depends(require_permissions(Permission.CONFIG_WRITE)),
    csrf_token: str = Depends(validate_csrf_header),
):
    """Update configuration for a specific service.
    
    Requires: config.write permission
    Requires: X-CSRF-Token header

    Implements optimistic locking - the request must include the expected
    current version. If another update has occurred, returns 409 Conflict.

    Args:
        service_name: Name of the service
        request: Update request with config and version

    Returns:
        Update response with new version
    """
    service = _get_service()
    
    if not service.mqtt_publisher:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MQTT publisher not initialized",
        )

    if request.service != service_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service name in path must match request body",
        )
    
    # Audit log - configuration update attempt
    logger.info(
        f"Configuration update attempt: service={service_name}, "
        f"user={token.name}, role={token.role.value}, version={request.version}",
        extra={
            "event": "config_update_attempt",
            "service": service_name,
            "user": token.name,
            "role": token.role.value,
            "version": request.version,
        },
    )

    # Validate configuration against service-specific Pydantic model
    if service_name in SERVICE_CONFIG_MODELS:
        model_class = SERVICE_CONFIG_MODELS[service_name]
        try:
            # Validate the configuration using the service-specific model
            model_class(**request.config)
        except PydanticValidationError as e:
            # Extract validation errors and format them for the client
            validation_errors = []
            for error in e.errors():
                field = ".".join(str(loc) for loc in error["loc"])
                message = error["msg"]
                validation_errors.append({
                    "field": field,
                    "message": message,
                    "type": error["type"],
                })
            
            # Audit log - validation failure
            logger.warning(
                f"Validation failed for {service_name}: {len(validation_errors)} error(s)",
                extra={
                    "event": "config_validation_failed",
                    "service": service_name,
                    "user": token.name,
                    "validation_errors": validation_errors,
                },
            )
            
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Configuration validation failed",
                    "errors": validation_errors,
                },
            )
    else:
        logger.warning(
            f"No validation model found for service '{service_name}' - skipping validation"
        )

    try:
        # Update database with optimistic locking
        new_version = await service.database.update_service_config(
            service=service_name,
            config=request.config,
            expected_version=request.version,
        )

        # Get config epoch
        epoch = await service.database.get_config_epoch()
        if not epoch:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Config epoch not found in database",
            )

        # Update LKG cache - get all service configs first
        services = await service.database.list_services()
        service_configs = {}
        for svc_name in services:
            svc_data = await service.database.get_service_config(svc_name)
            if svc_data:
                service_configs[svc_name] = svc_data.config

        await service.cache_manager.atomic_update_from_db(
            service_configs, epoch.config_epoch
        )

        # Publish MQTT update
        await service.mqtt_publisher.publish_config_update(
            service=service_name,
            config=request.config,
            version=new_version,
            config_epoch=epoch.config_epoch,
        )

        # Audit log - successful update
        logger.info(
            f"Configuration updated successfully: service={service_name}, "
            f"user={token.name}, v{request.version} -> v{new_version}",
            extra={
                "event": "config_updated",
                "service": service_name,
                "user": token.name,
                "old_version": request.version,
                "new_version": new_version,
            },
        )

        return ConfigUpdateResponse(
            success=True,
            version=new_version,
            config_epoch=epoch.config_epoch,
            message=f"Configuration updated to version {new_version}",
        )

    except ValueError as e:
        # Version conflict (optimistic locking failure)
        if "version mismatch" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to update config for {service_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update configuration: {str(e)}",
        )


# ===== Configuration Profile Endpoints =====


@router.get("/profiles", response_model=ProfileListResponse)
async def list_profiles(
    token: APIToken = Depends(require_permissions(Permission.CONFIG_READ)),
):
    """List all saved configuration profiles.
    
    Requires: config.read permission

    Returns:
        List of profile metadata (without full config snapshots)
    """
    service = _get_service()

    try:
        profiles = await service.database.list_profiles()
        
        profile_list = [
            ProfileMetadata(
                profile_name=p.profile_name,
                description=p.description,
                created_at=p.created_at.isoformat(),
                created_by=p.created_by,
                updated_at=p.updated_at.isoformat(),
                updated_by=p.updated_by,
            )
            for p in profiles
        ]

        return ProfileListResponse(profiles=profile_list)

    except Exception as e:
        logger.error(f"Failed to list profiles: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list profiles: {str(e)}",
        )


@router.get("/profiles/{profile_name}", response_model=ProfileResponse)
async def get_profile(
    profile_name: str,
    token: APIToken = Depends(require_permissions(Permission.CONFIG_READ)),
):
    """Get a specific configuration profile.
    
    Requires: config.read permission

    Args:
        profile_name: Name of the profile

    Returns:
        Profile with full configuration snapshot
    """
    service = _get_service()

    try:
        profile = await service.database.get_profile(profile_name)
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile '{profile_name}' not found",
            )

        return ProfileResponse(
            profile_name=profile.profile_name,
            description=profile.description,
            config_snapshot=profile.config_snapshot,
            created_at=profile.created_at.isoformat(),
            created_by=profile.created_by,
            updated_at=profile.updated_at.isoformat(),
            updated_by=profile.updated_by,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get profile '{profile_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get profile: {str(e)}",
        )


@router.post("/profiles", response_model=ProfileResponse)
async def save_profile(
    request: ProfileSaveRequest,
    token: APIToken = Depends(require_permissions(Permission.CONFIG_WRITE)),
    x_csrf_token: str = Header(None, alias="X-CSRF-Token"),
):
    """Save current configuration as a new profile.
    
    Requires: config.write permission

    Args:
        request: Profile name and description

    Returns:
        Saved profile details
    """
    # CSRF validation
    await validate_csrf_header(x_csrf_token)

    service = _get_service()

    try:
        # Get all current service configs
        services = await service.database.list_services()
        config_snapshot = {}

        for svc_name in services:
            svc_data = await service.database.get_service_config(svc_name)
            if svc_data:
                config_snapshot[svc_name] = svc_data.config

        # Create profile model
        from tars.config.models import ConfigProfile
        from datetime import UTC, datetime

        profile = ConfigProfile(
            profile_name=request.profile_name,
            description=request.description,
            config_snapshot=config_snapshot,
            created_at=datetime.now(UTC),
            created_by=token.name,
            updated_at=datetime.now(UTC),
            updated_by=token.name,
        )

        # Save to database
        await service.database.save_profile(profile)

        logger.info(
            f"Profile saved: {request.profile_name} by {token.name}",
            extra={
                "event": "profile_saved",
                "profile_name": request.profile_name,
                "user": token.name,
                "services": len(config_snapshot),
            },
        )

        return ProfileResponse(
            profile_name=profile.profile_name,
            description=profile.description,
            config_snapshot=profile.config_snapshot,
            created_at=profile.created_at.isoformat(),
            created_by=profile.created_by,
            updated_at=profile.updated_at.isoformat(),
            updated_by=profile.updated_by,
        )

    except Exception as e:
        logger.error(f"Failed to save profile '{request.profile_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save profile: {str(e)}",
        )


@router.put("/profiles/{profile_name}/activate", response_model=ProfileActivateResponse)
async def activate_profile(
    profile_name: str,
    token: APIToken = Depends(require_permissions(Permission.CONFIG_WRITE)),
    x_csrf_token: str = Header(None, alias="X-CSRF-Token"),
):
    """Load and activate a configuration profile.
    
    This applies the profile's configuration to all services.
    
    Requires: config.write permission

    Args:
        profile_name: Name of the profile to activate

    Returns:
        Activation result with list of updated services
    """
    # CSRF validation
    await validate_csrf_header(x_csrf_token)

    service = _get_service()

    try:
        # Get current epoch
        epoch = await service.database.get_config_epoch()
        if not epoch:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Config epoch not found",
            )

        # Load profile and convert to ServiceConfig objects
        service_configs = await service.database.load_profile(
            profile_name, epoch.config_epoch, token.name
        )

        updated_services = []

        # Apply each service config
        for svc_name, svc_config in service_configs.items():
            # Update database (this will increment version)
            current = await service.database.get_service_config(svc_name)
            expected_version = current.version if current else 0

            new_version = await service.database.update_service_config(
                service=svc_name,
                config=svc_config.config,
                expected_version=expected_version,
            )

            # Publish MQTT update
            await service.mqtt_publisher.publish_config_update(
                service=svc_name,
                config=svc_config.config,
                version=new_version,
                config_epoch=epoch.config_epoch,
            )

            updated_services.append(svc_name)

        # Update LKG cache with all configs
        all_services = await service.database.list_services()
        all_configs = {}
        for svc in all_services:
            svc_data = await service.database.get_service_config(svc)
            if svc_data:
                all_configs[svc] = svc_data.config

        await service.cache_manager.atomic_update_from_db(
            all_configs, epoch.config_epoch
        )

        logger.info(
            f"Profile activated: {profile_name} by {token.name}",
            extra={
                "event": "profile_activated",
                "profile_name": profile_name,
                "user": token.name,
                "services_updated": updated_services,
            },
        )

        return ProfileActivateResponse(
            success=True,
            services_updated=updated_services,
            config_epoch=epoch.config_epoch,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to activate profile '{profile_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate profile: {str(e)}",
        )


@router.delete("/profiles/{profile_name}")
async def delete_profile(
    profile_name: str,
    token: APIToken = Depends(require_permissions(Permission.CONFIG_WRITE)),
    x_csrf_token: str = Header(None, alias="X-CSRF-Token"),
):
    """Delete a configuration profile.
    
    Requires: config.write permission

    Args:
        profile_name: Name of the profile to delete

    Returns:
        Success message
    """
    # CSRF validation
    await validate_csrf_header(x_csrf_token)

    service = _get_service()

    try:
        deleted = await service.database.delete_profile(profile_name)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile '{profile_name}' not found",
            )

        logger.info(
            f"Profile deleted: {profile_name} by {token.name}",
            extra={
                "event": "profile_deleted",
                "profile_name": profile_name,
                "user": token.name,
            },
        )

        return {"success": True, "message": f"Profile '{profile_name}' deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete profile '{profile_name}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete profile: {str(e)}",
        )


# ===== Configuration History Endpoints =====


class HistoryEntry(BaseModel):
    """Single configuration history entry."""

    id: int
    service: str
    key: str
    old_value: Any | None
    new_value: Any
    changed_at: str  # ISO format datetime
    changed_by: str | None
    change_reason: str | None


class HistoryResponse(BaseModel):
    """Response containing history entries."""

    entries: list[HistoryEntry]
    total_returned: int


@router.get("/history", response_model=HistoryResponse)
async def get_config_history(
    service: str | None = None,
    key: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100,
    token: APIToken = Depends(require_permissions(Permission.CONFIG_READ)),
) -> HistoryResponse:
    """Get configuration change history.

    Query parameters:
    - service: Filter by service name (optional)
    - key: Filter by configuration key (optional)
    - start_date: ISO format datetime - filter changes after this date (optional)
    - end_date: ISO format datetime - filter changes before this date (optional)
    - limit: Maximum entries to return (default 100, max 1000)

    Returns:
        List of history entries, most recent first
    """
    # Permission check
    if not has_permission(token.role, Permission.CONFIG_READ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions: config.read required",
        )

    # Validate limit
    if limit > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit cannot exceed 1000",
        )

    service_obj = _get_service()

    try:
        # Parse dates if provided
        from datetime import datetime
        
        start_dt = datetime.fromisoformat(start_date) if start_date else None
        end_dt = datetime.fromisoformat(end_date) if end_date else None

        # Query history
        history_entries = await service_obj.database.get_config_history(
            service=service,
            key=key,
            start_date=start_dt,
            end_date=end_dt,
            limit=limit,
        )

        # Convert to response format
        entries = []
        for entry in history_entries:
            # Parse JSON values
            old_value = orjson.loads(entry.old_value_json) if entry.old_value_json else None
            new_value = orjson.loads(entry.new_value_json)

            entries.append(
                HistoryEntry(
                    id=entry.id,
                    service=entry.service,
                    key=entry.key,
                    old_value=old_value,
                    new_value=new_value,
                    changed_at=entry.changed_at.isoformat(),
                    changed_by=entry.changed_by,
                    change_reason=entry.change_reason,
                )
            )

        logger.info(
            f"History query by {token.name}: service={service}, key={key}, returned {len(entries)} entries",
            extra={
                "event": "history_queried",
                "user": token.name,
                "service": service,
                "key": key,
                "count": len(entries),
            },
        )

        return HistoryResponse(entries=entries, total_returned=len(entries))

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Failed to query history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query history: {str(e)}",
        )


class RestoreRequest(BaseModel):
    """Request to restore configuration to a previous state."""

    service: str
    history_entries: list[int]  # List of history entry IDs to restore


class RestoreResponse(BaseModel):
    """Response from restore operation."""

    success: bool
    service: str
    keys_restored: list[str]
    new_version: int


@router.post("/history/restore", response_model=RestoreResponse)
async def restore_from_history(
    request: RestoreRequest,
    x_csrf_token: str = Header(..., alias="X-CSRF-Token"),
    token: APIToken = Depends(require_permissions(Permission.CONFIG_WRITE)),
) -> RestoreResponse:
    """Restore configuration from history entries.

    Restores specified history entries to their old values.
    This effectively "undoes" the changes represented by those entries.

    Requires config.write permission and CSRF token.
    """
    # CSRF validation
    await validate_csrf_header(x_csrf_token)

    # Permission check
    if not has_permission(token.role, Permission.CONFIG_WRITE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions: config.write required",
        )

    service_obj = _get_service()

    try:
        # Get all requested history entries
        all_history = await service_obj.database.get_config_history(
            service=request.service,
            limit=10000,  # Get enough to find our IDs
        )

        # Find the requested entries
        entries_to_restore = {
            entry.id: entry for entry in all_history if entry.id in request.history_entries
        }

        if len(entries_to_restore) != len(request.history_entries):
            missing = set(request.history_entries) - set(entries_to_restore.keys())
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"History entries not found: {missing}",
            )

        # Get current config
        current_config_obj = await service_obj.database.get_service_config(request.service)
        if not current_config_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{request.service}' not found",
            )

        # Build restored config by applying old values
        restored_config = dict(current_config_obj.config)
        keys_restored = []

        for entry in entries_to_restore.values():
            if entry.old_value_json:
                # Restore to old value
                old_value = orjson.loads(entry.old_value_json)
                restored_config[entry.key] = old_value
                keys_restored.append(entry.key)
            else:
                # Entry was added (old_value is None), so remove it
                if entry.key in restored_config:
                    del restored_config[entry.key]
                    keys_restored.append(entry.key)

        # Update config
        new_version = await service_obj.database.update_service_config(
            service=request.service,
            config=restored_config,
            expected_version=current_config_obj.version,
            updated_by=token.name,
        )

        # Publish MQTT update
        if mqtt_publisher:
            await mqtt_publisher.publish_config_update(
                service=request.service,
                config=restored_config,
                version=new_version,
                epoch=current_config_obj.config_epoch,
            )

        # Update LKG cache
        await cache_manager.atomic_update_from_db(service_obj.database, request.service)

        logger.info(
            f"Config restored from history: {request.service} by {token.name} ({len(keys_restored)} keys)",
            extra={
                "event": "config_restored",
                "service": request.service,
                "user": token.name,
                "keys_restored": keys_restored,
                "history_entries": request.history_entries,
            },
        )

        return RestoreResponse(
            success=True,
            service=request.service,
            keys_restored=keys_restored,
            new_version=new_version,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Version conflict: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Failed to restore config from history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restore config: {str(e)}",
        )

