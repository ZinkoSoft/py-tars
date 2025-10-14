"""Entry point for mcp-bridge build-time script.

Usage:
    python -m mcp_bridge
"""

import asyncio
import sys

from .main import main

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
