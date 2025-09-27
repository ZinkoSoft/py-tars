import logging
from typing import Tuple

import pytest

from tars.contracts.envelope import Envelope  # type: ignore[import]
from tars.contracts.registry import register  # type: ignore[import]
from tars.contracts.v1 import (  # type: ignore[import]
    EVENT_TYPE_LLM_REQUEST,
    EVENT_TYPE_SAY,
    FinalTranscript,
    LLMRequest,
    TtsSay,
    WakeEvent,
)
from tars.domain.ports import Publisher  # type: ignore[import]
from tars.domain.router import RouterPolicy, RouterSettings  # type: ignore[import]
from tars.runtime.ctx import Ctx  # type: ignore[import]


_EVENT_MODEL_MAP = {
    EVENT_TYPE_SAY: TtsSay,
    EVENT_TYPE_LLM_REQUEST: LLMRequest,
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
def router_policy() -> Tuple[RouterPolicy, RouterSettings]:
    settings = RouterSettings(
        wake_ack_text="Ready.",
        wake_ack_choices_raw="Ready.",
        wake_reprompt_text="",
        wake_interrupt_text="Pausing.",
        wake_resume_text="Resuming.",
        wake_cancel_text="Cancelled.",
        wake_timeout_text="Are you still there?",
        live_mode_enter_ack="Live mode on.",
        live_mode_exit_ack="Live mode off.",
        live_mode_active_hint="Already on.",
        live_mode_inactive_hint="Already off.",
    )
    for event_type, topic in settings.as_topic_map().items():
        register(event_type, topic)
    return RouterPolicy(settings), settings


def _make_ctx(policy: RouterPolicy) -> tuple[Ctx, DummyPublisher]:
    publisher = DummyPublisher()
    logger = logging.getLogger("router-test")
    return Ctx(pub=publisher, policy=policy, logger=logger), publisher


def test_default_ack_choices_when_blank() -> None:
    settings = RouterSettings(wake_ack_text="", wake_ack_choices_raw="", wake_ack_enabled=True)
    assert settings.wake_ack_choices == ("Hmm?", "Huh?", "Yes?")
    assert settings.wake_ack_text == "Hmm?"


@pytest.mark.asyncio
async def test_drop_without_wake(router_policy: Tuple[RouterPolicy, RouterSettings]) -> None:
    policy, _settings = router_policy
    ctx, publisher = _make_ctx(policy)

    transcript = FinalTranscript(text="What's the weather today?")
    await policy.handle_stt_final(transcript, ctx)
    assert publisher.messages == []


@pytest.mark.asyncio
async def test_wake_then_llm_request(router_policy: Tuple[RouterPolicy, RouterSettings]) -> None:
    policy, settings = router_policy
    ctx, publisher = _make_ctx(policy)

    await policy.handle_wake_event(WakeEvent(type="wake"), ctx)
    decoded = publisher.decoded()
    assert decoded and decoded[0][0] == settings.topic_tts_say
    say = decoded[0][1]
    assert isinstance(say, TtsSay)
    assert say.text == "Ready."
    assert say.wake_ack is True
    publisher.clear()

    await policy.handle_stt_final(FinalTranscript(text="What's the weather today?"), ctx)
    decoded = publisher.decoded()
    assert decoded and decoded[0][0] == settings.topic_llm_req
    llm_req = decoded[0][1]
    assert isinstance(llm_req, LLMRequest)
    assert llm_req.text == "What's the weather today?"


@pytest.mark.asyncio
async def test_wake_inline_rule(router_policy: Tuple[RouterPolicy, RouterSettings]) -> None:
    policy, settings = router_policy
    ctx, publisher = _make_ctx(policy)

    await policy.handle_wake_event(WakeEvent(type="wake"), ctx)
    publisher.clear()

    await policy.handle_stt_final(FinalTranscript(text="Hey Tars what time is it"), ctx)
    decoded = publisher.decoded()
    assert decoded and decoded[0][0] == settings.topic_tts_say
    say = decoded[0][1]
    assert isinstance(say, TtsSay)
    assert "It is" in say.text


@pytest.mark.asyncio
async def test_live_mode_enable_disable(router_policy: Tuple[RouterPolicy, RouterSettings]) -> None:
    policy, settings = router_policy
    ctx, publisher = _make_ctx(policy)

    await policy.handle_wake_event(WakeEvent(type="wake"), ctx)
    publisher.clear()

    await policy.handle_stt_final(FinalTranscript(text="enter live mode"), ctx)
    decoded = publisher.decoded()
    assert decoded and decoded[0][0] == settings.topic_tts_say
    say = decoded[0][1]
    assert isinstance(say, TtsSay)
    assert say.text == "Live mode on."
    assert policy.live_mode is True
    publisher.clear()

    await policy.handle_stt_final(FinalTranscript(text="tell me a joke"), ctx)
    decoded = publisher.decoded()
    assert decoded and decoded[0][0] == settings.topic_llm_req
    llm_req = decoded[0][1]
    assert isinstance(llm_req, LLMRequest)
    assert llm_req.text == "tell me a joke"
    publisher.clear()

    await policy.handle_stt_final(FinalTranscript(text="exit live mode"), ctx)
    decoded = publisher.decoded()
    assert decoded and decoded[0][0] == settings.topic_tts_say
    say = decoded[0][1]
    assert isinstance(say, TtsSay)
    assert say.text == "Live mode off."
    assert policy.live_mode is False
    publisher.clear()

    await policy.handle_stt_final(FinalTranscript(text="tell me a joke"), ctx)
    assert publisher.messages == []


@pytest.mark.asyncio
async def test_timeout_event_closes_window(router_policy: Tuple[RouterPolicy, RouterSettings]) -> None:
    policy, settings = router_policy
    ctx, publisher = _make_ctx(policy)

    await policy.handle_wake_event(WakeEvent(type="wake"), ctx)
    assert policy.wake_session_active is True
    publisher.clear()

    await policy.handle_wake_event(WakeEvent(type="timeout"), ctx)
    assert policy.wake_session_active is False
    publisher.clear()

    await policy.handle_stt_final(FinalTranscript(text="Tell me something"), ctx)
    assert publisher.messages == []
