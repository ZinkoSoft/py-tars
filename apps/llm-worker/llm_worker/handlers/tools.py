"""Tool calling and execution."""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, List

import orjson as json

from ..mcp_client import get_mcp_client
from ..providers.base import LLMResult

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Handles MCP tool execution and conversation management."""
    
    def __init__(self):
        self.tools: List[dict] = []
        self._initialized = False
        self._pending_tool_calls: Dict[str, asyncio.Future] = {}  # call_id -> Future
    
    async def load_tools_from_registry(self, registry_payload: dict) -> None:
        """Load tools from MCP bridge registry and initialize client."""
        logger.info("load_tools_from_registry called with payload keys: %s", list(registry_payload.keys()))
        try:
            self.tools = registry_payload.get("tools", [])
            logger.info("Loaded %d tools from registry", len(self.tools))
            
            if self.tools:
                logger.info("First tool format: %s", self.tools[0] if self.tools else "N/A")
                mcp_client = get_mcp_client()
                await mcp_client.initialize_from_registry(registry_payload)
                self._initialized = True
                logger.info("MCP client initialized with %d tools (servers will connect on-demand)", len(self.tools))
            else:
                logger.warning("No tools found in registry payload!")
        except Exception as e:
            logger.error("Failed to load tools: %s", e, exc_info=True)
    
    def extract_tool_calls(self, result: LLMResult) -> List[dict]:
        """Extract tool calls from LLM result."""
        if hasattr(result, 'tool_calls') and result.tool_calls:
            return result.tool_calls
        return []
    
    async def execute_tool_calls(self, tool_calls: List[dict], mqtt_client, client) -> List[dict]:
        """Execute tool calls via MQTT to mcp-bridge.
        
        Args:
            tool_calls: List of tool calls from LLM
            mqtt_client: MQTT client wrapper
            client: Connected MQTT client
            
        Returns:
            List of results with call_id and content/error
        """
        if not self._initialized:
            logger.warning("Tool executor not initialized")
            return []
        
        results = []
        
        # Publish all tool calls to MQTT and create futures
        for call in tool_calls:
            call_id = call.get("id")
            if not call_id:
                continue
            
            tool_name = call.get("function", {}).get("name")
            arguments_str = call.get("function", {}).get("arguments", "{}")
            
            try:
                arguments = json.loads(arguments_str)
                logger.info("Requesting tool execution via MQTT: %s (call_id=%s)", tool_name, call_id)
                
                # Create future for this call
                future = asyncio.Future()
                self._pending_tool_calls[call_id] = future
                
                # Publish tool call request to mcp-bridge
                await mqtt_client.publish_tool_call(client, call_id, tool_name, arguments)
                    
            except Exception as e:
                logger.error("Failed to publish tool call %s: %s", tool_name, e, exc_info=True)
                results.append({"call_id": call_id, "error": str(e)})
        
        # Wait for all results with timeout
        timeout = 30.0  # 30 second timeout for tool execution
        for call_id in list(self._pending_tool_calls.keys()):
            future = self._pending_tool_calls.get(call_id)
            if not future:
                continue
                
            try:
                logger.debug("Waiting for tool result: call_id=%s (timeout=%ss)", call_id, timeout)
                result = await asyncio.wait_for(future, timeout=timeout)
                results.append(result)
            except asyncio.TimeoutError:
                error_msg = f"Tool execution timeout ({timeout}s)"
                logger.error("Tool call timeout: call_id=%s", call_id)
                results.append({"call_id": call_id, "error": error_msg})
            finally:
                # Clean up future
                self._pending_tool_calls.pop(call_id, None)
        
        return results
    
    def handle_tool_result(self, call_id: str, content: str = None, error: str = None):
        """Handle tool execution result from mcp-bridge.
        
        Args:
            call_id: Tool call ID
            content: Tool result content (success)
            error: Error message (failure)
        """
        future = self._pending_tool_calls.get(call_id)
        if not future or future.done():
            logger.warning("Received tool result for unknown or completed call_id: %s", call_id)
            return
        
        result = {"call_id": call_id}
        if error:
            result["error"] = error
            logger.info("Tool call %s failed: %s", call_id, error)
        else:
            result["content"] = content or ""
            logger.info("Tool call %s succeeded (%d chars)", call_id, len(content or ""))
        
        # Resolve the future
        future.set_result(result)
    
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
