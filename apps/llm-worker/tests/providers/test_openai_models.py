from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROVIDER_DIR = Path(__file__).resolve().parents[2]
if str(PROVIDER_DIR) not in sys.path:
    sys.path.insert(0, str(PROVIDER_DIR))

from llm_worker.providers.models import (  # type: ignore[import]
    ChatCompletionRequest,
    ChatCompletionResponse,
    StreamChunk,
    build_messages,
)


def test_build_messages_with_system_prompt() -> None:
    messages = build_messages("hi", "system prompt")
    assert len(messages) == 2
    assert messages[0].role == "system"
    assert messages[0].content == "system prompt"
    assert messages[1].role == "user"
    assert messages[1].content == "hi"


def test_build_messages_without_system_prompt() -> None:
    messages = build_messages("hi", None)
    assert len(messages) == 1
    assert messages[0].role == "user"


def test_chat_completion_request_serialization() -> None:
    req = ChatCompletionRequest(
        model="gpt-test",
        messages=build_messages("hello", "system"),
        temperature=0.5,
        top_p=0.9,
        max_tokens=256,
        stream=True,
    )
    payload = req.model_dump(exclude_none=True)
    assert payload["max_tokens"] == 256
    assert payload["stream"] is True
    assert len(payload["messages"]) == 2


def test_chat_completion_response_parsing() -> None:
    raw = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "response text",
                }
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    parsed = ChatCompletionResponse.model_validate(raw)
    assert parsed.choices[0].message.content == "response text"
    assert parsed.usage and parsed.usage.total_tokens == 15


def test_stream_chunk_parsing() -> None:
    raw = {
        "choices": [
            {
                "delta": {
                    "content": "partial",
                }
            }
        ]
    }
    parsed = StreamChunk.model_validate(raw)
    assert parsed.choices[0].delta.content == "partial"


def test_stream_chunk_accepts_extra_fields() -> None:
    raw = {
        "id": "abc",
        "object": "chat.completion.chunk",
        "created": 123,
        "model": "gpt-test",
        "choices": [
            {
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": "Hi",
                },
                "finish_reason": None,
                "logprobs": None,
            }
        ],
    }
    parsed = StreamChunk.model_validate(raw)
    assert parsed.choices[0].delta.role == "assistant"
    assert parsed.choices[0].delta.content == "Hi"


@pytest.mark.parametrize(
    "invalid",
    [
        {"choices": [{"delta": {"content": 123}}]},
    ],
)
def test_stream_chunk_validation_errors(invalid: dict) -> None:
    with pytest.raises(Exception):
        StreamChunk.model_validate(invalid)
