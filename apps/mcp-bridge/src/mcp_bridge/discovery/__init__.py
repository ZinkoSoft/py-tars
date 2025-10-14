"""MCP server discovery module.

Discovers MCP servers from multiple sources:
- Local packages (packages/tars-mcp-*)
- Extensions (extensions/mcp-servers/*)
- External configuration (ops/mcp/mcp.server.yml)
"""

from .base import MCPServerMetadata, ServerSource, TransportType
from .service import ServerDiscoveryService

__all__ = [
    "MCPServerMetadata",
    "ServerSource",
    "TransportType",
    "ServerDiscoveryService",
]
