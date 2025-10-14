"""Configuration generator for MCP servers.

Converts discovered and installed server metadata into configuration structure
suitable for JSON serialization and consumption by llm-worker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ..discovery.base import MCPServerMetadata
from ..installation.service import InstallationResult, InstallationSummary


@dataclass
class ServerConfig:
    """Configuration for a single MCP server.

    This is the structure written to mcp-servers.json for llm-worker to consume.

    Attributes:
        name: Server name
        source: Discovery source (local_package, extension, external_config)
        transport: Transport type (stdio, http)
        command: Command to execute server
        args: Command arguments
        env: Environment variables
        allowed_tools: List of allowed tool names (None = all allowed)
        package_name: Package name if applicable
        installed: Whether package was installed
        install_path: Path where package was installed (for local/extension)
        url: URL for HTTP transport servers
    """

    name: str
    source: str
    transport: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    allowed_tools: list[str] | None = None
    package_name: str | None = None
    installed: bool = False
    install_path: str | None = None
    url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict representation suitable for JSON
        """
        return {
            "name": self.name,
            "source": self.source,
            "transport": self.transport,
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "allowed_tools": self.allowed_tools,
            "package_name": self.package_name,
            "installed": self.installed,
            "install_path": self.install_path,
            "url": self.url,
        }

    @classmethod
    def from_metadata(
        cls,
        metadata: MCPServerMetadata,
        installation_result: InstallationResult | None = None,
    ) -> ServerConfig:
        """Create ServerConfig from MCPServerMetadata and installation result.

        Args:
            metadata: Server metadata from discovery
            installation_result: Installation result if package was installed

        Returns:
            ServerConfig instance
        """
        # Determine if installed
        installed = False
        install_path = None
        if installation_result:
            installed = installation_result.status.value in ["installed", "already_installed"]
            if installed and metadata.package_path:
                install_path = str(metadata.package_path)

        # HTTP transport servers don't use command/args
        is_http = metadata.transport.value == "http"

        return cls(
            name=metadata.name,
            source=metadata.source.value,
            transport=metadata.transport.value,
            command=None if is_http else metadata.command,
            args=[] if is_http else (metadata.args or []),
            env=metadata.env or {},
            allowed_tools=metadata.tools_allowlist,
            package_name=metadata.package_name,
            installed=installed,
            install_path=install_path,
            url=metadata.url,
        )


@dataclass
class GeneratedConfig:
    """Complete generated configuration file structure.

    Attributes:
        version: Config format version
        generated_at: ISO 8601 timestamp of generation
        servers: List of server configurations
        discovery_summary: Summary of discovery phase
        installation_summary: Summary of installation phase
    """

    version: int
    generated_at: str
    servers: list[ServerConfig]
    discovery_summary: dict[str, Any]
    installation_summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict representation suitable for JSON
        """
        return {
            "version": self.version,
            "generated_at": self.generated_at,
            "servers": [s.to_dict() for s in self.servers],
            "discovery_summary": self.discovery_summary,
            "installation_summary": self.installation_summary,
        }


class ConfigGenerator:
    """Generates MCP server configuration from discovery and installation results.

    Takes discovered servers and installation results, produces a structured
    configuration that llm-worker can consume to connect to MCP servers at runtime.
    """

    def __init__(self, version: int = 1) -> None:
        """Initialize config generator.

        Args:
            version: Config format version (default: 1)
        """
        self.version = version

    def generate(
        self,
        discovered_servers: list[MCPServerMetadata],
        installation_summary: InstallationSummary | None = None,
    ) -> GeneratedConfig:
        """Generate complete configuration from discovery and installation results.

        Args:
            discovered_servers: List of discovered servers
            installation_summary: Installation results (optional)

        Returns:
            Complete generated configuration
        """
        # Build installation results map
        installation_map: dict[str, InstallationResult] = {}
        if installation_summary:
            for result in installation_summary.results:
                installation_map[result.server_name] = result

        # Convert each server to ServerConfig
        server_configs = []
        for server in discovered_servers:
            install_result = installation_map.get(server.name)
            config = ServerConfig.from_metadata(server, install_result)
            server_configs.append(config)

        # Build discovery summary
        discovery_summary = self._build_discovery_summary(discovered_servers)

        # Build installation summary
        install_summary_dict = self._build_installation_summary(installation_summary)

        # Get current timestamp in ISO 8601 format
        generated_at = datetime.now(UTC).isoformat()

        return GeneratedConfig(
            version=self.version,
            generated_at=generated_at,
            servers=server_configs,
            discovery_summary=discovery_summary,
            installation_summary=install_summary_dict,
        )

    def _build_discovery_summary(self, servers: list[MCPServerMetadata]) -> dict[str, Any]:
        """Build discovery phase summary.

        Args:
            servers: List of discovered servers

        Returns:
            Discovery summary dict
        """
        sources: dict[str, int] = {}
        for server in servers:
            source = server.source
            sources[source] = sources.get(source, 0) + 1

        return {
            "total_servers": len(servers),
            "sources": sources,
        }

    def _build_installation_summary(self, installation_summary: InstallationSummary | None) -> dict[str, Any]:
        """Build installation phase summary.

        Args:
            installation_summary: Installation results

        Returns:
            Installation summary dict
        """
        if not installation_summary:
            return {
                "total_servers": 0,
                "installed": 0,
                "already_installed": 0,
                "failed": 0,
                "skipped": 0,
                "success_rate": 0.0,
                "duration_sec": 0.0,
            }

        return {
            "total_servers": installation_summary.total_servers,
            "installed": installation_summary.installed,
            "already_installed": installation_summary.already_installed,
            "failed": installation_summary.failed,
            "skipped": installation_summary.skipped,
            "success_rate": installation_summary.success_rate,
            "duration_sec": installation_summary.total_duration_sec,
        }
