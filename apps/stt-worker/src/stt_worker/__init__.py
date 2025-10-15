from __future__ import annotations

"""Installable package for the TARS STT worker."""

__version__ = "0.1.0"

from .app import STTWorker, main

__all__ = ["STTWorker", "main", "__version__"]
