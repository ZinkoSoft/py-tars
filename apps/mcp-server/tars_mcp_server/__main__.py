"""Entry point for TARS MCP server."""
from __future__ import annotations

import sys
from .server import app

def main():
    """Main entry point for the MCP server."""
    # FastMCP CLI handles stdio/http/sse automatically
    app.run()

if __name__ == "__main__":
    main()
