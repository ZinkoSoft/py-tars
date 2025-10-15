#!/usr/bin/env python3
"""Test script to verify discovery of real tars-mcp-character package."""

import asyncio
import sys
from pathlib import Path

# Add mcp_bridge to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_bridge.discovery import ServerDiscoveryService


async def main():
    """Test server discovery."""
    print("🔍 Testing MCP Server Discovery")
    print("=" * 60)

    # Use actual workspace paths
    workspace = Path("/home/james/git/py-tars")

    service = ServerDiscoveryService(
        packages_path=workspace / "packages",
        extensions_path=workspace / "extensions" / "mcp-servers",
        config_path=workspace / "ops" / "mcp" / "mcp.server.yml",
        workspace_root=workspace,
    )

    print("\n📦 Discovering servers...")
    servers = await service.discover_all()

    print(f"\n✅ Found {len(servers)} server(s):\n")

    for i, server in enumerate(servers, 1):
        print(f"{i}. {server.name} (v{server.version})")
        print(f"   Source: {server.source.value}")
        print(f"   Transport: {server.transport.value}")
        print(f"   Command: {server.command} {' '.join(server.args)}")
        if server.package_path:
            print(f"   Path: {server.package_path}")
        if server.tools_allowlist:
            print(f"   Allowlist: {', '.join(server.tools_allowlist)}")
        print()

    # Check for tars-mcp-character specifically
    character_server = next((s for s in servers if s.name == "tars-mcp-character"), None)

    if character_server:
        print("🎯 TARS Character Server Details:")
        print(f"   Name: {character_server.name}")
        print(f"   Version: {character_server.version}")
        print(f"   Module: {character_server.get_module_name()}")
        print(f"   Editable: {character_server.is_editable_install()}")
        print(f"   Install target: {character_server.get_install_target()}")
        print(f"   Dependencies: {', '.join(character_server.dependencies)}")
        print("\n✅ Discovery working correctly!")
    else:
        print("❌ tars-mcp-character not found!")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
