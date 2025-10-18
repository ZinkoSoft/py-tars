"""Configuration precedence resolution.

Resolution order: .env → database → defaults

Environment variables take precedence over database values, which take precedence
over hardcoded defaults. This allows operators to override any setting via .env
while still enabling runtime configuration management for non-critical settings.
"""

from __future__ import annotations

import os
from typing import Any, TypeVar

from pydantic import BaseModel

from tars.config.types import ConfigSource

T = TypeVar("T", bound=BaseModel)


class ConfigResolver:
    """Resolves configuration from multiple sources with precedence."""

    def __init__(self, env_prefix: str = ""):
        """Initialize resolver.

        Args:
            env_prefix: Prefix for environment variables (e.g., "TARS_")
        """
        self.env_prefix = env_prefix

    def resolve_config(
        self,
        config_model: type[T],
        db_config: dict[str, Any] | None = None,
    ) -> T:
        """Resolve configuration with precedence: .env → database → defaults.

        Args:
            config_model: Pydantic model class for configuration
            db_config: Configuration from database (optional)

        Returns:
            Resolved configuration instance

        Example:
            >>> from tars.config.models import STTWorkerConfig
            >>> resolver = ConfigResolver()
            >>> config = resolver.resolve_config(
            ...     STTWorkerConfig,
            ...     db_config={"whisper_model": "small.en"}
            ... )
            >>> config.whisper_model  # Returns value from .env if set, else db, else default
        """
        # Start with defaults (from Pydantic model)
        resolved: dict[str, Any] = {}

        # Get model field defaults
        for field_name, field_info in config_model.model_fields.items():
            if field_info.default is not None:
                resolved[field_name] = field_info.default
            elif field_info.default_factory is not None:
                resolved[field_name] = field_info.default_factory()

        # Apply database values (overrides defaults)
        if db_config:
            for key, value in db_config.items():
                if key in config_model.model_fields:
                    resolved[key] = value

        # Apply environment variables (overrides everything)
        for field_name in config_model.model_fields:
            env_key = f"{self.env_prefix}{field_name.upper()}"
            env_value = os.getenv(env_key)
            if env_value is not None:
                # Parse env value based on field type
                resolved[field_name] = self._parse_env_value(
                    env_value, config_model.model_fields[field_name].annotation
                )

        # Validate and construct model
        return config_model.model_validate(resolved)

    def get_config_source(
        self, field_name: str, db_config: dict[str, Any] | None = None
    ) -> ConfigSource:
        """Determine where a configuration value came from.

        Args:
            field_name: Configuration field name
            db_config: Configuration from database

        Returns:
            ConfigSource (ENV, DATABASE, or DEFAULT)
        """
        env_key = f"{self.env_prefix}{field_name.upper()}"
        if os.getenv(env_key) is not None:
            return ConfigSource.ENV

        if db_config and field_name in db_config:
            return ConfigSource.DATABASE

        return ConfigSource.DEFAULT

    def _parse_env_value(self, value: str, field_type: Any) -> Any:
        """Parse environment variable string to appropriate type.

        Args:
            value: String value from environment
            field_type: Target type annotation

        Returns:
            Parsed value
        """
        # Handle None/null
        if value.lower() in ("none", "null", ""):
            return None

        # Get origin type (handles Optional[T], list[T], etc.)
        origin = getattr(field_type, "__origin__", None)

        # Handle Union types (e.g., str | None)
        if origin is type(None) or str(field_type) == "typing.Union":
            args = getattr(field_type, "__args__", ())
            if args:
                # Use first non-None type
                for arg in args:
                    if arg is not type(None):
                        return self._parse_env_value(value, arg)

        # Handle basic types
        if field_type is bool or field_type == "bool":
            return value.lower() in ("true", "1", "yes", "on")
        elif field_type is int or field_type == "int":
            return int(value)
        elif field_type is float or field_type == "float":
            return float(value)
        elif field_type is str or field_type == "str":
            return value

        # Handle Literal types
        if hasattr(field_type, "__origin__") and str(field_type.__origin__) == "typing.Literal":
            # Return value as-is if it's a valid literal option
            return value

        # Default: return as string
        return value

    def resolve_with_metadata(
        self,
        config_model: type[T],
        db_config: dict[str, Any] | None = None,
    ) -> tuple[T, dict[str, ConfigSource]]:
        """Resolve configuration and return source metadata.

        Args:
            config_model: Pydantic model class
            db_config: Configuration from database

        Returns:
            Tuple of (resolved_config, source_map)
            where source_map maps field_name -> ConfigSource
        """
        config = self.resolve_config(config_model, db_config)
        source_map = {
            field_name: self.get_config_source(field_name, db_config)
            for field_name in config_model.model_fields
        }
        return config, source_map
