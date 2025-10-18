"""Metadata extraction utilities for Pydantic configuration models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from tars.config.types import ConfigComplexity, ConfigType


def extract_field_metadata(config_model: type[BaseModel]) -> dict[str, dict[str, Any]]:
    """Extract metadata from Pydantic model fields.

    Extracts complexity level, type, description, and validation constraints from
    Field definitions and json_schema_extra annotations.

    Args:
        config_model: Pydantic model class (e.g., STTWorkerConfig)

    Returns:
        Dictionary mapping field_name -> metadata dict with keys:
        - type: ConfigType value (string, integer, float, boolean, enum, path, secret)
        - complexity: 'simple' or 'advanced' (default: 'simple')
        - description: Field description from Field(description=...) or json_schema_extra
        - help_text: Optional detailed help text
        - is_secret: Whether field is a secret (bool)
        - validation_min: Minimum value for numeric types (if applicable)
        - validation_max: Maximum value for numeric types (if applicable)
        - validation_pattern: Regex pattern for string validation (if applicable)
        - validation_allowed: List of allowed values for enums (if applicable)

    Example:
        >>> from tars.config.models import STTWorkerConfig
        >>> metadata = extract_field_metadata(STTWorkerConfig)
        >>> metadata['whisper_model']['complexity']
        'simple'
        >>> metadata['vad_threshold']['type']
        'float'
    """
    metadata = {}

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
