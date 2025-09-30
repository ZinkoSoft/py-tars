from __future__ import annotations

import uuid
from pydantic import BaseModel, Field
from typing import List, Literal

EVENT_TYPE_LLM_REQUEST = "llm.request"
EVENT_TYPE_LLM_RESPONSE = "llm.response"
EVENT_TYPE_LLM_STREAM = "llm.stream"
EVENT_TYPE_LLM_CANCEL = "llm.cancel"


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
