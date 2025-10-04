"""Pip installer wrapper for MCP servers."""

import asyncio
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PipInstallResult:
    """Result of a pip install operation."""
    
    success: bool
    """Whether installation succeeded."""
    
    package: str
    """Package name or path that was installed."""
    
    stdout: str = ""
    """Standard output from pip."""
    
    stderr: str = ""
    """Standard error from pip."""
    
    return_code: int = 0
    """Process return code."""
    
    error_message: Optional[str] = None
    """Human-readable error message if failed."""
    
    duration_sec: float = 0.0
    """Installation duration in seconds."""


class PipInstaller:
    """Wrapper for pip installation operations.
    
    Provides async interface to pip with proper error handling,
    output capture, and timeout support.
    """
    
    def __init__(
        self,
        pip_executable: str = "pip",
        timeout_sec: float = 300.0,  # 5 minutes default
    ):
        """Initialize pip installer.
        
        Args:
            pip_executable: Path to pip executable (default: "pip")
            timeout_sec: Timeout for pip operations (default: 300s)
        """
        self.pip_executable = pip_executable
        self.timeout_sec = timeout_sec
        
        # Verify pip is available
        if not shutil.which(self.pip_executable):
            logger.warning(f"pip executable not found: {self.pip_executable}")
    
    async def install_editable(self, package_path: Path) -> PipInstallResult:
        """Install package in editable mode.
        
        Runs: pip install -e <package_path>
        
        Args:
            package_path: Path to package directory containing pyproject.toml
        
        Returns:
            PipInstallResult with installation outcome.
        """
        package_str = str(package_path)
        
        logger.info(f"Installing editable package: {package_str}")
        
        cmd = [
            self.pip_executable,
            "install",
            "-e",
            package_str,
        ]
        
        return await self._run_pip_command(cmd, package_str)
    
    async def install_package(self, package_name: str) -> PipInstallResult:
        """Install package from PyPI.
        
        Runs: pip install <package_name>
        
        Args:
            package_name: Package name (e.g., "mcp-server-example")
        
        Returns:
            PipInstallResult with installation outcome.
        """
        logger.info(f"Installing package from PyPI: {package_name}")
        
        cmd = [
            self.pip_executable,
            "install",
            package_name,
        ]
        
        return await self._run_pip_command(cmd, package_name)
    
    async def uninstall_package(self, package_name: str) -> PipInstallResult:
        """Uninstall package.
        
        Runs: pip uninstall -y <package_name>
        
        Args:
            package_name: Package name to uninstall
        
        Returns:
            PipInstallResult with uninstall outcome.
        """
        logger.info(f"Uninstalling package: {package_name}")
        
        cmd = [
            self.pip_executable,
            "uninstall",
            "-y",  # Don't ask for confirmation
            package_name,
        ]
        
        return await self._run_pip_command(cmd, package_name)
    
    async def is_installed(self, package_name: str) -> bool:
        """Check if package is installed.
        
        Runs: pip show <package_name>
        
        Args:
            package_name: Package name to check
        
        Returns:
            True if package is installed, False otherwise.
        """
        cmd = [
            self.pip_executable,
            "show",
            package_name,
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            await asyncio.wait_for(process.wait(), timeout=10.0)
            return process.returncode == 0
            
        except Exception as e:
            logger.debug(f"Error checking if {package_name} is installed: {e}")
            return False
    
    async def _run_pip_command(self, cmd: list[str], package: str) -> PipInstallResult:
        """Run pip command with timeout and output capture.
        
        Args:
            cmd: Command list (e.g., ["pip", "install", "package"])
            package: Package identifier for result
        
        Returns:
            PipInstallResult with command outcome.
        """
        import time
        
        start_time = time.monotonic()
        
        try:
            logger.debug(f"Running: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout_sec
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                
                duration = time.monotonic() - start_time
                
                logger.error(f"pip command timed out after {duration:.1f}s: {package}")
                return PipInstallResult(
                    success=False,
                    package=package,
                    error_message=f"Installation timed out after {duration:.1f}s",
                    duration_sec=duration,
                )
            
            duration = time.monotonic() - start_time
            
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")
            
            success = process.returncode == 0
            
            if success:
                logger.info(f"✅ Successfully installed {package} in {duration:.1f}s")
            else:
                logger.error(f"❌ Failed to install {package} (exit {process.returncode})")
                logger.debug(f"stderr: {stderr_str}")
            
            return PipInstallResult(
                success=success,
                package=package,
                stdout=stdout_str,
                stderr=stderr_str,
                return_code=process.returncode,
                error_message=stderr_str if not success else None,
                duration_sec=duration,
            )
            
        except Exception as e:
            duration = time.monotonic() - start_time
            
            logger.error(f"❌ Exception during pip install {package}: {e}", exc_info=True)
            return PipInstallResult(
                success=False,
                package=package,
                error_message=str(e),
                duration_sec=duration,
            )
