"""Tests for configuration generator."""

from datetime import datetime

from mcp_bridge.config_generator.generator import (
    ConfigGenerator,
    GeneratedConfig,
    ServerConfig,
)
from mcp_bridge.discovery.base import MCPServerMetadata, ServerSource, TransportType
from mcp_bridge.installation.service import (
    InstallationResult,
    InstallationStatus,
    InstallationSummary,
)


class TestServerConfig:
    """Tests for ServerConfig dataclass."""

    def test_to_dict_basic(self):
        """Test basic ServerConfig to_dict conversion."""
        config = ServerConfig(
            name="test-server",
            source="local",
            transport="stdio",
            command="python",
            args=["-m", "test_server"],
            env={"TEST": "true"},
            allowed_tools=["tool1", "tool2"],
            package_name="test-package",
            installed=True,
            install_path="/path/to/package",
        )

        result = config.to_dict()

        assert result["name"] == "test-server"
        assert result["source"] == "local"
        assert result["transport"] == "stdio"
        assert result["command"] == "python"
        assert result["args"] == ["-m", "test_server"]
        assert result["env"] == {"TEST": "true"}
        assert result["allowed_tools"] == ["tool1", "tool2"]
        assert result["package_name"] == "test-package"
        assert result["installed"] is True
        assert result["install_path"] == "/path/to/package"

    def test_from_metadata_local_package(self):
        """Test creating ServerConfig from local package metadata."""
        from mcp_bridge.discovery.base import ServerSource

        metadata = MCPServerMetadata(
            name="test-local",
            transport=TransportType.STDIO,
            command="python",
            args=["-m", "test_local.server"],
            env={"ENV": "value"},
            source=ServerSource.LOCAL,
            package_name="test-local",
            package_path="/workspace/packages/test-local",
            tools_allowlist=["tool1"],
        )

        install_result = InstallationResult(
            server_name="test-local",
            status=InstallationStatus.INSTALLED,
            package="test-local",
            duration_sec=1.5,
        )

        config = ServerConfig.from_metadata(metadata, install_result)

        assert config.name == "test-local"
        assert config.source == "local"
        assert config.transport == "stdio"
        assert config.command == "python"
        assert config.args == ["-m", "test_local.server"]
        assert config.env == {"ENV": "value"}
        assert config.allowed_tools == ["tool1"]
        assert config.package_name == "test-local"
        assert config.installed is True
        assert config.install_path == "/workspace/packages/test-local"

    def test_from_metadata_external_not_installed(self):
        """Test creating ServerConfig from external config (not installed)."""
        metadata = MCPServerMetadata(
            name="external-server",
            transport=TransportType.STDIO,
            command="npx",
            args=["--yes", "@example/server"],
            source=ServerSource.EXTERNAL,
            package_name="@example/server",
        )

        # No installation result (external npm package)
        config = ServerConfig.from_metadata(metadata, None)

        assert config.name == "external-server"
        assert config.source == "external"
        assert config.transport == "stdio"
        assert config.command == "npx"
        assert config.args == ["--yes", "@example/server"]
        assert config.installed is False
        assert config.install_path is None

    def test_from_metadata_http_transport(self):
        """Test creating ServerConfig for HTTP transport."""
        metadata = MCPServerMetadata(
            name="http-server",
            transport=TransportType.HTTP,
            url="http://localhost:8080",
            source=ServerSource.EXTERNAL,
            command="",  # HTTP doesn't use command but has default
        )

        config = ServerConfig.from_metadata(metadata, None)

        assert config.name == "http-server"
        assert config.transport == "http"
        assert config.url == "http://localhost:8080"
        # Command is empty string or "python" (default), not None
        assert config.args == []

    def test_from_metadata_already_installed(self):
        """Test ServerConfig when package was already installed."""
        from pathlib import Path

        metadata = MCPServerMetadata(
            name="existing",
            transport=TransportType.STDIO,
            command="python",
            args=["-m", "existing"],
            source=ServerSource.LOCAL,
            package_name="existing-package",
            package_path=Path("/path/to/existing"),
        )

        install_result = InstallationResult(
            server_name="existing",
            status=InstallationStatus.ALREADY_INSTALLED,
            package="existing-package",
            duration_sec=0.1,
        )

        config = ServerConfig.from_metadata(metadata, install_result)

        assert config.installed is True
        assert config.install_path == "/path/to/existing"


