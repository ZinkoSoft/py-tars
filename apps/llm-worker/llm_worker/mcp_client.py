"""
MCP Tool Client for LLM Worker.

Provides direct access to MCP tools without going through MQTT.
Loads tools from registry and executes them via MCP protocol.
"""
import asyncio
import logging
import orjson
from typing import Any, Dict, List, Optional

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger(__name__)


class MCPToolClient:
    """Client for executing MCP tools directly."""
    
    def __init__(self):
        self.sessions: Dict[str, ClientSession] = {}
        self.contexts: Dict[str, Any] = {}  # Store context managers for cleanup
        self.tools: Dict[str, dict] = {}  # tool_name -> {server, mcp_tool_name, schema}
        self._initialized = False
        
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
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize from registry: {e}", exc_info=True)
            
    async def connect_to_server(self, server_name: str, url: str):
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
            logger.info(f"✅ Connected to MCP server: {server_name}")
            logger.debug(f"Session initialized: {init_result}")
            
            # Store both for cleanup
            self.sessions[server_name] = sess
            self.contexts[server_name] = http_context
            
        except Exception as e:
            logger.error(f"Failed to connect to MCP server {server_name}: {e}", exc_info=True)
            
    async def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool by name.
        
        Args:
            tool_name: Full tool name (e.g., mcp__test-server__add)
            arguments: Tool arguments as dict
            
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
        
        session = self.sessions.get(server_name)
        if not session:
            return {"error": f"Not connected to server: {server_name}"}
            
        try:
            logger.info(f"Executing tool: {server_name}:{mcp_tool_name} with args: {arguments}")
            
            # Call the MCP server
            result = await session.call_tool(mcp_tool_name, arguments)
            
            # Extract content from CallToolResult
            if hasattr(result, 'content') and result.content:
                # result.content is a list of content items
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
            
    async def close(self):
        """Close all MCP sessions."""
        for name in list(self.sessions.keys()):
            try:
                # Close session first
                if name in self.sessions:
                    await self.sessions[name].__aexit__(None, None, None)
                    logger.info(f"Closed session: {name}")
                
                # Then close HTTP context
                if name in self.contexts:
                    await self.contexts[name].__aexit__(None, None, None)
                    logger.info(f"Closed context: {name}")
                    
            except Exception as e:
                logger.error(f"Error closing {name}: {e}")
        
        self.sessions.clear()
        self.contexts.clear()


# Global instance
_mcp_client: Optional[MCPToolClient] = None


def get_mcp_client() -> MCPToolClient:
    """Get or create the global MCP client instance."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPToolClient()
    return _mcp_client
