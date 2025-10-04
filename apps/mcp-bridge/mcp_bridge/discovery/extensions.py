"""Extension discovery for MCP servers in extensions/mcp-servers/*."""

import logging
from pathlib import Path
from typing import Optional

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Fallback for Python 3.10

from .base import MCPServerMetadata, ServerSource, TransportType

logger = logging.getLogger(__name__)


class ExtensionDiscovery:
    """Discovers MCP servers from extensions directory.
    
    Scans extensions/mcp-servers/* directories and extracts metadata from pyproject.toml.
    """
    
    def __init__(self, extensions_path: Path):
        """Initialize discovery service.
        
        Args:
            extensions_path: Path to extensions/mcp-servers directory
        """
        self.extensions_path = Path(extensions_path)
        if not self.extensions_path.exists():
            logger.warning(f"Extensions path does not exist: {self.extensions_path}")
    
    async def discover(self) -> list[MCPServerMetadata]:
        """Discover all extension MCP servers.
        
        Returns:
            List of validated server metadata objects.
        """
        servers = []
        
        if not self.extensions_path.exists():
            logger.debug(f"Extensions directory not found: {self.extensions_path}")
            return servers
        
        # Find all subdirectories in extensions/mcp-servers/
        for extension_dir in self.extensions_path.iterdir():
            if not extension_dir.is_dir():
                continue
            
            # Skip hidden directories and __pycache__
            if extension_dir.name.startswith(".") or extension_dir.name == "__pycache__":
                continue
            
            logger.debug(f"Scanning extension: {extension_dir.name}")
            
            try:
                metadata = await self._extract_metadata(extension_dir)
                if metadata:
                    servers.append(metadata)
                    logger.info(f"✅ Discovered extension: {metadata}")
            except Exception as e:
                logger.error(f"❌ Failed to process extension {extension_dir.name}: {e}")
                continue
        
        logger.info(f"Discovered {len(servers)} extension MCP servers")
        return servers
    
    async def _extract_metadata(self, extension_dir: Path) -> Optional[MCPServerMetadata]:
        """Extract metadata from an extension directory.
        
        Args:
            extension_dir: Path to extension (e.g., extensions/mcp-servers/my-server)
        
        Returns:
            MCPServerMetadata if valid, None if invalid/incomplete.
        """
        pyproject_path = extension_dir / "pyproject.toml"
        if not pyproject_path.exists():
            logger.debug(f"No pyproject.toml in {extension_dir.name}")
            return None
        
        # Parse pyproject.toml
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)
        
        project = pyproject.get("project", {})
        if not project:
            logger.debug(f"No [project] section in {extension_dir.name}/pyproject.toml")
            return None
        
        # Extract basic metadata
        package_name = project.get("name")
        if not package_name:
            logger.warning(f"No package name in {extension_dir.name}/pyproject.toml")
            return None
        
        # Check for MCP dependencies
        dependencies = project.get("dependencies", [])
        has_mcp = any("mcp" in dep for dep in dependencies)
        if not has_mcp:
            logger.debug(f"Extension {package_name} does not have MCP dependency, skipping")
            return None
        
        # Derive module name
        module_name = package_name.replace("-", "_")
        
        # Check if __main__.py exists (required for stdio)
        main_path = extension_dir / module_name / "__main__.py"
        if not main_path.exists():
            logger.warning(f"Extension {package_name} missing {module_name}/__main__.py entry point")
            return None
        
        # Extract optional MCP-specific config
        tool_mcp = pyproject.get("tool", {}).get("mcp", {})
        
        # Build metadata
        metadata = MCPServerMetadata(
            name=package_name,
            source=ServerSource.EXTENSION,
            package_path=extension_dir,
            package_name=package_name,
            version=project.get("version", "0.0.0"),
            description=project.get("description", ""),
            transport=TransportType(tool_mcp.get("transport", "stdio")),
            command=tool_mcp.get("command", "python"),
            args=tool_mcp.get("args", ["-m", module_name]),
            env=dict(tool_mcp.get("env_defaults", {})),
            env_defaults=dict(tool_mcp.get("env_defaults", {})),
            dependencies=dependencies,
            tools_allowlist=tool_mcp.get("tools_allowlist"),
            validated=True,
        )
        
        return metadata
