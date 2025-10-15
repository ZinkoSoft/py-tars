from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROVIDER_DIR = Path(__file__).resolve().parents[2]
if str(PROVIDER_DIR) not in sys.path:
    sys.path.insert(0, str(PROVIDER_DIR))

from llm_worker.providers.models import (  # type: ignore[import]  # noqa: E402
    ChatCompletionRequest,
    ChatCompletionResponse,
    StreamChunk,
    build_messages,
)
from llm_worker.providers.openai import (  # type: ignore[import]  # noqa: E402
    OpenAIEndpoint,
    _ModelRouter,
    build_responses_input,
    extract_responses_output,
    parse_responses_event,
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


def test_model_router_prefix_matching() -> None:
    router = _ModelRouter(["gpt-5*", "gpt-4.1"])
    assert router.endpoint_for("gpt-5") is OpenAIEndpoint.RESPONSES
    assert router.endpoint_for("gpt-5-nano") is OpenAIEndpoint.RESPONSES
    assert router.endpoint_for("gpt-3.5-turbo") is OpenAIEndpoint.CHAT_COMPLETIONS


def test_build_responses_input_normalises_text() -> None:
    messages = [{"role": "user", "content": "hello"}]
    converted = build_responses_input(messages)
    assert converted[0]["role"] == "user"
    assert converted[0]["content"] == "hello"


def test_build_responses_input_strips_tool_metadata() -> None:
    messages = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "call-1", "type": "function"}],
        }
    ]
    converted = build_responses_input(messages)
    assert "tool_calls" not in converted[0]
    assert converted[0]["content"] == ""


def test_extract_responses_output_handles_tool_calls() -> None:
    payload = {
        "output": [
            {
                "content": [
                    {"type": "output_text", "text": "Hi there"},
                    {
                        "type": "tool_call",
                        "id": "call_x",
                        "name": "lookup",
                        "arguments": {"city": "Paris"},
                    },
                ]
            }
        ]
    }
    text, tool_calls = extract_responses_output(payload)
    assert text == "Hi there"
    assert tool_calls and tool_calls[0]["function"]["name"] == "lookup"
    assert tool_calls[0]["function"]["arguments"] == '{"city":"Paris"}'


def test_parse_responses_event_delta() -> None:
    delta, done, response = parse_responses_event(
        {"type": "response.output_text.delta", "delta": "Hello"}
    )
    assert delta == "Hello"
    assert done is False
    assert response is None


def test_parse_responses_event_completed() -> None:
    payload = {"type": "response.completed", "response": {"usage": {"input": 1}}}
    delta, done, response = parse_responses_event(payload)
    assert delta is None
    assert done is True
    assert response == payload["response"]


def test_parse_responses_event_error() -> None:
    with pytest.raises(RuntimeError):
        parse_responses_event({"type": "response.error", "error": {"message": "boom"}})
