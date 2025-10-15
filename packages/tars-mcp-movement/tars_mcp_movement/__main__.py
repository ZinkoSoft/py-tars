"""Entry point for TARS MCP Movement server."""
import asyncio
import logging
import sys

from .server import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,  # MCP uses stderr for logs, stdout for protocol
)


def main():
    """Run the MCP server."""
    asyncio.run(app.run())


if __name__ == "__main__":
    main()
