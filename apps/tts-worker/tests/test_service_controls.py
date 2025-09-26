import asyncio
import signal
import sys
import time
from pathlib import Path
from typing import Any, Generator


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import orjson
import pytest

from tts_worker.service import (
    STATUS_TOPIC,
    PlaybackSession,
    TTSService,
    _HAS_SIGCONT,
    _HAS_SIGSTOP,
)


class FakeMQTTClient:
    def __init__(self) -> None:
        self.published: list[tuple[str, bytes, int, bool]] = []

    async def publish(self, topic: str, payload: bytes, qos: int = 0, retain: bool = False) -> None:
        self.published.append((topic, payload, qos, retain))


class DummyProc:
    def __init__(self) -> None:
        self.signals: list[int] = []
        self.terminated = False
        self.killed = False
        self._returncode: int | None = None

    def poll(self) -> int | None:
        return self._returncode

    def send_signal(self, sig: int) -> None:
        self.signals.append(sig)

    def terminate(self) -> None:
        self.terminated = True
        self._returncode = -signal.SIGTERM

    def wait(self, timeout: float | None = None) -> int | None:
        return self._returncode

    def kill(self) -> None:
        self.killed = True
        self._returncode = -signal.SIGKILL


class DummySynth:
    def synth_and_play(self, text: str, streaming: bool = False, pipeline: bool = True) -> float:
        return 0.0


@pytest.fixture(autouse=True)
def restore_signal_flags(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    # Ensure pause/resume paths remain available in test environment.
    monkeypatch.setattr("tts_worker.service._HAS_SIGSTOP", True)
    monkeypatch.setattr("tts_worker.service._HAS_SIGCONT", True)
    yield
    monkeypatch.setattr("tts_worker.service._HAS_SIGSTOP", _HAS_SIGSTOP, raising=False)
    monkeypatch.setattr("tts_worker.service._HAS_SIGCONT", _HAS_SIGCONT, raising=False)


def _decode_status_messages(messages: list[tuple[str, bytes, int, bool]]) -> list[dict[str, Any]]:
    return [orjson.loads(payload) for topic, payload, *_ in messages if topic == STATUS_TOPIC]


@pytest.mark.asyncio
async def test_pause_without_player_sets_pending_state() -> None:
    service = TTSService(DummySynth())
    client = FakeMQTTClient()
    session = PlaybackSession(utt_id="utt-1", text="hello", started_at=time.time())
    service._current_session = session

    await service._apply_pause(client, session, "wake_interrupt")

    assert session.pause_pending is True
    assert session.paused is True
    statuses = _decode_status_messages(client.published)
    assert statuses[-1]["event"] == "paused"
    assert statuses[-1]["reason"] == "wake_interrupt"


@pytest.mark.asyncio
async def test_pause_sends_signal_when_player_exists() -> None:
    service = TTSService(DummySynth())
    client = FakeMQTTClient()
    session = PlaybackSession(utt_id="utt-2", text="hello", started_at=time.time())
    session.player_proc = DummyProc()
    service._current_session = session

    await service._apply_pause(client, session, "wake_interrupt")

    assert session.pause_pending is False
    assert session.paused is True
    assert session.player_proc is not None
    assert session.player_proc.signals == [signal.SIGSTOP]
    statuses = _decode_status_messages(client.published)
    assert statuses[-1]["event"] == "paused"


@pytest.mark.asyncio
async def test_resume_issues_sigcont_and_status() -> None:
    service = TTSService(DummySynth())
    client = FakeMQTTClient()
    session = PlaybackSession(utt_id="utt-3", text="hello", started_at=time.time())
    proc = DummyProc()
    session.player_proc = proc
    session.paused = True
    service._current_session = session

    await service._apply_resume(client, session, "wake_resume")

    assert session.paused is False
    assert proc.signals[-1] == signal.SIGCONT
    statuses = _decode_status_messages(client.published)
    assert statuses[-1]["event"] == "resumed"
    assert statuses[-1]["reason"] == "wake_resume"


@pytest.mark.asyncio
async def test_stop_terminates_player_and_clears_queue() -> None:
    service = TTSService(DummySynth())
    client = FakeMQTTClient()
    session = PlaybackSession(utt_id="utt-4", text="hello", started_at=time.time())
    proc = DummyProc()
    session.player_proc = proc
    service._current_session = session
    service._agg_id = "utt-4"
    service._agg_texts = ["chunk"]

    await service._apply_stop(client, session, "wake_cancel")

    assert proc.terminated is True or proc.killed is True
    assert service._agg_texts == []
    assert service._agg_id is None
    statuses = _decode_status_messages(client.published)
    assert statuses[-1]["event"] == "stopped"
    assert statuses[-1]["reason"] == "wake_cancel"


@pytest.mark.asyncio
async def test_control_message_ignores_mismatched_id() -> None:
    service = TTSService(DummySynth())
    client = FakeMQTTClient()
    session = PlaybackSession(utt_id="utt-5", text="hello", started_at=time.time())
    service._current_session = session

    await service._handle_control_message(client, {"action": "pause", "reason": "wake", "id": "other"})

    # No status should be emitted because the ids do not match.
    assert not _decode_status_messages(client.published)
