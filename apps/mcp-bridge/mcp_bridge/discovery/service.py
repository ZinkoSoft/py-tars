"""Main server discovery service that orchestrates all discovery sources."""

import logging
from pathlib import Path
from typing import Optional

from .base import MCPServerMetadata, ServerSource
from .extensions import ExtensionDiscovery
from .external_config import ExternalConfigDiscovery
from .local_packages import LocalPackageDiscovery

logger = logging.getLogger(__name__)


class ServerDiscoveryService:
    """Orchestrates MCP server discovery from all sources.
    
    Discovers servers from:
    1. Local packages (packages/tars-mcp-*)
    2. Extensions (extensions/mcp-servers/*)
    3. External config (ops/mcp/mcp.server.yml)
    
    Handles deduplication and merging of server configurations.
    """
    
    def __init__(
        self,
        packages_path: Optional[Path] = None,
        extensions_path: Optional[Path] = None,
        config_path: Optional[Path] = None,
        workspace_root: Optional[Path] = None,
    ):
        """Initialize discovery service.
        
        Args:
            packages_path: Path to packages directory (default: workspace/packages)
            extensions_path: Path to extensions directory (default: workspace/extensions/mcp-servers)
            config_path: Path to YAML config (default: workspace/ops/mcp/mcp.server.yml)
            workspace_root: Workspace root for relative paths (default: /workspace)
        """
        # Determine workspace root
        if workspace_root is None:
            workspace_root = Path("/workspace")
        self.workspace_root = Path(workspace_root)
        
        # Set default paths if not provided
        if packages_path is None:
            packages_path = self.workspace_root / "packages"
        if extensions_path is None:
            extensions_path = self.workspace_root / "extensions" / "mcp-servers"
        if config_path is None:
            config_path = self.workspace_root / "ops" / "mcp" / "mcp.server.yml"
        
        # Initialize discovery sources
        self.local_packages = LocalPackageDiscovery(packages_path)
        self.extensions = ExtensionDiscovery(extensions_path)
        self.external_config = ExternalConfigDiscovery(config_path)
        
        logger.info(f"Discovery service initialized:")
        logger.info(f"  Local packages: {packages_path}")
        logger.info(f"  Extensions: {extensions_path}")
        logger.info(f"  External config: {config_path}")
    
    async def discover_all(self) -> list[MCPServerMetadata]:
        """Discover servers from all sources.
        
        Returns:
            List of deduplicated and merged server metadata.
        """
        logger.info("🔍 Starting server discovery from all sources...")
        
        # Discover from each source
        local_servers = await self.local_packages.discover()
        extension_servers = await self.extensions.discover()
        external_servers = await self.external_config.discover()
        
        # Combine all discoveries
        all_servers = local_servers + extension_servers + external_servers
        
        logger.info(f"Discovery summary:")
        logger.info(f"  Local packages: {len(local_servers)} servers")
        logger.info(f"  Extensions: {len(extension_servers)} servers")
        logger.info(f"  External config: {len(external_servers)} servers")
        logger.info(f"  Total: {len(all_servers)} servers")
        
        # Deduplicate and merge
        merged = self._merge_servers(all_servers, external_servers)
        
        logger.info(f"✅ Discovery complete: {len(merged)} unique servers")
        return merged
    
    def _merge_servers(
        self,
        all_servers: list[MCPServerMetadata],
        external_servers: list[MCPServerMetadata],
    ) -> list[MCPServerMetadata]:
        """Merge and deduplicate server configurations.
        
        Rules:
        1. External config overrides discovered servers (explicit > implicit)
        2. Duplicate names: keep first occurrence, log warning
        3. Merge allowlists and env vars from external config
        
        Args:
            all_servers: All discovered servers
            external_servers: Servers from external config (for override detection)
        
        Returns:
            Deduplicated list of servers with merged configs.
        """
        merged: dict[str, MCPServerMetadata] = {}
        external_names = {s.name for s in external_servers}
        
        for server in all_servers:
            name = server.name
            
            # First occurrence wins for deduplication
            if name in merged:
                existing = merged[name]
                
                # External config overrides discovered
                if server.source == ServerSource.EXTERNAL:
                    logger.info(f"🔄 External config overrides {existing.source.value} server: {name}")
                    # Merge: keep discovered package_path but use external config for runtime
                    if existing.package_path and not server.package_path:
                        server.package_path = existing.package_path
                    merged[name] = server
                else:
                    logger.debug(f"Skipping duplicate server '{name}' from {server.source.value} "
                                f"(already have from {existing.source.value})")
                continue
            
            # Check if external config will override this
            if name in external_names and server.source != ServerSource.EXTERNAL:
                logger.debug(f"Server '{name}' will be overridden by external config, adding temporarily")
            
            merged[name] = server
        
        return list(merged.values())
    
    async def discover_by_source(self, source: ServerSource) -> list[MCPServerMetadata]:
        """Discover servers from a specific source.
        
        Args:
            source: Source to discover from
        
        Returns:
            List of servers from that source.
        """
        if source == ServerSource.LOCAL:
            return await self.local_packages.discover()
        elif source == ServerSource.EXTENSION:
            return await self.extensions.discover()
        elif source == ServerSource.EXTERNAL:
            return await self.external_config.discover()
        else:
            logger.error(f"Unknown source: {source}")
            return []
