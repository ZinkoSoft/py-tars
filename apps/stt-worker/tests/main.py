from __future__ import annotations

import asyncio
import logging
from typing import Any

import orjson
from pydantic import BaseModel, ValidationError

from tars.contracts.envelope import Envelope  # type: ignore[import]
from tars.contracts.v1 import (  # type: ignore[import]
    EVENT_TYPE_WAKE_EVENT,
    EVENT_TYPE_WAKE_MIC,
    WakeEvent,
    WakeMicCommand,
)

WAKE_EVENT_FALLBACK_DELAY_MS = 250
WAKE_EVENT_FALLBACK_TTL_MS = 3500

logger = logging.getLogger("stt-worker.test")


class STTWorker:
    """Lightweight test shim exposing wake handlers from the production worker."""

    audio_capture: Any
    pending_tts: bool
    recent_unmute_time: float
    fallback_unmute_task: asyncio.Task | None
    _wake_ttl_task: asyncio.Task | None
    _wake_fallback_task: asyncio.Task | None

    def __init__(self) -> None:
        self.audio_capture = None
        self.pending_tts = False
        self.recent_unmute_time = 0.0
        self.fallback_unmute_task = None
        self._wake_ttl_task = None
        self._wake_fallback_task = None

    async def _handle_wake_mic(self, payload: bytes) -> None:
        command = self._decode_event(payload, WakeMicCommand, event_type=EVENT_TYPE_WAKE_MIC)
        if command is None:
            return

        action = command.action
        reason = (command.reason or "wake").strip() or "wake"
        ttl_ms = command.ttl_ms

        self._cancel_wake_fallback()

        if self._wake_ttl_task and not self._wake_ttl_task.done():
            self._wake_ttl_task.cancel()
            self._wake_ttl_task = None

        if action == "unmute":
            if self.fallback_unmute_task and not self.fallback_unmute_task.done():
                self.fallback_unmute_task.cancel()
                self.fallback_unmute_task = None
            self.pending_tts = False
            if self.audio_capture:
                self.audio_capture.unmute(f"wake/{reason}")
            if isinstance(ttl_ms, (int, float)) and ttl_ms > 0:
                self._wake_ttl_task = asyncio.create_task(
                    self._schedule_wake_ttl("mute", ttl_ms, reason)
                )
        else:
            if self.audio_capture:
                self.audio_capture.mute(f"wake/{reason}")
            if isinstance(ttl_ms, (int, float)) and ttl_ms > 0:
                self._wake_ttl_task = asyncio.create_task(
                    self._schedule_wake_ttl("unmute", ttl_ms, reason)
                )

    def _cancel_wake_fallback(self) -> None:
        task = getattr(self, "_wake_fallback_task", None)
        if task and not task.done():
            task.cancel()
        self._wake_fallback_task = None

    def _schedule_wake_fallback(self, event_type: str, delay_ms: int | None = None) -> None:
        if WAKE_EVENT_FALLBACK_DELAY_MS <= 0 and delay_ms is None:
            return
        self._cancel_wake_fallback()

        delay = (delay_ms if delay_ms is not None else WAKE_EVENT_FALLBACK_DELAY_MS) / 1000.0
        delay = max(0.0, delay)
        ttl_ms = max(0, WAKE_EVENT_FALLBACK_TTL_MS)

        async def _fallback() -> None:
            try:
                if delay:
                    await asyncio.sleep(delay)
                if not getattr(self.audio_capture, "is_muted", False):
                    return
                if self.fallback_unmute_task and not self.fallback_unmute_task.done():
                    self.fallback_unmute_task.cancel()
                    self.fallback_unmute_task = None
                self.pending_tts = False
                if self.audio_capture:
                    self.audio_capture.unmute(f"wake-event/{event_type}")
                if ttl_ms > 0:
                    if self._wake_ttl_task and not self._wake_ttl_task.done():
                        self._wake_ttl_task.cancel()
                    self._wake_ttl_task = asyncio.create_task(
                        self._schedule_wake_ttl("mute", ttl_ms, f"{event_type}-fallback")
                    )
            except asyncio.CancelledError:  # pragma: no cover - cancellation path
                pass

        self._wake_fallback_task = asyncio.create_task(_fallback())

    async def _schedule_wake_ttl(self, next_action: str, ttl_ms: float, reason: str) -> None:
        try:
            await asyncio.sleep(ttl_ms / 1000.0)
            if next_action == "mute":
                if self.audio_capture:
                    self.audio_capture.mute(f"wake/ttl/{reason}")
            else:
                if self.audio_capture:
                    self.audio_capture.unmute(f"wake/ttl/{reason}")
                self.pending_tts = False
        except asyncio.CancelledError:  # pragma: no cover - cancellation path
            pass

    async def _handle_wake_event(self, payload: bytes) -> None:
        event = self._decode_event(payload, WakeEvent, event_type=EVENT_TYPE_WAKE_EVENT)
        if event is None:
            return

        event_type = (event.type or "").lower()
        if event_type in {"wake", "interrupt"}:
            delay_override = 0 if event_type == "interrupt" else None
            self._schedule_wake_fallback(event_type, delay_override)
        elif event_type in {"timeout", "cancelled", "resume"}:
            self._cancel_wake_fallback()

    @staticmethod
    def _decode_event(
        payload: bytes,
        model: type[BaseModel],
        *,
        event_type: str | None = None,
    ) -> BaseModel | None:
        try:
            envelope = Envelope.model_validate_json(payload)
            raw = envelope.data
            if event_type and envelope.type != event_type:
                logger.debug(
                    "[test shim] envelope type mismatch expected=%s actual=%s",
                    event_type,
                    envelope.type,
                )
        except ValidationError:
            try:
                raw = orjson.loads(payload)
            except orjson.JSONDecodeError as exc:  # pragma: no cover - guard
                logger.error("Failed to decode %s payload: %s", model.__name__, exc)
                return None

        try:
            return model.model_validate(raw)
        except ValidationError as exc:  # pragma: no cover - guard
            logger.error("Invalid %s payload: %s", model.__name__, exc)
            return None
