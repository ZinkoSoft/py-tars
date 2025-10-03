#!/usr/bin/env python3
"""
Simple test MCP server using FastMCP with HTTP transport.
"""
from mcp.server.fastmcp import FastMCP

# Create FastMCP server (stateful mode for MCP client compatibility)
mcp = FastMCP("test-server")

@mcp.tool()
def hello(name: str = "World") -> str:
    """
    A simple greeting tool for testing.
    
    Args:
        name: Name to greet (default: "World")
    
    Returns:
        A greeting message
    """
    return f"Hello, {name}!"

@mcp.tool()
def add(a: int, b: int) -> int:
    """
    Add two numbers together.
    
    Args:
        a: First number
        b: Second number
    
    Returns:
        The sum of the two numbers
    """
    return a + b

@mcp.tool()
def get_time() -> str:
    """Get the current server time."""
    from datetime import datetime
    return f"Server time: {datetime.now().isoformat()}"

if __name__ == "__main__":
    # Configure server settings before run
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = 8080
    # Run with streamable-http transport
    mcp.run(transport="streamable-http")
