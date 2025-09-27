from __future__ import annotations

import sys
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[3] / "src"
if SRC_DIR.exists():
    src_path = str(SRC_DIR)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


from tars.contracts.envelope import Envelope  # type: ignore[import]
from tars.contracts.v1.llm import (  # type: ignore[import]
    EVENT_TYPE_LLM_REQUEST,
    EVENT_TYPE_LLM_RESPONSE,
    EVENT_TYPE_LLM_STREAM,
    LLMRequest,
    LLMResponse,
    LLMStreamDelta,
)


def _roundtrip(event_type: str, payload: object) -> dict:
    envelope = Envelope.new(event_type=event_type, data=payload, source="test-llm")
    encoded = envelope.model_dump_json().encode()
    decoded = Envelope.model_validate_json(encoded)
    assert decoded.type == event_type
    assert decoded.source == "test-llm"
    return decoded.data


def test_llm_request_roundtrip() -> None:
    req = LLMRequest(
        id="req-123",
        text="Hello world",
        stream=False,
        use_rag=True,
        rag_k=3,
        system="system prompt",
        params={"max_tokens": 128, "temperature": 0.5},
    )
    data = _roundtrip(EVENT_TYPE_LLM_REQUEST, req)
    parsed = LLMRequest.model_validate(data)
    assert parsed.id == req.id
    assert parsed.text == req.text
    assert parsed.message_id == req.message_id
    assert parsed.rag_k == 3
    assert parsed.params == req.params


def test_llm_response_roundtrip() -> None:
    resp = LLMResponse(
        id="req-456",
        reply="All good",
        provider="openai",
        model="gpt-test",
        tokens={"prompt": 42, "completion": 21},
    )
    data = _roundtrip(EVENT_TYPE_LLM_RESPONSE, resp)
    parsed = LLMResponse.model_validate(data)
    assert parsed.id == resp.id
    assert parsed.reply == resp.reply
    assert parsed.tokens == resp.tokens
    assert parsed.message_id == resp.message_id


def test_llm_stream_delta_roundtrip() -> None:
    delta = LLMStreamDelta(
        id="req-789",
        seq=2,
        delta="chunk",
        provider="openai",
        model="gpt-test",
    )
    data = _roundtrip(EVENT_TYPE_LLM_STREAM, delta)
    parsed = LLMStreamDelta.model_validate(data)
    assert parsed.id == delta.id
    assert parsed.seq == 2
    assert parsed.delta == "chunk"
    assert parsed.provider == "openai"
    assert parsed.model == "gpt-test"
    assert parsed.message_id == delta.message_id
