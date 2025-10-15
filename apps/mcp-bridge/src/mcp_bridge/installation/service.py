"""Installation service for MCP servers."""

import logging
from dataclasses import dataclass, field
from enum import Enum

from ..discovery.base import MCPServerMetadata
from .pip_installer import PipInstaller, PipInstallResult

logger = logging.getLogger(__name__)


class InstallationStatus(str, Enum):
    """Installation status for a server."""

    PENDING = "pending"  # Not yet attempted
    INSTALLING = "installing"  # Currently installing
    INSTALLED = "installed"  # Successfully installed
    FAILED = "failed"  # Installation failed
    SKIPPED = "skipped"  # Skipped (e.g., HTTP transport)
    ALREADY_INSTALLED = "already_installed"  # Was already installed


@dataclass
class InstallationResult:
    """Result of installing a single server."""

    server_name: str
    """Server name."""

    status: InstallationStatus
    """Installation status."""

    package: str | None = None
    """Package that was installed (name or path)."""

    duration_sec: float = 0.0
    """Installation duration."""

    error_message: str | None = None
    """Error message if failed."""

    pip_result: PipInstallResult | None = None
    """Detailed pip result."""

    @property
    def success(self) -> bool:
        """Check if installation succeeded."""
        return self.status in (
            InstallationStatus.INSTALLED,
            InstallationStatus.ALREADY_INSTALLED,
            InstallationStatus.SKIPPED,
        )


@dataclass
class InstallationSummary:
    """Summary of installation run."""

    total_servers: int = 0
    """Total servers to install."""

    installed: int = 0
    """Successfully installed."""

    already_installed: int = 0
    """Already installed."""

    failed: int = 0
    """Failed to install."""

    skipped: int = 0
    """Skipped (e.g., HTTP transport)."""

    total_duration_sec: float = 0.0
    """Total time for all installations."""

    results: list[InstallationResult] = field(default_factory=list)
    """Individual installation results."""

    @property
    def success_rate(self) -> float:
        """Calculate success rate (0.0 to 1.0)."""
        if self.total_servers == 0:
            return 1.0
        successful = self.installed + self.already_installed + self.skipped
        return successful / self.total_servers


