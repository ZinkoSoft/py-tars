"""Shared pytest fixtures for mcp-bridge tests."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """Provide a temporary workspace root directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


@pytest.fixture
def packages_path(workspace_root: Path) -> Path:
    """Provide a packages directory for local MCP server discovery."""
    packages = workspace_root / "packages"
    packages.mkdir()
    return packages


@pytest.fixture
def extensions_path(workspace_root: Path) -> Path:
    """Provide an extensions directory for MCP server discovery."""
    extensions = workspace_root / "extensions" / "mcp-servers"
    extensions.mkdir(parents=True)
    return extensions


@pytest.fixture
def config_path(workspace_root: Path) -> Path:
    """Provide a config file path for external MCP server configuration."""
    config_dir = workspace_root / "ops" / "mcp"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "mcp.server.yml"
    return config_file


@pytest.fixture
def output_dir(workspace_root: Path) -> Path:
    """Provide an output directory for generated config files."""
    output = workspace_root / "config"
    output.mkdir()
    return output


@pytest.fixture
def mock_pip_installer():
    """Provide a mock PipInstaller for testing."""
    installer = Mock()
    installer.install = AsyncMock(return_value=True)
    installer.is_installed = Mock(return_value=False)
    return installer


@pytest.fixture
def sample_server_metadata() -> dict:
    """Provide sample MCP server metadata for testing."""
    return {
        "name": "test-server",
        "version": "1.0.0",
        "description": "Test MCP server",
        "command": "test-server",
        "args": [],
        "env": {},
        "install_spec": "test-server>=1.0.0",
    }
