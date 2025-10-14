"""Unit tests for PipInstaller."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_bridge.installation.pip_installer import PipInstaller


@pytest.fixture
def pip_installer():
    """Create a PipInstaller instance."""
    return PipInstaller(pip_executable="pip", timeout_sec=30.0)


@pytest.mark.asyncio
async def test_install_editable_success(pip_installer):
    """Test successful editable installation."""
    package_path = Path("/workspace/packages/test-package")

    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        # Mock successful installation
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"Successfully installed", b""))
        mock_process.wait = AsyncMock()
        mock_subprocess.return_value = mock_process

        result = await pip_installer.install_editable(package_path)

        assert result.success is True
        assert result.package == str(package_path)
        assert result.return_code == 0
        assert "Successfully installed" in result.stdout

        # Verify command
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args[0]
        assert call_args == ("pip", "install", "-e", str(package_path))


@pytest.mark.asyncio
async def test_install_package_success(pip_installer):
    """Test successful PyPI package installation."""
    package_name = "mcp-server-test"

    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"Successfully installed", b""))
        mock_process.wait = AsyncMock()
        mock_subprocess.return_value = mock_process

        result = await pip_installer.install_package(package_name)

        assert result.success is True
        assert result.package == package_name
        assert result.return_code == 0


@pytest.mark.asyncio
async def test_install_failure(pip_installer):
    """Test failed installation."""
    package_name = "nonexistent-package"

    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"ERROR: Could not find a version"))
        mock_process.wait = AsyncMock()
        mock_subprocess.return_value = mock_process

        result = await pip_installer.install_package(package_name)

        assert result.success is False
        assert result.return_code == 1
        assert "ERROR" in result.stderr
        assert result.error_message is not None


@pytest.mark.asyncio
async def test_install_timeout(pip_installer):
    """Test installation timeout."""
    pip_installer.timeout_sec = 0.1  # Very short timeout

    package_name = "slow-package"

    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = MagicMock()
        mock_process.kill = MagicMock()
        mock_process.wait = AsyncMock()

        # Simulate slow installation
        async def slow_communicate():
            await asyncio.sleep(1.0)  # Longer than timeout
            return (b"output", b"")

        mock_process.communicate = slow_communicate
        mock_subprocess.return_value = mock_process

        result = await pip_installer.install_package(package_name)

        assert result.success is False
        assert "timed out" in result.error_message.lower()
        mock_process.kill.assert_called_once()


@pytest.mark.asyncio
async def test_uninstall_package(pip_installer):
    """Test package uninstallation."""
    package_name = "test-package"

    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"Successfully uninstalled", b""))
        mock_process.wait = AsyncMock()
        mock_subprocess.return_value = mock_process

        result = await pip_installer.uninstall_package(package_name)

        assert result.success is True

        # Verify -y flag is used
        call_args = mock_subprocess.call_args[0]
        assert "-y" in call_args


@pytest.mark.asyncio
async def test_is_installed_true(pip_installer):
    """Test checking if package is installed (installed)."""
    package_name = "installed-package"

    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.wait = AsyncMock()
        mock_subprocess.return_value = mock_process

        is_installed = await pip_installer.is_installed(package_name)

        assert is_installed is True


@pytest.mark.asyncio
async def test_is_installed_false(pip_installer):
    """Test checking if package is installed (not installed)."""
    package_name = "not-installed-package"

    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = MagicMock()
        mock_process.returncode = 1  # pip show returns 1 if not found
        mock_process.wait = AsyncMock()
        mock_subprocess.return_value = mock_process

        is_installed = await pip_installer.is_installed(package_name)

        assert is_installed is False


@pytest.mark.asyncio
async def test_duration_tracking(pip_installer):
    """Test that installation duration is tracked."""
    package_name = "test-package"

    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_process = MagicMock()
        mock_process.returncode = 0

        # Simulate some processing time
        async def mock_communicate():
            await asyncio.sleep(0.1)
            return (b"Success", b"")

        mock_process.communicate = mock_communicate
        mock_subprocess.return_value = mock_process

        result = await pip_installer.install_package(package_name)

        assert result.success is True
        assert result.duration_sec > 0.0
        assert result.duration_sec < 1.0  # Should be quick


@pytest.mark.asyncio
async def test_exception_handling(pip_installer):
    """Test handling of unexpected exceptions."""
    package_name = "test-package"

    with patch("asyncio.create_subprocess_exec") as mock_subprocess:
        mock_subprocess.side_effect = Exception("Unexpected error")

        result = await pip_installer.install_package(package_name)

        assert result.success is False
        assert "Unexpected error" in result.error_message
