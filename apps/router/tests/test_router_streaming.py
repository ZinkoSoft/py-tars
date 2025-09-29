import logging
from typing import Tuple

import pytest

from tars.contracts.envelope import Envelope  # type: ignore[import]
from tars.contracts.registry import register  # type: ignore[import]
from tars.contracts.v1 import (  # type: ignore[import]
    EVENT_TYPE_LLM_REQUEST,
    EVENT_TYPE_SAY,
    LLMResponse,
    LLMStreamDelta,
    TtsSay,
)
from tars.domain.ports import Publisher  # type: ignore[import]
from tars.domain.router import RouterPolicy, RouterSettings  # type: ignore[import]
from tars.runtime.ctx import Ctx  # type: ignore[import]


_EVENT_MODEL_MAP = {
    EVENT_TYPE_SAY: TtsSay,
    EVENT_TYPE_LLM_REQUEST: None,
}


class DummyPublisher(Publisher):
    def __init__(self) -> None:
        self.messages: list[Tuple[str, object]] = []

    async def publish(self, topic: str, payload: bytes, qos: int = 0, retain: bool = False) -> None:  # pragma: no cover - trivial
        envelope = Envelope.model_validate_json(payload)
        model_cls = _EVENT_MODEL_MAP.get(envelope.type)
        parsed = model_cls.model_validate(envelope.data) if model_cls else envelope.data
        self.messages.append((topic, parsed))

    def clear(self) -> None:
        self.messages.clear()

    def decoded(self) -> list[Tuple[str, object]]:
        return list(self.messages)


@pytest.fixture()
def streaming_policy() -> Tuple[RouterPolicy, RouterSettings]:
    settings = RouterSettings(
        router_llm_tts_stream=True,
        stream_min_chars=1,
        stream_max_chars=120,
        stream_boundary_only=True,
    )
    for event_type, topic in settings.as_topic_map().items():
        register(event_type, topic)
    return RouterPolicy(settings), settings


def _make_ctx(policy: RouterPolicy) -> tuple[Ctx, DummyPublisher]:
    publisher = DummyPublisher()
    logger = logging.getLogger("router-stream-test")
    return Ctx(pub=publisher, policy=policy, logger=logger), publisher


@pytest.mark.asyncio
async def test_streaming_skips_duplicate_final_response(streaming_policy: Tuple[RouterPolicy, RouterSettings]) -> None:
    policy, settings = streaming_policy
    ctx, publisher = _make_ctx(policy)
    rid = "rt-stream-duplicate"

    await policy.handle_llm_stream(LLMStreamDelta(id=rid, delta="Certainly! ", done=False), ctx)
    await policy.handle_llm_stream(
        LLMStreamDelta(id=rid, delta="The capital of Florida is Tallahassee. ", done=False),
        ctx,
    )
    await policy.handle_llm_stream(LLMStreamDelta(id=rid, delta="Need anything else?", done=True), ctx)

    tts_messages = [msg for topic, msg in publisher.decoded() if topic == settings.topic_tts_say]
    assert [m.text for m in tts_messages if isinstance(m, TtsSay)] == [
        "Certainly!",
        "The capital of Florida is Tallahassee.",
        "Need anything else?",
    ]
    before_count = len(tts_messages)

    await policy.handle_llm_response(
        LLMResponse(
            id=rid,
            reply="Certainly! The capital of Florida is Tallahassee. Need anything else?",
            provider="openai",
            model="gpt-4o-mini",
        ),
        ctx,
    )

    after_tts = [msg for topic, msg in publisher.decoded() if topic == settings.topic_tts_say]
    assert len(after_tts) == before_count
    assert rid not in policy.llm_stream_segments
    assert rid not in policy.llm_stream_completed


@pytest.mark.asyncio
async def test_streaming_speaks_residual_text(streaming_policy: Tuple[RouterPolicy, RouterSettings]) -> None:
    policy, settings = streaming_policy
    ctx, publisher = _make_ctx(policy)
    rid = "rt-stream-residual"

    await policy.handle_llm_stream(LLMStreamDelta(id=rid, delta="Certainly!", done=False), ctx)
    await policy.handle_llm_stream(LLMStreamDelta(id=rid, delta="", done=True), ctx)
    first_msgs = [msg for topic, msg in publisher.decoded() if topic == settings.topic_tts_say]
    assert [m.text for m in first_msgs if isinstance(m, TtsSay)] == ["Certainly!"]

    await policy.handle_llm_response(
        LLMResponse(
            id=rid,
            reply="Certainly! Additional details for you.",
            provider="openai",
            model="gpt-4o-mini",
        ),
        ctx,
    )

    tts_messages = [msg for topic, msg in publisher.decoded() if topic == settings.topic_tts_say]
    assert [m.text for m in tts_messages if isinstance(m, TtsSay)] == [
        "Certainly!",
        "Additional details for you.",
    ]
    assert rid not in policy.llm_stream_segments
    assert rid not in policy.llm_stream_completed