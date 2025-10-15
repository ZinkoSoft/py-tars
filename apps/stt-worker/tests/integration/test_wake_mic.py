import asyncio
import contextlib
import importlib.util
import sys
from pathlib import Path

import pytest

from tars.contracts.envelope import Envelope  # type: ignore[import]
from tars.contracts.v1 import (  # type: ignore[import]
    EVENT_TYPE_WAKE_EVENT,
    EVENT_TYPE_WAKE_MIC,
    WakeEvent,
    WakeMicCommand,
)


def _load_stt_module():
    module_name = "stt_worker_main_for_test"
    if module_name in sys.modules:
        return sys.modules[module_name]
    # Updated path for src/ layout
    module_path = Path(__file__).resolve().parents[2] / "src" / "stt_worker" / "__main__.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore[assignment]
    return module


class DummyCapture:
    def __init__(self) -> None:
        self.mute_calls: list[str] = []
        self.unmute_calls: list[str] = []
        self.is_muted = False

    def mute(self, reason: str = "") -> None:
        self.is_muted = True
        self.mute_calls.append(reason)

    def unmute(self, reason: str = "") -> None:
        self.is_muted = False
        self.unmute_calls.append(reason)


def _encode_event(event_type: str, model) -> bytes:
    envelope = Envelope.new(event_type=event_type, data=model)
    return envelope.model_dump_json().encode()


@pytest.mark.asyncio
async def test_wake_mic_unmute_triggers_mute_ttl():
    stt_main = _load_stt_module()
    worker = object.__new__(stt_main.STTWorker)
    worker.audio_capture = DummyCapture()
    worker.pending_tts = True
    worker.recent_unmute_time = 0.0
    worker.fallback_unmute_task = None
    worker._wake_ttl_task = None
    worker._wake_fallback_task = None

    command = WakeMicCommand(action="unmute", reason="wake", ttl_ms=20)
    payload = _encode_event(EVENT_TYPE_WAKE_MIC, command)
    await stt_main.STTWorker._handle_wake_mic(worker, payload)

    assert worker.audio_capture.unmute_calls == ["wake/wake"]
    assert worker.pending_tts is False
    assert worker._wake_ttl_task is not None

    await asyncio.sleep(0.05)

    assert worker.audio_capture.mute_calls
    if worker._wake_ttl_task:
        worker._wake_ttl_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker._wake_ttl_task


@pytest.mark.asyncio
async def test_wake_mic_mute_triggers_unmute_ttl():
    stt_main = _load_stt_module()
    worker = object.__new__(stt_main.STTWorker)
    worker.audio_capture = DummyCapture()
    worker.pending_tts = False
    worker.recent_unmute_time = 0.0
    worker.fallback_unmute_task = None
    worker._wake_ttl_task = None
    worker._wake_fallback_task = None

    command = WakeMicCommand(action="mute", reason="wake", ttl_ms=10)
    payload = _encode_event(EVENT_TYPE_WAKE_MIC, command)
    await stt_main.STTWorker._handle_wake_mic(worker, payload)

    assert worker.audio_capture.mute_calls == ["wake/wake"]
    await asyncio.sleep(0.03)
    assert worker.audio_capture.unmute_calls
    if worker._wake_ttl_task:
        worker._wake_ttl_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker._wake_ttl_task


@pytest.mark.asyncio
async def test_wake_event_fallback_unmutes_when_mic_stays_muted(monkeypatch):
    import stt_worker.app as stt_app

    stt_main = _load_stt_module()
    worker = object.__new__(stt_main.STTWorker)
    dummy = DummyCapture()
    dummy.is_muted = True
    worker.audio_capture = dummy
    worker.pending_tts = True
    worker.recent_unmute_time = 0.0
    worker.fallback_unmute_task = None
    worker._wake_ttl_task = None
    worker._wake_fallback_task = None

    monkeypatch.setattr(stt_app, "WAKE_EVENT_FALLBACK_DELAY_MS", 5)
    monkeypatch.setattr(stt_app, "WAKE_EVENT_FALLBACK_TTL_MS", 20)

    event = WakeEvent(type="wake")
    payload = _encode_event(EVENT_TYPE_WAKE_EVENT, event)
    await stt_main.STTWorker._handle_wake_event(worker, payload)

    await asyncio.sleep(0.02)

    assert worker.audio_capture.unmute_calls == ["wake-event/wake"]
    assert worker.pending_tts is False
    assert worker._wake_ttl_task is not None

    if worker._wake_ttl_task:
        worker._wake_ttl_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker._wake_ttl_task
    if worker._wake_fallback_task:
        worker._wake_fallback_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker._wake_fallback_task
