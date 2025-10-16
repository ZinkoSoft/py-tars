from __future__ import annotations

import itertools
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from tars.contracts.v1 import (
    EVENT_TYPE_LLM_REQUEST,
    EVENT_TYPE_SAY,
    ConversationMessage,
    FinalTranscript,
    HealthPing,
    LLMCancel,
    LLMRequest,
    LLMResponse,
    LLMStreamDelta,
    TestMovementCommand,
    TestMovementRequest,
    TtsSay,
    TtsStatus,
    WakeEvent,
)
from tars.runtime.ctx import Ctx

from .config import RouterSettings
from .metrics import RouterMetrics


@dataclass(slots=True)
class RouterPolicy:
    """Stateful policy that translates observed events into actions."""

    settings: RouterSettings
    metrics: RouterMetrics | None = None
    ready: Dict[str, bool] = field(default_factory=lambda: {"tts": False, "stt": False})
    announced: bool = False
    llm_buf: Dict[str, str] = field(default_factory=dict)
    llm_stream_segments: Dict[str, List[str]] = field(default_factory=dict)
    llm_stream_completed: set[str] = field(default_factory=set)
    live_mode: bool = field(init=False)
    wake_active_until: float = 0.0
    wake_session_active: bool = False
    response_window_active: bool = False
    response_window_until: float = 0.0
    conversation_history: List[ConversationMessage] = field(default_factory=list)
    _wake_regex: re.Pattern[str] = field(init=False)
    _wake_ack_cycle: Optional[itertools.cycle[str]] = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.live_mode = self.settings.live_mode_default
        wake_pattern = "|".join(re.escape(phrase) for phrase in self.settings.wake_phrases)
        self._wake_regex = re.compile(rf"^\s*(?:{wake_pattern})\\b[\s,]*", re.IGNORECASE)
        self._wake_ack_cycle = (
            itertools.cycle(self.settings.wake_ack_choices)
            if self.settings.wake_ack_choices
            else None
        )

    async def handle_health(self, service: str, event: HealthPing, ctx: Ctx) -> None:
        ctx.logger.debug("router.health", extra={"service": service, "ok": event.ok})
        if service not in self.ready:
            self.ready[service] = False
        previous = self.ready[service]
        self.ready[service] = self.ready[service] or event.ok
        if previous != self.ready[service]:
            ctx.logger.info("router.health.update", extra={"service": service, "ok": event.ok, "state": self.ready})
        if (
            self.settings.online_announce
            and self.ready.get("tts")
            and self.ready.get("stt")
            and not self.announced
        ):
            self.announced = True
            ctx.logger.info("router.health.online")
            await self._speak(
                ctx,
                text=self.settings.online_text,
                style="neutral",
                utt_id="boot",
                system_announce=True,  # Don't open response window for system boot announcement
                correlate=ctx.id_from(event),
            )
            self._log_metrics(ctx)

    async def handle_wake_event(self, event: WakeEvent, ctx: Ctx) -> None:
        event_type = (event.type or "").lower()
        ctx.logger.info("router.wake", extra={"event": event_type})
        tts_id = event.tts_id
        if event_type == "wake":
            self._open_wake_window()
            ack_text = self._next_wake_ack_text()
            if ack_text:
                ack_utt_id = tts_id or f"wake-ack-{int(time.time() * 1000)}"
                await self._speak(
                    ctx,
                    text=ack_text,
                    style=self.settings.wake_ack_style,
                    utt_id=ack_utt_id,
                    wake_ack=True,
                    correlate=ctx.id_from(event),
                )
            if self.settings.wake_reprompt_text:
                await self._speak(
                    ctx,
                    text=self.settings.wake_reprompt_text,
                    utt_id=tts_id,
                    correlate=ctx.id_from(event),
                )
        elif event_type == "interrupt":
            self._open_wake_window()
            if self.settings.wake_interrupt_text:
                await self._speak(
                    ctx,
                    text=self.settings.wake_interrupt_text,
                    utt_id=tts_id,
                    correlate=ctx.id_from(event),
                )
        elif event_type == "resume":
            self._close_wake_window()
            if self.settings.wake_resume_text:
                await self._speak(
                    ctx,
                    text=self.settings.wake_resume_text,
                    utt_id=tts_id,
                    correlate=ctx.id_from(event),
                )
        elif event_type == "cancelled":
            self._close_wake_window()
            if self.settings.wake_cancel_text:
                await self._speak(
                    ctx,
                    text=self.settings.wake_cancel_text,
                    utt_id=tts_id,
                    correlate=ctx.id_from(event),
                )
        elif event_type == "timeout":
            self._close_wake_window()
            if self.settings.wake_timeout_text:
                await self._speak(
                    ctx,
                    text=self.settings.wake_timeout_text,
                    utt_id=tts_id,
                    correlate=ctx.id_from(event),
                )
        else:
            ctx.logger.debug("router.wake.ignored", extra={"event": event_type})

    async def handle_tts_status(self, event: TtsStatus, ctx: Ctx) -> None:
        event_type = (event.event or "").lower()
        if event_type == "speaking_end" and not event.wake_ack:
            # Start a response window for conversational follow-ups
            self._open_response_window()
            ctx.logger.debug("router.response_window.opened", extra={"until": self.response_window_until})

    async def handle_stt_final(self, event: FinalTranscript, ctx: Ctx) -> None:
        text = (event.text or "").strip()
        if not text:
            ctx.logger.debug("router.stt.empty")
            return

        now = time.monotonic()
        if self.wake_session_active and now > self.wake_active_until:
            ctx.logger.info("router.wake.expired")
            self._close_wake_window()

        if self.response_window_active and now > self.response_window_until:
            ctx.logger.debug("router.response_window.expired")
            self._close_response_window()

        candidate_text = text
        remainder = self._strip_wake_phrase(text)
        if remainder:
            candidate_text = remainder

        window_active = self.wake_session_active
        response_window_active = self.response_window_active
        gating_reason: Optional[str] = None
        if self.live_mode:
            gating_reason = "live-mode"
        elif window_active:
            gating_reason = "wake-event"
        elif response_window_active:
            gating_reason = "response-window"

        if not self.live_mode and not window_active and not response_window_active:
            ctx.logger.info("router.stt.dropped", extra={"reason": "no-wake"})
            return

        norm_candidate = self._normalize_command(candidate_text)

        if norm_candidate == self.settings.live_mode_enter_phrase:
            if self.live_mode:
                await self._speak(
                    ctx,
                    text=self.settings.live_mode_active_hint,
                    utt_id=event.utt_id,
                    correlate=ctx.id_from(event),
                )
            else:
                self.live_mode = True
                self._close_wake_window()
                await self._speak(
                    ctx,
                    text=self.settings.live_mode_enter_ack,
                    utt_id=event.utt_id,
                    correlate=ctx.id_from(event),
                )
            return

        if norm_candidate == self.settings.live_mode_exit_phrase:
            if not self.live_mode:
                await self._speak(
                    ctx,
                    text=self.settings.live_mode_inactive_hint,
                    utt_id=event.utt_id,
                    correlate=ctx.id_from(event),
                )
            else:
                self.live_mode = False
                self._close_wake_window()
                await self._speak(
                    ctx,
                    text=self.settings.live_mode_exit_ack,
                    utt_id=event.utt_id,
                    correlate=ctx.id_from(event),
                )
            return

        if window_active:
            self._close_wake_window()

        if response_window_active:
            self._close_response_window()

        ctx.logger.debug("router.stt.route", extra={"gating": gating_reason or "wake"})

        # Check for movement commands first
        movement_cmd = self._detect_movement_command(candidate_text)
        if movement_cmd is not None:
            req = TestMovementRequest(
                command=movement_cmd,
                speed=1.0,
                request_id=event.utt_id or f"mv-{uuid.uuid4().hex[:8]}"
            )
            await ctx.publish(
                self.settings.topic_movement_test,
                req,
                correlate=ctx.id_from(event),
                qos=1
            )
            ctx.logger.info("router.movement.command", extra={"command": movement_cmd.value})
            return

        resp = self._rule_route(candidate_text)
        if resp is not None:
            await self._speak(
                ctx,
                text=resp["text"],
                style=resp["style"],
                utt_id=event.utt_id,
                stt_ts=event.ts,
                correlate=ctx.id_from(event),
            )
            return

        req_id = event.utt_id or f"rt-{uuid.uuid4().hex[:8]}"
        # Add user message to conversation history
        self._add_user_message(candidate_text, event.ts)
        # Include recent conversation history (limit to avoid token limits)
        recent_history = self._get_recent_history(max_messages=10)
        llm_req = LLMRequest(id=req_id, text=candidate_text, stream=True, conversation_history=recent_history)
        ctx.logger.info(
            "router.llm.request",
            extra={"id": req_id, "len": len(candidate_text or ""), "reason": gating_reason, "history_len": len(recent_history)},
        )
        await ctx.publish(EVENT_TYPE_LLM_REQUEST, llm_req, correlate=ctx.id_from(event), qos=1)
        if self.metrics:
            self.metrics.record_llm_request(req_id)
            self._log_metrics(ctx)

    async def handle_llm_cancel(self, event: LLMCancel, ctx: Ctx) -> None:
        rid = event.id.strip()
        if rid and rid in self.llm_buf:
            ctx.logger.info("router.llm.cancel", extra={"id": rid})
            self.llm_buf.pop(rid, None)
        if rid:
            self.llm_stream_segments.pop(rid, None)
            self.llm_stream_completed.discard(rid)
        if self.metrics:
            self.metrics.abandon_llm_request(rid)
            self._log_metrics(ctx)

    async def handle_llm_response(self, event: LLMResponse, ctx: Ctx) -> None:
        ctx.logger.info("router.llm.response.raw", extra={"id": event.id or "", "error": bool(event.error)})
        text = (event.reply or "").strip()
        rid = (event.id or "").strip()
        ctx.logger.info(
            "router.llm.response.received",
            extra={"id": event.id or "", "len": len(text), "provider": event.provider, "model": event.model},
        )
        stream_completed = bool(rid and rid in self.llm_stream_completed)
        if self.settings.router_llm_tts_stream and rid and stream_completed:
            segments = self.llm_stream_segments.pop(rid, [])
            residual, matched = self._residual_after_stream(text, segments)
            if matched and not residual:
                ctx.logger.info(
                    "router.llm.response.skip",
                    extra={"id": rid, "reason": "already-streamed"},
                )
                self.llm_stream_completed.discard(rid)
                return
            if matched and residual:
                ctx.logger.info(
                    "router.llm.response.residual",
                    extra={"id": rid, "len": len(residual)},
                )
                text = residual
            elif segments:
                ctx.logger.warning(
                    "router.llm.response.desync",
                    extra={"id": rid, "segments": len(segments), "len": len(text)},
                )
        else:
            if rid:
                self.llm_stream_segments.pop(rid, None)
        if not text:
            return
        ctx.logger.info("router.llm.response", extra={"len": len(text)})
        # Add assistant response to conversation history
        self._add_assistant_message(text)
        await self._speak(
            ctx,
            text=text,
            utt_id=rid or None,
            correlate=ctx.id_from(event),
        )
        if self.metrics and (not rid or rid not in self.llm_stream_completed):
            self.metrics.record_llm_response(rid or "")
            self._log_metrics(ctx)
        if rid:
            self.llm_stream_completed.discard(rid)

    async def handle_llm_stream(self, event: LLMStreamDelta, ctx: Ctx) -> None:
        if not self.settings.router_llm_tts_stream:
            return
        rid = (event.id or "").strip()
        if not rid:
            return
        self.llm_stream_completed.discard(rid)
        delta = event.delta or ""
        done = bool(event.done)
        buf = self.llm_buf.get(rid, "")
        if delta:
            buf += delta
            flushed_any = False
            while self._should_flush(buf):
                sent, remainder = self._split_on_boundary(buf)
                if not sent:
                    if self.settings.stream_boundary_only:
                        break
                    cut = min(len(buf), self.settings.stream_max_chars)
                    if cut <= 0:
                        break
                    sent, remainder = buf[:cut].strip(), buf[cut:].lstrip()
                    if not sent:
                        break
                ctx.logger.info("router.llm.stream.flush", extra={"len": len(sent), "id": rid})
                self._record_stream_segment(rid, sent)
                await self._speak(ctx, text=sent, utt_id=rid, correlate=ctx.id_from(event))
                buf = remainder
                flushed_any = True
            self.llm_buf[rid] = buf
            if not flushed_any:
                ctx.logger.debug("router.llm.stream.buffer", extra={"id": rid, "len": len(buf)})
            if self.settings.stream_boundary_only and len(buf) > self.settings.stream_hard_max_chars:
                cut_idx = buf.rfind(" ", 0, self.settings.stream_hard_max_chars)
                if cut_idx <= 0:
                    cut_idx = self.settings.stream_hard_max_chars
                sent, remainder = buf[:cut_idx].strip(), buf[cut_idx:].lstrip()
                if sent:
                    ctx.logger.info("router.llm.stream.safety", extra={"len": len(sent), "id": rid})
                    self._record_stream_segment(rid, sent)
                    await self._speak(ctx, text=sent, utt_id=rid, correlate=ctx.id_from(event))
                    self.llm_buf[rid] = remainder
        if done:
            final = self.llm_buf.pop(rid, "").strip()
            if final:
                ctx.logger.info("router.llm.stream.final", extra={"len": len(final), "id": rid})
                self._record_stream_segment(rid, final)
                await self._speak(ctx, text=final, utt_id=rid, correlate=ctx.id_from(event))
            if self.metrics:
                self.metrics.record_llm_response(rid)
                self._log_metrics(ctx)
            self.llm_stream_completed.add(rid)

    # ------------------------------------------------------------------
    # Helpers

    def _open_wake_window(self) -> None:
        self.wake_session_active = True
        self.wake_active_until = time.monotonic() + self.settings.wake_window_sec

    def _close_wake_window(self) -> None:
        self.wake_session_active = False
        self.wake_active_until = 0.0

    def _open_response_window(self) -> None:
        # Use the same duration as the STT worker's response window
        self.response_window_active = True
        self.response_window_until = time.monotonic() + 10.0  # 10 seconds

    def _close_response_window(self) -> None:
        self.response_window_active = False
        self.response_window_until = 0.0

    def _next_wake_ack_text(self) -> Optional[str]:
        if not self.settings.wake_ack_enabled:
            return None
        if self._wake_ack_cycle is not None:
            return next(self._wake_ack_cycle)
        return self.settings.wake_ack_text

    async def _speak(
        self,
        ctx: Ctx,
        *,
        text: str,
        style: str = "neutral",
        utt_id: Optional[str] = None,
        wake_ack: Optional[bool] = None,
        system_announce: Optional[bool] = None,
        correlate: Optional[str] = None,
        stt_ts: Optional[float] = None,
    ) -> None:
        if not text:
            return
        say = TtsSay(
            text=text,
            voice=self.settings.tts_voice,
            lang="en",
            utt_id=utt_id,
            style=style,
            wake_ack=wake_ack,
            system_announce=system_announce,
            stt_ts=stt_ts,
        )
        await ctx.publish(EVENT_TYPE_SAY, say, correlate=correlate, qos=1)
        ctx.logger.info(
            "router.tts.say",
            extra={
                "utt_id": utt_id,
                "len": len(text),
                "wake_ack": wake_ack,
                "system_announce": system_announce,
                "stream_mode": self.settings.router_llm_tts_stream,
            },
        )
        if self.metrics:
            self.metrics.record_tts_message()
            self._log_metrics(ctx)

    def _record_stream_segment(self, rid: str, segment: str) -> None:
        seg = segment.strip()
        if not rid or not seg:
            return
        self.llm_stream_segments.setdefault(rid, []).append(seg)

    def _residual_after_stream(self, text: str, segments: List[str]) -> tuple[str, bool]:
        remainder = text
        for segment in segments:
            seg = segment.strip()
            if not seg:
                continue
            remainder = remainder.lstrip()
            if remainder.startswith(seg):
                remainder = remainder[len(seg) :]
            else:
                return text, False
        return remainder.lstrip(), True

    @staticmethod
    def _normalize_command(text: str) -> str:
        cleaned = re.sub(r"[^a-z0-9\s]", "", text.lower())
        return re.sub(r"\s+", " ", cleaned).strip()

    def _detect_movement_command(self, text: str) -> Optional[TestMovementCommand]:
        """
        Detect movement commands from user input.
        
        Returns TestMovementCommand if a movement is detected, None otherwise.
        """
        t = text.lower().strip()
        
        # Map common phrases to movement commands
        movement_patterns = {
            TestMovementCommand.WAVE: ["wave", "wave your hand", "wave hello"],
            TestMovementCommand.LAUGH: ["laugh", "do a laugh", "laugh animation"],
            TestMovementCommand.BOW: ["bow", "take a bow", "bow down"],
            TestMovementCommand.SWING_LEGS: ["swing legs", "swing your legs", "leg swing"],
            TestMovementCommand.BALANCE: ["balance", "stand up", "balance yourself"],
            TestMovementCommand.POSE: ["pose", "strike a pose", "do a pose"],
            TestMovementCommand.STEP_FORWARD: ["step forward", "walk forward", "move forward"],
            TestMovementCommand.STEP_BACKWARD: ["step backward", "step back", "walk backward", "move back"],
            TestMovementCommand.TURN_LEFT: ["turn left", "rotate left"],
            TestMovementCommand.TURN_RIGHT: ["turn right", "rotate right"],
            TestMovementCommand.RESET: ["reset", "reset position", "go to reset"],
            TestMovementCommand.DISABLE: ["disable", "turn off", "power down"],
            TestMovementCommand.STOP: ["stop", "stop moving", "halt"],
            TestMovementCommand.MIC_DROP: ["mic drop", "drop the mic"],
            TestMovementCommand.MONSTER: ["monster", "monster pose"],
            TestMovementCommand.PEZZ_DISPENSER: ["pez", "pez dispenser", "pezz"],
            TestMovementCommand.NOW: ["now", "now pose"],
        }
        
        # Check for exact or substring matches
        for cmd, patterns in movement_patterns.items():
            for pattern in patterns:
                if pattern in t or t == pattern:
                    return cmd
        
        return None


    def _strip_wake_phrase(self, text: str) -> Optional[str]:
        match = self._wake_regex.match(text)
        if not match:
            return None
        remainder = text[match.end() :].strip()
        return remainder

    def _rule_route(self, text: str) -> Optional[dict[str, str]]:
        t = text.lower().strip()
        if any(x in t for x in ("what time", "time is it")):
            from datetime import datetime

            now = datetime.now().strftime("%-I:%M %p")
            return {"text": f"It is {now}.", "style": "neutral"}
        if t.startswith("say "):
            return {"text": text[4:], "style": "neutral"}
        if re.search(r"\b(hello|hi|hey|hiya|howdy)\b", t):
            return {"text": "Hello! How can I help?", "style": "friendly"}
        return None

    def _should_flush(self, buf: str) -> bool:
        if self.settings.stream_boundary_only:
            return any(ch in buf for ch in self.settings.stream_boundary_chars)
        if any(ch in buf for ch in self.settings.stream_boundary_chars):
            return True
        if len(buf) >= self.settings.stream_min_chars:
            return True
        return len(buf) >= self.settings.stream_max_chars

    def _split_on_boundary(self, text: str) -> tuple[str, str]:
        idx = -1
        for i in range(len(text) - 1, -1, -1):
            ch = text[i]
            if ch in self.settings.stream_boundary_chars:
                if i == len(text) - 1 or text[i + 1].isspace():
                    idx = i
                    break
        if idx < 0:
            idx = max((text.rfind(ch) for ch in self.settings.stream_boundary_chars), default=-1)
        if idx >= 0:
            return text[: idx + 1].strip(), text[idx + 1 :].lstrip()
        return "", text

    def _log_metrics(self, ctx: Ctx) -> None:
        if not self.metrics:
            return
        ctx.logger.debug("router.metrics", extra=self.metrics.snapshot())

    def _add_user_message(self, text: str, timestamp: Optional[float] = None) -> None:
        """Add a user message to conversation history."""
        self.conversation_history.append(
            ConversationMessage(role="user", content=text, timestamp=timestamp)
        )

    def _add_assistant_message(self, text: str, timestamp: Optional[float] = None) -> None:
        """Add an assistant message to conversation history."""
        self.conversation_history.append(
            ConversationMessage(role="assistant", content=text, timestamp=timestamp or time.time())
        )

    def _get_recent_history(self, max_messages: int = 10) -> List[ConversationMessage]:
        """Get recent conversation history, limited to max_messages."""
        return self.conversation_history[-max_messages:] if self.conversation_history else []

    def _clear_conversation_history(self) -> None:
        """Clear conversation history (useful for new sessions)."""
        self.conversation_history.clear()
