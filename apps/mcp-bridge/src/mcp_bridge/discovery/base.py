"""Base dataclasses and types for MCP server discovery."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ServerSource(str, Enum):
    """Source of server discovery."""

    LOCAL = "local"  # packages/tars-mcp-*
    EXTENSION = "extension"  # extensions/mcp-servers/*
    EXTERNAL = "external"  # ops/mcp/mcp.server.yml


class TransportType(str, Enum):
    """MCP transport protocol type."""

    STDIO = "stdio"
    HTTP = "http"


@dataclass
class MCPServerMetadata:
    """Metadata for a discovered MCP server.

    This represents a fully validated server configuration that can be
    installed, connected to, and queried for tools.
    """

    # Identity
    name: str
    """Server name (unique identifier)."""

    source: ServerSource
    """Discovery source (local/extension/external)."""

    # Package information
    package_path: Path | None = None
    """Path to package directory (for local/extension sources)."""

    package_name: str | None = None
    """PyPI package name (for external sources requiring pip install)."""

    version: str = "0.0.0"
    """Package version."""

    description: str = ""
    """Human-readable description."""

    # Transport configuration
    transport: TransportType = TransportType.STDIO
    """Transport protocol (stdio or http)."""

    command: str = "python"
    """Command to execute server (for stdio transport)."""

    args: list[str] = field(default_factory=list)
    """Arguments for command (for stdio transport)."""

    url: str | None = None
    """URL for HTTP transport."""

    # Environment and dependencies
    env: dict[str, str] = field(default_factory=dict)
    """Environment variables required by server."""

    env_defaults: dict[str, str] = field(default_factory=dict)
    """Default values for environment variables."""

    dependencies: list[str] = field(default_factory=list)
    """Python package dependencies from pyproject.toml."""

    # Tool filtering
    tools_allowlist: list[str] | None = None
    """Optional whitelist of tool names to expose (None = all tools)."""

    # Metadata flags
    installed: bool = False
    """Whether package is currently installed."""

    validated: bool = False
    """Whether metadata has been validated."""

    def __post_init__(self) -> None:
        """Validate metadata after initialization."""
        # Ensure Path objects
        if self.package_path and not isinstance(self.package_path, Path):
            self.package_path = Path(self.package_path)

        # Stdio transport requires command and args
        if self.transport == TransportType.STDIO:
            if not self.command:
                raise ValueError(f"Server {self.name}: stdio transport requires command")

        # HTTP transport requires URL
        if self.transport == TransportType.HTTP:
            if not self.url:
                raise ValueError(f"Server {self.name}: http transport requires url")

        # Note: External sources can override discovered servers, so package_name/path
        # is optional (will be filled in during merge if overriding a discovered server)

    def get_module_name(self) -> str:
        """Derive Python module name from package name.

        Examples:
            tars-mcp-character -> tars_mcp_character
            my-custom-server -> my_custom_server
        """
        if self.package_name:
            return self.package_name.replace("-", "_")
        elif self.package_path:
            return self.package_path.name.replace("-", "_")
        return self.name.replace("-", "_")

    def get_install_target(self) -> str:
        """Get the target for pip install.

        Returns:
            - Editable path for local/extension: "-e /path/to/package"
            - Package name for external: "package-name"
        """
        if self.package_path:
            return str(self.package_path)
        elif self.package_name:
            return self.package_name
        raise ValueError(f"Server {self.name}: no install target (no package_path or package_name)")

    def is_editable_install(self) -> bool:
        """Check if this should be an editable install."""
        return self.source in (ServerSource.LOCAL, ServerSource.EXTENSION) and self.package_path is not None

    def __str__(self) -> str:
        """Human-readable representation."""
        parts = [
            f"{self.name} v{self.version}",
            f"source={self.source.value}",
            f"transport={self.transport.value}",
        ]
        if self.package_path:
            parts.append(f"path={self.package_path.name}")
        elif self.package_name:
            parts.append(f"package={self.package_name}")
        if self.tools_allowlist:
            parts.append(f"tools={len(self.tools_allowlist)}")
        return f"MCPServer({', '.join(parts)})"
