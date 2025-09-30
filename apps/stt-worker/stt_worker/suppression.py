from __future__ import annotations

"""Speech suppression heuristics.

This module provides lightweight, rule-based suppression to filter out
false-positive or low-quality transcriptions before publishing them.

Behavior is unchanged; improvements include:
- Dataclass for SuppressionState (slots for memory and attribute safety)
- Type hints and docstrings for public surfaces
- Minor readability tweaks (no logic changes)
"""

import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional, Tuple

import numpy as np

from .config import (
    AVG_LOGPROB_MIN,
    COUGH_ACTIVE_MIN_RATIO,
    COUGH_MIN_DURATION_MS,
    COUGH_MIN_SYLLABLES,
    COUGH_SUSPICIOUS_PHRASES,
    COMMON_WORDS,
    DICT_MATCH_MIN_RATIO,
    ECHO_FUZZ_MIN_RATIO,
    ECHO_SUPPRESS_MATCH,
    NOISE_FLOOR_ALPHA,
    NOISE_FLOOR_INIT,
    NOISE_GATE_OFFSET,
    NOISE_MAX_PUNCT_RATIO,
    NOISE_MIN_ALPHA_RATIO,
    NOISE_MIN_DURATION_MS,
    NOISE_MIN_LENGTH,
    NOISE_MIN_RMS,
    NO_SPEECH_MAX,
    POST_PUBLISH_COOLDOWN_MS,
    REPEAT_COOLDOWN_SEC,
    SUPPRESS_USE_RAPIDFUZZ,
    SUPPRESS_USE_SYLLAPY,
    TTS_BASE_MUTE_MS,
    TTS_MAX_MUTE_MS,
    TTS_PER_CHAR_MS,
)

logger = logging.getLogger("stt-worker.suppression")

__all__ = ["SuppressionState", "SuppressionEngine"]


@dataclass(slots=True)
class SuppressionState:
    """State tracked across suppression decisions.

    Attributes:
        recent_phrases: Rolling window of recent normalized phrases and timestamps.
        last_published_text: Most recent published normalized text.
        last_published_at: Timestamp of last publish.
        cooldown_until: Do-not-publish-before timestamp.
        last_tts_text: Last TTS text, used for echo suppression.
    """

    recent_phrases: Deque[Tuple[str, float]] = field(default_factory=lambda: deque(maxlen=5))
    last_published_text: str = ""
    last_published_at: float = 0.0
    cooldown_until: float = 0.0
    last_tts_text: str = ""


