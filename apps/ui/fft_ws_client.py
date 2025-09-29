"""Synchronous websocket client streaming FFT frames into the UI queue."""
from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any

import orjson
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

logger = logging.getLogger("tars.ui.fft_ws")


class FFTWebsocketClient:
    """Background thread that consumes FFT frames from a websocket endpoint."""

    def __init__(
        self,
        url: str,
        target_topic: str,
        event_queue: queue.Queue,
        *,
        retry_seconds: float = 5.0,
    ) -> None:
        self.url = url
        self.target_topic = target_topic
        self.q = event_queue
        self.retry_seconds = max(1.0, float(retry_seconds))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="fft-ws", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                logger.info("Connecting to FFT websocket %s", self.url)
                with connect(
                    self.url,
                    ping_interval=20.0,
                    ping_timeout=20.0,
                    close_timeout=1.0,
                ) as ws:
                    logger.info("FFT websocket connected")
                    while not self._stop.is_set():
                        try:
                            message = ws.recv()
                        except ConnectionClosed as exc:
                            logger.warning("FFT websocket closed: %s", exc)
                            break
                        if message is None:
                            break
                        try:
                            data: Any = orjson.loads(message)
                        except Exception:
                            continue
                        try:
                            self.q.put_nowait((self.target_topic, data))
                        except queue.Full:
                            logger.debug("UI event queue full; dropping websocket frame")
            except Exception as exc:
                if self._stop.is_set():
                    break
                logger.warning(
                    "FFT websocket connection error: %s; retrying in %.1fs",
                    exc,
                    self.retry_seconds,
                )
                time.sleep(self.retry_seconds)
            else:
                if not self._stop.is_set():
                    time.sleep(self.retry_seconds)

