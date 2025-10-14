"""End-to-end tests for complete MCP bridge pipeline.

Tests the full workflow: Discovery → Installation → Config Generation → Exit
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add parent directory to path to import mcp_bridge.main
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_bridge.main import main


@pytest.mark.asyncio
async def test_e2e_pipeline_with_local_package(tmp_path):
    """Test complete pipeline with a real local package (tars-mcp-character)."""
    # Setup: Create a fake workspace structure
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    packages_dir = workspace_root / "packages"
    packages_dir.mkdir()

    config_dir = workspace_root / "config"
    config_dir.mkdir()

    # Point to real tars-mcp-character package
    # Path: tests/test_e2e_pipeline.py -> tests -> apps/mcp-bridge -> apps -> py-tars
    repo_root = Path(__file__).parent.parent.parent.parent
    real_char_package = repo_root / "packages" / "tars-mcp-character"

    if not real_char_package.exists():
        pytest.skip("tars-mcp-character package not found")

    # Create symlink to real package (absolute path symlink)
    try:
        (packages_dir / "tars-mcp-character").symlink_to(real_char_package.absolute(), target_is_directory=True)
    except (OSError, NotImplementedError):
        # Fallback: just test with empty packages (CI/Windows compatibility)
        pytest.skip("Cannot create symlink to real package")

    # Set environment variables
    env_vars = {
        "WORKSPACE_ROOT": str(workspace_root),
        "MCP_LOCAL_PACKAGES_PATH": str(packages_dir),
        "MCP_EXTENSIONS_PATH": str(workspace_root / "extensions"),
        "MCP_SERVERS_YAML": str(workspace_root / "mcp.server.yml"),
        "MCP_OUTPUT_DIR": str(config_dir),
        "MCP_CONFIG_FILENAME": "mcp-servers.json",
    }

    with patch.dict(os.environ, env_vars):
        # Run the complete pipeline
        exit_code = await main()

    # Verify exit code (0 = success, even if some packages already installed)
    assert exit_code == 0, "Pipeline should succeed"

    # Verify config file was created
    config_file = config_dir / "mcp-servers.json"
    assert config_file.exists(), "Config file should be created"

    # Verify config file is valid JSON
    with open(config_file) as f:
        config = json.load(f)

    # Verify config structure
    assert "version" in config
    assert config["version"] == 1

    assert "generated_at" in config
    assert "servers" in config
    assert "discovery_summary" in config
    assert "installation_summary" in config

    # Verify at least one server was discovered
    assert len(config["servers"]) > 0, "Should discover at least tars-mcp-character"

    # Verify tars-mcp-character is in the config
    server_names = [s["name"] for s in config["servers"]]
    assert "tars-mcp-character" in server_names, "Should discover tars-mcp-character"

    # Verify server has correct structure
    character_server = next(s for s in config["servers"] if s["name"] == "tars-mcp-character")
    assert character_server["source"] == "local"
    assert character_server["transport"] == "stdio"
    assert character_server["command"] == "python"
    assert "-m" in character_server["args"]
    assert character_server["package_name"] == "tars-mcp-character"

    # Verify installation summary
    install_summary = config["installation_summary"]
    assert install_summary["total_servers"] > 0
    assert install_summary["success_rate"] >= 0.0
    assert install_summary["success_rate"] <= 1.0


@pytest.mark.asyncio
async def test_e2e_pipeline_no_servers_found(tmp_path):
    """Test pipeline with no servers discovered."""
    # Setup: Empty workspace
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    (workspace_root / "packages").mkdir()
    (workspace_root / "extensions").mkdir()
    (workspace_root / "config").mkdir()

    env_vars = {
        "WORKSPACE_ROOT": str(workspace_root),
        "MCP_LOCAL_PACKAGES_PATH": str(workspace_root / "packages"),
        "MCP_EXTENSIONS_PATH": str(workspace_root / "extensions"),
        "MCP_SERVERS_YAML": str(workspace_root / "mcp.server.yml"),
        "MCP_OUTPUT_DIR": str(workspace_root / "config"),
    }

    with patch.dict(os.environ, env_vars):
        exit_code = await main()

    # Should exit with success (nothing to do)
    assert exit_code == 0, "Should succeed when no servers found"

    # Config file should NOT be created when no servers discovered
    config_file = workspace_root / "config" / "mcp-servers.json"
    assert not config_file.exists(), "Config file should not be created when no servers found"


@pytest.mark.asyncio
async def test_e2e_pipeline_with_external_config(tmp_path):
    """Test pipeline with external YAML config."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    (workspace_root / "packages").mkdir()
    (workspace_root / "extensions").mkdir()
    config_dir = workspace_root / "config"
    config_dir.mkdir()

    # Create external config YAML
    yaml_config = workspace_root / "mcp.server.yml"
    yaml_content = """
servers:
  - name: example-http-server
    transport: http
    url: http://localhost:8080/mcp
  - name: example-npm-server
    transport: stdio
    command: npx
    args:
      - "--yes"
      - "@example/mcp-server"
    package_name: "@example/mcp-server"
"""
    yaml_config.write_text(yaml_content)

    env_vars = {
        "WORKSPACE_ROOT": str(workspace_root),
        "MCP_LOCAL_PACKAGES_PATH": str(workspace_root / "packages"),
        "MCP_EXTENSIONS_PATH": str(workspace_root / "extensions"),
        "MCP_SERVERS_YAML": str(yaml_config),
        "MCP_OUTPUT_DIR": str(config_dir),
    }

    with patch.dict(os.environ, env_vars):
        exit_code = await main()

    # Should succeed (HTTP servers are skipped, npm servers may fail but won't fail pipeline)
    assert exit_code in [0, 1], "Should exit with valid code"

    # Config file should be created
    config_file = config_dir / "mcp-servers.json"
    assert config_file.exists(), "Config file should be created"

    # Verify servers were discovered
    with open(config_file) as f:
        config = json.load(f)

    assert len(config["servers"]) == 2, "Should discover 2 servers from YAML"

    server_names = [s["name"] for s in config["servers"]]
    assert "example-http-server" in server_names
    assert "example-npm-server" in server_names

    # Verify HTTP server has no command
    http_server = next(s for s in config["servers"] if s["name"] == "example-http-server")
    assert http_server["transport"] == "http"
    assert http_server["command"] is None
    assert http_server["url"] == "http://localhost:8080/mcp"

    # Verify npm server has correct command
    npm_server = next(s for s in config["servers"] if s["name"] == "example-npm-server")
    assert npm_server["transport"] == "stdio"
    assert npm_server["command"] == "npx"
    assert "--yes" in npm_server["args"]


