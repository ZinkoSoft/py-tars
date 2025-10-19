"""Metadata extraction utilities for Pydantic configuration models."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from tars.config.types import ConfigComplexity, ConfigType

logger = logging.getLogger(__name__)

# Cache for loaded YAML metadata
_METADATA_CACHE: dict[str, dict[str, dict[str, Any]]] | None = None
_METADATA_FILE_PATH = Path("/etc/tars/config-metadata.yml")


def extract_field_metadata(
    config_model: type[BaseModel], service_name: str | None = None
) -> dict[str, dict[str, Any]]:
    """Extract metadata from Pydantic model fields.

    Extracts complexity level, type, description, and validation constraints from
    Field definitions and json_schema_extra annotations. If service_name is provided,
    also attempts to load additional metadata from {service_name}/config_metadata.py.

    Args:
        config_model: Pydantic model class (e.g., STTWorkerConfig)
        service_name: Service name (e.g., 'stt-worker') to load custom metadata

    Returns:
        Dictionary mapping field_name -> metadata dict with keys:
        - type: ConfigType value (string, integer, float, boolean, enum, path, secret)
        - complexity: 'simple' or 'advanced' (default: 'simple')
        - description: Field description from Field(description=...) or json_schema_extra
        - help_text: Optional detailed help text
        - examples: List of example values
        - is_secret: Whether field is a secret (bool)
        - validation_min: Minimum value for numeric types (if applicable)
        - validation_max: Maximum value for numeric types (if applicable)
        - validation_pattern: Regex pattern for string validation (if applicable)
        - validation_allowed: List of allowed values for enums (if applicable)

    Example:
        >>> from tars.config.models import STTWorkerConfig
        >>> metadata = extract_field_metadata(STTWorkerConfig, 'stt-worker')
        >>> metadata['whisper_model']['complexity']
        'simple'
        >>> metadata['vad_threshold']['type']
        'float'
    """
    metadata = {}
    
    # Try to load custom metadata from service config_metadata.py
    custom_metadata = {}
    if service_name:
        custom_metadata = _load_service_metadata(service_name)

    for field_name, field_info in config_model.model_fields.items():
        field_meta: dict[str, Any] = {}

        # Extract type from annotation and json_schema_extra
        field_type = _infer_config_type(field_info.annotation)
        json_extra = field_info.json_schema_extra or {}

        # Type: use json_schema_extra if available, else infer from annotation
        if isinstance(json_extra, dict) and "type" in json_extra:
            field_meta["type"] = json_extra["type"]
        else:
            field_meta["type"] = field_type.value

        # Complexity: default to 'simple'
        if isinstance(json_extra, dict) and "complexity" in json_extra:
            field_meta["complexity"] = json_extra["complexity"]
        else:
            field_meta["complexity"] = ConfigComplexity.SIMPLE.value

        # Description: from Field(description=...) or json_schema_extra
        field_meta["description"] = field_info.description or ""
        if isinstance(json_extra, dict) and "description" in json_extra:
            field_meta["description"] = json_extra["description"]

        # Help text: from json_schema_extra if available
        field_meta["help_text"] = ""
        if isinstance(json_extra, dict) and "help_text" in json_extra:
            field_meta["help_text"] = json_extra["help_text"]
        
        # Examples: from json_schema_extra if available
        field_meta["examples"] = []
        if isinstance(json_extra, dict) and "examples" in json_extra:
            field_meta["examples"] = json_extra["examples"]

        # Merge with custom metadata if available (custom metadata takes precedence)
        if field_name in custom_metadata:
            custom = custom_metadata[field_name]
            if "description" in custom:
                field_meta["description"] = custom["description"]
            if "help_text" in custom:
                field_meta["help_text"] = custom["help_text"]
            if "examples" in custom:
                field_meta["examples"] = custom["examples"]

        # Secret detection: field name contains 'key', 'secret', 'password', 'token'
        secret_keywords = ["key", "secret", "password", "token", "credential"]
        field_meta["is_secret"] = any(kw in field_name.lower() for kw in secret_keywords)
        if isinstance(json_extra, dict) and "is_secret" in json_extra:
            field_meta["is_secret"] = json_extra["is_secret"]

        # Validation constraints from Field(ge=, le=, gt=, lt=, pattern=)
        if hasattr(field_info, "metadata"):
            for constraint in field_info.metadata:
                if hasattr(constraint, "ge"):
                    field_meta["validation_min"] = constraint.ge
                if hasattr(constraint, "le"):
                    field_meta["validation_max"] = constraint.le
                if hasattr(constraint, "pattern"):
                    field_meta["validation_pattern"] = constraint.pattern

        # For Literal types, extract allowed values
        if hasattr(field_info.annotation, "__origin__"):
            origin = getattr(field_info.annotation, "__origin__", None)
            if origin and str(origin) == "typing.Literal":
                args = getattr(field_info.annotation, "__args__", ())
                if args:
                    field_meta["validation_allowed"] = list(args)
                    field_meta["type"] = ConfigType.ENUM.value

        metadata[field_name] = field_meta

    return metadata


def _infer_config_type(annotation: Any) -> ConfigType:
    """Infer ConfigType from Python type annotation.

    Args:
        annotation: Type annotation (e.g., int, str, bool, float)

    Returns:
        ConfigType enum value
    """
    # Handle Union types (e.g., str | None, Optional[str])
    origin = getattr(annotation, "__origin__", None)
    if origin is type(None) or str(annotation).startswith("typing.Union"):
        args = getattr(annotation, "__args__", ())
        if args:
            # Use first non-None type
            for arg in args:
                if arg is not type(None):
                    return _infer_config_type(arg)

    # Handle Literal types (enums)
    if origin and str(origin) == "typing.Literal":
        return ConfigType.ENUM

    # Basic type mapping
    if annotation is int or annotation == "int":
        return ConfigType.INTEGER
    elif annotation is float or annotation == "float":
        return ConfigType.FLOAT
    elif annotation is bool or annotation == "bool":
        return ConfigType.BOOLEAN
    elif annotation is str or annotation == "str":
        return ConfigType.STRING

    # Default to string
    return ConfigType.STRING


def get_all_service_configs() -> dict[str, type[BaseModel]]:
    """Get all service configuration model classes.

    Returns:
        Dictionary mapping service_name -> config_model_class

    Example:
        >>> configs = get_all_service_configs()
        >>> 'stt-worker' in configs
        True
        >>> configs['stt-worker']
        <class 'tars.config.models.STTWorkerConfig'>
    """
    from tars.config.models import (
        LLMWorkerConfig,
        MemoryWorkerConfig,
        RouterConfig,
        STTWorkerConfig,
        TTSWorkerConfig,
        WakeActivationConfig,
    )

    return {
        "stt-worker": STTWorkerConfig,
        "tts-worker": TTSWorkerConfig,
        "router": RouterConfig,
        "llm-worker": LLMWorkerConfig,
        "memory-worker": MemoryWorkerConfig,
        "wake-activation": WakeActivationConfig,
    }


def create_default_service_configs() -> dict[str, dict[str, Any]]:
    """Create default configuration for all services.

    Instantiates all service config models with their default values.

    Returns:
        Dictionary mapping service_name -> config_dict (with default values)

    Example:
        >>> configs = create_default_service_configs()
        >>> configs['stt-worker']['whisper_model']
        'base.en'
    """
    service_configs = {}
    all_configs = get_all_service_configs()

    for service_name, config_model in all_configs.items():
        # Instantiate model with defaults
        instance = config_model()
        # Convert to dict
        service_configs[service_name] = instance.model_dump()

    return service_configs


def _load_service_metadata(service_name: str) -> dict[str, dict[str, Any]]:
    """Load custom metadata from YAML configuration file.
    
    Args:
        service_name: Service name (e.g., 'stt-worker')
    
    Returns:
        Dictionary mapping field_name -> metadata dict, or empty dict if not found
    """
    global _METADATA_CACHE
    
    # Load and cache YAML file on first access
    if _METADATA_CACHE is None:
        _METADATA_CACHE = _load_yaml_metadata()
    
    # Return metadata for this service
    service_metadata = _METADATA_CACHE.get(service_name, {})
    if service_metadata:
        logger.debug(f"Loaded metadata for {service_name} with {len(service_metadata)} fields from YAML")
    
    return service_metadata


def _load_yaml_metadata() -> dict[str, dict[str, dict[str, Any]]]:
    """Load all service metadata from YAML file.
    
    Returns:
        Dictionary mapping service_name -> field_name -> metadata dict
    """
    try:
        if not _METADATA_FILE_PATH.exists():
            logger.warning(f"Metadata file not found: {_METADATA_FILE_PATH}")
            return {}
        
        with open(_METADATA_FILE_PATH, 'r') as f:
            data = yaml.safe_load(f)
        
        if not isinstance(data, dict):
            logger.error(f"Invalid metadata file format: expected dict, got {type(data)}")
            return {}
        
        logger.info(f"Loaded metadata for {len(data)} services from {_METADATA_FILE_PATH}")
        return data
        
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse YAML metadata file: {e}", exc_info=True)
        return {}
    except Exception as e:
        logger.error(f"Error loading metadata file: {e}", exc_info=True)
        return {}
