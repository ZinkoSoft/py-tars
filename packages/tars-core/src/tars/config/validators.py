"""Custom validators for configuration fields."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def validate_path_exists(value: str | None, field_name: str = "path") -> str | None:
    """Validate that a file or directory path exists.
    
    Args:
        value: Path string to validate
        field_name: Name of the field (for error messages)
    
    Returns:
        The validated path string
    
    Raises:
        ValueError: If path doesn't exist
    """
    if value is None:
        return None
    
    path = Path(value)
    if not path.exists():
        raise ValueError(
            f"{field_name} '{value}' does not exist. "
            "Please ensure the path is correct and accessible."
        )
    
    return value


def validate_directory_path(value: str | None, field_name: str = "directory") -> str | None:
    """Validate that a path is a directory.
    
    Args:
        value: Path string to validate
        field_name: Name of the field (for error messages)
    
    Returns:
        The validated path string
    
    Raises:
        ValueError: If path is not a directory
    """
    if value is None:
        return None
    
    path = Path(value)
    if path.exists() and not path.is_dir():
        raise ValueError(
            f"{field_name} '{value}' exists but is not a directory"
        )
    
    return value


def validate_file_path(value: str | None, field_name: str = "file") -> str | None:
    """Validate that a path is a file.
    
    Args:
        value: Path string to validate
        field_name: Name of the field (for error messages)
    
    Returns:
        The validated path string
    
    Raises:
        ValueError: If path is not a file
    """
    if value is None:
        return None
    
    path = Path(value)
    if path.exists() and not path.is_file():
        raise ValueError(
            f"{field_name} '{value}' exists but is not a file"
        )
    
    return value


def validate_absolute_path(value: str | None, field_name: str = "path") -> str | None:
    """Validate that a path is absolute.
    
    Args:
        value: Path string to validate
        field_name: Name of the field (for error messages)
    
    Returns:
        The validated path string
    
    Raises:
        ValueError: If path is not absolute
    """
    if value is None:
        return None
    
    path = Path(value)
    if not path.is_absolute():
        raise ValueError(
            f"{field_name} '{value}' must be an absolute path"
        )
    
    return value


def validate_url(value: str | None, allowed_schemes: list[str] | None = None) -> str | None:
    """Validate that a string is a valid URL.
    
    Args:
        value: URL string to validate
        allowed_schemes: List of allowed URL schemes (e.g., ['http', 'https', 'ws', 'wss'])
    
    Returns:
        The validated URL string
    
    Raises:
        ValueError: If URL is invalid or scheme not allowed
    """
    if value is None:
        return None
    
    if allowed_schemes is None:
        allowed_schemes = ['http', 'https']
    
    try:
        parsed = urlparse(value)
    except Exception as e:
        raise ValueError(f"Invalid URL format: {e}")
    
    if not parsed.scheme:
        raise ValueError("URL must include a scheme (e.g., http://, https://)")
    
    if parsed.scheme not in allowed_schemes:
        raise ValueError(
            f"URL scheme '{parsed.scheme}' not allowed. "
            f"Allowed schemes: {', '.join(allowed_schemes)}"
        )
    
    if not parsed.netloc:
        raise ValueError("URL must include a host (e.g., example.com)")
    
    return value


def validate_mqtt_url(value: str | None) -> str | None:
    """Validate that a string is a valid MQTT URL.
    
    Args:
        value: MQTT URL string to validate
    
    Returns:
        The validated URL string
    
    Raises:
        ValueError: If MQTT URL is invalid
    """
    return validate_url(value, allowed_schemes=['mqtt', 'mqtts'])


def validate_ws_url(value: str | None) -> str | None:
    """Validate that a string is a valid WebSocket URL.
    
    Args:
        value: WebSocket URL string to validate
    
    Returns:
        The validated URL string
    
    Raises:
        ValueError: If WebSocket URL is invalid
    """
    return validate_url(value, allowed_schemes=['ws', 'wss'])


def validate_regex_pattern(value: str | None, field_name: str = "pattern") -> str | None:
    """Validate that a string is a valid regex pattern.
    
    Args:
        value: Regex pattern string to validate
        field_name: Name of the field (for error messages)
    
    Returns:
        The validated pattern string
    
    Raises:
        ValueError: If pattern is not valid regex
    """
    if value is None:
        return None
    
    try:
        re.compile(value)
    except re.error as e:
        raise ValueError(f"Invalid regex {field_name}: {e}")
    
    return value


def validate_port(value: int | None) -> int | None:
    """Validate that a value is a valid network port.
    
    Args:
        value: Port number to validate
    
    Returns:
        The validated port number
    
    Raises:
        ValueError: If port is not in valid range
    """
    if value is None:
        return None
    
    if not (1 <= value <= 65535):
        raise ValueError(
            f"Port {value} is not valid. Must be between 1 and 65535."
        )
    
    return value


def validate_percentage(value: int | float | None) -> int | float | None:
    """Validate that a value is a valid percentage (0-100).
    
    Args:
        value: Percentage value to validate
    
    Returns:
        The validated percentage
    
    Raises:
        ValueError: If value is not in 0-100 range
    """
    if value is None:
        return None
    
    if not (0 <= value <= 100):
        raise ValueError(
            f"Percentage {value} is not valid. Must be between 0 and 100."
        )
    
    return value


def validate_probability(value: float | None) -> float | None:
    """Validate that a value is a valid probability (0.0-1.0).
    
    Args:
        value: Probability value to validate
    
    Returns:
        The validated probability
    
    Raises:
        ValueError: If value is not in 0.0-1.0 range
    """
    if value is None:
        return None
    
    if not (0.0 <= value <= 1.0):
        raise ValueError(
            f"Probability {value} is not valid. Must be between 0.0 and 1.0."
        )
    
    return value


def validate_positive_number(value: int | float | None, field_name: str = "value") -> int | float | None:
    """Validate that a number is positive.
    
    Args:
        value: Number to validate
        field_name: Name of the field (for error messages)
    
    Returns:
        The validated number
    
    Raises:
        ValueError: If value is not positive
    """
    if value is None:
        return None
    
    if value <= 0:
        raise ValueError(f"{field_name} must be positive (got {value})")
    
    return value