class InstallationService:
    """Service for installing discovered MCP servers.

    Orchestrates pip installation of servers discovered by ServerDiscoveryService.
    Handles editable installs for local/extension packages and PyPI installs for
    external packages.
    """

    def __init__(
        self,
        pip_installer: PipInstaller | None = None,
        skip_already_installed: bool = True,
        fail_fast: bool = False,
    ):
        """Initialize installation service.

        Args:
            pip_installer: PipInstaller instance (creates default if None)
            skip_already_installed: Skip packages that are already installed
            fail_fast: Stop on first failure (default: continue with other servers)
        """
        self.pip_installer = pip_installer or PipInstaller()
        self.skip_already_installed = skip_already_installed
        self.fail_fast = fail_fast

    async def install_all(
        self,
        servers: list[MCPServerMetadata],
    ) -> InstallationSummary:
        """Install all discovered servers.

        Args:
            servers: List of server metadata from discovery

        Returns:
            InstallationSummary with results for each server.
        """
        import time

        start_time = time.monotonic()

        logger.info(f"📦 Installing {len(servers)} MCP server(s)...")

        summary = InstallationSummary(total_servers=len(servers))

        for server in servers:
            result = await self.install_server(server)
            summary.results.append(result)

            # Update counters
            if result.status == InstallationStatus.INSTALLED:
                summary.installed += 1
            elif result.status == InstallationStatus.ALREADY_INSTALLED:
                summary.already_installed += 1
            elif result.status == InstallationStatus.FAILED:
                summary.failed += 1
            elif result.status == InstallationStatus.SKIPPED:
                summary.skipped += 1

            # Fail fast if enabled
            if self.fail_fast and not result.success:
                logger.error(f"Fail-fast enabled, stopping after failure: {server.name}")
                break

        summary.total_duration_sec = time.monotonic() - start_time

        # Log summary
        logger.info(f"✅ Installation complete in {summary.total_duration_sec:.1f}s:")
        logger.info(f"   Installed: {summary.installed}")
        logger.info(f"   Already installed: {summary.already_installed}")
        logger.info(f"   Skipped: {summary.skipped}")
        if summary.failed > 0:
            logger.warning(f"   Failed: {summary.failed}")
        logger.info(f"   Success rate: {summary.success_rate * 100:.1f}%")

        return summary

    async def install_server(
        self,
        server: MCPServerMetadata,
    ) -> InstallationResult:
        """Install a single MCP server.

        Args:
            server: Server metadata

        Returns:
            InstallationResult with outcome.
        """
        # HTTP transport servers don't need installation
        if server.url:
            logger.debug(f"Skipping HTTP server: {server.name}")
            return InstallationResult(
                server_name=server.name,
                status=InstallationStatus.SKIPPED,
            )

        # Check if already installed
        if self.skip_already_installed:
            package_name = server.package_name or server.get_module_name()
            is_installed = await self.pip_installer.is_installed(package_name)

            if is_installed:
                logger.info(f"⏭️  {server.name} already installed")
                return InstallationResult(
                    server_name=server.name,
                    status=InstallationStatus.ALREADY_INSTALLED,
                    package=package_name,
                )

        # Perform installation
        try:
            logger.info(f"📦 Installing {server.name}...")

            if server.is_editable_install():
                # Editable install for local/extension packages
                if not server.package_path:
                    return InstallationResult(
                        server_name=server.name,
                        status=InstallationStatus.FAILED,
                        error_message="No package_path specified for editable install",
                    )
                pip_result = await self.pip_installer.install_editable(server.package_path)
            else:
                # PyPI install for external packages
                if not server.package_name:
                    return InstallationResult(
                        server_name=server.name,
                        status=InstallationStatus.FAILED,
                        error_message="No package_name specified for external server",
                    )
                pip_result = await self.pip_installer.install_package(server.package_name)

            if pip_result.success:
                return InstallationResult(
                    server_name=server.name,
                    status=InstallationStatus.INSTALLED,
                    package=pip_result.package,
                    duration_sec=pip_result.duration_sec,
                    pip_result=pip_result,
                )
            else:
                return InstallationResult(
                    server_name=server.name,
                    status=InstallationStatus.FAILED,
                    package=pip_result.package,
                    duration_sec=pip_result.duration_sec,
                    error_message=pip_result.error_message,
                    pip_result=pip_result,
                )

        except Exception as e:
            logger.error(f"❌ Exception installing {server.name}: {e}", exc_info=True)
            return InstallationResult(
                server_name=server.name,
                status=InstallationStatus.FAILED,
                error_message=str(e),
            )

    async def rollback_installation(
        self,
        result: InstallationResult,
    ) -> bool:
        """Rollback a failed installation.

        Args:
            result: Installation result to rollback

        Returns:
            True if rollback succeeded, False otherwise.
        """
        if not result.package:
            logger.warning(f"Cannot rollback {result.server_name}: no package info")
            return False

        if result.status != InstallationStatus.INSTALLED:
            logger.debug(f"Not rolling back {result.server_name}: not installed")
            return False

        logger.info(f"🔄 Rolling back installation: {result.server_name}")

        try:
            # Try to extract package name from result
            package_name = result.package
            if "/" in package_name or "\\" in package_name:
                # It's a path, extract package name from metadata if available
                logger.warning(f"Cannot rollback editable install: {package_name}")
                return False

            uninstall_result = await self.pip_installer.uninstall_package(package_name)

            if uninstall_result.success:
                logger.info(f"✅ Rollback successful: {result.server_name}")
                return True
            else:
                logger.error(f"❌ Rollback failed: {result.server_name}")
                return False

        except Exception as e:
            logger.error(f"❌ Exception during rollback: {e}", exc_info=True)
            return False
