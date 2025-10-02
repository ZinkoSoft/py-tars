from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import signal
import subprocess
import tempfile
import threading
import time
from contextlib import suppress
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from typing import Any, Awaitable, Callable, ClassVar, Literal, Optional, Protocol

from bs4 import BeautifulSoup
from markdown import markdown as md_render

from tars.contracts.v1 import TtsSay

logger = logging.getLogger("tars.domain.tts")

StatusEvent = Literal["speaking_start", "speaking_end", "paused", "resumed", "stopped"]


class Synthesizer(Protocol):
    """Protocol describing synthesizer behavior required by the domain.
    
    Supports both sync and async implementations via duck typing.
    Async methods (synth_and_play_async, synth_to_wav_async) are optional;
    if present, domain will prefer them to avoid event loop blocking.
    """

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
    wake_cache_dir: str | None = None
    wake_cache_max_entries: int = 8
    wake_ack_preload_texts: tuple[str, ...] = ()  # All phrases to preload (wake acks + system messages)


@dataclass(slots=True)
class WakeAckCache:
    """Phrase cache for commonly used TTS text (wake acks, system messages, etc.).
    
    Caches synthesized WAV files to avoid redundant API calls to TTS providers.
    Particularly useful for frequently repeated phrases like wake acknowledgements
    and system status messages (e.g., "System online").
    """
    base_dir: Path
    max_entries: int = 16
    _lock: threading.Lock = field(init=False, repr=False)
    _index: dict[str, Path] = field(init=False, repr=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def ensure(self, text: str, synth: Synthesizer) -> Path:
        key = self._key(text)
        target = self.base_dir / f"{key}.wav"
        with self._lock:
            if target.exists():
                self._index[key] = target
                return target
            tmp = target.with_suffix(".tmp")
            try:
                synth.synth_to_wav(text, str(tmp))
            except Exception:
                with suppress(Exception):
                    tmp.unlink()
                raise
            os.replace(tmp, target)
            self._index[key] = target
            self._prune_locked()
            return target

    def _key(self, text: str) -> str:
        normalized = text.strip().lower()
        return hashlib.sha1(normalized.encode("utf-8")).hexdigest()

    def _prune_locked(self) -> None:
        if self.max_entries <= 0:
            return
        self._cleanup_missing_locked()
        if len(self._index) <= self.max_entries:
            return
        # Remove oldest files beyond the max_entries threshold
        items = sorted(
            self._index.items(),
            key=lambda item: item[1].stat().st_mtime if item[1].exists() else 0.0,
            reverse=True,
        )
        for key, path in items[self.max_entries :]:
            with suppress(Exception):
                path.unlink(missing_ok=True)
            self._index.pop(key, None)

    def _cleanup_missing_locked(self) -> None:
        missing = [key for key, path in self._index.items() if not path.exists()]
        for key in missing:
            self._index.pop(key, None)


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
        self._wake_cache: WakeAckCache | None = None
        if config.wake_cache_dir:
            try:
                self._wake_cache = WakeAckCache(
                    Path(config.wake_cache_dir),
                    max_entries=max(1, int(config.wake_cache_max_entries)),
                )
            except Exception as exc:
                logger.warning("Wake acknowledgement cache unavailable: %s", exc)
                self._wake_cache = None
        self._wake_preloaded = False
        self._wake_preload_lock: asyncio.Lock | None = None

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
                
                # Use async synth if available to avoid double-threading overhead
                if self._has_async_synth(synth):
                    elapsed = await self._do_synth_and_play_async(
                        synth,
                        text,
                        streaming,
                        pipeline,
                        wake_ack,
                    )
                else:
                    # Offload to thread to avoid blocking event loop during synthesis
                    elapsed = await asyncio.to_thread(
                        self._do_synth_and_play_blocking,
                        synth,
                        text,
                        streaming,
                        pipeline,
                        wake_ack,
                    )
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

    def _is_cacheable(self, text: str, wake_ack: bool) -> bool:
        """Check if this text should use the phrase cache.
        
        Returns True if:
        1. It's explicitly marked as wake_ack, OR
        2. It matches one of the preloaded texts (case-insensitive)
        """
        if wake_ack:
            return True
        if not self._config.wake_ack_preload_texts:
            return False
        text_normalized = text.strip().lower()
        for preload_text in self._config.wake_ack_preload_texts:
            if preload_text.strip().lower() == text_normalized:
                return True
        return False

    def _has_async_synth(self, synth: Synthesizer) -> bool:
        """Check if synthesizer supports async methods."""
        return hasattr(synth, "synth_and_play_async") and callable(getattr(synth, "synth_and_play_async"))

    async def _do_synth_and_play_async(
        self,
        synth: Synthesizer,
        text: str,
        streaming: bool,
        pipeline: bool,
        wake_ack: bool,
    ) -> float:
        """Async synthesis using native async synthesizer methods (no double-threading)."""
        session = self._current_session
        try:
            if self._is_cacheable(text, wake_ack) and self._wake_cache is not None and hasattr(synth, "synth_to_wav_async"):
                try:
                    # Wake cache ensure is still sync (lightweight I/O check)
                    cache_path = await asyncio.to_thread(self._wake_cache.ensure, text, synth)
                    logger.debug("Using cached phrase for '%s'", text[:48])
                except Exception as exc:
                    logger.debug("Phrase cache unavailable for '%s': %s", text[:48], exc)
                else:
                    return await asyncio.to_thread(self._play_wav_path, cache_path, session)
            if not streaming and hasattr(synth, "synth_to_wav_async"):
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
                    await synth.synth_to_wav_async(text, f.name)  # type: ignore[attr-defined]
                    return await asyncio.to_thread(self._play_wav_path, Path(f.name), session)
            try:
                return await synth.synth_and_play_async(text, streaming=streaming, pipeline=pipeline)  # type: ignore[attr-defined]
            except TypeError:
                return await synth.synth_and_play_async(text)  # type: ignore[attr-defined]
        finally:
            if session is not None:
                session.player_proc = None

    def _do_synth_and_play_blocking(
        self,
        synth: Synthesizer,
        text: str,
        streaming: bool,
        pipeline: bool,
        wake_ack: bool,
    ) -> float:
        session = self._current_session
        try:
            if self._is_cacheable(text, wake_ack) and self._wake_cache is not None and hasattr(synth, "synth_to_wav"):
                try:
                    cache_path = self._wake_cache.ensure(text, synth)
                    logger.debug("Using cached phrase for '%s'", text[:48])
                except Exception as exc:
                    logger.debug("Phrase cache unavailable for '%s': %s", text[:48], exc)
                else:
                    return self._play_wav_path(cache_path, session)
            if not streaming and hasattr(synth, "synth_to_wav"):
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
                    synth.synth_to_wav(text, f.name)
                    return self._play_wav_path(Path(f.name), session)
            try:
                return synth.synth_and_play(text, streaming=streaming, pipeline=pipeline)
            except TypeError:
                return synth.synth_and_play(text)
        finally:
            if session is not None:
                session.player_proc = None

    def _play_wav_path(self, path: Path, session: PlaybackSession | None) -> float:
        start = time.time()
        try:
            proc = subprocess.Popen(["paplay", str(path)])
        except FileNotFoundError:
            proc = subprocess.Popen(["aplay", str(path)])
        if session is not None:
            session.player_proc = proc
        proc.wait()
        return time.time() - start

    async def preload_wake_cache(self) -> None:
        cache = self._wake_cache
        if cache is None:
            return
        lock = self._wake_preload_lock
        if lock is None:
            lock = asyncio.Lock()
            self._wake_preload_lock = lock
        async with lock:
            if self._wake_preloaded:
                return
            texts = [t.strip() for t in self._config.wake_ack_preload_texts if t.strip()]
            if not texts:
                self._wake_preloaded = True
                return
            synth = self._wake_synth if self._wake_synth is not None else self._primary_synth
            if not hasattr(synth, "synth_to_wav"):
                logger.debug("Synth lacks synth_to_wav; skipping phrase cache preload")
                self._wake_preloaded = True
                return
            for text in texts:
                try:
                    await asyncio.to_thread(cache.ensure, text, synth)
                    logger.info("Phrase cache preloaded", extra={"text": text[:48]})
                except Exception as exc:
                    logger.warning("Phrase cache preload failed", extra={"text": text[:48], "error": str(exc)})
            self._wake_preloaded = True

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