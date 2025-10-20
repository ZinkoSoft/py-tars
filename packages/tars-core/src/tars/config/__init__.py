"""Configuration management module for TARS.

This module provides:
- Centralized configuration storage and retrieval
- MQTT-based configuration updates
- Read-only fallback with last-known-good cache
- Encryption for sensitive secrets
- Schema version tracking for compatibility
"""

from tars.config.library import ConfigLibrary
from tars.config.metadata import (
    create_default_service_configs,
    extract_field_metadata,
    get_all_service_configs,
)
from tars.config.models import (
    ConfigComplexity,
    ConfigFieldMetadata,
    ConfigItem,
    ConfigType,
    ServiceConfig,
)
from tars.config.types import ConfigSource

__all__ = [
    "ConfigLibrary",
    "ConfigComplexity",
    "ConfigFieldMetadata",
    "ConfigItem",
    "ConfigSource",
    "ConfigType",
    "ServiceConfig",
    "create_default_service_configs",
    "extract_field_metadata",
    "get_all_service_configs",
]
