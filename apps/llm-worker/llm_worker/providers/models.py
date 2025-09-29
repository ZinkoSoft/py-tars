from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str

    model_config = {"extra": "ignore"}


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = False

    model_config = {"extra": "forbid"}


class ChoiceDelta(BaseModel):
    content: Optional[str] = None
    role: Optional[str] = None

    model_config = {"extra": "ignore"}


class Choice(BaseModel):
    index: int = 0
    delta: ChoiceDelta = Field(default_factory=ChoiceDelta)
    finish_reason: Optional[str] = None
    logprobs: Any | None = None

    model_config = {"extra": "ignore"}


class StreamChunk(BaseModel):
    id: Optional[str] = None
    object: Optional[str] = None
    created: Optional[int] = None
    model: Optional[str] = None
    choices: list[Choice] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChatMessage
    finish_reason: Optional[str] = None
    logprobs: Any | None = None

    model_config = {"extra": "ignore"}


class Usage(BaseModel):
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    model_config = {"extra": "forbid"}


class ChatCompletionResponse(BaseModel):
    choices: list[ChatCompletionChoice]
    usage: Optional[Usage] = None

    model_config = {"extra": "forbid"}


def build_messages(prompt: str, system: str | None) -> list[ChatMessage]:
    messages: list[ChatMessage] = []
    if system:
        messages.append(ChatMessage(role="system", content=system))
    messages.append(ChatMessage(role="user", content=prompt))
    return messages
