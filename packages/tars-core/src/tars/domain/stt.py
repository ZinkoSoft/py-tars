from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol

from tars.contracts.v1.stt import FinalTranscript, PartialTranscript


class VadProcessor(Protocol):
    """Protocol describing the VAD interface required by the STT service."""

    is_speech: bool

    def process_chunk(self, chunk: bytes) -> Optional[bytes]: ...

    def get_active_buffer(self) -> bytes: ...


class Transcriber(Protocol):
    """Protocol describing a synchronous transcription engine."""

    def transcribe(self, audio: bytes, sample_rate: int) -> tuple[str, Optional[float], dict[str, Any]]: ...


class AsyncTranscriber(Protocol):
    """Protocol describing an async transcription engine (preferred for event loop contexts)."""

    async def transcribe_async(self, audio: bytes, sample_rate: int) -> tuple[str, Optional[float], dict[str, Any]]: ...


class SuppressionState(Protocol):
    cooldown_until: float


class SuppressionEngine(Protocol):
    """Protocol describing suppression heuristics."""

    state: SuppressionState

    def evaluate(
        self,
        text: str,
        confidence: Optional[float],
        metrics: dict[str, Any],
        utterance: bytes,
        sample_rate: int,
        frame_size: int,
        in_response_window: bool = False,
    ) -> tuple[bool, dict[str, Any]]: ...

    def register_publication(self, norm_text: str) -> None: ...


Preprocessor = Callable[[bytes, int], bytes]


@dataclass(slots=True)
class PartialSettings:
    enabled: bool
    min_duration_ms: int
    min_chars: int
    min_new_chars: int
    alpha_ratio_min: float


@dataclass(slots=True)
class STTServiceConfig:
    post_publish_cooldown_ms: int
    preprocess_min_ms: int
    partials: PartialSettings


@dataclass(slots=True)
class STTProcessResult:
    final: Optional[FinalTranscript] = None
    candidate_text: str = ""
    confidence: Optional[float] = None
    rejection_reasons: tuple[str, ...] = ()
    error: Optional[str] = None


class STTService:
    """Orchestrate VAD, transcription, and suppression into typed outputs."""

    def __init__(
        self,
        *,
        vad: VadProcessor,
        transcriber: Transcriber | AsyncTranscriber,
        suppression: SuppressionEngine,
        sample_rate: int,
        frame_size: int,
        config: STTServiceConfig,
        preprocess: Optional[Preprocessor] = None,
    ) -> None:
        self._vad = vad
        self._transcriber = transcriber
        self._suppression = suppression
        self._sample_rate = sample_rate
        self._frame_size = frame_size
        self._config = config
        self._preprocess = preprocess
        self._partials = config.partials
        self._last_partial_text: str = ""
        # Check if transcriber supports async (preferred)
        self._has_async_transcribe = hasattr(transcriber, "transcribe_async")

    def in_cooldown(self, now: Optional[float] = None) -> bool:
        now = now if now is not None else time.time()
        cooldown_until = float(getattr(self._suppression.state, "cooldown_until", 0.0) or 0.0)
        return cooldown_until > 0.0 and now < cooldown_until

    @property
    def partials_enabled(self) -> bool:
        return self._partials.enabled

    def reset_partials(self) -> None:
        self._last_partial_text = ""

    async def process_chunk(self, chunk: bytes, *, now: Optional[float] = None, in_response_window: bool = False) -> STTProcessResult:
        result = STTProcessResult()
        current_time = now if now is not None else time.time()
        if self.in_cooldown(current_time):
            return result

        try:
            utterance = await asyncio.to_thread(self._vad.process_chunk, chunk)
        except Exception as exc:  # pragma: no cover - defensive
            result.error = f"VAD failure: {exc}"
            return result

        if not utterance:
            return result

        processed = utterance
        if self._preprocess is not None:
            duration_ms = (len(utterance) / 2) / self._sample_rate * 1000.0
            if duration_ms >= self._config.preprocess_min_ms:
                try:
                    processed = await asyncio.to_thread(self._preprocess, utterance, self._sample_rate)
                except Exception:  # pragma: no cover - preprocess errors fall back to raw audio
                    processed = utterance

        try:
            if self._has_async_transcribe:
                # Use async transcriber (preferred - already uses to_thread internally)
                text, confidence, metrics = await self._transcriber.transcribe_async(processed, self._sample_rate)  # type: ignore[attr-defined]
            else:
                # Fallback to sync transcriber wrapped in to_thread
                text, confidence, metrics = await asyncio.to_thread(
                    self._transcriber.transcribe,
                    processed,
                    self._sample_rate,
                )
        except Exception as exc:
            result.error = f"Transcription error: {exc}"
            return result

        candidate = text.strip()
        if not candidate:
            return result

        result.candidate_text = candidate
        result.confidence = confidence

        accepted, info = self._suppression.evaluate(
            candidate,
            confidence,
            metrics,
            processed,
            self._sample_rate,
            self._frame_size,
            in_response_window=in_response_window,
        )
        if not accepted:
            reasons = info.get("reasons") if isinstance(info, dict) else None
            if isinstance(reasons, (list, tuple)):
                result.rejection_reasons = tuple(str(r) for r in reasons if r)
            return result

        self._suppression.register_publication(candidate.lower())
        cooldown_sec = max(0.0, self._config.post_publish_cooldown_ms / 1000.0)
        self._suppression.state.cooldown_until = current_time + cooldown_sec
        self.reset_partials()

        result.final = FinalTranscript(text=candidate, confidence=confidence)
        return result

    async def maybe_partial(self) -> Optional[PartialTranscript]:
        if not self._partials.enabled:
            return None
        if not getattr(self._vad, "is_speech", False):
            return None

        buffer_bytes = self._vad.get_active_buffer()
        if not buffer_bytes:
            return None

        duration_ms = (len(buffer_bytes) / 2) / self._sample_rate * 1000.0
        if duration_ms < self._partials.min_duration_ms:
            return None

        try:
            if self._has_async_transcribe:
                # Use async transcriber (preferred - already uses to_thread internally)
                text, confidence, _ = await self._transcriber.transcribe_async(buffer_bytes, self._sample_rate)  # type: ignore[attr-defined]
            else:
                # Fallback to sync transcriber wrapped in to_thread
                text, confidence, _ = await asyncio.to_thread(
                    self._transcriber.transcribe,
                    buffer_bytes,
                    self._sample_rate,
                )
        except Exception:  # pragma: no cover - partial failures are non-fatal
            return None

        candidate = text.strip()
        if not candidate or len(candidate) < self._partials.min_chars:
            return None

        alpha = sum(c.isalpha() for c in candidate)
        alpha_ratio = alpha / max(1, len(candidate))
        if alpha_ratio < self._partials.alpha_ratio_min:
            return None

        if self._last_partial_text:
            delta = len(candidate) - len(self._last_partial_text)
            if delta < self._partials.min_new_chars and not candidate.endswith('.'):
                return None
            if candidate == self._last_partial_text:
                return None

        self._last_partial_text = candidate
        return PartialTranscript(text=candidate, confidence=confidence)