from __future__ import annotations

import asyncio
import logging
import signal
import subprocess
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse

import asyncio_mqtt as mqtt
import orjson as json
from asyncio_mqtt import MqttError
from markdown import markdown as md_render
from bs4 import BeautifulSoup
from html import unescape

import tempfile

from .config import MQTT_URL, TTS_STREAMING, TTS_PIPELINE, TTS_AGGREGATE, TTS_AGGREGATE_DEBOUNCE_MS, TTS_AGGREGATE_SINGLE_WAV
from .models import TTSControlMessage
from .piper_synth import PiperSynth, _spawn_player, set_player_observer, set_stop_checker


logger = logging.getLogger("tts-worker")

STATUS_TOPIC = "tts/status"
SAY_TOPIC = "tts/say"
CONTROL_TOPIC = "tts/control"

_HAS_SIGSTOP = hasattr(signal, "SIGSTOP")
_HAS_SIGCONT = hasattr(signal, "SIGCONT")


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


def parse_mqtt(url: str):
    u = urlparse(url)
    return (u.hostname or "127.0.0.1", u.port or 1883, u.username, u.password)


class TTSService:
    def __init__(self, synth: Any):
        self.synth = synth
        # Aggregation state
        self._agg_id: str | None = None
        self._agg_texts: list[str] = []
        self._agg_timer: asyncio.TimerHandle | None = None
        # Ensure only one playback happens at a time to avoid overlapping audio
        self._play_lock = asyncio.Lock()
        self._current_session: Optional[PlaybackSession] = None
        set_player_observer(self._on_player_spawn)
        set_stop_checker(self._should_abort_playback)

    def _cancel_timer(self):
        try:
            if self._agg_timer and not self._agg_timer.cancelled():
                self._agg_timer.cancel()
        except Exception:
            pass
        self._agg_timer = None

    def _schedule_flush(self, loop: asyncio.AbstractEventLoop, client: mqtt.Client, stt_ts: float | None):
        delay = max(0.01, TTS_AGGREGATE_DEBOUNCE_MS / 1000.0)

        def _cb():
            asyncio.create_task(self._flush_aggregate(client, stt_ts))

        self._cancel_timer()
        self._agg_timer = loop.call_later(delay, _cb)

    async def _flush_aggregate(self, client: mqtt.Client, stt_ts: float | None):
        self._cancel_timer()
        if not self._agg_texts:
            return
        logger.debug("Flushing TTS aggregate: count=%d single_wav=%s", len(self._agg_texts), bool(TTS_AGGREGATE_SINGLE_WAV))
        utt_id = self._agg_id
        if TTS_AGGREGATE_SINGLE_WAV:
            text = " ".join(t.strip() for t in self._agg_texts if t and t.strip())
            self._agg_texts.clear()
            self._agg_id = None
            # For a single WAV, disable streaming/pipeline to ensure a single continuous file
            await self._speak(
                client,
                text,
                stt_ts,
                utt_id=self._normalize_utt_id(utt_id),
                streaming_override=False,
                pipeline_override=False,
            )
        else:
            texts = [t.strip() for t in self._agg_texts if t and t.strip()]
            self._agg_texts.clear()
            self._agg_id = None
            for t in texts:
                await self._speak(client, t, stt_ts, utt_id=self._normalize_utt_id(utt_id))

    @staticmethod
    def md_to_text(md: str) -> str:
        """Convert Markdown to plain text for clean TTS.

        - Renders Markdown to HTML using python-markdown (with a couple of safe extensions)
        - Strips HTML to text via BeautifulSoup
        - Normalizes whitespace and unescapes HTML entities
        """
        if not md:
            return ""
        try:
            html = md_render(md, extensions=["extra", "sane_lists"])  # type: ignore[arg-type]
        except Exception:
            # If markdown parsing fails for any reason, fall back to raw text
            html = md
        text = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
        return unescape(" ".join(text.split()))

    async def _publish_status(
        self,
        mqtt_client: mqtt.Client,
        *,
        event: str,
        text: str,
        utt_id: Optional[str],
        reason: Optional[str] = None,
        log_level: int = logging.INFO,
    ) -> None:
        payload: dict[str, Any] = {"event": event, "text": text, "timestamp": time.time()}
        if utt_id:
            payload["utt_id"] = utt_id
        if reason:
            payload["reason"] = reason
        message = json.dumps(payload)
        await mqtt_client.publish(STATUS_TOPIC, message)
        logger.log(log_level, "Published TTS %s status: %s", event, message)

    async def run(self) -> None:
        host, port, username, password = parse_mqtt(MQTT_URL)
        logger.info(f"Connecting to MQTT {host}:{port}")
        try:
            async with mqtt.Client(hostname=host, port=port, username=username, password=password, client_id="tars-tts") as client:
                logger.info(f"Connected to MQTT {host}:{port} as tars-tts")
                await client.publish("system/health/tts", json.dumps({"ok": True, "event": "ready"}), retain=True)
                await client.subscribe([(SAY_TOPIC, 0), (CONTROL_TOPIC, 0)])
                logger.info("Subscribed to %s and %s, ready to process messages", SAY_TOPIC, CONTROL_TOPIC)
                async with client.messages() as messages:
                    async for msg in messages:
                        try:
                            data = json.loads(msg.payload)
                            if msg.topic == SAY_TOPIC:
                                await self._handle_tts_say(client, data)
                            elif msg.topic == CONTROL_TOPIC:
                                await self._handle_control_message(client, data)
                            else:
                                logger.debug("Ignoring unexpected topic %s", msg.topic)
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
                            await client.publish("system/health/tts", json.dumps({"ok": False, "err": str(e)}), retain=True)
        except MqttError as e:
            logger.info(f"MQTT disconnected: {e}; shutting down gracefully")

    async def _handle_tts_say(self, client: mqtt.Client, data: Any) -> None:
        if not isinstance(data, dict):
            logger.warning("tts/say payload must be an object, received %s", type(data).__name__)
            return
        raw_text = data.get("text", "")
        text = self.md_to_text(raw_text)
        if not text:
            return
        stt_ts = data.get("stt_ts") or data.get("timestamp")
        utt_id_raw = data.get("utt_id")
        if TTS_AGGREGATE and isinstance(utt_id_raw, str) and utt_id_raw:
            loop = asyncio.get_running_loop()
            if self._agg_id and self._agg_id != utt_id_raw and self._agg_texts:
                await self._flush_aggregate(client, stt_ts)
            self._agg_id = utt_id_raw
            self._agg_texts.append(text)
            self._schedule_flush(loop, client, stt_ts)
            return
        # Non-aggregated path or missing utt_id: flush any pending aggregate first
        if self._agg_texts:
            await self._flush_aggregate(client, stt_ts)
        await self._speak(client, text, stt_ts, utt_id=self._normalize_utt_id(utt_id_raw if isinstance(utt_id_raw, str) else None))

    async def _handle_control_message(self, client: mqtt.Client, data: Any) -> None:
        try:
            control = TTSControlMessage.from_dict(data)
        except ValueError as exc:
            logger.warning("Invalid tts/control payload: %s", exc)
            return

        session = self._match_session(control.request_id)
        if session is None:
            logger.debug("No active playback for control id %s", control.request_id)
            return

        action = control.action
        if action == "pause":
            await self._apply_pause(client, session, control.reason)
        elif action == "resume":
            await self._apply_resume(client, session, control.reason)
        elif action == "stop":
            await self._apply_stop(client, session, control.reason)

    async def _speak(
        self,
        mqtt_client: mqtt.Client,
        text: str,
        stt_ts: float | None,
        *,
        utt_id: Optional[str] = None,
        streaming_override: bool | None = None,
        pipeline_override: bool | None = None,
    ) -> None:
        if self._play_lock.locked():
            logger.debug("Playback busy; queuing next utterance (len=%d)", len(text or ""))
        async with self._play_lock:
            session = PlaybackSession(utt_id=utt_id, text=text, started_at=time.time())
            self._current_session = session
            try:
                logger.debug("Playback start (len=%d)", len(text or ""))
                await self._publish_status(mqtt_client, event="speaking_start", text=text, utt_id=session.utt_id)

                t0 = time.time()
                streaming = bool(TTS_STREAMING) if streaming_override is None else bool(streaming_override)
                pipeline = bool(TTS_PIPELINE) if pipeline_override is None else bool(pipeline_override)
                # Offload blocking synthesis/playback to a thread to keep event loop responsive
                elapsed = await asyncio.to_thread(self._do_synth_and_play_blocking, text, streaming, pipeline)
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
                await self._publish_status(
                    mqtt_client,
                    event="speaking_end",
                    text=text,
                    utt_id=session.utt_id,
                    reason=reason,
                )
                logger.debug("Playback end (len=%d)", len(text or ""))
            finally:
                self._current_session = None

    @staticmethod
    def _normalize_utt_id(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        trimmed = value.strip()
        return trimmed or None

    def _match_session(self, control_id: Optional[str]) -> Optional[PlaybackSession]:
        session = self._current_session
        if session is None:
            return None
        if control_id and session.utt_id and control_id != session.utt_id:
            logger.debug("Control id %s does not match active utt_id %s", control_id, session.utt_id)
            return None
        return session

    def _should_abort_playback(self) -> bool:
        session = self._current_session
        return bool(session and session.stop_requested)

    def _ensure_active_proc(self, session: PlaybackSession) -> Optional[subprocess.Popen]:
        proc = session.player_proc
        if proc is None:
            return None
        if proc.poll() is not None:
            session.player_proc = None
            return None
        return proc

    async def _apply_pause(self, client: mqtt.Client, session: PlaybackSession, reason: str) -> None:
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
            if not _HAS_SIGSTOP:
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
        await self._publish_status(client, event="paused", text=session.text, utt_id=session.utt_id, reason=reason)

    async def _apply_resume(self, client: mqtt.Client, session: PlaybackSession, reason: str) -> None:
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
            if not _HAS_SIGCONT:
                logger.warning("Resume unsupported on this platform; playback may remain paused")
            else:
                try:
                    proc.send_signal(signal.SIGCONT)
                except Exception as exc:
                    logger.warning("Failed to resume playback (utt_id=%s): %s", session.utt_id, exc)
                    return

        await self._publish_status(client, event="resumed", text=session.text, utt_id=session.utt_id, reason=reason)

    async def _apply_stop(self, client: mqtt.Client, session: PlaybackSession, reason: str) -> None:
        if session.stop_requested:
            logger.debug("Stop already requested for utt_id=%s", session.utt_id)
            if session.stop_reason == reason:
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
        await self._publish_status(client, event="stopped", text=session.text, utt_id=session.utt_id, reason=reason)

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

    def _on_player_spawn(self, proc: subprocess.Popen, role: str) -> None:
        session = self._current_session
        if session is None:
            return
        session.player_proc = proc
        session.last_role = role
        if session.stop_requested:
            self._terminate_player(proc, session)
            return
        if session.pause_pending and _HAS_SIGSTOP:
            try:
                proc.send_signal(signal.SIGSTOP)
            except Exception as exc:
                logger.warning("Deferred pause failed for utt_id=%s: %s", session.utt_id, exc)
                session.pause_pending = False
            else:
                session.pause_pending = False
                session.paused = True

    # ----- blocking helper (runs in thread) -----
    def _do_synth_and_play_blocking(self, text: str, streaming: bool, pipeline: bool) -> float:
        session = self._current_session
        t0 = time.time()
        # If the synthesizer supports explicit single-WAV synthesis and streaming is disabled,
        # honor the "single WAV" path (used by aggregation) even for external providers.
        try:
            if not streaming and hasattr(self.synth, "synth_to_wav"):
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
                    self.synth.synth_to_wav(text, f.name)
                    p = _spawn_player(args=[f.name], role="playback")
                    p.wait()
                return time.time() - t0
            # Otherwise use provider's synth_and_play API
            try:
                return self.synth.synth_and_play(text, streaming=streaming, pipeline=pipeline)
            except TypeError:
                return self.synth.synth_and_play(text)
        finally:
            if session is not None:
                session.player_proc = None
