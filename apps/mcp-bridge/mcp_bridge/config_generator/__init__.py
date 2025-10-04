"""Configuration generation for MCP servers.

Converts discovered and installed MCP servers into a JSON configuration file
for llm-worker to consume at runtime.
"""

from .generator import ConfigGenerator, GeneratedConfig, ServerConfig
from .writer import ConfigWriter

__all__ = [
    "ConfigGenerator",
    "GeneratedConfig",
    "ServerConfig",
    "ConfigWriter",
]
