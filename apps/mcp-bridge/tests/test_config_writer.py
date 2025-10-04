"""Tests for configuration file writer."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from mcp_bridge.config_generator.generator import GeneratedConfig, ServerConfig
from mcp_bridge.config_generator.writer import ConfigWriter


@pytest.fixture
def temp_dir():
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_config():
    """Create sample configuration for tests."""
    servers = [
        ServerConfig(
            name="test-server",
            source="local_package",
            transport="stdio",
            command="python",
            args=["-m", "test_server"],
            env={"TEST": "true"},
            installed=True,
            install_path="/path/to/package",
        )
    ]

    return GeneratedConfig(
        version=1,
        generated_at="2025-10-04T12:00:00Z",
        servers=servers,
        discovery_summary={"total_servers": 1, "sources": {"local_package": 1}},
        installation_summary={"total_servers": 1, "installed": 1, "success_rate": 1.0},
    )


class TestConfigWriter:
    """Tests for ConfigWriter class."""

    def test_write_basic(self, temp_dir, sample_config):
        """Test basic write operation."""
        writer = ConfigWriter(output_dir=temp_dir)
        output_path = writer.write(sample_config)

        assert os.path.exists(output_path)
        assert output_path.endswith("mcp-servers.json")

        # Verify file contents
        with open(output_path, "r") as f:
            data = json.load(f)

        assert data["version"] == 1
        assert len(data["servers"]) == 1
        assert data["servers"][0]["name"] == "test-server"

    def test_write_creates_directory(self, temp_dir, sample_config):
        """Test that write creates output directory if it doesn't exist."""
        nested_dir = os.path.join(temp_dir, "nested", "path")
        writer = ConfigWriter(output_dir=nested_dir, ensure_dir=True)

        output_path = writer.write(sample_config)

        assert os.path.exists(output_path)
        assert os.path.exists(nested_dir)

    def test_write_custom_filename(self, temp_dir, sample_config):
        """Test writing with custom filename."""
        writer = ConfigWriter(output_dir=temp_dir, filename="custom-config.json")
        output_path = writer.write(sample_config)

        assert output_path.endswith("custom-config.json")
        assert os.path.exists(output_path)

    def test_write_custom_indent(self, temp_dir, sample_config):
        """Test JSON indentation."""
        writer = ConfigWriter(output_dir=temp_dir, indent=4)
        output_path = writer.write(sample_config)

        with open(output_path, "r") as f:
            content = f.read()

        # Check that indentation is 4 spaces
        lines = content.split("\n")
        # Find a line that should be indented
        indented_line = next(line for line in lines if line.startswith("    ") and not line.startswith("        "))
        assert indented_line.startswith("    ")  # 4 spaces

    def test_write_overwrites_existing(self, temp_dir, sample_config):
        """Test that write overwrites existing file."""
        writer = ConfigWriter(output_dir=temp_dir)

        # Write first time
        output_path = writer.write(sample_config)
        with open(output_path, "r") as f:
            first_data = json.load(f)

        # Modify config and write again
        sample_config.version = 2
        writer.write(sample_config)

        with open(output_path, "r") as f:
            second_data = json.load(f)

        assert first_data["version"] == 1
        assert second_data["version"] == 2

    def test_write_atomic_operation(self, temp_dir, sample_config):
        """Test that write is atomic (temp file + rename)."""
        writer = ConfigWriter(output_dir=temp_dir)
        output_path = writer.write(sample_config)

        # Check that no temp files remain
        temp_files = [f for f in os.listdir(temp_dir) if f.startswith(".mcp-servers.json.")]
        assert len(temp_files) == 0

        # Verify final file exists
        assert os.path.exists(output_path)

    def test_write_directory_not_exists_no_create(self, temp_dir, sample_config):
        """Test that write fails if directory doesn't exist and ensure_dir=False."""
        nonexistent_dir = os.path.join(temp_dir, "nonexistent")
        writer = ConfigWriter(output_dir=nonexistent_dir, ensure_dir=False)

        with pytest.raises(OSError, match="Output directory does not exist"):
            writer.write(sample_config)

    def test_write_directory_not_writable(self, temp_dir, sample_config):
        """Test that write fails if directory is not writable."""
        # Create read-only directory
        readonly_dir = os.path.join(temp_dir, "readonly")
        os.makedirs(readonly_dir)
        os.chmod(readonly_dir, 0o444)  # Read-only

        writer = ConfigWriter(output_dir=readonly_dir)

        try:
            with pytest.raises(PermissionError, match="not writable"):
                writer.write(sample_config)
        finally:
            # Restore permissions for cleanup
            os.chmod(readonly_dir, 0o755)

    def test_exists_true(self, temp_dir, sample_config):
        """Test exists() returns True when file exists."""
        writer = ConfigWriter(output_dir=temp_dir)
        writer.write(sample_config)

        assert writer.exists() is True

    def test_exists_false(self, temp_dir):
        """Test exists() returns False when file doesn't exist."""
        writer = ConfigWriter(output_dir=temp_dir)

        assert writer.exists() is False

    def test_delete_existing(self, temp_dir, sample_config):
        """Test deleting existing config file."""
        writer = ConfigWriter(output_dir=temp_dir)
        output_path = writer.write(sample_config)

        assert os.path.exists(output_path)

        result = writer.delete()

        assert result is True
        assert not os.path.exists(output_path)

    def test_delete_nonexistent(self, temp_dir):
        """Test deleting non-existent file returns False."""
        writer = ConfigWriter(output_dir=temp_dir)

        result = writer.delete()

        assert result is False

    def test_read_existing(self, temp_dir, sample_config):
        """Test reading existing config file."""
        writer = ConfigWriter(output_dir=temp_dir)
        writer.write(sample_config)

        config_dict = writer.read()

        assert config_dict is not None
        assert config_dict["version"] == 1
        assert len(config_dict["servers"]) == 1

    def test_read_nonexistent(self, temp_dir):
        """Test reading non-existent file returns None."""
        writer = ConfigWriter(output_dir=temp_dir)

        config = writer.read()

        assert config is None

    def test_read_invalid_json(self, temp_dir):
        """Test reading invalid JSON raises ValueError."""
        writer = ConfigWriter(output_dir=temp_dir)
        output_path = Path(temp_dir) / "mcp-servers.json"

        # Write invalid JSON
        with open(output_path, "w") as f:
            f.write("{invalid json")

        with pytest.raises(ValueError, match="Invalid JSON"):
            writer.read()

    def test_read_invalid_structure(self, temp_dir):
        """Test reading file with invalid structure raises OSError."""
        writer = ConfigWriter(output_dir=temp_dir)
        output_path = Path(temp_dir) / "mcp-servers.json"

        # Write JSON with missing required fields
        with open(output_path, "w") as f:
            json.dump({"invalid": "structure"}, f)

        with pytest.raises(OSError, match="Missing required field"):
            writer.read()

    def test_read_without_validation(self, temp_dir):
        """Test reading without validation accepts any JSON."""
        writer = ConfigWriter(output_dir=temp_dir)
        output_path = Path(temp_dir) / "mcp-servers.json"

        # Write JSON with missing fields
        data = {"incomplete": "data"}
        with open(output_path, "w") as f:
            json.dump(data, f)

        config = writer.read(validate=False)

        assert config is not None
        assert config["incomplete"] == "data"

    def test_write_empty_servers(self, temp_dir):
        """Test writing config with no servers."""
        config = GeneratedConfig(
            version=1,
            generated_at="2025-10-04T12:00:00Z",
            servers=[],
            discovery_summary={"total_servers": 0, "sources": {}},
            installation_summary={"total_servers": 0, "installed": 0, "success_rate": 0.0},
        )

        writer = ConfigWriter(output_dir=temp_dir)
        output_path = writer.write(config)

        with open(output_path, "r") as f:
            data = json.load(f)

        assert len(data["servers"]) == 0
        assert data["discovery_summary"]["total_servers"] == 0

    def test_write_multiple_servers(self, temp_dir):
        """Test writing config with multiple servers."""
        servers = [
            ServerConfig(
                name="server1",
                source="local_package",
                transport="stdio",
                command="python",
                args=["-m", "server1"],
                installed=True,
            ),
            ServerConfig(
                name="server2",
                source="extension",
                transport="stdio",
                command="python",
                args=["-m", "server2"],
                installed=True,
            ),
            ServerConfig(
                name="server3",
                source="external_config",
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
            discovery_summary={"total_servers": 3, "sources": {"local_package": 1, "extension": 1, "external_config": 1}},
            installation_summary={"total_servers": 3, "installed": 2, "success_rate": 0.67},
        )

        writer = ConfigWriter(output_dir=temp_dir)
        output_path = writer.write(config)

        with open(output_path, "r") as f:
            data = json.load(f)

        assert len(data["servers"]) == 3
        assert data["servers"][0]["name"] == "server1"
        assert data["servers"][1]["name"] == "server2"
        assert data["servers"][2]["name"] == "server3"

    def test_write_preserves_all_fields(self, temp_dir):
        """Test that all fields are preserved in written config."""
        servers = [
            ServerConfig(
                name="complete-server",
                source="local_package",
                transport="stdio",
                command="python",
                args=["-m", "complete"],
                env={"KEY1": "value1", "KEY2": "value2"},
                allowed_tools=["tool1", "tool2", "tool3"],
                package_name="complete-package",
                installed=True,
                install_path="/path/to/complete",
                url=None,
            )
        ]

        config = GeneratedConfig(
            version=1,
            generated_at="2025-10-04T12:00:00Z",
            servers=servers,
            discovery_summary={"total_servers": 1, "sources": {"local_package": 1}},
            installation_summary={
                "total_servers": 1,
                "installed": 1,
                "already_installed": 0,
                "failed": 0,
                "skipped": 0,
                "success_rate": 1.0,
                "duration_sec": 5.5,
            },
        )

        writer = ConfigWriter(output_dir=temp_dir)
        output_path = writer.write(config)

        with open(output_path, "r") as f:
            data = json.load(f)

        server = data["servers"][0]
        assert server["name"] == "complete-server"
        assert server["source"] == "local_package"
        assert server["transport"] == "stdio"
        assert server["command"] == "python"
        assert server["args"] == ["-m", "complete"]
        assert server["env"] == {"KEY1": "value1", "KEY2": "value2"}
        assert server["allowed_tools"] == ["tool1", "tool2", "tool3"]
        assert server["package_name"] == "complete-package"
        assert server["installed"] is True
        assert server["install_path"] == "/path/to/complete"
        assert server["url"] is None

        assert data["installation_summary"]["duration_sec"] == 5.5
