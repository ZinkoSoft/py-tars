#!/usr/bin/env python3
"""End-to-end test for discovery → installation → connection flow."""

import asyncio
import sys
from pathlib import Path

# Add mcp_bridge to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_bridge.discovery import ServerDiscoveryService
from mcp_bridge.installation import InstallationService


async def main():
    """Test full discovery and installation pipeline."""
    print("🚀 End-to-End Test: Discovery → Installation → Connection")
    print("=" * 70)

    # Use actual workspace paths
    workspace = Path("/home/james/git/py-tars")

    # Phase 1: Discovery
    print("\n📍 Phase 1: Server Discovery")
    print("-" * 70)

    discovery_service = ServerDiscoveryService(
        packages_path=workspace / "packages",
        extensions_path=workspace / "extensions" / "mcp-servers",
        config_path=workspace / "ops" / "mcp" / "mcp.server.yml",
        workspace_root=workspace,
    )

    servers = await discovery_service.discover_all()
    print(f"\n✅ Discovered {len(servers)} server(s)")

    for i, server in enumerate(servers, 1):
        print(f"   {i}. {server.name} (v{server.version}) - {server.source.value}")

    if len(servers) == 0:
        print("\n❌ No servers discovered!")
        return 1

    # Phase 2: Installation
    print("\n📦 Phase 2: Server Installation")
    print("-" * 70)

    installation_service = InstallationService(
        skip_already_installed=True,  # Don't reinstall
        fail_fast=False,  # Continue on errors
    )

    summary = await installation_service.install_all(servers)

    print("\n✅ Installation Summary:")
    print(f"   Total servers: {summary.total_servers}")
    print(f"   Installed: {summary.installed}")
    print(f"   Already installed: {summary.already_installed}")
    print(f"   Skipped (HTTP): {summary.skipped}")
    print(f"   Failed: {summary.failed}")
    print(f"   Success rate: {summary.success_rate * 100:.1f}%")
    print(f"   Total duration: {summary.total_duration_sec:.2f}s")

    # Show individual results
    print("\n📋 Individual Results:")
    for result in summary.results:
        status_icon = "✅" if result.success else "❌"
        print(f"   {status_icon} {result.server_name}: {result.status.value}")
        if result.error_message:
            print(f"      Error: {result.error_message[:80]}")
        if result.duration_sec > 0:
            print(f"      Duration: {result.duration_sec:.2f}s")

    # Phase 3: Validation
    print("\n🔍 Phase 3: Validation")
    print("-" * 70)

    # Check if tars-mcp-character was processed
    character_result = next((r for r in summary.results if r.server_name == "tars-mcp-character"), None)

    if character_result:
        print("\n✅ tars-mcp-character found:")
        print(f"   Status: {character_result.status.value}")
        print(f"   Success: {character_result.success}")
        if character_result.package:
            print(f"   Package: {character_result.package}")

        if character_result.success:
            print("\n🎉 End-to-end test PASSED!")
            print("   Discovery → Installation pipeline is working correctly.")
            return 0
        else:
            print("\n⚠️  tars-mcp-character installation failed")
            if character_result.error_message:
                print(f"   Error: {character_result.error_message}")
            return 1
    else:
        print("\n❌ tars-mcp-character not found in discovery results!")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
