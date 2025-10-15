"""Local package discovery for MCP servers in packages/tars-mcp-*."""

import logging
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]  # Fallback for Python 3.10

from .base import MCPServerMetadata, ServerSource, TransportType

logger = logging.getLogger(__name__)


class LocalPackageDiscovery:
    """Discovers MCP servers from local packages directory.

    Scans packages/tars-mcp-* directories and extracts metadata from pyproject.toml.
    """

    def __init__(self, packages_path: Path):
        """Initialize discovery service.

        Args:
            packages_path: Path to packages directory (e.g., /workspace/packages)
        """
        self.packages_path = Path(packages_path)
        if not self.packages_path.exists():
            logger.warning(f"Packages path does not exist: {self.packages_path}")

    async def discover(self) -> list[MCPServerMetadata]:
        """Discover all tars-mcp-* packages.

        Returns:
            List of validated server metadata objects.
        """
        servers: list[MCPServerMetadata] = []

        if not self.packages_path.exists():
            logger.warning(f"Packages directory not found: {self.packages_path}")
            return servers

        # Find all tars-mcp-* directories
        pattern = "tars-mcp-*"
        for package_dir in self.packages_path.glob(pattern):
            if not package_dir.is_dir():
                continue

            logger.debug(f"Scanning package: {package_dir.name}")

            try:
                metadata = await self._extract_metadata(package_dir)
                if metadata:
                    servers.append(metadata)
                    logger.info(f"✅ Discovered local package: {metadata}")
            except Exception as e:
                logger.error(f"❌ Failed to process package {package_dir.name}: {e}")
                continue

        logger.info(f"Discovered {len(servers)} local MCP servers")
        return servers

    async def _extract_metadata(self, package_dir: Path) -> MCPServerMetadata | None:
        """Extract metadata from a package directory.

        Args:
            package_dir: Path to package (e.g., packages/tars-mcp-character)

        Returns:
            MCPServerMetadata if valid, None if invalid/incomplete.
        """
        pyproject_path = package_dir / "pyproject.toml"
        if not pyproject_path.exists():
            logger.debug(f"No pyproject.toml in {package_dir.name}")
            return None

        # Parse pyproject.toml
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)

        project = pyproject.get("project", {})
        if not project:
            logger.debug(f"No [project] section in {package_dir.name}/pyproject.toml")
            return None

        # Extract basic metadata
        package_name = project.get("name")
        if not package_name:
            logger.warning(f"No package name in {package_dir.name}/pyproject.toml")
            return None

        # Check for MCP dependencies (must have mcp[cli] or mcp)
        dependencies = project.get("dependencies", [])
        has_mcp = any("mcp" in dep for dep in dependencies)
        if not has_mcp:
            logger.debug(f"Package {package_name} does not have MCP dependency, skipping")
            return None

        # Derive module name (tars-mcp-character -> tars_mcp_character)
        module_name = package_name.replace("-", "_")

        # Check if __main__.py exists (required for stdio)
        main_path = package_dir / module_name / "__main__.py"
        if not main_path.exists():
            logger.warning(f"Package {package_name} missing {module_name}/__main__.py entry point")
            return None

        # Extract optional MCP-specific config
        tool_mcp = pyproject.get("tool", {}).get("mcp", {})

        # Build metadata
        metadata = MCPServerMetadata(
            name=package_name,
            source=ServerSource.LOCAL,
            package_path=package_dir,
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