@pytest.mark.asyncio
async def test_e2e_config_output_path_customization(tmp_path):
    """Test that custom output paths work correctly."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    packages_dir = workspace_root / "packages"
    packages_dir.mkdir()

    # Custom output location
    custom_output = tmp_path / "custom_output"
    custom_output.mkdir()

    # Point to real package
    repo_root = Path(__file__).parent.parent.parent.parent
    try:
        (packages_dir / "tars-mcp-character").symlink_to(repo_root / "packages" / "tars-mcp-character")
    except (OSError, NotImplementedError):
        pytest.skip("Cannot create symlink")

    env_vars = {
        "WORKSPACE_ROOT": str(workspace_root),
        "MCP_LOCAL_PACKAGES_PATH": str(packages_dir),
        "MCP_EXTENSIONS_PATH": str(workspace_root / "extensions"),
        "MCP_SERVERS_YAML": str(workspace_root / "mcp.server.yml"),
        "MCP_OUTPUT_DIR": str(custom_output),
        "MCP_CONFIG_FILENAME": "custom-config.json",
    }

    with patch.dict(os.environ, env_vars):
        exit_code = await main()

    assert exit_code == 0

    # Verify custom output path was used
    custom_config = custom_output / "custom-config.json"
    assert custom_config.exists(), "Config should be written to custom path"

    # Verify it's valid JSON
    with open(custom_config) as f:
        config = json.load(f)
    assert len(config["servers"]) > 0


@pytest.mark.asyncio
async def test_e2e_config_file_content_validity(tmp_path):
    """Test that generated config file has all required fields and valid values."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    packages_dir = workspace_root / "packages"
    packages_dir.mkdir()

    config_dir = workspace_root / "config"
    config_dir.mkdir()

    # Point to real package
    repo_root = Path(__file__).parent.parent.parent.parent
    try:
        (packages_dir / "tars-mcp-character").symlink_to(repo_root / "packages" / "tars-mcp-character")
    except (OSError, NotImplementedError):
        pytest.skip("Cannot create symlink")

    env_vars = {
        "WORKSPACE_ROOT": str(workspace_root),
        "MCP_LOCAL_PACKAGES_PATH": str(packages_dir),
        "MCP_EXTENSIONS_PATH": str(workspace_root / "extensions"),
        "MCP_SERVERS_YAML": str(workspace_root / "mcp.server.yml"),
        "MCP_OUTPUT_DIR": str(config_dir),
    }

    with patch.dict(os.environ, env_vars):
        exit_code = await main()

    assert exit_code == 0

    config_file = config_dir / "mcp-servers.json"
    with open(config_file) as f:
        config = json.load(f)

    # Validate top-level structure
    required_top_level = ["version", "generated_at", "servers", "discovery_summary", "installation_summary"]
    for field in required_top_level:
        assert field in config, f"Config must have '{field}' field"

    # Validate version
    assert isinstance(config["version"], int)
    assert config["version"] == 1

    # Validate generated_at timestamp (ISO 8601 format)
    assert isinstance(config["generated_at"], str)
    assert "T" in config["generated_at"]  # ISO format has 'T' separator

    # Validate servers array
    assert isinstance(config["servers"], list)

    # Validate each server has required fields
    for server in config["servers"]:
        required_server_fields = [
            "name",
            "source",
            "transport",
            "command",
            "args",
            "env",
            "allowed_tools",
            "package_name",
            "installed",
            "install_path",
            "url",
        ]
        for field in required_server_fields:
            assert field in server, f"Server must have '{field}' field"

        # Validate field types
        assert isinstance(server["name"], str)
        assert server["source"] in ["local", "extension", "external"]
        assert server["transport"] in ["stdio", "http"]
        assert isinstance(server["args"], list)
        assert isinstance(server["env"], dict)
        assert isinstance(server["installed"], bool)

        # If HTTP transport, command should be None
        if server["transport"] == "http":
            assert server["command"] is None
            assert server["url"] is not None

        # If stdio transport, command should be set
        if server["transport"] == "stdio":
            assert server["command"] is not None

    # Validate discovery_summary
    summary = config["discovery_summary"]
    assert "total_servers" in summary
    assert "sources" in summary
    assert isinstance(summary["total_servers"], int)
    assert summary["total_servers"] > 0
    assert isinstance(summary["sources"], dict)

    # Validate installation_summary
    install = config["installation_summary"]
    required_install_fields = [
        "total_servers",
        "installed",
        "already_installed",
        "failed",
        "skipped",
        "success_rate",
        "duration_sec",
    ]
    for field in required_install_fields:
        assert field in install, f"Installation summary must have '{field}' field"

    assert isinstance(install["success_rate"], float)
    assert 0.0 <= install["success_rate"] <= 1.0
    assert isinstance(install["duration_sec"], (int, float))
    assert install["duration_sec"] >= 0


