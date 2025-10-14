"""Unit tests for MCPServerMetadata dataclass."""

from pathlib import Path

import pytest

from mcp_bridge.discovery.base import (
    MCPServerMetadata,
    ServerSource,
    TransportType,
)


def test_metadata_basic_creation():
    """Test creating basic server metadata."""
    metadata = MCPServerMetadata(
        name="test-server",
        source=ServerSource.LOCAL,
        command="python",
        args=["-m", "test_server"],
    )

    assert metadata.name == "test-server"
    assert metadata.source == ServerSource.LOCAL
    assert metadata.command == "python"
    assert metadata.args == ["-m", "test_server"]
    assert metadata.transport == TransportType.STDIO
    assert metadata.version == "0.0.0"


def test_metadata_with_package_path():
    """Test metadata with package path."""
    package_path = Path("/workspace/packages/tars-mcp-character")

    metadata = MCPServerMetadata(
        name="tars-mcp-character",
        source=ServerSource.LOCAL,
        package_path=package_path,
        version="0.1.1",
        command="python",
        args=["-m", "tars_mcp_character"],
    )

    assert metadata.package_path == package_path
    assert metadata.get_module_name() == "tars_mcp_character"
    assert metadata.is_editable_install() is True


def test_metadata_http_transport():
    """Test HTTP transport validation."""
    metadata = MCPServerMetadata(
        name="http-server",
        source=ServerSource.EXTERNAL,
        transport=TransportType.HTTP,
        url="http://localhost:8080/mcp",
    )

    assert metadata.transport == TransportType.HTTP
    assert metadata.url == "http://localhost:8080/mcp"


def test_metadata_http_missing_url_fails():
    """Test that HTTP transport without URL raises error."""
    with pytest.raises(ValueError, match="http transport requires url"):
        MCPServerMetadata(
            name="broken-http",
            source=ServerSource.EXTERNAL,
            transport=TransportType.HTTP,
            # Missing url!
        )


def test_metadata_stdio_missing_command_fails():
    """Test that stdio transport without command raises error."""
    with pytest.raises(ValueError, match="stdio transport requires command"):
        MCPServerMetadata(
            name="broken-stdio",
            source=ServerSource.EXTERNAL,
            command="",  # Empty command
        )


def test_metadata_external_missing_install_target_succeeds():
    """Test that external server without install target is allowed (for overrides)."""
    # This is valid - external config can override discovered servers
    metadata = MCPServerMetadata(
        name="override-external",
        source=ServerSource.EXTERNAL,
        command="python",
        args=["-m", "some_module"],
        # Missing both package_name and package_path - OK for overrides
    )

    assert metadata.name == "override-external"
    assert metadata.source == ServerSource.EXTERNAL


def test_get_module_name():
    """Test module name derivation."""
    metadata = MCPServerMetadata(
        name="test-server",
        source=ServerSource.LOCAL,
        package_name="my-custom-server",
        command="python",
    )

    assert metadata.get_module_name() == "my_custom_server"


def test_get_install_target_editable():
    """Test install target for editable install."""
    package_path = Path("/workspace/packages/test-server")

    metadata = MCPServerMetadata(
        name="test-server",
        source=ServerSource.LOCAL,
        package_path=package_path,
        command="python",
    )

    assert metadata.get_install_target() == str(package_path)
    assert metadata.is_editable_install() is True


def test_get_install_target_pypi():
    """Test install target for PyPI package."""
    metadata = MCPServerMetadata(
        name="test-server",
        source=ServerSource.EXTERNAL,
        package_name="mcp-server-test",
        command="python",
    )

    assert metadata.get_install_target() == "mcp-server-test"
    assert metadata.is_editable_install() is False


def test_metadata_with_env_vars():
    """Test metadata with environment variables."""
    metadata = MCPServerMetadata(
        name="test-server",
        source=ServerSource.EXTERNAL,
        package_name="test-pkg",
        command="python",
        env={"API_KEY": "secret", "CONFIG_PATH": "/etc/config"},
        env_defaults={"CONFIG_PATH": "/etc/config"},
    )

    assert metadata.env["API_KEY"] == "secret"
    assert metadata.env_defaults["CONFIG_PATH"] == "/etc/config"


def test_metadata_with_tools_allowlist():
    """Test metadata with tool allowlist."""
    metadata = MCPServerMetadata(
        name="test-server",
        source=ServerSource.LOCAL,
        package_name="test-pkg",
        command="python",
        tools_allowlist=["tool1", "tool2", "tool3"],
    )

    assert metadata.tools_allowlist == ["tool1", "tool2", "tool3"]


def test_metadata_string_representation():
    """Test string representation of metadata."""
    metadata = MCPServerMetadata(
        name="test-server",
        source=ServerSource.LOCAL,
        package_name="test-pkg",
        version="1.0.0",
        command="python",
        tools_allowlist=["tool1", "tool2"],
    )

    str_repr = str(metadata)
    assert "test-server" in str_repr
    assert "v1.0.0" in str_repr
    assert "source=local" in str_repr
    assert "transport=stdio" in str_repr
    assert "tools=2" in str_repr


def test_metadata_path_conversion():
    """Test that string paths are converted to Path objects."""
    metadata = MCPServerMetadata(
        name="test-server",
        source=ServerSource.LOCAL,
        package_path="/workspace/packages/test",  # String path
        command="python",
    )

    assert isinstance(metadata.package_path, Path)
    assert metadata.package_path == Path("/workspace/packages/test")
