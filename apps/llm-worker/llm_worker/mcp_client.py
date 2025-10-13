"""
MCP Tool Client for LLM Worker.

Provides direct access to MCP tools without going through MQTT.
Loads tools from registry and executes them via MCP protocol.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)


class MCPToolClient:
    """Client for executing MCP tools directly."""
    
    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.contexts: List[Any] = []  # Store context managers to keep them alive
        self.tools: Dict[str, dict] = {}  # tool_name -> {server, mcp_tool_name, schema}
        self._initialized = False
        self._context_task: Optional[asyncio.Task] = None
        
    async def initialize_from_registry(self, registry_payload: dict):
        """Initialize tools from the tool registry.
        
        Args:
            registry_payload: The payload from llm/tools/registry topic
                             Expected format: {"tools": [{type:"function", function:{name:..., ...}}]}
        """
        try:
            tools = registry_payload.get("tools", [])
            logger.info(f"Initializing MCP client with {len(tools)} tools from registry")
            
            # Group tools by server
            servers_by_name = {}
            for tool in tools:
                func = tool.get("function", {})
                full_name = func.get("name", "")
                
                # Parse: mcp__server-name__tool-name
                if not full_name.startswith("mcp__"):
                    logger.warning(f"Skipping non-MCP tool: {full_name}")
                    continue
                    
                parts = full_name.split("__")
                if len(parts) != 3:
                    logger.warning(f"Invalid MCP tool name format: {full_name}")
                    continue
                    
                _, server_name, tool_name = parts
                
                # Store tool info
                self.tools[full_name] = {
                    "server": server_name,
                    "mcp_tool_name": tool_name,
                    "schema": func
                }
                
                # Track which servers we need to connect to
                if server_name not in servers_by_name:
                    servers_by_name[server_name] = []
                servers_by_name[server_name].append(tool_name)
            
            logger.info(f"Loaded {len(self.tools)} tools from {len(servers_by_name)} servers")
            
            # Note: We don't connect here anymore. Connection happens lazily on first tool execution.
            # This avoids async context issues during message processing.
            
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize from registry: {e}", exc_info=True)
            
    async def _execute_with_stdio(self, server_name: str, command: str, args: list, tool_name: str, arguments: dict) -> dict:
        """Execute a tool by launching stdio subprocess for each call.
        
        This is simpler than managing long-lived connections and avoids
        async context issues.
        
        Args:
            server_name: Name of the server
            command: Command to launch (e.g., "python")
            args: Arguments for the command (e.g., ["-m", "tars_mcp_character"])
            tool_name: MCP tool name (without prefix)
            arguments: Tool arguments
            
        Returns:
            Dict with 'content' or 'error'
        """
        try:
            logger.info(f"Launching MCP server for tool execution: {command} {' '.join(args)}")
            # Use python -m for better stdio handling compared to console scripts
            server_params = StdioServerParameters(
                command=command,
                args=args,
            )
            
            logger.info(f"Creating stdio_client with command: {command} {args}")
            async with stdio_client(server_params) as (read_stream, write_stream):
                # Create and initialize session
                logger.info(f"stdio_client context entered, streams: read={type(read_stream).__name__}, write={type(write_stream).__name__}")
                async with ClientSession(read_stream, write_stream) as session:
                    logger.info(f"ClientSession created, calling initialize()...")
                    try:
                        await session.initialize()
                        logger.info("Session initialized successfully")
                    except asyncio.TimeoutError:
                        logger.error(f"Timeout waiting for initialize response from {command}")
                        raise
                    except Exception as e:
                        logger.error(f"Error during initialize: {e}", exc_info=True)
                        raise
                    
                    # Execute tool
                    logger.info(f"Executing tool: {server_name}:{tool_name} with args: {arguments}")
                    result = await session.call_tool(tool_name, arguments)
                    
                    # Extract content
                    if hasattr(result, 'content') and result.content:
                        content_text = " ".join(
                            item.text if hasattr(item, 'text') else str(item)
                            for item in result.content
                        )
                        logger.info(f"Tool result: {content_text}")
                        return {"content": content_text}
                    else:
                        logger.warning(f"Tool returned no content: {result}")
                        return {"content": ""}
                    
        except Exception as e:
            logger.error(f"Tool execution failed: {e}", exc_info=True)
            return {"error": str(e)}
            
    async def connect_to_http_server(self, server_name: str, url: str):
        """Connect to an MCP server via HTTP.
        
        Args:
            server_name: Name of the server
            url: HTTP URL (e.g., http://mcp-test-server:8080/mcp)
        """
        try:
            logger.info(f"Connecting to MCP server: {server_name} at {url}")
            
            # Create and enter the streamable HTTP context
            http_context = streamablehttp_client(url)
            read_stream, write_stream, _ = await http_context.__aenter__()
            
            # Create and enter the session context
            sess = ClientSession(read_stream, write_stream)
            await sess.__aenter__()
            
            # Initialize session
            init_result = await sess.initialize()
            logger.info(f"✅ Connected to MCP HTTP server: {server_name}")
            logger.debug(f"Session initialized: {init_result}")
            
            # Store both for cleanup
            self.sessions[server_name] = sess
            self.contexts[server_name] = http_context
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP HTTP server {server_name}: {e}", exc_info=True)
            
    async def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool via MCP.
        
        Args:
            tool_name: Full tool name (mcp__server__tool)
            arguments: Tool arguments
            
        Returns:
            Dict with 'content' or 'error'
        """
        if not self._initialized:
            return {"error": "MCP client not initialized"}
            
        tool_info = self.tools.get(tool_name)
        if not tool_info:
            return {"error": f"Unknown tool: {tool_name}"}
            
        server_name = tool_info["server"]
        mcp_tool_name = tool_info["mcp_tool_name"]
        
        # Map server names to Python module commands
        # Use python -m instead of console script for better stdio handling
        command_map = {
            "tars-character": ("python", ["-m", "tars_mcp_character"]),
            "tars-movement": ("python", ["-m", "tars_mcp_movement"]),
        }
        
        command_info = command_map.get(server_name)
        if not command_info:
            return {"error": f"Unknown server: {server_name}"}
            
        command, args = command_info
        return await self._execute_with_stdio(server_name, command, args, mcp_tool_name, arguments)
            
    async def close(self):
        """Close client - nothing to clean up with per-call subprocess approach."""
        self.tools.clear()
        self._initialized = False


# Global instance
_mcp_client: Optional[MCPToolClient] = None


def get_mcp_client() -> MCPToolClient:
    """Get or create the global MCP client instance."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPToolClient()
    return _mcp_client
