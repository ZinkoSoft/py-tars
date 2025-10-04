"""Integration tests for ServerDiscoveryService."""

import pytest
from pathlib import Path

from mcp_bridge.discovery.service import ServerDiscoveryService
from mcp_bridge.discovery.base import ServerSource


@pytest.fixture
def test_workspace(tmp_path):
    """Create a complete test workspace structure."""
    # Create packages directory with tars-mcp-character
    packages = tmp_path / "packages"
    packages.mkdir()
    
    char_pkg = packages / "tars-mcp-character"
    char_pkg.mkdir()
    char_module = char_pkg / "tars_mcp_character"
    char_module.mkdir()
    (char_module / "__main__.py").write_text("# Character server\n")
    
    (char_pkg / "pyproject.toml").write_text("""
[project]
name = "tars-mcp-character"
version = "0.1.1"
description = "Character management"
dependencies = ["mcp[cli]>=1.16.0"]
""")
    
    # Create extensions directory with custom server
    extensions = tmp_path / "extensions" / "mcp-servers"
    extensions.mkdir(parents=True)
    
    custom_pkg = extensions / "custom-server"
    custom_pkg.mkdir()
    custom_module = custom_pkg / "custom_server"
    custom_module.mkdir()
    (custom_module / "__main__.py").write_text("# Custom server\n")
    
    (custom_pkg / "pyproject.toml").write_text("""
[project]
name = "custom-server"
version = "1.0.0"
dependencies = ["mcp[cli]>=1.16.0"]
""")
    
    # Create external config
    ops = tmp_path / "ops" / "mcp"
    ops.mkdir(parents=True)
    
    (ops / "mcp.server.yml").write_text("""
servers:
  - name: external-server
    transport: stdio
    package: "mcp-server-external"
    command: "python"
    args: ["-m", "mcp_server_external"]
    env:
      API_KEY: "test-key"
""")
    
    return tmp_path


@pytest.mark.asyncio
async def test_discover_all_sources(test_workspace):
    """Test discovering from all sources."""
    service = ServerDiscoveryService(workspace_root=test_workspace)
    servers = await service.discover_all()
    
    # Should have 3 servers: local + extension + external
    assert len(servers) == 3
    
    server_names = {s.name for s in servers}
    assert "tars-mcp-character" in server_names
    assert "custom-server" in server_names
    assert "external-server" in server_names
    
    # Check sources
    sources = {s.name: s.source for s in servers}
    assert sources["tars-mcp-character"] == ServerSource.LOCAL
    assert sources["custom-server"] == ServerSource.EXTENSION
    assert sources["external-server"] == ServerSource.EXTERNAL


@pytest.mark.asyncio
async def test_discover_by_source_local(test_workspace):
    """Test discovering only local packages."""
    service = ServerDiscoveryService(workspace_root=test_workspace)
    servers = await service.discover_by_source(ServerSource.LOCAL)
    
    assert len(servers) == 1
    assert servers[0].name == "tars-mcp-character"
    assert servers[0].source == ServerSource.LOCAL


@pytest.mark.asyncio
async def test_discover_by_source_extension(test_workspace):
    """Test discovering only extensions."""
    service = ServerDiscoveryService(workspace_root=test_workspace)
    servers = await service.discover_by_source(ServerSource.EXTENSION)
    
    assert len(servers) == 1
    assert servers[0].name == "custom-server"
    assert servers[0].source == ServerSource.EXTENSION


@pytest.mark.asyncio
async def test_discover_by_source_external(test_workspace):
    """Test discovering only external config."""
    service = ServerDiscoveryService(workspace_root=test_workspace)
    servers = await service.discover_by_source(ServerSource.EXTERNAL)
    
    assert len(servers) == 1
    assert servers[0].name == "external-server"
    assert servers[0].source == ServerSource.EXTERNAL


@pytest.mark.asyncio
async def test_duplicate_server_deduplication(tmp_path):
    """Test that duplicate server names are handled correctly."""
    # Create two servers with same name in different sources
    packages = tmp_path / "packages"
    packages.mkdir()
    
    pkg1 = packages / "tars-mcp-test"
    pkg1.mkdir()
    module1 = pkg1 / "tars_mcp_test"
    module1.mkdir()
    (module1 / "__main__.py").write_text("# Test 1\n")
    (pkg1 / "pyproject.toml").write_text("""
[project]
name = "tars-mcp-test"
version = "1.0.0"
dependencies = ["mcp[cli]>=1.16.0"]
""")
    
    extensions = tmp_path / "extensions" / "mcp-servers"
    extensions.mkdir(parents=True)
    
    pkg2 = extensions / "tars-mcp-test"
    pkg2.mkdir()
    module2 = pkg2 / "tars_mcp_test"
    module2.mkdir()
    (module2 / "__main__.py").write_text("# Test 2\n")
    (pkg2 / "pyproject.toml").write_text("""
[project]
name = "tars-mcp-test"
version = "2.0.0"
dependencies = ["mcp[cli]>=1.16.0"]
""")
    
    service = ServerDiscoveryService(workspace_root=tmp_path)
    servers = await service.discover_all()
    
    # Should only have one server (first wins)
    assert len(servers) == 1
    assert servers[0].name == "tars-mcp-test"
    # Local packages are discovered first, so should win
    assert servers[0].version == "1.0.0"


@pytest.mark.asyncio
async def test_external_config_overrides_discovered(tmp_path):
    """Test that external config overrides discovered servers."""
    # Create local package
    packages = tmp_path / "packages"
    packages.mkdir()
    
    pkg = packages / "tars-mcp-override"
    pkg.mkdir()
    module = pkg / "tars_mcp_override"
    module.mkdir()
    (module / "__main__.py").write_text("# Original\n")
    (pkg / "pyproject.toml").write_text("""
[project]
name = "tars-mcp-override"
version = "1.0.0"
dependencies = ["mcp[cli]>=1.16.0"]
""")
    
    # Create external config that overrides it
    ops = tmp_path / "ops" / "mcp"
    ops.mkdir(parents=True)
    (ops / "mcp.server.yml").write_text("""
servers:
  - name: tars-mcp-override
    transport: stdio
    command: "python"
    args: ["-m", "tars_mcp_override"]
    tools_allowlist: ["only_this_tool"]
""")
    
    service = ServerDiscoveryService(workspace_root=tmp_path)
    servers = await service.discover_all()
    
    assert len(servers) == 1
    server = servers[0]
    
    # External config should override
    assert server.source == ServerSource.EXTERNAL
    assert server.tools_allowlist == ["only_this_tool"]
    # But should keep package_path from discovered
    assert server.package_path == pkg
