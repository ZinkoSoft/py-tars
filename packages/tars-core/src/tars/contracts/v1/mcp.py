"""MCP (Model Context Protocol) event contracts."""

from pydantic import BaseModel, Field
from typing import Any, Dict, Optional


# Event types
EVENT_TYPE_TOOLS_REGISTRY = "llm/tools/registry"
EVENT_TYPE_TOOL_CALL_REQUEST = "llm/tool.call.request"
EVENT_TYPE_TOOL_CALL_RESULT = "llm/tool.call.result"


class ToolSpec(BaseModel):
    """Specification for a tool function."""
    type: str = "function"
    function: Dict[str, Any] = Field(..., description="OpenAI-style function specification")


class ToolsRegistry(BaseModel):
    """Registry of available tools."""
    tools: list[ToolSpec] = Field(default_factory=list, description="List of available tools")


class ToolCallRequest(BaseModel):
    """Request to execute a tool."""
    call_id: str = Field(..., description="Unique identifier for this tool call")
    name: str = Field(..., description="Tool name in format 'mcp:server:tool'")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")


class ToolCallResult(BaseModel):
    """Result of a tool execution."""
    call_id: str = Field(..., description="Unique identifier for this tool call")
    result: Optional[Any] = Field(None, description="Tool execution result")
    error_msg: Optional[str] = Field(None, description="Error message if execution failed")