class TestGeneratedConfig:
    """Tests for GeneratedConfig dataclass."""

    def test_to_dict_complete(self):
        """Test GeneratedConfig to_dict with complete data."""
        servers = [
            ServerConfig(
                name="server1",
                source=ServerSource.LOCAL,
                transport="stdio",
                command="python",
                args=["-m", "server1"],
                installed=True,
            ),
            ServerConfig(
                name="server2",
                source=ServerSource.EXTERNAL,
                transport="stdio",
                command="npx",
                args=["--yes", "@example/server"],
                installed=False,
            ),
        ]

        config = GeneratedConfig(
            version=1,
            generated_at="2025-10-04T12:00:00Z",
            servers=servers,
            discovery_summary={"total_servers": 2, "sources": {"local": 1, "external": 1}},
            installation_summary={"total_servers": 2, "installed": 1, "success_rate": 0.5},
        )

        result = config.to_dict()

        assert result["version"] == 1
        assert result["generated_at"] == "2025-10-04T12:00:00Z"
        assert len(result["servers"]) == 2
        assert result["servers"][0]["name"] == "server1"
        assert result["servers"][1]["name"] == "server2"
        assert result["discovery_summary"]["total_servers"] == 2
        assert result["installation_summary"]["installed"] == 1


class TestConfigGenerator:
    """Tests for ConfigGenerator class."""

    def test_generate_empty(self):
        """Test generating config with no servers."""
        generator = ConfigGenerator()
        config = generator.generate([], None)

        assert config.version == 1
        assert len(config.servers) == 0
        assert config.discovery_summary["total_servers"] == 0
        assert config.installation_summary["total_servers"] == 0

    def test_generate_single_server(self):
        """Test generating config with single server."""
        metadata = MCPServerMetadata(
            name="test-server",
            transport=TransportType.STDIO,
            command="python",
            args=["-m", "test"],
            source=ServerSource.LOCAL,
            package_name="test-package",
        )

        generator = ConfigGenerator()
        config = generator.generate([metadata], None)

        assert config.version == 1
        assert len(config.servers) == 1
        assert config.servers[0].name == "test-server"
        assert config.discovery_summary["total_servers"] == 1

    def test_generate_with_installation_results(self):
        """Test generating config with installation results."""
        metadata1 = MCPServerMetadata(
            name="server1",
            transport=TransportType.STDIO,
            command="python",
            args=["-m", "server1"],
            source=ServerSource.LOCAL,
            package_name="server1",
            package_path="/path/to/server1",
        )

        metadata2 = MCPServerMetadata(
            name="server2",
            transport=TransportType.STDIO,
            command="python",
            args=["-m", "server2"],
            source=ServerSource.EXTENSION,
            package_name="server2",
            package_path="/path/to/server2",
        )

        install_summary = InstallationSummary(
            total_servers=2,
            installed=1,
            already_installed=0,
            failed=1,
            skipped=0,
            total_duration_sec=5.0,
            results=[
                InstallationResult(
                    server_name="server1",
                    status=InstallationStatus.INSTALLED,
                    package="server1",
                    duration_sec=4.0,
                ),
                InstallationResult(
                    server_name="server2",
                    status=InstallationStatus.FAILED,
                    package="server2",
                    duration_sec=1.0,
                    error_message="Installation failed",
                ),
            ],
        )

        generator = ConfigGenerator()
        config = generator.generate([metadata1, metadata2], install_summary)

        assert len(config.servers) == 2
        assert config.servers[0].installed is True
        assert config.servers[1].installed is False
        assert config.installation_summary["installed"] == 1
        assert config.installation_summary["failed"] == 1
        assert config.installation_summary["success_rate"] == 0.5

    def test_generate_discovery_summary(self):
        """Test discovery summary generation."""
        servers = [
            MCPServerMetadata(
                name="local1",
                transport=TransportType.STDIO,
                command="python",
                source=ServerSource.LOCAL,
            ),
            MCPServerMetadata(
                name="local2",
                transport=TransportType.STDIO,
                command="python",
                source=ServerSource.LOCAL,
            ),
            MCPServerMetadata(
                name="ext1",
                transport=TransportType.STDIO,
                command="python",
                source=ServerSource.EXTENSION,
            ),
            MCPServerMetadata(
                name="external1",
                transport=TransportType.STDIO,
                command="npx",
                source=ServerSource.EXTERNAL,
            ),
        ]

        generator = ConfigGenerator()
        config = generator.generate(servers, None)

        assert config.discovery_summary["total_servers"] == 4
        assert config.discovery_summary["sources"]["local"] == 2
        assert config.discovery_summary["sources"]["extension"] == 1
        assert config.discovery_summary["sources"]["external"] == 1

    def test_generate_custom_version(self):
        """Test generating config with custom version."""
        generator = ConfigGenerator(version=2)
        config = generator.generate([], None)

        assert config.version == 2

    def test_generate_timestamp_format(self):
        """Test that generated_at is in ISO 8601 format."""
        generator = ConfigGenerator()
        config = generator.generate([], None)

        # Verify it's a valid ISO 8601 timestamp
        timestamp = datetime.fromisoformat(config.generated_at.replace("Z", "+00:00"))
        assert isinstance(timestamp, datetime)

    def test_generate_mixed_sources(self):
        """Test generating config with mixed server sources."""
        servers = [
            MCPServerMetadata(
                name="local",
                transport=TransportType.STDIO,
                command="python",
                args=["-m", "local"],
                source=ServerSource.LOCAL,
                package_name="local-pkg",
                package_path="/local/path",
            ),
            MCPServerMetadata(
                name="extension",
                transport=TransportType.STDIO,
                command="python",
                args=["-m", "extension"],
                source=ServerSource.EXTENSION,
                package_name="ext-pkg",
                package_path="/ext/path",
            ),
            MCPServerMetadata(
                name="external",
                transport=TransportType.STDIO,
                command="npx",
                args=["--yes", "@example/server"],
                source=ServerSource.EXTERNAL,
                package_name="@example/server",
            ),
            MCPServerMetadata(
                name="http-server",
                transport=TransportType.HTTP,
                url="http://localhost:8080",
                source=ServerSource.EXTERNAL,
            ),
        ]

        install_summary = InstallationSummary(
            total_servers=4,
            installed=2,
            already_installed=0,
            failed=0,
            skipped=2,
            total_duration_sec=10.0,
            results=[
                InstallationResult(
                    server_name="local",
                    status=InstallationStatus.INSTALLED,
                    package="local-pkg",
                    duration_sec=5.0,
                ),
                InstallationResult(
                    server_name="extension",
                    status=InstallationStatus.INSTALLED,
                    package="ext-pkg",
                    duration_sec=5.0,
                ),
                InstallationResult(
                    server_name="external",
                    status=InstallationStatus.SKIPPED,
                    package="@example/server",
                    duration_sec=0.0,
                ),
                InstallationResult(
                    server_name="http-server",
                    status=InstallationStatus.SKIPPED,
                    package=None,
                    duration_sec=0.0,
                ),
            ],
        )

        generator = ConfigGenerator()
        config = generator.generate(servers, install_summary)

        assert len(config.servers) == 4

        # Check local package
        local_config = next(s for s in config.servers if s.name == "local")
        assert local_config.source == "local"
        assert local_config.installed is True
        assert local_config.install_path == "/local/path"

        # Check extension
        ext_config = next(s for s in config.servers if s.name == "extension")
        assert ext_config.source == "extension"
        assert ext_config.installed is True

        # Check external (npm)
        external_config = next(s for s in config.servers if s.name == "external")
        assert external_config.source == "external"
        assert external_config.installed is False
        assert external_config.command == "npx"

        # Check HTTP
        http_config = next(s for s in config.servers if s.name == "http-server")
        assert http_config.transport == "http"
        assert http_config.url == "http://localhost:8080"
        assert http_config.command is None