class SuppressionEngine:
    """Evaluate whether an utterance should be suppressed.

    This class contains heuristic checks based on audio and text metrics. It does not
    perform I/O and is deterministic given its inputs and state.
    """

    def __init__(self, state: SuppressionState):
        self.state = state
        self.repeat_cooldown_sec = REPEAT_COOLDOWN_SEC

    def evaluate(
        self,
        text: str,
        confidence: Optional[float],
        metrics: Dict[str, float],
        utterance: bytes,
        sample_rate: int,
        frame_size: int,
        in_response_window: bool = False,
    ) -> Tuple[bool, Dict[str, object]]:
        """Return (accepted, info) for a candidate transcription.

        Args:
            text: Candidate transcript string.
            confidence: Optional model confidence metric.
            metrics: Additional per-utterance metrics from the transcriber.
            utterance: Raw PCM16LE bytes for the utterance.
            sample_rate: PCM sample rate.
            frame_size: Frame size (samples) used by VAD.

        Returns:
            Tuple where first element indicates acceptance, and second is a dict
            with diagnostic details and/or rejection reasons.
        """
        raw_text = text.strip()
        norm_text = raw_text.lower()
        info: Dict[str, object] = {"reasons": []}
        # Basic metrics
        duration_ms = (len(utterance) / 2) / sample_rate * 1000.0
        utt_np = np.frombuffer(utterance, dtype=np.int16)
        utt_rms = float(np.sqrt(np.mean(utt_np.astype(np.float32) ** 2))) if utt_np.size else 0.0
        alpha = sum(c.isalpha() for c in raw_text)
        punct = sum(c in ".,!?;:" for c in raw_text)
        total = max(1, len(raw_text))
        alpha_ratio = alpha / total
        punct_ratio = punct / total

        # Frame-level activity (require minimum percentage of frames above threshold)
        active_frames = 0
        total_frames = max(1, len(utterance) // (frame_size * 2))
        speech_threshold = NOISE_MIN_RMS * 0.8  # Slightly below main threshold for frame validation
        if total_frames > 0:
            for i in range(total_frames):
                seg = utt_np[i * frame_size : (i + 1) * frame_size]
                if seg.size:
                    seg_rms = float(np.sqrt(np.mean(seg.astype(np.float32) ** 2)))
                    if seg_rms > speech_threshold:
                        active_frames += 1
        active_ratio = active_frames / float(total_frames)
        min_active_ratio = 0.3  # Require at least 30% of frames to have speech-like energy

        # Syllable heuristic (optionally use syllapy if enabled)
        lowered = norm_text
        syllables = 0
        if SUPPRESS_USE_SYLLAPY:
            try:
                import syllapy  # type: ignore

                # Count over tokens to avoid punctuation effects
                tokens_for_syll = [t for t in re.split(r"\s+", lowered) if t]
                syllables = sum(syllapy.count(t) for t in tokens_for_syll)
            except Exception:
                # Fallback to simple vowel-run heuristic
                prev_vowel = False
                for ch in lowered:
                    is_vowel = ch in "aeiou"
                    if is_vowel and not prev_vowel:
                        syllables += 1
                    prev_vowel = is_vowel
        else:
            prev_vowel = False
            for ch in lowered:
                is_vowel = ch in "aeiou"
                if is_vowel and not prev_vowel:
                    syllables += 1
                prev_vowel = is_vowel

        # Accumulate reasons
        if duration_ms < NOISE_MIN_DURATION_MS:
            info["reasons"].append(f"dur {duration_ms:.0f}ms < {NOISE_MIN_DURATION_MS}")
        if utt_rms < NOISE_MIN_RMS:
            info["reasons"].append(f"rms {utt_rms:.0f} < {NOISE_MIN_RMS}")
        if active_ratio < min_active_ratio:
            info["reasons"].append(f"active_ratio {active_ratio:.2f} < {min_active_ratio}")
        if len(raw_text) < NOISE_MIN_LENGTH:
            info["reasons"].append(f"len {len(raw_text)} < {NOISE_MIN_LENGTH}")
        if alpha_ratio < NOISE_MIN_ALPHA_RATIO:
            info["reasons"].append(f"alpha_ratio {alpha_ratio:.2f} < {NOISE_MIN_ALPHA_RATIO}")
        if punct_ratio > NOISE_MAX_PUNCT_RATIO:
            info["reasons"].append(f"punct_ratio {punct_ratio:.2f} > {NOISE_MAX_PUNCT_RATIO}")

        suspicious_set = {p.strip().lower() for p in COUGH_SUSPICIOUS_PHRASES if p.strip()}
        stripped_norm = norm_text.strip(".!? ")
        if stripped_norm in suspicious_set:
            if (
                duration_ms < COUGH_MIN_DURATION_MS
                or active_ratio < COUGH_ACTIVE_MIN_RATIO
                or syllables < COUGH_MIN_SYLLABLES
            ):
                info["reasons"].append(
                    "cough_guard phrase='%s' dur=%.0fms active=%.2f syll=%s"
                    % (stripped_norm, duration_ms, active_ratio, syllables)
                )

        avg_no_speech = metrics.get("avg_no_speech_prob")
        avg_logprob = metrics.get("avg_logprob")
        tokens = [t for t in re.split(r"\s+", norm_text) if t]
        word_tokens = [re.sub(r"[^a-z']", "", w) for w in tokens]
        word_tokens = [w for w in word_tokens if w]
        if word_tokens:
            dict_matches = sum(1 for w in word_tokens if w in COMMON_WORDS)
            dict_ratio = dict_matches / len(word_tokens)
        else:
            dict_ratio = 0.0
        if dict_ratio < DICT_MATCH_MIN_RATIO and len(raw_text) >= NOISE_MIN_LENGTH:
            # During response windows, be more lenient with dictionary matching
            min_ratio = 0.05 if in_response_window else DICT_MATCH_MIN_RATIO  # 5% vs 12% during response window
            if dict_ratio < min_ratio:
                matched_words = [w for w in word_tokens if w in COMMON_WORDS]
                info["dict_ratio"] = round(dict_ratio, 3)
                info["dict_tokens"] = len(word_tokens)
                info["dict_matches"] = len(matched_words)
                if matched_words:
                    info["dict_matched_words"] = matched_words[:8]
                logger.debug(
                    "Suppression: dict_ratio gate ratio=%.2f<th=%.2f tokens=%d matches=%d matched=%s text='%s' response_window=%s",
                    dict_ratio,
                    min_ratio,
                    len(word_tokens),
                    len(matched_words),
                    matched_words[:8],
                    raw_text,
                    in_response_window,
                )
                info["reasons"].append(f"dict_ratio {dict_ratio:.2f} < {min_ratio}")
        elif in_response_window:
            # During response windows, log successful dictionary matches for debugging
            matched_words = [w for w in word_tokens if w in COMMON_WORDS]
            logger.debug(
                "Response window: dict_ratio=%.2f >= %.2f tokens=%d matches=%d text='%s'",
                dict_ratio,
                0.05,
                len(word_tokens),
                len(matched_words),
                raw_text,
            )
        if avg_no_speech is not None and avg_no_speech > NO_SPEECH_MAX:
            logger.debug(
                "Suppression: no_speech gate prob=%.2f>th=%.2f text='%s'",
                avg_no_speech,
                NO_SPEECH_MAX,
                raw_text,
            )
            info["reasons"].append(f"no_speech {avg_no_speech:.2f} > {NO_SPEECH_MAX}")
        if avg_logprob is not None and avg_logprob < AVG_LOGPROB_MIN:
            logger.debug(
                "Suppression: avg_logprob gate avg=%.2f<th=%.2f text='%s'",
                avg_logprob,
                AVG_LOGPROB_MIN,
                raw_text,
            )
            info["reasons"].append(f"avg_logprob {avg_logprob:.2f} < {AVG_LOGPROB_MIN}")

        high_conf = (
            confidence is not None
            and confidence > 0.95
            and (avg_no_speech is None or avg_no_speech < NO_SPEECH_MAX)
        )
        if info["reasons"] and not high_conf:
            return False, info

        # Additional polite phrase gating
        if stripped_norm in suspicious_set:
            if (
                duration_ms < COUGH_MIN_DURATION_MS
                or active_ratio < COUGH_ACTIVE_MIN_RATIO
                or syllables < COUGH_MIN_SYLLABLES
            ):
                info["reasons"].append(f"suspicious_polite '{norm_text}' dur={duration_ms:.0f}ms")
                return False, info

        # Lexical gating
        tokens_clean = [t for t in re.split(r"\s+", stripped_norm) if t]
        vowel_ratio = (
            (sum(c in "aeiou" for c in stripped_norm) / max(1, len(stripped_norm)))
            if stripped_norm
            else 0
        )
        if stripped_norm not in suspicious_set:
            if (len(tokens_clean) < 2 and len(stripped_norm) < 5) or vowel_ratio < 0.25:
                info["reasons"].append(
                    "lexical_low tokens=%d len=%d vowel_ratio=%.2f"
                    % (len(tokens_clean), len(stripped_norm), vowel_ratio)
                )
                return False, info

        # Loop breaker repeat check
        if self.state.last_published_text and norm_text == self.state.last_published_text.lower():
            if time.time() - self.state.last_published_at < self.repeat_cooldown_sec:
                info["reasons"].append("repeat_last_published")
                return False, info

        # Echo suppression
        if ECHO_SUPPRESS_MATCH and self.state.last_tts_text:
            last_norm = self.state.last_tts_text.lower()
            if norm_text == last_norm:
                info["reasons"].append("exact_echo")
                return False, info
            # Optional rapidfuzz fuzzy match for echo suppression
            if SUPPRESS_USE_RAPIDFUZZ:
                try:
                    from rapidfuzz.fuzz import ratio as fuzz_ratio  # type: ignore

                    sim = float(fuzz_ratio(norm_text, last_norm)) / 100.0
                    if sim >= ECHO_FUZZ_MIN_RATIO:
                        info["reasons"].append(f"fuzzy_echo {sim:.2f}")
                        return False, info
                except Exception:
                    pass
            else:
                min_len = min(len(norm_text), len(last_norm))
                if min_len > 4:
                    matches = sum(1 for a, b in zip(norm_text, last_norm) if a == b)
                    ratio = matches / float(min_len)
                    if ratio >= 0.85:
                        info["reasons"].append(f"fuzzy_echo {ratio:.2f}")
                        return False, info

        # Rolling repeated phrases list
        now = time.time()
        for prev_text, ts in list(self.state.recent_phrases):
            if norm_text == prev_text and (now - ts) < self.repeat_cooldown_sec:
                info["reasons"].append("recent_repeat")
                return False, info

        # Accept
        info.update(
            {
                "norm_text": norm_text,
                "duration_ms": duration_ms,
                "utt_rms": utt_rms,
                "active_ratio": active_ratio,
                "syllables": syllables,
            }
        )
        return True, info

    def register_publication(self, norm_text: str) -> None:
        self.state.last_published_text = norm_text
        self.state.last_published_at = time.time()
        self.state.recent_phrases.append((norm_text, time.time()))
