from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from urllib.parse import urlparse

# Handle TaskGroup compatibility for Python 3.10
try:
    from asyncio import TaskGroup
except ImportError:
    from typing import Any

    # Fallback for Python < 3.11
    class TaskGroup:  # type: ignore[no-redef]
        def __init__(self) -> None:
            self._tasks: list[asyncio.Task[Any]] = []

        def create_task(self, coro: Any) -> asyncio.Task[Any]:
            task = asyncio.create_task(coro)
            self._tasks.append(task)
            return task

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)


from tars.adapters.mqtt_client import MQTTClient  # type: ignore[import]
import orjson

from .audio import AudioFanoutClient
from .config import WakeActivationConfig
from .detector import DetectionResult, DetectorUnavailableError, WakeDetector, create_wake_detector
from .models import (
    HealthPayload,
    MicAction,
    MicCommand,
    TtsAction,
    TtsControl,
    WakeEvent,
    WakeEventType,
)

CANCEL_PHRASES = {
    "cancel",
    "cancel it",
    "cancel that",
    "cancel please",
    "stop",
    "stop it",
    "stop that",
    "never mind",
    "never mind that",
    "nevermind",
}


def _normalize_phrase(text: str) -> str:
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return " ".join(cleaned.split())


@dataclass(slots=True)
class InterruptContext:
    tts_id: str | None
    started_at: float
    deadline: float


