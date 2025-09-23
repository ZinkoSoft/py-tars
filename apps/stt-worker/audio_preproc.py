from __future__ import annotations

"""Lightweight FFmpeg-based audio preprocessing for STT utterances.

Takes PCM16 mono bytes and returns processed PCM16 mono bytes at the same
sample rate. Uses FFmpeg filters to optionally trim leading/trailing silence,
apply gentle noise reduction, and normalize dynamics.

This module is pure and side-effect free aside from spawning FFmpeg.
On any error or timeout, the original input is returned.
"""

import logging
import shutil
import subprocess
from typing import Optional

from config import PREPROCESS_FILTERS, PREPROCESS_TIMEOUT_S

logger = logging.getLogger("stt-worker.preproc")


def _ffmpeg_path() -> Optional[str]:
    p = shutil.which("ffmpeg")
    if not p:
        logger.warning("ffmpeg not found in PATH; skipping preprocessing")
    return p


def preprocess_pcm(pcm: bytes, sample_rate: int) -> bytes:
    """Run FFmpeg filters on PCM16 mono audio.

    Args:
        pcm: Raw PCM16LE mono audio bytes.
        sample_rate: Sample rate of the PCM.

    Returns:
        Processed PCM16LE mono bytes. If FFmpeg is unavailable, filters are
        invalid, or a timeout/error occurs, returns the original input.
    """
    if not pcm:
        return pcm

    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        return pcm

    # Build ffmpeg command: s16le -> filters -> s16le (keep same rate/channels)
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "s16le",
        "-ar",
        str(sample_rate),
        "-ac",
        "1",
        "-i",
        "pipe:0",
        "-af",
        PREPROCESS_FILTERS,
        "-f",
        "s16le",
        "-ar",
        str(sample_rate),
        "-ac",
        "1",
        "pipe:1",
    ]

    try:
        proc = subprocess.run(
            cmd,
            input=pcm,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=PREPROCESS_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        logger.warning("ffmpeg preprocessing timed out after %.1fs", PREPROCESS_TIMEOUT_S)
        return pcm
    except Exception as e:
        logger.warning("ffmpeg preprocessing failed to start: %s", e)
        return pcm

    if proc.returncode != 0:
        # Log a short tail of stderr for diagnosis without being too noisy
        tail = (proc.stderr or b"").decode(errors="ignore").strip().splitlines()[-3:]
        logger.warning("ffmpeg returned %s; stderr tail: %s", proc.returncode, tail)
        return pcm

    out = proc.stdout or b""
    if not out:
        # Defensive: if filters removed everything, keep original
        logger.debug("ffmpeg preprocessing produced empty output; using original audio")
        return pcm
    return out
