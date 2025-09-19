import time
import re
import logging
from collections import deque
from typing import List, Tuple, Dict, Optional
import numpy as np

from config import (
    NOISE_MIN_DURATION_MS, NOISE_MIN_RMS, NOISE_MIN_LENGTH, NOISE_MIN_ALPHA_RATIO,
    NOISE_MAX_PUNCT_RATIO, COUGH_SUSPICIOUS_PHRASES, COUGH_MIN_DURATION_MS, COUGH_ACTIVE_MIN_RATIO,
    COUGH_MIN_SYLLABLES, NO_SPEECH_MAX, AVG_LOGPROB_MIN, DICT_MATCH_MIN_RATIO,
    ECHO_SUPPRESS_MATCH, TTS_BASE_MUTE_MS, TTS_PER_CHAR_MS, TTS_MAX_MUTE_MS, POST_PUBLISH_COOLDOWN_MS,
    REPEAT_COOLDOWN_SEC, COMMON_WORDS
)

logger = logging.getLogger("stt-worker.suppression")

class SuppressionState:
    def __init__(self):
        self.recent_phrases = deque(maxlen=5)
        self.last_published_text: str = ""
        self.last_published_at: float = 0.0
        self.cooldown_until: float = 0.0
        self.last_tts_text: str = ""

class SuppressionEngine:
    def __init__(self, state: SuppressionState):
        self.state = state
        self.repeat_cooldown_sec = REPEAT_COOLDOWN_SEC

    def evaluate(self, text: str, confidence: Optional[float], metrics: Dict[str, float], utterance: bytes,
                 sample_rate: int, frame_size: int) -> Tuple[bool, Dict[str, any]]:
        raw_text = text.strip()
        norm_text = raw_text.lower()
        info = {"reasons": []}
        # Basic metrics
        duration_ms = (len(utterance) / 2) / sample_rate * 1000.0
        utt_np = np.frombuffer(utterance, dtype=np.int16)
        utt_rms = float(np.sqrt(np.mean(utt_np.astype(np.float32) ** 2))) if utt_np.size else 0.0
        alpha = sum(c.isalpha() for c in raw_text)
        punct = sum(c in '.,!?;:' for c in raw_text)
        total = max(1, len(raw_text))
        alpha_ratio = alpha / total
        punct_ratio = punct / total

        # Frame-level activity
        active_frames = 0
        total_frames = max(1, len(utterance) // (frame_size * 2))
        if total_frames > 0:
            for i in range(total_frames):
                seg = utt_np[i * frame_size:(i + 1) * frame_size]
                if seg.size:
                    seg_rms = float(np.sqrt(np.mean(seg.astype(np.float32) ** 2)))
                    if seg_rms > (NOISE_MIN_RMS * 0.6):
                        active_frames += 1
        active_ratio = active_frames / float(total_frames)

        # Syllable heuristic
        lowered = norm_text
        syllables = 0
        prev_vowel = False
        for ch in lowered:
            is_vowel = ch in 'aeiou'
            if is_vowel and not prev_vowel:
                syllables += 1
            prev_vowel = is_vowel

        # Accumulate reasons
        if duration_ms < NOISE_MIN_DURATION_MS:
            info["reasons"].append(f"dur {duration_ms:.0f}ms < {NOISE_MIN_DURATION_MS}")
        if utt_rms < NOISE_MIN_RMS:
            info["reasons"].append(f"rms {utt_rms:.0f} < {NOISE_MIN_RMS}")
        if len(raw_text) < NOISE_MIN_LENGTH:
            info["reasons"].append(f"len {len(raw_text)} < {NOISE_MIN_LENGTH}")
        if alpha_ratio < NOISE_MIN_ALPHA_RATIO:
            info["reasons"].append(f"alpha_ratio {alpha_ratio:.2f} < {NOISE_MIN_ALPHA_RATIO}")
        if punct_ratio > NOISE_MAX_PUNCT_RATIO:
            info["reasons"].append(f"punct_ratio {punct_ratio:.2f} > {NOISE_MAX_PUNCT_RATIO}")

        suspicious_set = {p.strip().lower() for p in COUGH_SUSPICIOUS_PHRASES if p.strip()}
        stripped_norm = norm_text.strip('.!? ')
        if stripped_norm in suspicious_set:
            if (duration_ms < COUGH_MIN_DURATION_MS or active_ratio < COUGH_ACTIVE_MIN_RATIO or syllables < COUGH_MIN_SYLLABLES):
                info["reasons"].append(
                    f"cough_guard phrase='{stripped_norm}' dur={duration_ms:.0f}ms active={active_ratio:.2f} syll={syllables}"
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
            info["reasons"].append(f"dict_ratio {dict_ratio:.2f} < {DICT_MATCH_MIN_RATIO}")
        if avg_no_speech is not None and avg_no_speech > NO_SPEECH_MAX:
            info["reasons"].append(f"no_speech {avg_no_speech:.2f} > {NO_SPEECH_MAX}")
        if avg_logprob is not None and avg_logprob < AVG_LOGPROB_MIN:
            info["reasons"].append(f"avg_logprob {avg_logprob:.2f} < {AVG_LOGPROB_MIN}")

        high_conf = confidence is not None and confidence > 0.95 and (avg_no_speech is None or avg_no_speech < NO_SPEECH_MAX)
        if info["reasons"] and not high_conf:
            return False, info

        # Additional polite phrase gating
        if stripped_norm in suspicious_set:
            if (duration_ms < COUGH_MIN_DURATION_MS or active_ratio < COUGH_ACTIVE_MIN_RATIO or syllables < COUGH_MIN_SYLLABLES):
                info["reasons"].append(
                    f"suspicious_polite '{norm_text}' dur={duration_ms:.0f}ms"
                )
                return False, info

        # Lexical gating
        tokens_clean = [t for t in re.split(r"\s+", stripped_norm) if t]
        vowel_ratio = (sum(c in 'aeiou' for c in stripped_norm) / max(1, len(stripped_norm))) if stripped_norm else 0
        if stripped_norm not in suspicious_set:
            if (len(tokens_clean) < 2 and len(stripped_norm) < 5) or vowel_ratio < 0.25:
                info["reasons"].append(
                    f"lexical_low tokens={len(tokens_clean)} len={len(stripped_norm)} vowel_ratio={vowel_ratio:.2f}"
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
        info.update({
            "norm_text": norm_text,
            "duration_ms": duration_ms,
            "utt_rms": utt_rms,
            "active_ratio": active_ratio,
            "syllables": syllables
        })
        return True, info

    def register_publication(self, norm_text: str):
        self.state.last_published_text = norm_text
        self.state.last_published_at = time.time()
        self.state.recent_phrases.append((norm_text, time.time()))
