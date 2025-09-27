from __future__ import annotations

import asyncio
import logging
import signal
import subprocess
import tempfile
import time
from contextlib import suppress
from dataclasses import dataclass
from html import unescape
from typing import Any, Awaitable, Callable, ClassVar, Literal, Optional, Protocol

from bs4 import BeautifulSoup
from markdown import markdown as md_render

from tars.contracts.v1 import TtsSay

logger = logging.getLogger("tars.domain.tts")

StatusEvent = Literal["speaking_start", "speaking_end", "paused", "resumed", "stopped"]


class Synthesizer(Protocol):
    """Protocol describing synthesizer behavior required by the domain."""

    def synth_and_play(self, text: str, streaming: bool = False, pipeline: bool = True) -> float: ...

    def synth_to_wav(self, text: str, wav_path: str) -> None: ...


@dataclass(slots=True)
class TTSCallbacks:
    """Callback bundle for publishing status events to the transport layer."""

    publish_status: Callable[[StatusEvent, str, Optional[str], Optional[str], Optional[bool]], Awaitable[None]]


@dataclass(slots=True)
class TTSConfig:
    """Runtime configuration for the TTS domain service."""

    streaming_enabled: bool
    pipeline_enabled: bool
    aggregate_enabled: bool
    aggregate_debounce_ms: int
    aggregate_single_wav: bool


@dataclass(slots=True)
class TTSControlMessage:
    """Typed representation of a `tts/control` command."""

    VALID_ACTIONS: ClassVar[set[str]] = {"pause", "resume", "stop"}

    action: str
    reason: str
    request_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Any) -> "TTSControlMessage":
        if not isinstance(data, dict):
            raise ValueError("control payload must be a JSON object")
        action = data.get("action")
        if not isinstance(action, str) or action.lower() not in cls.VALID_ACTIONS:
            raise ValueError(f"unsupported control action: {action!r}")
        reason = data.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("control reason is required")
        ctrl_id = data.get("id")
        if ctrl_id is not None and not isinstance(ctrl_id, str):
            raise ValueError("control id must be a string when provided")
        return cls(action=action.lower(), reason=reason.strip(), request_id=ctrl_id)


@dataclass(slots=True)
class PlaybackSession:
    utt_id: Optional[str]
    text: str
    started_at: float
    player_proc: Optional[subprocess.Popen] = None
    paused: bool = False
    pause_pending: bool = False
    pause_reason: Optional[str] = None
    stop_requested: bool = False
    stop_reason: Optional[str] = None
    last_role: Optional[str] = None


