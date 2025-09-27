import asyncio
import signal
import sys
import time
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SRC_DIR = Path(__file__).resolve().parents[3] / "src"
if SRC_DIR.exists():
    src_path = str(SRC_DIR)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

import pytest

from tars.contracts.v1 import TtsSay, TtsStatus  # type: ignore[import]
from tars.domain.tts import (  # type: ignore[import]
    PlaybackSession,
    TTSCallbacks,
    TTSConfig,
    TTSControlMessage,
    TTSDomainService,
)


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
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def synth_and_play(self, text: str, streaming: bool = False, pipeline: bool = True) -> float:
        self.calls.append({"text": text, "streaming": streaming, "pipeline": pipeline})
        return 0.0

def make_callbacks(collected: list[TtsStatus]) -> TTSCallbacks:
    async def publish_status(
        event: str,
        text: str,
        utt_id: str | None,
        reason: str | None,
        wake_ack: bool | None,
    ) -> None:
        collected.append(
            TtsStatus(
                event=event,  # type: ignore[arg-type]
                text=text,
                utt_id=utt_id,
                reason=reason,
                wake_ack=wake_ack,
            )
        )

    return TTSCallbacks(publish_status=publish_status)


def make_service(
    *,
    streaming_enabled: bool = False,
    pipeline_enabled: bool = True,
    aggregate_enabled: bool = False,
    aggregate_debounce_ms: int = 150,
    aggregate_single_wav: bool = True,
    wake_ack_synth: DummySynth | None = None,
) -> tuple[TTSDomainService, DummySynth, list[TtsStatus], TTSCallbacks]:
    config = TTSConfig(
        streaming_enabled=streaming_enabled,
        pipeline_enabled=pipeline_enabled,
        aggregate_enabled=aggregate_enabled,
        aggregate_debounce_ms=aggregate_debounce_ms,
        aggregate_single_wav=aggregate_single_wav,
    )
    synth = DummySynth()
    service = TTSDomainService(synth, config, wake_synth=wake_ack_synth)
    statuses: list[TtsStatus] = []
    callbacks = make_callbacks(statuses)
    return service, synth, statuses, callbacks


async def wait_for_condition(predicate, *, timeout: float = 0.5, interval: float = 0.01) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(interval)
    raise AssertionError("Timed out waiting for condition")


@pytest.mark.asyncio
async def test_pause_without_player_sets_pending_state() -> None:
    service, _synth, statuses, callbacks = make_service()
    session = PlaybackSession(utt_id="utt-1", text="hello", started_at=time.time())
    service._current_session = session  # type: ignore[attr-defined]

    await service.handle_control(TTSControlMessage(action="pause", reason="wake_interrupt", request_id="utt-1"), callbacks)

    assert session.pause_pending is True
    assert session.paused is True
    assert statuses[-1].event == "paused"
    assert statuses[-1].reason == "wake_interrupt"


@pytest.mark.asyncio
async def test_pause_sends_signal_when_player_exists() -> None:
    service, _synth, statuses, callbacks = make_service()
    session = PlaybackSession(utt_id="utt-2", text="hello", started_at=time.time())
    session.player_proc = DummyProc()
    service._current_session = session  # type: ignore[attr-defined]

    await service.handle_control(TTSControlMessage(action="pause", reason="wake_interrupt", request_id="utt-2"), callbacks)

    assert session.pause_pending is False
    assert session.paused is True
    assert session.player_proc is not None
    assert session.player_proc.signals == [signal.SIGSTOP]
    assert statuses[-1].event == "paused"


@pytest.mark.asyncio
async def test_resume_issues_sigcont_and_status() -> None:
    service, _synth, statuses, callbacks = make_service()
    session = PlaybackSession(utt_id="utt-3", text="hello", started_at=time.time())
    proc = DummyProc()
    session.player_proc = proc
    session.paused = True
    service._current_session = session  # type: ignore[attr-defined]

    await service.handle_control(TTSControlMessage(action="resume", reason="wake_resume", request_id="utt-3"), callbacks)

    assert session.paused is False
    assert proc.signals[-1] == signal.SIGCONT
    assert statuses[-1].event == "resumed"
    assert statuses[-1].reason == "wake_resume"


@pytest.mark.asyncio
async def test_stop_terminates_player_and_clears_queue() -> None:
    service, _synth, statuses, callbacks = make_service()
    session = PlaybackSession(utt_id="utt-4", text="hello", started_at=time.time())
    proc = DummyProc()
    session.player_proc = proc
    service._current_session = session  # type: ignore[attr-defined]
    service._agg_id = "utt-4"  # type: ignore[attr-defined]
    service._agg_texts = ["chunk"]  # type: ignore[attr-defined]

    await service.handle_control(TTSControlMessage(action="stop", reason="wake_cancel", request_id="utt-4"), callbacks)

    assert proc.terminated is True or proc.killed is True
    assert service._agg_texts == []  # type: ignore[attr-defined]
    assert service._agg_id is None  # type: ignore[attr-defined]
    assert statuses[-1].event == "stopped"
    assert statuses[-1].reason == "wake_cancel"


@pytest.mark.asyncio
async def test_control_message_ignores_mismatched_id() -> None:
    service, _synth, statuses, callbacks = make_service()
    session = PlaybackSession(utt_id="utt-5", text="hello", started_at=time.time())
    service._current_session = session  # type: ignore[attr-defined]

    await service.handle_control(TTSControlMessage(action="pause", reason="wake", request_id="other"), callbacks)

    # No status should be emitted because the ids do not match.
    assert not statuses


@pytest.mark.asyncio
async def test_handle_say_aggregates_into_single_playback() -> None:
    service, synth, statuses, callbacks = make_service(
        aggregate_enabled=True,
        aggregate_single_wav=True,
        aggregate_debounce_ms=10,
    )

    await service.handle_say(TtsSay(text="Hello", utt_id="utt-agg"), callbacks)
    assert service._agg_id == "utt-agg"  # type: ignore[attr-defined]
    assert service._agg_texts == ["Hello"]  # type: ignore[attr-defined]

    await service.handle_say(TtsSay(text="world", utt_id="utt-agg"), callbacks)

    await wait_for_condition(lambda: len(statuses) >= 2)

    assert [s.event for s in statuses] == ["speaking_start", "speaking_end"]
    assert all(s.utt_id == "utt-agg" for s in statuses)
    assert len(synth.calls) == 1
    assert synth.calls[0]["text"] == "Hello world"
    assert synth.calls[0]["streaming"] is False
    assert synth.calls[0]["pipeline"] is False
    assert service._agg_texts == []  # type: ignore[attr-defined]
    assert service._agg_id is None  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_wake_ack_uses_fallback_synth() -> None:
    fallback = DummySynth()
    service, primary, statuses, callbacks = make_service(wake_ack_synth=fallback)

    await service.handle_say(TtsSay(text="Ping", utt_id="utt-wake", wake_ack=True), callbacks)

    await wait_for_condition(lambda: len(statuses) >= 2)

    assert len(fallback.calls) == 1
    assert fallback.calls[0]["text"] == "Ping"
    assert len(primary.calls) == 0
