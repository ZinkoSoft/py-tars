import asyncio
import contextlib
import importlib.util
import sys
import time
from pathlib import Path
from typing import Any

import orjson
import pytest

from wake_activation.config import WakeActivationConfig
from wake_activation.detector import DetectionResult
from wake_activation.service import InterruptContext, WakeActivationService


class FakeClient:
    def __init__(self) -> None:
        self.published: list[tuple[str, bytes, int, bool]] = []

    async def publish(self, topic: str, payload: bytes, qos: int = 0, retain: bool = False) -> None:
        self.published.append((topic, payload, qos, retain))


def _load_stt_module() -> Any:
    module_name = "stt_worker_main_for_wake_activation_tests"
    if module_name in sys.modules:
        return sys.modules[module_name]
    module_path = Path(__file__).resolve().parents[2] / "stt-worker" / "main.py"
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


@pytest.mark.asyncio
async def test_detection_publishes_unmute_with_idle_ttl() -> None:
    cfg = WakeActivationConfig(idle_timeout_sec=0.05)
    service = WakeActivationService(cfg)
    client = FakeClient()
    result = DetectionResult(score=0.9, energy=0.2, ts=123.456)

    await service._handle_detection(client, result)

    assert len(client.published) >= 2
    event_topic, event_payload, *_ = client.published[0]
    mic_topic, mic_payload, *_ = client.published[1]

    event_data = orjson.loads(event_payload)
    assert event_topic == cfg.wake_event_topic
    assert event_data["type"] == "wake"

    mic_data = orjson.loads(mic_payload)
    assert mic_topic == cfg.mic_control_topic
    assert mic_data == {
        "action": "unmute",
        "reason": "wake",
        "ttl_ms": int(cfg.idle_timeout_sec * 1000),
    }

    await service._cancel_idle_timeout()


@pytest.mark.asyncio
async def test_idle_timeout_emits_timeout_event() -> None:
    cfg = WakeActivationConfig(idle_timeout_sec=0.05)
    service = WakeActivationService(cfg)
    client = FakeClient()
    result = DetectionResult(score=0.85, energy=0.18, ts=42.0)

    await service._handle_detection(client, result)
    await asyncio.sleep(cfg.idle_timeout_sec + 0.05)

    timeout_events = [
        orjson.loads(payload)
        for topic, payload, *_ in client.published
        if topic == cfg.wake_event_topic and orjson.loads(payload)["type"] == "timeout"
    ]
    assert timeout_events, "Expected a timeout wake event to be published"

    await service._cancel_idle_timeout()


@pytest.mark.asyncio
async def test_stt_mic_ttl_remutes_after_idle_timeout() -> None:
    cfg = WakeActivationConfig(idle_timeout_sec=0.05)
    service = WakeActivationService(cfg)
    client = FakeClient()
    result = DetectionResult(score=0.92, energy=0.25, ts=77.0)

    await service._handle_detection(client, result)

    stt_main = _load_stt_module()
    worker = object.__new__(stt_main.STTWorker)
    worker.audio_capture = DummyCapture()
    worker.pending_tts = True
    worker.recent_unmute_time = 0.0
    worker.fallback_unmute_task = None
    worker._wake_ttl_task = None

    mic_payload = next(
        (payload for topic, payload, *_ in client.published if topic == cfg.mic_control_topic),
        None,
    )
    assert mic_payload is not None

    await stt_main.STTWorker._handle_wake_mic(worker, mic_payload)

    assert worker.audio_capture.unmute_calls == ["wake/wake"]
    assert worker.audio_capture.is_muted is False

    await asyncio.sleep(cfg.idle_timeout_sec + 0.05)

    assert worker.audio_capture.is_muted is True
    assert worker.audio_capture.mute_calls[-1] == "wake/ttl/wake"

    if worker._wake_ttl_task:
        worker._wake_ttl_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker._wake_ttl_task

    await service._cancel_idle_timeout()


@pytest.mark.asyncio
async def test_interrupt_detection_pauses_tts_and_starts_timer() -> None:
    cfg = WakeActivationConfig(idle_timeout_sec=0, interrupt_window_sec=0.05)
    service = WakeActivationService(cfg)
    service._tts_state = "speaking"
    service._tts_utt_id = "utt-123"
    client = FakeClient()
    result = DetectionResult(score=0.93, energy=0.3, ts=12.0)

    await service._handle_interrupt_detection(client, result, confidence=0.93, session_id=1)

    interrupt_event = orjson.loads(client.published[0][1])
    mic_command = orjson.loads(client.published[1][1])
    control_command = orjson.loads(client.published[2][1])

    assert interrupt_event["type"] == "interrupt"
    assert interrupt_event["tts_id"] == "utt-123"
    assert mic_command["action"] == "unmute"
    assert control_command == {"action": "pause", "reason": "wake_interrupt", "id": "utt-123"}
    assert service._tts_state == "paused"
    assert service._active_interrupt is not None
    assert service._active_interrupt.tts_id == "utt-123"

    await service._cancel_interrupt_timer()


@pytest.mark.asyncio
async def test_interrupt_cancel_phrase_triggers_stop_command() -> None:
    cfg = WakeActivationConfig(idle_timeout_sec=0, interrupt_window_sec=0.5)
    service = WakeActivationService(cfg)
    client = FakeClient()
    context = InterruptContext(tts_id="utt-9", started_at=time.monotonic(), deadline=time.monotonic() + 1.0)
    service._active_interrupt = context
    service._tts_state = "paused"

    await service._handle_interrupt_cancel(client, "cancel")

    control_command = orjson.loads(client.published[0][1])
    event_payload = orjson.loads(client.published[1][1])

    assert control_command == {"action": "stop", "reason": "wake_cancel", "id": "utt-9"}
    assert event_payload["type"] == "cancelled"
    assert service._tts_state == "idle"
    assert service._active_interrupt is None


@pytest.mark.asyncio
async def test_interrupt_timeout_resumes_tts() -> None:
    cfg = WakeActivationConfig(idle_timeout_sec=0, interrupt_window_sec=0.05)
    service = WakeActivationService(cfg)
    client = FakeClient()
    context = InterruptContext(tts_id="utt-55", started_at=time.monotonic(), deadline=time.monotonic() + 0.05)

    await service._start_interrupt_timer(client, context)
    assert service._interrupt_task is not None

    await asyncio.sleep(0.06)

    resume_event = orjson.loads(client.published[0][1])
    resume_control = orjson.loads(client.published[1][1])

    assert resume_event == {
        "type": "resume",
        "confidence": None,
        "energy": None,
        "cause": "timeout",
        "ts": resume_event["ts"],
        "tts_id": "utt-55",
    }
    assert resume_control == {"action": "resume", "reason": "wake_resume", "id": "utt-55"}
    assert service._tts_state == "speaking"
    assert service._interrupt_task is None
    assert service._active_interrupt is None


@pytest.mark.asyncio
async def test_interrupt_resolved_by_speech_clears_context() -> None:
    cfg = WakeActivationConfig(idle_timeout_sec=0, interrupt_window_sec=1.0)
    service = WakeActivationService(cfg)
    client = FakeClient()
    context = InterruptContext(tts_id="utt-77", started_at=time.monotonic(), deadline=time.monotonic() + 1.0)
    service._active_interrupt = context
    service._tts_state = "paused"

    payload = {"text": "keep going", "is_final": True}
    await service._handle_stt_final(client, payload)

    assert service._active_interrupt is None
    assert service._tts_state == "paused"
