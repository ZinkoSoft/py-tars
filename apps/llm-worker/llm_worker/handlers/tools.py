"""Tool calling and execution."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import orjson as json

from ..mcp_client import get_mcp_client
from ..providers.base import LLMResult

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Handles MCP tool execution and conversation management."""
    
    def __init__(self):
        self.tools: List[dict] = []
        self._initialized = False
    
    async def load_tools_from_registry(self, registry_payload: dict) -> None:
        """Load tools from MCP bridge registry and initialize client."""
        try:
            self.tools = registry_payload.get("tools", [])
            logger.info("Loaded %d tools from registry", len(self.tools))
            
            if self.tools:
                mcp_client = get_mcp_client()
                await mcp_client.initialize_from_registry(registry_payload)
                
                # TODO: Get server URLs from config instead of hardcoded
                await mcp_client.connect_to_server("test-server", "http://mcp-test-server:8080/mcp")
                self._initialized = True
                logger.info("MCP client initialized and connected")
        except Exception as e:
            logger.error("Failed to load tools: %s", e)
    
    def extract_tool_calls(self, result: LLMResult) -> List[dict]:
        """Extract tool calls from LLM result."""
        if hasattr(result, 'tool_calls') and result.tool_calls:
            return result.tool_calls
        return []
    
    async def execute_tool_calls(self, tool_calls: List[dict]) -> List[dict]:
        """Execute tool calls via MCP client.
        
        Returns:
            List of results with call_id and content/error
        """
        if not self._initialized:
            logger.warning("Tool executor not initialized")
            return []
        
        results = []
        mcp_client = get_mcp_client()
        
        for call in tool_calls:
            call_id = call.get("id")
            if not call_id:
                continue
            
            tool_name = call.get("function", {}).get("name")
            arguments_str = call.get("function", {}).get("arguments", "{}")
            
            try:
                arguments = json.loads(arguments_str)
                logger.info("Executing tool: %s with args: %s", tool_name, arguments)
                
                result = await mcp_client.execute_tool(tool_name, arguments)
                
                if "error" in result and result.get("error"):
                    results.append({"call_id": call_id, "error": result["error"]})
                    logger.error("Tool %s failed: %s", tool_name, result["error"])
                else:
                    results.append({"call_id": call_id, "content": result.get("content", "")})
                    logger.info("Tool %s succeeded: %s", tool_name, result.get("content", "")[:100])
                    
            except Exception as e:
                logger.error("Failed to execute tool %s: %s", tool_name, e, exc_info=True)
                results.append({"call_id": call_id, "error": str(e)})
        
        return results
    
    @staticmethod
    def format_tool_messages(tool_results: List[dict]) -> List[dict]:
        """Format tool results as OpenAI chat messages."""
        messages = []
        for result in tool_results:
            error = result.get("error")
            content = result.get("content") if not error else error
            messages.append({
                "role": "tool",
                "content": content or "",
                "tool_call_id": result["call_id"]
            })
        return messages
    
    async def load_tools(self, payload: bytes) -> None:
        """Load tools from raw payload (wrapper for backward compatibility)."""
        try:
            data = json.loads(payload)
            await self.load_tools_from_registry(data)
        except Exception as e:
            logger.error("Failed to load tools from payload: %s", e)
    
    async def handle_tool_result(self, payload: bytes) -> None:
        """Handle tool result (legacy compatibility - no-op with direct MCP)."""
        logger.debug("Tool result received (legacy handler - ignored with direct MCP)")
