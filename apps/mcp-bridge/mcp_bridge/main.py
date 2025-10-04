"""MCP Bridge - Build-time MCP server discovery, installation, and configuration generation.

This is a ONE-SHOT script that runs at Docker build time (not a runtime service).
It discovers MCP servers, installs them, generates mcp-servers.json, and exits.

The generated config file is consumed by llm-worker at runtime.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

from .discovery import ServerDiscoveryService
from .installation import InstallationService
from .config_generator import ConfigGenerator
from .config_generator.writer import ConfigWriter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp-bridge")


async def main():
    """Run complete MCP bridge pipeline: discover -> install -> generate config -> exit.
    
    Exit codes:
        0: Success (all or partial success with >= 50% install rate)
        1: Failure (no servers discovered or install rate < 50%)
    """
    try:
        # ========== Phase 1: Discovery ==========
        logger.info("=" * 60)
        logger.info("Phase 1: MCP Server Discovery")
        logger.info("=" * 60)
        
        # Get paths from environment
        workspace_root = Path(os.getenv("WORKSPACE_ROOT", "/workspace"))
        packages_path = Path(os.getenv("MCP_LOCAL_PACKAGES_PATH", workspace_root / "packages"))
        extensions_path = Path(os.getenv("MCP_EXTENSIONS_PATH", workspace_root / "extensions" / "mcp-servers"))
        config_path = Path(os.getenv("MCP_SERVERS_YAML", workspace_root / "ops" / "mcp" / "mcp.server.yml"))
        
        logger.info(f"Workspace root: {workspace_root}")
        logger.info(f"Local packages: {packages_path}")
        logger.info(f"Extensions: {extensions_path}")
        logger.info(f"External config: {config_path}")
        
        # Initialize discovery service
        discovery = ServerDiscoveryService(
            packages_path=packages_path,
            extensions_path=extensions_path,
            config_path=config_path,
            workspace_root=workspace_root,
        )
        
        # Discover all servers
        discovered_servers = await discovery.discover_all()
        
        logger.info("")
        logger.info(f"✅ Discovery complete: {len(discovered_servers)} servers found")
        
        if not discovered_servers:
            logger.warning("⚠️  No MCP servers discovered - nothing to install")
            logger.info("Exiting with success (nothing to do)")
            return 0
        
        # ========== Phase 2: Installation ==========
        logger.info("")
        logger.info("=" * 60)
        logger.info("Phase 2: Package Installation")
        logger.info("=" * 60)
        
        installation_service = InstallationService(
            skip_already_installed=True,
            fail_fast=False,
        )
        
        install_summary = await installation_service.install_all(discovered_servers)
        
        logger.info("")
        logger.info(f"✅ Installation complete in {install_summary.total_duration_sec:.1f}s")
        logger.info(f"   Total servers: {install_summary.total_servers}")
        logger.info(f"   Installed: {install_summary.installed}")
        logger.info(f"   Already installed: {install_summary.already_installed}")
        logger.info(f"   Skipped: {install_summary.skipped}")
        logger.info(f"   Failed: {install_summary.failed}")
        logger.info(f"   Success rate: {install_summary.success_rate * 100:.1f}%")
        
        # ========== Phase 3: Configuration Generation ==========
        logger.info("")
        logger.info("=" * 60)
        logger.info("Phase 3: Configuration Generation")
        logger.info("=" * 60)
        
        # Generate configuration
        config_generator = ConfigGenerator()
        config = config_generator.generate(
            discovered_servers=discovered_servers,
            installation_summary=install_summary,
        )
        
        logger.info(f"Generated configuration for {len(config.servers)} servers")
        
        # Write configuration to disk
        output_dir = Path(os.getenv("MCP_OUTPUT_DIR", workspace_root / "config"))
        config_filename = os.getenv("MCP_CONFIG_FILENAME", "mcp-servers.json")
        
        logger.info(f"Writing configuration to: {output_dir / config_filename}")
        
        config_writer = ConfigWriter(
            output_dir=output_dir,
            filename=config_filename,
        )
        
        config_path_str = config_writer.write(config)
        config_path = Path(config_path_str)
        
        logger.info(f"✅ Configuration written: {config_path}")
        logger.info(f"   File size: {config_path.stat().st_size} bytes")
        
        # ========== Summary ==========
        logger.info("")
        logger.info("=" * 60)
        logger.info("MCP Bridge Complete")
        logger.info("=" * 60)
        logger.info(f"Discovered: {len(discovered_servers)} servers")
        logger.info(f"Installed: {install_summary.installed + install_summary.already_installed}/{install_summary.total_servers}")
        logger.info(f"Config file: {config_path}")
        logger.info("")
        
        # Determine exit code based on success rate
        if install_summary.success_rate >= 0.5:
            logger.info("✅ Build succeeded (>= 50% install success)")
            return 0
        else:
            logger.error(f"❌ Build failed (< 50% install success: {install_summary.success_rate * 100:.1f}%)")
            return 1
            
    except Exception as e:
        logger.error(f"❌ Fatal error in MCP bridge: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
