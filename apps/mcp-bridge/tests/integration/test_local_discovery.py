"""Unit tests for LocalPackageDiscovery."""

from pathlib import Path

import pytest

from mcp_bridge.discovery.base import ServerSource, TransportType
from mcp_bridge.discovery.local_packages import LocalPackageDiscovery


@pytest.fixture
def mock_packages_dir(tmp_path):
    """Create a mock packages directory structure."""
    packages = tmp_path / "packages"
    packages.mkdir()
    return packages


@pytest.fixture
def valid_package_dir(mock_packages_dir):
    """Create a valid tars-mcp-character package structure."""
    pkg_dir = mock_packages_dir / "tars-mcp-character"
    pkg_dir.mkdir()

    # Create module directory
    module_dir = pkg_dir / "tars_mcp_character"
    module_dir.mkdir()

    # Create __main__.py
    (module_dir / "__main__.py").write_text("# Entry point\n")

    # Create pyproject.toml
    pyproject_content = """
[project]
name = "tars-mcp-character"
version = "0.1.1"
description = "TARS character management"
dependencies = [
    "mcp[cli]>=1.16.0",
]

[tool.mcp]
transport = "stdio"
command = "python"
args = ["-m", "tars_mcp_character"]
tools_allowlist = ["adjust_personality_trait", "get_current_traits"]
"""
    (pkg_dir / "pyproject.toml").write_text(pyproject_content)

    return pkg_dir


@pytest.mark.asyncio
async def test_discover_valid_package(valid_package_dir):
    """Test discovering a valid MCP package."""
    discovery = LocalPackageDiscovery(valid_package_dir.parent)
    servers = await discovery.discover()

    assert len(servers) == 1
    server = servers[0]

    assert server.name == "tars-mcp-character"
    assert server.version == "0.1.1"
    assert server.source == ServerSource.LOCAL
    assert server.transport == TransportType.STDIO
    assert server.command == "python"
    assert server.args == ["-m", "tars_mcp_character"]
    assert server.tools_allowlist == ["adjust_personality_trait", "get_current_traits"]
    assert "mcp[cli]>=1.16.0" in server.dependencies


@pytest.mark.asyncio
async def test_discover_missing_pyproject(mock_packages_dir):
    """Test that packages without pyproject.toml are skipped."""
    pkg_dir = mock_packages_dir / "tars-mcp-invalid"
    pkg_dir.mkdir()

    discovery = LocalPackageDiscovery(mock_packages_dir)
    servers = await discovery.discover()

    assert len(servers) == 0


@pytest.mark.asyncio
async def test_discover_missing_mcp_dependency(mock_packages_dir):
    """Test that packages without MCP dependency are skipped."""
    pkg_dir = mock_packages_dir / "tars-mcp-nomcp"
    pkg_dir.mkdir()

    pyproject_content = """
[project]
name = "tars-mcp-nomcp"
version = "1.0.0"
dependencies = ["requests>=2.0.0"]
"""
    (pkg_dir / "pyproject.toml").write_text(pyproject_content)

    discovery = LocalPackageDiscovery(mock_packages_dir)
    servers = await discovery.discover()

    assert len(servers) == 0


@pytest.mark.asyncio
async def test_discover_missing_main_entrypoint(mock_packages_dir):
    """Test that packages without __main__.py are skipped."""
    pkg_dir = mock_packages_dir / "tars-mcp-nomain"
    pkg_dir.mkdir()

    # Create module dir but no __main__.py
    module_dir = pkg_dir / "tars_mcp_nomain"
    module_dir.mkdir()

    pyproject_content = """
[project]
name = "tars-mcp-nomain"
version = "1.0.0"
dependencies = ["mcp[cli]>=1.16.0"]
"""
    (pkg_dir / "pyproject.toml").write_text(pyproject_content)

    discovery = LocalPackageDiscovery(mock_packages_dir)
    servers = await discovery.discover()

    assert len(servers) == 0


@pytest.mark.asyncio
async def test_discover_multiple_packages(mock_packages_dir):
    """Test discovering multiple packages."""
    # Create two valid packages
    for i in range(1, 3):
        pkg_dir = mock_packages_dir / f"tars-mcp-server{i}"
        pkg_dir.mkdir()

        module_dir = pkg_dir / f"tars_mcp_server{i}"
        module_dir.mkdir()
        (module_dir / "__main__.py").write_text("# Entry\n")

        pyproject_content = f"""
[project]
name = "tars-mcp-server{i}"
version = "1.0.{i}"
dependencies = ["mcp[cli]>=1.16.0"]
"""
        (pkg_dir / "pyproject.toml").write_text(pyproject_content)

    discovery = LocalPackageDiscovery(mock_packages_dir)
    servers = await discovery.discover()

    assert len(servers) == 2
    assert {s.name for s in servers} == {"tars-mcp-server1", "tars-mcp-server2"}


@pytest.mark.asyncio
async def test_discover_nonexistent_directory():
    """Test handling of nonexistent packages directory."""
    discovery = LocalPackageDiscovery(Path("/nonexistent/path"))
    servers = await discovery.discover()

    assert len(servers) == 0


@pytest.mark.asyncio
async def test_module_name_derivation(mock_packages_dir):
    """Test that module names are correctly derived from package names."""
    pkg_dir = mock_packages_dir / "tars-mcp-my-custom-server"
    pkg_dir.mkdir()

    module_dir = pkg_dir / "tars_mcp_my_custom_server"
    module_dir.mkdir()
    (module_dir / "__main__.py").write_text("# Entry\n")

    pyproject_content = """
[project]
name = "tars-mcp-my-custom-server"
version = "1.0.0"
dependencies = ["mcp[cli]>=1.16.0"]
"""
    (pkg_dir / "pyproject.toml").write_text(pyproject_content)

    discovery = LocalPackageDiscovery(mock_packages_dir)
    servers = await discovery.discover()

    assert len(servers) == 1
    assert servers[0].args == ["-m", "tars_mcp_my_custom_server"]
