"""
Configuration management for UI E-Ink Display service.

Loads and validates environment variables using Pydantic.
"""

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class DisplayConfig(BaseModel):
    """Configuration for the e-ink display service."""

    # MQTT Configuration
    mqtt_host: str = Field(..., description="MQTT broker hostname or IP address")
    mqtt_port: int = Field(default=1883, description="MQTT broker port", ge=1, le=65535)
    mqtt_client_id: str = Field(
        default="ui-eink-display",
        description="MQTT client identifier",
    )

    # Display Configuration
    display_timeout_sec: int = Field(
        default=45,
        description="Seconds before returning to standby mode",
        ge=5,
        le=300,
    )
    mock_display: bool = Field(
        default=False,
        description="Use mock display for testing without hardware",
    )

    # System Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    pythonpath: Optional[str] = Field(
        default=None,
        description="Additional Python paths (for waveshare-epd library)",
    )
    font_path: Path = Field(
        default=Path("/usr/share/fonts/truetype/dejavu"),
        description="Path to font files directory",
    )

    # Health Check Configuration
    health_check_interval_sec: int = Field(
        default=30,
        description="Interval for health check publishing",
        ge=10,
        le=300,
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the standard Python logging levels."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(
                f"Invalid log level: {v}. Must be one of {valid_levels}"
            )
        return v_upper

    @field_validator("font_path")
    @classmethod
    def validate_font_path(cls, v: Path) -> Path:
        """Validate font path exists (skip in mock mode)."""
        # Skip validation if MOCK_DISPLAY is set
        if os.getenv("MOCK_DISPLAY", "0") == "1":
            return v
        
        if not v.exists():
            raise ValueError(f"Font path does not exist: {v}")
        if not v.is_dir():
            raise ValueError(f"Font path is not a directory: {v}")
        return v

    @classmethod
    def from_env(cls) -> "DisplayConfig":
        """
        Load configuration from environment variables.

        Environment variables:
        - MQTT_HOST (required)
        - MQTT_PORT (default: 1883)
        - MQTT_CLIENT_ID (default: ui-eink-display)
        - DISPLAY_TIMEOUT_SEC (default: 45)
        - MOCK_DISPLAY (default: 0, set to 1 to enable)
        - LOG_LEVEL (default: INFO)
        - PYTHONPATH (optional, for waveshare-epd)
        - FONT_PATH (default: /usr/share/fonts/truetype/dejavu)
        - HEALTH_CHECK_INTERVAL_SEC (default: 30)

        Returns:
            DisplayConfig: Validated configuration instance

        Raises:
            ValueError: If MQTT_HOST is missing or validation fails
        """
        mqtt_host = os.getenv("MQTT_HOST")
        if not mqtt_host:
            raise ValueError("MQTT_HOST environment variable is required")

        return cls(
            mqtt_host=mqtt_host,
            mqtt_port=int(os.getenv("MQTT_PORT", "1883")),
            mqtt_client_id=os.getenv("MQTT_CLIENT_ID", "ui-eink-display"),
            display_timeout_sec=int(os.getenv("DISPLAY_TIMEOUT_SEC", "45")),
            mock_display=os.getenv("MOCK_DISPLAY", "0") == "1",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            pythonpath=os.getenv("PYTHONPATH"),
            font_path=Path(
                os.getenv("FONT_PATH", "/usr/share/fonts/truetype/dejavu")
            ),
            health_check_interval_sec=int(
                os.getenv("HEALTH_CHECK_INTERVAL_SEC", "30")
            ),
        )

    def setup_pythonpath(self) -> None:
        """
        Add pythonpath to sys.path if configured.

        This is necessary for the waveshare-epd library which may not be
        installed via pip.
        """
        if self.pythonpath:
            import sys
            paths = self.pythonpath.split(":")
            for path in paths:
                if path and path not in sys.path:
                    sys.path.insert(0, path)