class TTSDomainService:
    """Domain orchestration for TTS playback, aggregation, and controls."""

    def __init__(self, synth: Synthesizer, config: TTSConfig, *, wake_synth: Synthesizer | None = None) -> None:
        self._primary_synth = synth
        self._wake_synth = wake_synth
        self._config = config
        self._agg_id: str | None = None
        self._agg_texts: list[str] = []
        self._agg_timer: asyncio.TimerHandle | None = None
        self._agg_callbacks: TTSCallbacks | None = None
        self._agg_stt_ts: float | None = None
        self._play_lock = asyncio.Lock()
        self._current_session: PlaybackSession | None = None

    async def handle_say(self, say: TtsSay, callbacks: TTSCallbacks) -> None:
        text = self.md_to_text(say.text or "")
        if not text:
            return
        stt_ts = say.stt_ts
        utt_id_raw = say.utt_id
        wake_ack = bool(say.wake_ack)
        style = say.style
        logger.info(
            "TTS request received: text='%s' len=%d utt_id=%s style=%s streaming=%s pipeline=%s",
            text[:80].replace("\n", " ") + ("..." if len(text) > 80 else ""),
            len(text),
            utt_id_raw,
            style,
            self._config.streaming_enabled,
            self._config.pipeline_enabled,
        )

        if self._config.aggregate_enabled and isinstance(utt_id_raw, str) and utt_id_raw:
            if wake_ack:
                logger.debug("Bypassing aggregation for wake ack utterance")
            else:
                if self._agg_id and self._agg_id != utt_id_raw and self._agg_texts:
                    await self._flush_aggregate(callbacks, stt_ts)
                self._agg_id = utt_id_raw
                self._agg_texts.append(text)
                self._schedule_flush(stt_ts, callbacks)
                return

        if self._agg_texts:
            await self._flush_aggregate(callbacks, stt_ts)

        normalized_id = self._normalize_utt_id(utt_id_raw if isinstance(utt_id_raw, str) else None)
        await self._speak(text, stt_ts, callbacks, utt_id=normalized_id, wake_ack=wake_ack)
        logger.info("TTS playback finished for utt_id=%s wake_ack=%s", normalized_id, wake_ack)

    async def handle_control(self, control: TTSControlMessage, callbacks: TTSCallbacks) -> None:
        session = self._match_session(control.request_id)
        if session is None:
            logger.debug("No active playback for control id %s", control.request_id)
            return

        action = control.action
        if action == "pause":
            await self._apply_pause(session, control.reason, callbacks)
        elif action == "resume":
            await self._apply_resume(session, control.reason, callbacks)
        elif action == "stop":
            await self._apply_stop(session, control.reason, callbacks)

    def on_player_spawn(self, proc: subprocess.Popen, role: str) -> None:
        session = self._current_session
        if session is None:
            return
        session.player_proc = proc
        session.last_role = role
        if session.stop_requested:
            self._terminate_player(proc, session)
            return
        if session.pause_pending and hasattr(signal, "SIGSTOP"):
            try:
                proc.send_signal(signal.SIGSTOP)
            except Exception as exc:
                logger.warning("Deferred pause failed for utt_id=%s: %s", session.utt_id, exc)
                session.pause_pending = False
            else:
                session.pause_pending = False
                session.paused = True

    def should_abort_playback(self) -> bool:
        session = self._current_session
        return bool(session and session.stop_requested)

    def _schedule_flush(self, stt_ts: float | None, callbacks: TTSCallbacks) -> None:
        delay = max(0.01, self._config.aggregate_debounce_ms / 1000.0)
        loop = asyncio.get_running_loop()
        self._cancel_timer()
        self._agg_callbacks = callbacks
        self._agg_stt_ts = stt_ts

        def _cb() -> None:
            cb = self._agg_callbacks
            ts = self._agg_stt_ts
            if cb is None:
                return
            asyncio.create_task(self._flush_aggregate(cb, ts))

        self._agg_timer = loop.call_later(delay, _cb)

    def _cancel_timer(self) -> None:
        try:
            if self._agg_timer and not self._agg_timer.cancelled():
                self._agg_timer.cancel()
        except Exception:
            pass
        self._agg_timer = None

    async def _flush_aggregate(self, callbacks: TTSCallbacks, stt_ts: float | None) -> None:
        self._cancel_timer()
        if not self._agg_texts:
            self._agg_callbacks = None
            self._agg_stt_ts = None
            return
        logger.debug(
            "Flushing TTS aggregate: count=%d single_wav=%s",
            len(self._agg_texts),
            self._config.aggregate_single_wav,
        )
        utt_id = self._agg_id
        texts = [t.strip() for t in self._agg_texts if t and t.strip()]
        self._agg_texts.clear()
        self._agg_id = None
        self._agg_callbacks = None
        self._agg_stt_ts = None

        if not texts:
            return

        normalized_id = self._normalize_utt_id(utt_id)
        if self._config.aggregate_single_wav:
            text = " ".join(texts)
            await self._speak(
                text,
                stt_ts,
                callbacks,
                utt_id=normalized_id,
                streaming_override=False,
                pipeline_override=False,
                wake_ack=False,
            )
        else:
            for text in texts:
                await self._speak(text, stt_ts, callbacks, utt_id=normalized_id, wake_ack=False)

    async def _speak(
        self,
        text: str,
        stt_ts: float | None,
        callbacks: TTSCallbacks,
        *,
        utt_id: Optional[str] = None,
        streaming_override: Optional[bool] = None,
        pipeline_override: Optional[bool] = None,
        wake_ack: bool = False,
    ) -> None:
        synth = self._wake_synth if wake_ack and self._wake_synth is not None else self._primary_synth

        if self._play_lock.locked():
            logger.debug("Playback busy; queuing next utterance (len=%d)", len(text or ""))
        async with self._play_lock:
            session = PlaybackSession(utt_id=utt_id, text=text, started_at=time.time())
            self._current_session = session
            try:
                logger.debug("Playback start (len=%d)", len(text or ""))
                await callbacks.publish_status(
                    "speaking_start",
                    text=text,
                    utt_id=session.utt_id,
                    reason=None,
                    wake_ack=wake_ack,
                )

                t0 = time.time()
                streaming = self._config.streaming_enabled if streaming_override is None else bool(streaming_override)
                pipeline = self._config.pipeline_enabled if pipeline_override is None else bool(pipeline_override)
                elapsed = await asyncio.to_thread(self._do_synth_and_play_blocking, synth, text, streaming, pipeline)
                t1 = time.time()
                if stt_ts is not None:
                    logger.info(
                        "TTS time: %.3fs from STT final to playback-finished; time-to-first-audio ~%.3fs",
                        (t1 - stt_ts),
                        (elapsed if streaming else 0.0),
                    )
                else:
                    logger.info("TTS playback finished in %.3fs", (t1 - t0))

                reason = session.stop_reason if session.stop_requested else None
                await callbacks.publish_status(
                    "speaking_end",
                    text=text,
                    utt_id=session.utt_id,
                    reason=reason,
                    wake_ack=wake_ack,
                )
                logger.debug("Playback end (len=%d)", len(text or ""))
            finally:
                self._current_session = None

    async def _apply_pause(self, session: PlaybackSession, reason: str, callbacks: TTSCallbacks) -> None:
        if session.stop_requested:
            logger.debug("Pause ignored because stop already requested for utt_id=%s", session.utt_id)
            return
        if session.paused and not session.pause_pending:
            logger.debug("Pause ignored because playback already paused for utt_id=%s", session.utt_id)
            return

        proc = self._ensure_active_proc(session)
        if proc is None and not session.pause_pending:
            session.pause_pending = True
        if proc is not None:
            if not hasattr(signal, "SIGSTOP"):
                logger.warning("Pause unsupported on this platform; consider using stop instead")
                return
            try:
                proc.send_signal(signal.SIGSTOP)
            except Exception as exc:
                logger.warning("Failed to pause playback (utt_id=%s): %s", session.utt_id, exc)
                return
            session.pause_pending = False
            session.paused = True
        else:
            session.paused = True

        session.pause_reason = reason
        await callbacks.publish_status(
            "paused",
            text=session.text,
            utt_id=session.utt_id,
            reason=reason,
            wake_ack=None,
        )

    async def _apply_resume(self, session: PlaybackSession, reason: str, callbacks: TTSCallbacks) -> None:
        if session.stop_requested:
            logger.debug("Resume ignored because stop already requested for utt_id=%s", session.utt_id)
            return
        if not session.paused and not session.pause_pending:
            logger.debug("Resume ignored because playback is not paused for utt_id=%s", session.utt_id)
            return

        proc = self._ensure_active_proc(session)
        session.pause_pending = False
        session.paused = False
        session.pause_reason = None

        if proc is not None:
            if not hasattr(signal, "SIGCONT"):
                logger.warning("Resume unsupported on this platform; playback may remain paused")
            else:
                try:
                    proc.send_signal(signal.SIGCONT)
                except Exception as exc:
                    logger.warning("Failed to resume playback (utt_id=%s): %s", session.utt_id, exc)
                    return

        await callbacks.publish_status(
            "resumed",
            text=session.text,
            utt_id=session.utt_id,
            reason=reason,
            wake_ack=None,
        )

    async def _apply_stop(self, session: PlaybackSession, reason: str, callbacks: TTSCallbacks) -> None:
        if session.stop_requested and session.stop_reason == reason:
            return
        session.stop_requested = True
        session.stop_reason = reason
        session.pause_pending = False
        session.paused = False
        session.pause_reason = None
        proc = self._ensure_active_proc(session)
        if proc is not None:
            self._terminate_player(proc, session)
        self._cancel_timer()
        self._agg_texts.clear()
        self._agg_id = None
        self._agg_callbacks = None
        self._agg_stt_ts = None
        await callbacks.publish_status(
            "stopped",
            text=session.text,
            utt_id=session.utt_id,
            reason=reason,
            wake_ack=None,
        )

    def _ensure_active_proc(self, session: PlaybackSession) -> Optional[subprocess.Popen]:
        proc = session.player_proc
        if proc is None:
            return None
        if proc.poll() is not None:
            session.player_proc = None
            return None
        return proc

    def _terminate_player(self, proc: subprocess.Popen, session: PlaybackSession) -> None:
        try:
            if proc.poll() is not None:
                session.player_proc = None
                return
            proc.terminate()
        except Exception as exc:
            logger.warning("Failed to terminate playback process (utt_id=%s): %s", session.utt_id, exc)
        else:
            try:
                proc.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                with suppress(Exception):
                    proc.kill()
        finally:
            session.player_proc = None

    def _match_session(self, control_id: Optional[str]) -> Optional[PlaybackSession]:
        session = self._current_session
        if session is None:
            return None
        if control_id and session.utt_id and control_id != session.utt_id:
            logger.debug("Control id %s does not match active utt_id %s", control_id, session.utt_id)
            return None
        return session

    def _normalize_utt_id(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        trimmed = value.strip()
        return trimmed or None

    def _do_synth_and_play_blocking(self, synth: Synthesizer, text: str, streaming: bool, pipeline: bool) -> float:
        session = self._current_session
        t0 = time.time()
        try:
            if not streaming and hasattr(synth, "synth_to_wav"):
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
                    synth.synth_to_wav(text, f.name)
                    try:
                        proc = subprocess.Popen(["paplay", f.name])
                    except FileNotFoundError:
                        proc = subprocess.Popen(["aplay", f.name])
                    if session is not None:
                        session.player_proc = proc
                    proc.wait()
                return time.time() - t0
            try:
                return synth.synth_and_play(text, streaming=streaming, pipeline=pipeline)
            except TypeError:
                return synth.synth_and_play(text)
        finally:
            if session is not None:
                session.player_proc = None

    @staticmethod
    def md_to_text(md: str) -> str:
        if not md:
            return ""
        try:
            html = md_render(md, extensions=["extra", "sane_lists"])  # type: ignore[arg-type]
        except Exception:
            html = md
        text = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
        return unescape(" ".join(text.split()))