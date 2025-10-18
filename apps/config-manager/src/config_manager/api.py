"""REST API endpoints for configuration management."""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from tars.config.models import ServiceConfig

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/config", tags=["config"])


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


@router.get("/services", response_model=ServiceListResponse)
async def list_services():
    """List all available services with configuration.

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


@router.get("/services/{service_name}", response_model=ConfigGetResponse)
async def get_service_config(service_name: str, include_fields: bool = True):
    """Get configuration for a specific service.

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
async def update_service_config(service_name: str, request: ConfigUpdateRequest):
    """Update configuration for a specific service.

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

        logger.info(
            f"Updated config for {service_name}: v{request.version} -> v{new_version}"
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
