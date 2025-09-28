from __future__ import annotations

import itertools
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional

from tars.contracts.v1 import (
    EVENT_TYPE_LLM_REQUEST,
    EVENT_TYPE_SAY,
    FinalTranscript,
    HealthPing,
    LLMCancel,
    LLMRequest,
    LLMResponse,
    LLMStreamDelta,
    TtsSay,
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
    live_mode: bool = field(init=False)
    wake_active_until: float = 0.0
    wake_session_active: bool = False
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

    async def handle_stt_final(self, event: FinalTranscript, ctx: Ctx) -> None:
        text = (event.text or "").strip()
        if not text:
            ctx.logger.debug("router.stt.empty")
            return

        now = time.monotonic()
        if self.wake_session_active and now > self.wake_active_until:
            ctx.logger.info("router.wake.expired")
            self._close_wake_window()

        candidate_text = text
        remainder = self._strip_wake_phrase(text)
        if remainder:
            candidate_text = remainder

        window_active = self.wake_session_active
        gating_reason: Optional[str] = None
        if self.live_mode:
            gating_reason = "live-mode"
        elif window_active:
            gating_reason = "wake-event"

        if not self.live_mode and not window_active:
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

        ctx.logger.debug("router.stt.route", extra={"gating": gating_reason or "wake"})

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
        llm_req = LLMRequest(id=req_id, text=candidate_text, stream=True)
        ctx.logger.info(
            "router.llm.request",
            extra={"id": req_id, "len": len(candidate_text or ""), "reason": gating_reason},
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
        if self.metrics:
            self.metrics.abandon_llm_request(rid)
            self._log_metrics(ctx)

    async def handle_llm_response(self, event: LLMResponse, ctx: Ctx) -> None:
        text = (event.reply or "").strip()
        if not text:
            return
        ctx.logger.info("router.llm.response", extra={"len": len(text)})
        await self._speak(
            ctx,
            text=text,
            utt_id=event.id or None,
            correlate=ctx.id_from(event),
        )
        if self.metrics:
            self.metrics.record_llm_response(event.id or "")
            self._log_metrics(ctx)

    async def handle_llm_stream(self, event: LLMStreamDelta, ctx: Ctx) -> None:
        if not self.settings.router_llm_tts_stream:
            return
        rid = (event.id or "").strip()
        if not rid:
            return
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
                    await self._speak(ctx, text=sent, utt_id=rid, correlate=ctx.id_from(event))
                    self.llm_buf[rid] = remainder
        if done:
            final = self.llm_buf.pop(rid, "").strip()
            if final:
                ctx.logger.info("router.llm.stream.final", extra={"len": len(final), "id": rid})
                await self._speak(ctx, text=final, utt_id=rid, correlate=ctx.id_from(event))
            if self.metrics:
                self.metrics.record_llm_response(rid)
                self._log_metrics(ctx)

    # ------------------------------------------------------------------
    # Helpers

    def _open_wake_window(self) -> None:
        self.wake_session_active = True
        self.wake_active_until = time.monotonic() + self.settings.wake_window_sec

    def _close_wake_window(self) -> None:
        self.wake_session_active = False
        self.wake_active_until = 0.0

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
            stt_ts=stt_ts,
        )
        await ctx.publish(EVENT_TYPE_SAY, say, correlate=correlate, qos=1)
        if self.metrics:
            self.metrics.record_tts_message()
            self._log_metrics(ctx)

    @staticmethod
    def _normalize_command(text: str) -> str:
        cleaned = re.sub(r"[^a-z0-9\s]", "", text.lower())
        return re.sub(r"\s+", " ", cleaned).strip()

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