class WakeActivationService:
    """Async MQTT-driven wake activation service.

    Connects to MQTT, streams audio from the STT fan-out socket, runs the wake-word detector, and
    publishes `wake/event` payloads when detections occur. Also publishes periodic health heartbeats
    so other services can observe liveness.
    """

    def __init__(
        self,
        config: WakeActivationConfig,
        *,
        detector_factory: Callable[[WakeActivationConfig], WakeDetector] | None = None,
        audio_client_factory: (
            Callable[[WakeActivationConfig, int], AudioFanoutClient] | None
        ) = None,
    ) -> None:
        self.cfg = config
        self.log = logging.getLogger("wake-activation")
        self.health_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._detector_factory = detector_factory or self._default_detector_factory
        self._audio_client_factory = audio_client_factory or self._default_audio_client_factory
        self._idle_timeout_task: asyncio.Task[None] | None = None
        self._session_counter = 0
        self._tts_state = "idle"
        self._tts_utt_id: str | None = None
        self._interrupt_task: asyncio.Task[None] | None = None
        self._active_interrupt: InterruptContext | None = None

    async def run(self) -> None:
        """Run the wake activation event loop until cancelled."""

        # Convert string log level to logging constant
        log_level = getattr(logging, self.cfg.log_level.upper(), logging.INFO)
        logging.basicConfig(
            level=log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
        )

        mqtt_client = MQTTClient(self.cfg.mqtt_url, "wake-activation", enable_health=True)
        self.log.info("Connecting to MQTT %s", self.cfg.mqtt_url)
        await mqtt_client.connect()

        try:
            # Wait for STT health before starting if enabled
            if self.cfg.wait_for_stt_health:
                await self._wait_for_stt_health(mqtt_client)

            await self._publish_health(mqtt_client)
            async with TaskGroup() as tg:
                tg.create_task(self._health_loop(mqtt_client))
                tg.create_task(self._tts_status_loop(mqtt_client))
                tg.create_task(self._stt_final_loop(mqtt_client))
                tg.create_task(self._inference_loop(mqtt_client))
                await self._stop_event.wait()
                self.log.info("Stop signal received; shutting down wake activation service")
        finally:
            await mqtt_client.shutdown()

    async def stop(self) -> None:
        """Request cooperative shutdown."""

        self._stop_event.set()
        await self._cancel_idle_timeout()
        await self._cancel_interrupt_timer()

    async def _health_loop(self, client: MQTTClient) -> None:
        interval = max(1.0, self.cfg.health_interval_sec)
        self.log.info("Starting health heartbeat every %.1fs", interval)
        try:
            while not self._stop_event.is_set():
                await self._publish_health(client)
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
                except TimeoutError:
                    continue
        except Exception:  # pragma: no cover - log and propagate
            self.log.exception("Health loop terminated unexpectedly")
            raise

    async def _publish_health(self, client: MQTTClient) -> None:
        payload = HealthPayload(ts=time.time())
        await client.publish_event(
            topic=self.cfg.health_topic,
            event_type="wake.health",
            data=payload.model_dump(),
            qos=1,
            retain=True
        )
        self.log.debug("Published health heartbeat: %s", payload.model_dump())

    async def _tts_status_loop(self, client: MQTTClient) -> None:
        topic = self.cfg.tts_status_topic

        async def _handler(payload: bytes) -> None:
            if self._stop_event.is_set():
                return
            try:
                data = orjson.loads(payload)
            except Exception:
                self.log.warning("Invalid TTS status payload")
                return
            await self._handle_tts_status(data)

        await client.subscribe(topic, _handler)

    async def _stt_final_loop(self, client: MQTTClient) -> None:
        topic = self.cfg.stt_final_topic

        async def _handler(payload: bytes) -> None:
            if self._stop_event.is_set():
                return
            try:
                data = orjson.loads(payload)
            except Exception:
                self.log.debug("Invalid STT payload")
                return
            await self._handle_stt_final(client, data)

        await client.subscribe(topic, _handler)

    async def _inference_loop(self, client: MQTTClient) -> None:
        """Consume audio frames and publish wake events when detected."""

        try:
            detector = await asyncio.to_thread(self._detector_factory, self.cfg)
        except DetectorUnavailableError as exc:
            self.log.error("Unable to start wake detector: %s", exc)
            await self._publish_error_event(client, str(exc))
            await self.stop()
            return

        audio_client = self._audio_client_factory(self.cfg, detector.frame_samples)
        self.log.info(
            "Wake detector ready (threshold=%.2f, retrigger=%.2fs); consuming audio at %d Hz",
            self.cfg.wake_detection_threshold,
            self.cfg.min_retrigger_sec,
            detector.sample_rate,
        )

        try:
            async for frame in audio_client.frames():
                if self._stop_event.is_set():
                    break
                ts = time.monotonic()
                result = detector.process_frame(frame, ts=ts)
                if result is None:
                    continue
                await self._handle_detection(client, result)
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover - defensive logging
            self.log.exception("Wake-word inference loop terminated unexpectedly")
            await self._publish_error_event(client, "detector_failure")
            raise
        finally:
            await audio_client.close()
            await self._cancel_idle_timeout()

    async def publish_wake_event(self, client: MQTTClient, event: WakeEvent) -> None:
        await client.publish_event(
            topic=self.cfg.wake_event_topic,
            event_type="wake.event",
            data=event.model_dump(),
            qos=1
        )
        self.log.info("Published wake event: %s", event.model_dump())

    async def send_mic_command(self, client: MQTTClient, command: MicCommand) -> None:
        await client.publish_event(
            topic=self.cfg.mic_control_topic,
            event_type="mic.control",
            data=command.model_dump(),
            qos=1
        )
        self.log.info("Published mic command: %s", command.model_dump())

    async def send_tts_command(self, client: MQTTClient, command: TtsControl) -> None:
        await client.publish_event(
            topic=self.cfg.tts_control_topic,
            event_type="tts.control",
            data=command.model_dump(),
            qos=1
        )
        self.log.info("Published TTS control: %s", command.model_dump())

    def _parse_mqtt_url(self, url: str) -> tuple[str, int, str | None, str | None]:
        parsed = urlparse(url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 1883
        return host, port, parsed.username, parsed.password

    async def _handle_detection(self, client: MQTTClient, result: DetectionResult) -> None:
        confidence = max(0.0, min(result.score, 1.0))
        session_id = self._next_session_id()
        if self._tts_state == "speaking":
            await self._handle_interrupt_detection(client, result, confidence, session_id)
        else:
            await self._handle_standard_wake(client, result, confidence, session_id)

    async def _handle_standard_wake(
        self,
        client: MQTTClient,
        result: DetectionResult,
        confidence: float,
        session_id: int,
    ) -> None:
        await self._cancel_interrupt_timer()
        self._active_interrupt = None
        event = WakeEvent(
            type=WakeEventType.WAKE,
            confidence=confidence,
            energy=result.energy,
            cause="wake_phrase",
            ts=result.ts,
        )
        await self.publish_wake_event(client, event)
        ttl_ms = self._idle_timeout_ms()
        command = MicCommand(action=MicAction.UNMUTE, reason="wake", ttl_ms=ttl_ms)
        await self.send_mic_command(client, command)
        self._log_action(
            "wake_detected",
            session=session_id,
            confidence=confidence,
            energy=result.energy,
            ttl_ms=ttl_ms,
            threshold_used=result.effective_threshold or self.cfg.wake_detection_threshold,
        )
        await self._schedule_idle_timeout(client, session_id)

    async def _handle_interrupt_detection(
        self,
        client: MQTTClient,
        result: DetectionResult,
        confidence: float,
        session_id: int,
    ) -> None:
        tts_id = self._tts_utt_id
        event = WakeEvent(
            type=WakeEventType.INTERRUPT,
            confidence=confidence,
            energy=result.energy,
            cause="double_wake",
            ts=result.ts,
            tts_id=tts_id,
        )
        await self.publish_wake_event(client, event)
        ttl_ms = self._idle_timeout_ms()
        await self.send_mic_command(
            client, MicCommand(action=MicAction.UNMUTE, reason="wake", ttl_ms=ttl_ms)
        )
        pause = TtsControl(action=TtsAction.PAUSE, reason="wake_interrupt", id=tts_id)
        await self.send_tts_command(client, pause)
        self._tts_state = "paused"
        self._tts_utt_id = tts_id or self._tts_utt_id
        context = InterruptContext(
            tts_id=tts_id,
            started_at=time.monotonic(),
            deadline=time.monotonic() + max(0.1, self.cfg.interrupt_window_sec),
        )
        self._active_interrupt = context
        await self._start_interrupt_timer(client, context)
        self._log_action(
            "wake_interrupt",
            session=session_id,
            confidence=confidence,
            energy=result.energy,
            tts_id=tts_id,
            ttl_ms=ttl_ms,
            threshold_used=result.effective_threshold or self.cfg.wake_detection_threshold,
        )
        await self._schedule_idle_timeout(client, session_id)

    async def _handle_tts_status(self, payload: dict[str, object]) -> None:
        event = str(payload.get("event", "") or "")
        utt_id = payload.get("utt_id")
        if isinstance(utt_id, str):
            utt_id = utt_id or None
        else:
            utt_id = None

        if event == "speaking_start" or event == "resumed":
            self._tts_state = "speaking"
            self._tts_utt_id = utt_id
            await self._cancel_interrupt_timer()
            self._active_interrupt = None
        elif event == "paused":
            self._tts_state = "paused"
            if utt_id:
                self._tts_utt_id = utt_id
        elif event in {"speaking_end", "stopped"}:
            self._tts_state = "idle"
            self._tts_utt_id = None
            self._active_interrupt = None
            await self._cancel_interrupt_timer()

    async def _handle_stt_final(self, client: MQTTClient, payload: dict[str, object]) -> None:
        if self._active_interrupt is None:
            return
        if payload.get("is_final") is False:
            return
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            return
        normalized = _normalize_phrase(text)
        if not normalized:
            return
        if normalized in CANCEL_PHRASES:
            await self._handle_interrupt_cancel(client, normalized)
        else:
            await self._resolve_interrupt_with_speech()

    async def _handle_interrupt_cancel(self, client: MQTTClient, phrase: str) -> None:
        context = self._active_interrupt
        if context is None:
            return
        await self._cancel_interrupt_timer()
        stop_cmd = TtsControl(action=TtsAction.STOP, reason="wake_cancel", id=context.tts_id)
        await self.send_tts_command(client, stop_cmd)
        event = WakeEvent(
            type=WakeEventType.CANCELLED,
            confidence=None,
            energy=None,
            cause="cancel",
            ts=time.monotonic(),
            tts_id=context.tts_id,
        )
        await self.publish_wake_event(client, event)
        self._log_action("interrupt_cancelled", tts_id=context.tts_id, phrase=phrase)
        self._active_interrupt = None
        self._tts_state = "idle"
        self._tts_utt_id = None

    async def _resolve_interrupt_with_speech(self) -> None:
        context = self._active_interrupt
        if context is None:
            return
        await self._cancel_interrupt_timer()
        self._log_action("interrupt_resolved_by_speech", tts_id=context.tts_id)
        self._active_interrupt = None
        self._tts_state = "paused"
        self._tts_utt_id = None

    async def _publish_error_event(self, client: MQTTClient, cause: str) -> None:
        event = WakeEvent(
            type=WakeEventType.ERROR, confidence=None, energy=None, cause=cause, ts=time.monotonic()
        )
        await self.publish_wake_event(client, event)

    def _default_detector_factory(self, config: WakeActivationConfig) -> WakeDetector:
        return create_wake_detector(
            config.rknn_model_path if config.use_npu else config.wake_model_path,
            threshold=config.wake_detection_threshold,
            min_retrigger_sec=config.min_retrigger_sec,
            energy_window_ms=config.detection_window_ms,
            enable_speex_noise_suppression=config.enable_speex_noise_suppression,
            vad_threshold=config.vad_threshold,
            energy_boost_factor=config.energy_boost_factor,
            low_energy_threshold_factor=config.low_energy_threshold_factor,
            background_noise_sensitivity=config.background_noise_sensitivity,
            use_npu=config.use_npu,
            npu_core_mask=config.npu_core_mask,
        )

    def _default_audio_client_factory(
        self, config: WakeActivationConfig, frame_samples: int
    ) -> AudioFanoutClient:
        return AudioFanoutClient(config.audio_fanout_path, samples_per_chunk=frame_samples)

    def _idle_timeout_ms(self) -> int | None:
        if self.cfg.idle_timeout_sec <= 0:
            return None
        return int(self.cfg.idle_timeout_sec * 1000)

    def _next_session_id(self) -> int:
        self._session_counter += 1
        return self._session_counter

    async def _schedule_idle_timeout(self, client: MQTTClient, session_id: int) -> None:
        await self._cancel_idle_timeout()
        if self.cfg.idle_timeout_sec <= 0:
            return
        self._idle_timeout_task = asyncio.create_task(self._idle_timeout_flow(client, session_id))

    async def _idle_timeout_flow(self, client: MQTTClient, session_id: int) -> None:
        try:
            await asyncio.sleep(self.cfg.idle_timeout_sec)
        except asyncio.CancelledError:
            self._log_action("idle_timeout_cancelled", session=session_id)
            return

        context = self._active_interrupt
        tts_id = context.tts_id if context is not None else None
        event = WakeEvent(
            type=WakeEventType.TIMEOUT,
            confidence=None,
            energy=None,
            cause="silence",
            ts=time.monotonic(),
            tts_id=tts_id,
        )
        await self.publish_wake_event(client, event)

        resumed = False
        if context is not None:
            await self._cancel_interrupt_timer()
            resume_cmd = TtsControl(action=TtsAction.RESUME, reason="wake_timeout", id=tts_id)
            await self.send_tts_command(client, resume_cmd)
            self._active_interrupt = None
            self._tts_state = "speaking"
            self._tts_utt_id = tts_id
            resumed = True
        else:
            self._tts_state = "idle"
            self._tts_utt_id = None

        self._log_action(
            "idle_timeout_triggered",
            session=session_id,
            timeout_sec=self.cfg.idle_timeout_sec,
            tts_id=tts_id,
            resumed=resumed,
        )

    async def _cancel_idle_timeout(self) -> None:
        if self._idle_timeout_task and not self._idle_timeout_task.done():
            self._idle_timeout_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._idle_timeout_task
        self._idle_timeout_task = None

    async def _start_interrupt_timer(self, client: MQTTClient, context: InterruptContext) -> None:
        await self._cancel_interrupt_timer()
        if self.cfg.interrupt_window_sec <= 0:
            return
        self._interrupt_task = asyncio.create_task(self._interrupt_timeout_flow(client, context))

    async def _cancel_interrupt_timer(self) -> None:
        if self._interrupt_task and not self._interrupt_task.done():
            self._interrupt_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._interrupt_task
        self._interrupt_task = None

    async def _interrupt_timeout_flow(self, client: MQTTClient, context: InterruptContext) -> None:
        delay = max(0.0, context.deadline - time.monotonic())
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            self._log_action("interrupt_timeout_cancelled", tts_id=context.tts_id)
            self._interrupt_task = None
            return
        try:
            event = WakeEvent(
                type=WakeEventType.RESUME,
                confidence=None,
                energy=None,
                cause="timeout",
                ts=time.monotonic(),
                tts_id=context.tts_id,
            )
            await self.publish_wake_event(client, event)
            resume_cmd = TtsControl(
                action=TtsAction.RESUME, reason="wake_resume", id=context.tts_id
            )
            await self.send_tts_command(client, resume_cmd)
            self._tts_state = "speaking"
            self._active_interrupt = None
            self._log_action(
                "interrupt_timeout_triggered",
                tts_id=context.tts_id,
                window_sec=self.cfg.interrupt_window_sec,
            )
        finally:
            self._interrupt_task = None

    def _log_action(self, event: str, **fields: object) -> None:
        payload = {"event": event, **fields}
        try:
            message = orjson.dumps(payload).decode()
        except Exception:
            message = f"{event} {fields}"
        self.log.info(message)

    async def _wait_for_stt_health(self, client: MQTTClient) -> None:
        """Wait for STT service to report healthy status before starting audio processing."""
        self.log.info("Waiting for STT service health on topic '%s'...", self.cfg.stt_health_topic)

        # Create a future to wait for health message
        health_future: asyncio.Future[bool] = asyncio.Future()

        async def health_handler(payload: bytes) -> None:
            """Handler for STT health messages."""
            try:
                envelope = orjson.loads(payload)
                # Check both direct format and nested data format
                health_data = envelope.get("data", envelope)
                if health_data.get("ok") is True:
                    self.log.info(
                        "✅ STT service is healthy, proceeding with wake activation startup"
                    )
                    if not health_future.done():
                        health_future.set_result(True)
                else:
                    error = (
                        health_data.get("err")
                        or health_data.get("event")
                        or "unknown error"
                    )
                    self.log.warning("STT service reports unhealthy: %s", error)
            except Exception as exc:
                self.log.debug("Invalid STT health payload: %s (%s)", payload, exc)

        # Subscribe to STT health topic with handler
        await client.subscribe(self.cfg.stt_health_topic, health_handler)

        # Wait for health message with timeout
        try:
            health_received = await asyncio.wait_for(
                health_future,
                timeout=self.cfg.stt_health_timeout_sec
            )
        except asyncio.TimeoutError:
            health_received = False

        if not health_received:
            self.log.warning(
                "⚠️  STT health not received within %.1fs, starting anyway (audio fanout may be unstable)",
                self.cfg.stt_health_timeout_sec,
            )

        # Small additional delay to let STT fully stabilize
        await asyncio.sleep(2.0)
