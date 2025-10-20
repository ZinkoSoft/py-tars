"""Type definitions for configuration management."""

from __future__ import annotations

from enum import Enum


class ConfigComplexity(str, Enum):
    """Configuration complexity level for UI filtering."""

    SIMPLE = "simple"  # Commonly used, shown by default
    ADVANCED = "advanced"  # Technical, hidden unless expanded


class ConfigType(str, Enum):
    """Configuration value types."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    ENUM = "enum"
    PATH = "path"
    URL = "url"
    SECRET = "secret"


class ConfigSource(str, Enum):
    """Where configuration value comes from."""

    ENV = "env"  # .env file (immutable)
    DATABASE = "database"  # SQLite database (mutable)
    DEFAULT = "default"  # Hardcoded default
