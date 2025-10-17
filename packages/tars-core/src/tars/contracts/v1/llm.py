from __future__ import annotations

import uuid
from pydantic import BaseModel, Field
from typing import List, Literal

# Event types (legacy - prefer topic constants)
EVENT_TYPE_LLM_REQUEST = "llm.request"
EVENT_TYPE_LLM_RESPONSE = "llm.response"
EVENT_TYPE_LLM_STREAM = "llm.stream"
EVENT_TYPE_LLM_CANCEL = "llm.cancel"
EVENT_TYPE_TOOLS_REGISTRY = "llm.tools.registry"
EVENT_TYPE_TOOL_CALL_REQUEST = "llm.tool.call.request"
EVENT_TYPE_TOOL_CALL_RESULT = "llm.tool.call.result"

# MQTT Topic constants
TOPIC_LLM_REQUEST = "llm/request"
TOPIC_LLM_RESPONSE = "llm/response"
TOPIC_LLM_STREAM = "llm/stream"
TOPIC_LLM_CANCEL = "llm/cancel"
TOPIC_LLM_TOOLS_REGISTRY = "llm/tools/registry"
TOPIC_LLM_TOOL_CALL_REQUEST = "llm/tool.call.request"
TOPIC_LLM_TOOL_CALL_RESULT = "llm/tool.call.result"


class ConversationMessage(BaseModel):
    """A message in the conversation history."""
    role: Literal["user", "assistant"]
    content: str
    timestamp: float | None = None

    model_config = {"extra": "forbid"}


class BaseLLMMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)

    model_config = {"extra": "forbid"}


class LLMRequest(BaseLLMMessage):
    id: str
    text: str
    stream: bool = True
    use_rag: bool | None = None
    rag_k: int | None = None
    system: str | None = None
    params: dict | None = None
    conversation_history: List[ConversationMessage] | None = None


class LLMResponse(BaseLLMMessage):
    id: str
    reply: str | None = None
    error: str | None = None
    provider: str | None = None
    model: str | None = None
    tokens: dict | None = None


class LLMStreamDelta(BaseLLMMessage):
    id: str
    seq: int | None = None
    delta: str | None = None
    done: bool = False
    provider: str | None = None
    model: str | None = None


class LLMCancel(BaseLLMMessage):
    id: str


class ToolSpec(BaseModel):
    """Specification for a tool that can be called by the LLM."""
    type: str = "function"
    function: dict  # OpenAI function spec

    model_config = {"extra": "forbid"}


class ToolsRegistry(BaseLLMMessage):
    """Registry of available tools published by MCP bridge."""
    tools: List[ToolSpec]


class ToolCallRequest(BaseLLMMessage):
    """Request to call a tool."""
    call_id: str
    name: str  # "mcp:server:tool_name"
    arguments: dict


class ToolCallResult(BaseLLMMessage):
    """Result of a tool call."""
    call_id: str
    result: dict | None = None
    error: str | None = None
