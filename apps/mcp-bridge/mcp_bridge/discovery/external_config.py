"""External configuration discovery from YAML files."""

import logging
import os
from pathlib import Path
from typing import Any, Optional

import yaml

from .base import MCPServerMetadata, ServerSource, TransportType

logger = logging.getLogger(__name__)


class ExternalConfigDiscovery:
    """Discovers MCP servers from external YAML configuration.
    
    Parses ops/mcp/mcp.server.yml for explicit server definitions.
    """
    
    def __init__(self, config_path: Path):
        """Initialize discovery service.
        
        Args:
            config_path: Path to YAML config file (e.g., ops/mcp/mcp.server.yml)
        """
        self.config_path = Path(config_path)
    
    async def discover(self) -> list[MCPServerMetadata]:
        """Discover servers from YAML configuration.
        
        Returns:
            List of validated server metadata objects.
        """
        servers = []
        
        if not self.config_path.exists():
            logger.info(f"External config not found: {self.config_path} (this is optional)")
            return servers
        
        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to parse YAML config {self.config_path}: {e}")
            return servers
        
        if not config or not isinstance(config, dict):
            logger.warning(f"Invalid YAML config: {self.config_path}")
            return servers
        
        # Extract server definitions
        server_defs = config.get("servers", [])
        if not server_defs:
            logger.debug(f"No servers defined in {self.config_path}")
            return servers
        
        for server_def in server_defs:
            try:
                metadata = await self._parse_server_definition(server_def)
                if metadata:
                    servers.append(metadata)
                    logger.info(f"✅ Discovered external server: {metadata}")
            except Exception as e:
                logger.error(f"❌ Failed to parse server definition: {e}")
                logger.debug(f"Server definition: {server_def}")
                continue
        
        logger.info(f"Discovered {len(servers)} external MCP servers from config")
        return servers
    
    async def _parse_server_definition(self, definition: dict[str, Any]) -> Optional[MCPServerMetadata]:
        """Parse a single server definition from YAML.
        
        Args:
            definition: Server definition dict from YAML
        
        Returns:
            MCPServerMetadata if valid, None if invalid.
        """
        name = definition.get("name")
        if not name:
            logger.warning("Server definition missing 'name' field")
            return None
        
        # Parse transport type
        transport_str = definition.get("transport", "stdio")
        try:
            transport = TransportType(transport_str)
        except ValueError:
            logger.error(f"Invalid transport type '{transport_str}' for server {name}")
            return None
        
        # Extract command and args for stdio
        command = definition.get("command", "python")
        args = definition.get("args", [])
        
        # Extract URL for HTTP
        url = definition.get("url")
        
        # Parse environment variables with substitution
        env_raw = definition.get("env", {})
        env = self._substitute_env_vars(env_raw)
        
        # Extract package info for pip install
        package_name = definition.get("package")
        
        # Extract tool allowlist
        tools_allowlist = definition.get("tools_allowlist")
        
        # Build metadata
        metadata = MCPServerMetadata(
            name=name,
            source=ServerSource.EXTERNAL,
            package_name=package_name,
            version="external",  # External servers don't have versions from our perspective
            description=definition.get("description", ""),
            transport=transport,
            command=command,
            args=args,
            url=url,
            env=env,
            dependencies=[],  # Unknown for external servers
            tools_allowlist=tools_allowlist,
            validated=True,
        )
        
        return metadata
    
    def _substitute_env_vars(self, env_dict: dict[str, str]) -> dict[str, str]:
        """Substitute environment variables in config values.
        
        Supports ${VAR_NAME} syntax for environment variable substitution.
        
        Args:
            env_dict: Dictionary with potential ${VAR} references
        
        Returns:
            Dictionary with substituted values.
        """
        substituted = {}
        for key, value in env_dict.items():
            if isinstance(value, str) and "${" in value:
                # Simple substitution: ${VAR_NAME}
                import re
                pattern = r'\$\{([^}]+)\}'
                
                def replacer(match):
                    var_name = match.group(1)
                    return os.getenv(var_name, f"${{{var_name}}}")  # Keep placeholder if not found
                
                substituted[key] = re.sub(pattern, replacer, value)
            else:
                substituted[key] = value
        
        return substituted
