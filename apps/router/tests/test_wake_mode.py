import orjson
import pytest

from apps.router.main import Config, RouterService


class DummyClient:
    def __init__(self) -> None:
        self.messages = []

    async def publish(self, topic: str, payload: bytes) -> None:  # pragma: no cover - simple mock
        self.messages.append((topic, payload))

    def clear(self) -> None:
        self.messages.clear()

    def decoded(self):
        return [(topic, orjson.loads(payload)) for topic, payload in self.messages]


@pytest.fixture()
def router_service() -> RouterService:
    cfg = Config(
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
    return RouterService(cfg)


def test_default_ack_choices_when_blank() -> None:
    cfg = Config(wake_ack_text="", wake_ack_choices_raw="", wake_ack_enabled=True)
    assert cfg.wake_ack_choices == ("Hmm?", "Huh?", "Yes?")
    assert cfg.wake_ack_text == "Hmm?"


@pytest.mark.asyncio
async def test_drop_without_wake(router_service: RouterService) -> None:
    client = DummyClient()
    payload = orjson.dumps({"text": "What's the weather today?"})
    await router_service.handle_stt_final(client, payload)
    assert client.messages == []


@pytest.mark.asyncio
async def test_wake_then_llm_request(router_service: RouterService) -> None:
    client = DummyClient()
    await router_service.handle_wake_event(client, orjson.dumps({"type": "wake"}))
    decoded = client.decoded()
    assert decoded and decoded[0][0] == router_service.cfg.topic_tts_say
    assert decoded[0][1]["text"] == "Ready."
    assert decoded[0][1].get("wake_ack") is True
    client.clear()

    await router_service.handle_stt_final(client, orjson.dumps({"text": "What's the weather today?"}))
    decoded = client.decoded()
    assert decoded and decoded[0][0] == router_service.cfg.topic_llm_req
    assert decoded[0][1]["text"] == "What's the weather today?"


@pytest.mark.asyncio
async def test_wake_inline_rule(router_service: RouterService) -> None:
    client = DummyClient()
    await router_service.handle_wake_event(client, orjson.dumps({"type": "wake"}))
    client.clear()

    await router_service.handle_stt_final(client, orjson.dumps({"text": "Hey Tars what time is it"}))
    decoded = client.decoded()
    assert decoded and decoded[0][0] == router_service.cfg.topic_tts_say
    assert "It is" in decoded[0][1]["text"]


@pytest.mark.asyncio
async def test_live_mode_enable_disable(router_service: RouterService) -> None:
    client = DummyClient()
    await router_service.handle_wake_event(client, orjson.dumps({"type": "wake"}))
    client.clear()

    # Enable live mode within wake window
    await router_service.handle_stt_final(client, orjson.dumps({"text": "enter live mode"}))
    decoded = client.decoded()
    assert decoded and decoded[0][0] == router_service.cfg.topic_tts_say
    assert decoded[0][1]["text"] == "Live mode on."
    assert router_service.live_mode is True
    client.clear()

    # Live mode should allow routing without wake
    await router_service.handle_stt_final(client, orjson.dumps({"text": "tell me a joke"}))
    decoded = client.decoded()
    assert decoded and decoded[0][0] == router_service.cfg.topic_llm_req
    assert decoded[0][1]["text"] == "tell me a joke"
    client.clear()

    # Disable live mode
    await router_service.handle_stt_final(client, orjson.dumps({"text": "exit live mode"}))
    decoded = client.decoded()
    assert decoded and decoded[0][0] == router_service.cfg.topic_tts_say
    assert decoded[0][1]["text"] == "Live mode off."
    assert router_service.live_mode is False
    client.clear()

    # After disabling, utterances without wake should drop
    await router_service.handle_stt_final(client, orjson.dumps({"text": "tell me a joke"}))
    assert client.messages == []


@pytest.mark.asyncio
async def test_timeout_event_closes_window(router_service: RouterService) -> None:
    client = DummyClient()
    await router_service.handle_wake_event(client, orjson.dumps({"type": "wake"}))
    assert router_service.wake_session_active is True
    client.clear()

    await router_service.handle_wake_event(client, orjson.dumps({"type": "timeout"}))
    assert router_service.wake_session_active is False
    client.clear()

    await router_service.handle_stt_final(client, orjson.dumps({"text": "Tell me something"}))
    assert client.messages == []
