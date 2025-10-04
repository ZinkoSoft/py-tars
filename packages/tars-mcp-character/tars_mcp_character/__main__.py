"""Entry point for TARS MCP server."""
from __future__ import annotations

from .server import app

def main():
    """Main entry point for the MCP server."""
    # Explicitly run in stdio mode for MCP client compatibility
    # When invoked from command line, stdio is the default transport
    app.run(transport="stdio")

if __name__ == "__main__":
    main()
