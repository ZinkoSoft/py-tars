"""Unit tests for InstallationService."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_bridge.discovery.base import MCPServerMetadata, ServerSource, TransportType
from mcp_bridge.installation.pip_installer import PipInstaller, PipInstallResult
from mcp_bridge.installation.service import (
    InstallationResult,
    InstallationService,
    InstallationStatus,
)


@pytest.fixture
def mock_pip_installer():
    """Create a mocked PipInstaller."""
    installer = MagicMock(spec=PipInstaller)
    installer.is_installed = AsyncMock(return_value=False)
    return installer


@pytest.fixture
def installation_service(mock_pip_installer):
    """Create an InstallationService with mocked pip."""
    return InstallationService(pip_installer=mock_pip_installer)


@pytest.fixture
def local_server():
    """Create a local server metadata."""
    return MCPServerMetadata(
        name="test-local-server",
        source=ServerSource.LOCAL,
        package_path=Path("/workspace/packages/test-server"),
        package_name="test-local-server",
        version="1.0.0",
        command="python",
        args=["-m", "test_local_server"],
    )


@pytest.fixture
def external_server():
    """Create an external server metadata."""
    return MCPServerMetadata(
        name="external-server",
        source=ServerSource.EXTERNAL,
        package_name="mcp-server-external",
        version="1.0.0",
        command="python",
        args=["-m", "mcp_server_external"],
    )


@pytest.fixture
def http_server():
    """Create an HTTP server metadata."""
    return MCPServerMetadata(
        name="http-server",
        source=ServerSource.EXTERNAL,
        transport=TransportType.HTTP,
        url="http://localhost:8080/mcp",
    )


@pytest.mark.asyncio
async def test_install_local_server_success(installation_service, mock_pip_installer, local_server):
    """Test successful installation of local server."""
    mock_pip_installer.install_editable = AsyncMock(
        return_value=PipInstallResult(
            success=True,
            package=str(local_server.package_path),
            duration_sec=1.5,
        )
    )

    result = await installation_service.install_server(local_server)

    assert result.success is True
    assert result.status == InstallationStatus.INSTALLED
    assert result.duration_sec == 1.5
    mock_pip_installer.install_editable.assert_called_once_with(local_server.package_path)


@pytest.mark.asyncio
async def test_install_external_server_success(installation_service, mock_pip_installer, external_server):
    """Test successful installation of external server."""
    mock_pip_installer.install_package = AsyncMock(
        return_value=PipInstallResult(
            success=True,
            package=external_server.package_name,
            duration_sec=2.0,
        )
    )

    result = await installation_service.install_server(external_server)

    assert result.success is True
    assert result.status == InstallationStatus.INSTALLED
    mock_pip_installer.install_package.assert_called_once_with(external_server.package_name)


@pytest.mark.asyncio
async def test_install_http_server_skipped(installation_service, http_server):
    """Test that HTTP servers are skipped."""
    result = await installation_service.install_server(http_server)

    assert result.success is True
    assert result.status == InstallationStatus.SKIPPED


@pytest.mark.asyncio
async def test_install_already_installed(installation_service, mock_pip_installer, local_server):
    """Test skipping already installed package."""
    mock_pip_installer.is_installed = AsyncMock(return_value=True)

    result = await installation_service.install_server(local_server)

    assert result.success is True
    assert result.status == InstallationStatus.ALREADY_INSTALLED
    mock_pip_installer.is_installed.assert_called_once()


@pytest.mark.asyncio
async def test_install_failure(installation_service, mock_pip_installer, local_server):
    """Test failed installation."""
    mock_pip_installer.install_editable = AsyncMock(
        return_value=PipInstallResult(
            success=False,
            package=str(local_server.package_path),
            error_message="Installation failed",
        )
    )

    result = await installation_service.install_server(local_server)

    assert result.success is False
    assert result.status == InstallationStatus.FAILED
    assert "Installation failed" in result.error_message


@pytest.mark.asyncio
async def test_install_all_servers(installation_service, mock_pip_installer, local_server, external_server):
    """Test installing multiple servers."""
    mock_pip_installer.install_editable = AsyncMock(return_value=PipInstallResult(success=True, package="local"))
    mock_pip_installer.install_package = AsyncMock(return_value=PipInstallResult(success=True, package="external"))

    servers = [local_server, external_server]
    summary = await installation_service.install_all(servers)

    assert summary.total_servers == 2
    assert summary.installed == 2
    assert summary.failed == 0
    assert summary.success_rate == 1.0
    assert len(summary.results) == 2


@pytest.mark.asyncio
async def test_install_all_with_failures(installation_service, mock_pip_installer, local_server, external_server):
    """Test installing multiple servers with some failures."""
    mock_pip_installer.install_editable = AsyncMock(return_value=PipInstallResult(success=True, package="local"))
    mock_pip_installer.install_package = AsyncMock(
        return_value=PipInstallResult(success=False, package="external", error_message="Failed")
    )

    servers = [local_server, external_server]
    summary = await installation_service.install_all(servers)

    assert summary.total_servers == 2
    assert summary.installed == 1
    assert summary.failed == 1
    assert summary.success_rate == 0.5


@pytest.mark.asyncio
async def test_fail_fast(mock_pip_installer, local_server, external_server):
    """Test fail-fast mode."""
    service = InstallationService(pip_installer=mock_pip_installer, fail_fast=True)

    mock_pip_installer.install_editable = AsyncMock(
        return_value=PipInstallResult(success=False, package="local", error_message="Failed")
    )

    servers = [local_server, external_server]
    summary = await service.install_all(servers)

    # Should stop after first failure
    assert len(summary.results) == 1
    assert summary.failed == 1


@pytest.mark.asyncio
async def test_rollback_installation(installation_service, mock_pip_installer):
    """Test rolling back a successful installation."""
    result = InstallationResult(
        server_name="test-server",
        status=InstallationStatus.INSTALLED,
        package="test-package",
    )

    mock_pip_installer.uninstall_package = AsyncMock(
        return_value=PipInstallResult(success=True, package="test-package")
    )

    rollback_success = await installation_service.rollback_installation(result)

    assert rollback_success is True
    mock_pip_installer.uninstall_package.assert_called_once_with("test-package")


@pytest.mark.asyncio
async def test_rollback_editable_install(installation_service, mock_pip_installer):
    """Test that editable installs cannot be rolled back."""
    result = InstallationResult(
        server_name="test-server",
        status=InstallationStatus.INSTALLED,
        package="/path/to/package",  # Path, not package name
    )

    rollback_success = await installation_service.rollback_installation(result)

    assert rollback_success is False


@pytest.mark.asyncio
async def test_skip_already_installed_disabled(mock_pip_installer, local_server):
    """Test forcing installation even if already installed."""
    service = InstallationService(
        pip_installer=mock_pip_installer,
        skip_already_installed=False,
    )

    mock_pip_installer.is_installed = AsyncMock(return_value=True)
    mock_pip_installer.install_editable = AsyncMock(return_value=PipInstallResult(success=True, package="test"))

    result = await service.install_server(local_server)

    # Should install even though already installed
    assert result.status == InstallationStatus.INSTALLED
    mock_pip_installer.install_editable.assert_called_once()


@pytest.mark.asyncio
async def test_external_server_missing_package_name(installation_service, mock_pip_installer):
    """Test that external server without package_name fails."""
    server = MCPServerMetadata(
        name="broken-external",
        source=ServerSource.EXTERNAL,
        command="python",
        args=["-m", "test"],
        # Missing package_name!
    )

    result = await installation_service.install_server(server)

    assert result.success is False
    assert result.status == InstallationStatus.FAILED
    assert "package_name" in result.error_message.lower()