@pytest.mark.asyncio
async def test_e2e_pipeline_failure_conditions(tmp_path):
    """Test pipeline behavior under failure conditions."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    packages_dir = workspace_root / "packages"
    packages_dir.mkdir()

    # Create a broken package (missing pyproject.toml)
    broken_package = packages_dir / "broken-server"
    broken_package.mkdir()
    (broken_package / "__init__.py").write_text("# Broken package")

    config_dir = workspace_root / "config"
    config_dir.mkdir()

    env_vars = {
        "WORKSPACE_ROOT": str(workspace_root),
        "MCP_LOCAL_PACKAGES_PATH": str(packages_dir),
        "MCP_EXTENSIONS_PATH": str(workspace_root / "extensions"),
        "MCP_SERVERS_YAML": str(workspace_root / "mcp.server.yml"),
        "MCP_OUTPUT_DIR": str(config_dir),
    }

    with patch.dict(os.environ, env_vars):
        exit_code = await main()

    # Should exit with success (broken packages are skipped during discovery)
    assert exit_code == 0, "Should succeed (invalid packages skipped)"

    # No config file should be created (no valid servers found)
    config_file = config_dir / "mcp-servers.json"
    assert not config_file.exists(), "No config when no valid servers"


@pytest.mark.asyncio
async def test_e2e_config_file_is_atomic(tmp_path):
    """Test that config file writing is atomic (no partial writes)."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    packages_dir = workspace_root / "packages"
    packages_dir.mkdir()

    config_dir = workspace_root / "config"
    config_dir.mkdir()

    # Point to real package
    repo_root = Path(__file__).parent.parent.parent.parent
    try:
        (packages_dir / "tars-mcp-character").symlink_to(repo_root / "packages" / "tars-mcp-character")
    except (OSError, NotImplementedError):
        pytest.skip("Cannot create symlink")

    env_vars = {
        "WORKSPACE_ROOT": str(workspace_root),
        "MCP_LOCAL_PACKAGES_PATH": str(packages_dir),
        "MCP_EXTENSIONS_PATH": str(workspace_root / "extensions"),
        "MCP_SERVERS_YAML": str(workspace_root / "mcp.server.yml"),
        "MCP_OUTPUT_DIR": str(config_dir),
    }

    with patch.dict(os.environ, env_vars):
        exit_code = await main()

    assert exit_code == 0

    config_file = config_dir / "mcp-servers.json"
    assert config_file.exists()

    # Verify no temporary files left behind
    temp_files = list(config_dir.glob("*.tmp"))
    assert len(temp_files) == 0, "No temporary files should remain"

    # Verify file is complete and valid JSON (atomic write succeeded)
    with open(config_file) as f:
        config = json.load(f)

    assert "servers" in config
    assert len(config["servers"]) > 0
