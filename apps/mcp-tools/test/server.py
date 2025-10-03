#!/usr/bin/env python3
"""
Simple test MCP server to verify tool calling works.
Based on official MCP Python SDK lowlevel examples.
"""
import anyio
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

# Create server instance
app = Server("test-server")

@app.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="hello",
            description="A simple greeting tool for testing",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name to greet (default: World)"
                    }
                }
            }
        ),
        types.Tool(
            name="add",
            description="Add two numbers together",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "First number"},
                    "b": {"type": "number", "description": "Second number"}
                },
                "required": ["a", "b"]
            }
        )
    ]

@app.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool execution."""
    if name == "hello":
        greeting_name = arguments.get("name", "World")
        return [
            types.TextContent(
                type="text",
                text=f"Hello, {greeting_name}!"
            )
        ]
    elif name == "add":
        a = arguments.get("a", 0)
        b = arguments.get("b", 0)
        result = a + b
        return [
            types.TextContent(
                type="text",
                text=f"The sum of {a} and {b} is {result}"
            )
        ]
    else:
        raise ValueError(f"Unknown tool: {name}")

def main():
    """Main entry point using anyio.run like official examples."""
    async def arun():
        async with stdio_server() as streams:
            await app.run(
                streams[0],
                streams[1],
                app.create_initialization_options()
            )
    
    anyio.run(arun)

if __name__ == "__main__":
    main()
