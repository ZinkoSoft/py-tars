"""Configuration file writer with atomic operations.

Writes MCP server configuration to disk with proper error handling,
atomic operations, and file permissions.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from .generator import GeneratedConfig

logger = logging.getLogger(__name__)


class ConfigWriter:
    """Writes MCP server configuration to disk atomically.

    Uses atomic write operations (write to temp, then rename) to ensure
    the configuration file is never partially written or corrupted.
    """

    def __init__(
        self,
        output_dir: str = "./config",
        filename: str = "mcp-servers.json",
        indent: int = 2,
        ensure_dir: bool = True,
    ) -> None:
        """Initialize config writer.

        Args:
            output_dir: Directory to write config file
            filename: Name of config file (default: mcp-servers.json)
            indent: JSON indentation spaces (default: 2)
            ensure_dir: Create output directory if it doesn't exist (default: True)
        """
        self.output_dir = Path(output_dir)
        self.filename = filename
        self.indent = indent
        self.ensure_dir = ensure_dir

    def write(self, config: GeneratedConfig) -> str:
        """Write configuration to disk atomically.

        Args:
            config: Generated configuration to write

        Returns:
            Absolute path to written config file

        Raises:
            OSError: If directory creation or file writing fails
            PermissionError: If insufficient permissions
            ValueError: If config is invalid
        """
        # Ensure output directory exists
        if self.ensure_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        elif not self.output_dir.exists():
            raise OSError(f"Output directory does not exist: {self.output_dir}")

        # Verify directory is writable
        if not os.access(self.output_dir, os.W_OK):
            raise PermissionError(f"Output directory is not writable: {self.output_dir}")

        # Convert config to dict
        config_dict = config.to_dict()

        # Serialize to JSON
        try:
            json_content = json.dumps(config_dict, indent=self.indent, sort_keys=False)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Failed to serialize config to JSON: {e}") from e

        # Write atomically using temp file + rename
        output_path = self.output_dir / self.filename
        temp_path = None

        try:
            # Create temp file in same directory (ensures same filesystem)
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=self.output_dir,
                prefix=f".{self.filename}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_path = temp_file.name
                temp_file.write(json_content)
                temp_file.flush()
                os.fsync(temp_file.fileno())

            # Atomically replace old file with new file
            # On Unix, this is atomic. On Windows, it requires Python 3.3+
            os.replace(temp_path, output_path)
            temp_path = None  # Successfully moved

            logger.info(f"Successfully wrote config to {output_path}")
            return str(output_path.absolute())

        except Exception as e:
            # Clean up temp file on error
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
            raise OSError(f"Failed to write config file: {e}") from e

    def read(self, validate: bool = True) -> GeneratedConfig | None:
        """Read configuration from disk.

        Args:
            validate: Validate structure after reading (default: True)

        Returns:
            GeneratedConfig if file exists and is valid, None otherwise

        Raises:
            OSError: If file reading fails
            ValueError: If JSON is invalid or structure is wrong
        """
        config_path = self.output_dir / self.filename

        if not config_path.exists():
            return None

        try:
            with open(config_path) as f:
                config_dict = json.load(f)

            if validate:
                self._validate_structure(config_dict)

            # Note: We don't reconstruct full GeneratedConfig with dataclasses
            # since we'd need to reconstruct all nested objects. Just return dict.
            # If needed, add from_dict() methods to dataclasses.
            return config_dict  # type: ignore

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {e}") from e
        except Exception as e:
            raise OSError(f"Failed to read config file: {e}") from e

    def _validate_structure(self, config_dict: dict[str, Any]) -> None:
        """Validate config structure.

        Args:
            config_dict: Config dictionary to validate

        Raises:
            ValueError: If structure is invalid
        """
        required_fields = ["version", "generated_at", "servers"]
        for field in required_fields:
            if field not in config_dict:
                raise ValueError(f"Missing required field: {field}")

        if not isinstance(config_dict["servers"], list):
            raise ValueError("servers must be a list")

        if not isinstance(config_dict["version"], int):
            raise ValueError("version must be an integer")

    def exists(self) -> bool:
        """Check if config file exists.

        Returns:
            True if config file exists
        """
        return (self.output_dir / self.filename).exists()

    def delete(self) -> bool:
        """Delete config file if it exists.

        Returns:
            True if file was deleted, False if it didn't exist
        """
        config_path = self.output_dir / self.filename
        if config_path.exists():
            config_path.unlink()
            logger.info(f"Deleted config file: {config_path}")
            return True
        return False
