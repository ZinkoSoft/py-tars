from __future__ import annotations

"""Compatibility shim delegating to the packaged :mod:`stt_worker.app` module."""

from stt_worker.app import STTWorker, main

__all__ = ["STTWorker", "main"]


if __name__ == "__main__":
    main()
