from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Final

import numpy as np

_LOG = logging.getLogger("wake-activation.audio")

_SAMPLE_WIDTH_BYTES: Final[int] = 2  # int16 PCM
_INT16_SCALE: Final[float] = 1.0 / 32768.0


class AudioFanoutClient:
    """Consume PCM frames from the STT audio fan-out Unix socket."""

    def __init__(
        self,
        socket_path: Path,
        *,
        sample_rate: int = 16_000,
        samples_per_chunk: int = 1_600,
        reconnect_initial_delay: float = 0.5,
        reconnect_max_delay: float = 5.0,
    ) -> None:
        self._socket_path = socket_path
        self._sample_rate = sample_rate
        self._samples_per_chunk = samples_per_chunk
        self._chunk_bytes = samples_per_chunk * _SAMPLE_WIDTH_BYTES
        self._reconnect_initial_delay = reconnect_initial_delay
        self._reconnect_max_delay = reconnect_max_delay
        self._closing = asyncio.Event()

    async def close(self) -> None:
        self._closing.set()

    async def frames(self) -> AsyncIterator[np.ndarray]:
        """Yield normalized float32 frames from the fan-out socket.

        Frames are returned as NumPy arrays with shape (samples_per_chunk,).
        Values are scaled to the range [-1.0, 1.0).
        """

        backoff = self._reconnect_initial_delay
        while not self._closing.is_set():
            try:
                reader, writer = await asyncio.open_unix_connection(str(self._socket_path))
            except FileNotFoundError:
                _LOG.warning("Audio fan-out socket %s not found; retrying", self._socket_path)
            except OSError as exc:
                _LOG.warning("Audio fan-out connection error %s; retrying", exc)
            else:
                _LOG.info("Connected to audio fan-out at %s", self._socket_path)
                backoff = self._reconnect_initial_delay
                try:
                    async for frame in self._stream_frames(reader):
                        yield frame
                finally:
                    writer.close()
                    with contextlib.suppress(Exception):
                        await writer.wait_closed()
                    _LOG.info("Audio fan-out connection closed")
            if self._closing.is_set():
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, self._reconnect_max_delay)

    async def _stream_frames(self, reader: asyncio.StreamReader) -> AsyncIterator[np.ndarray]:
        while not self._closing.is_set():
            try:
                data = await reader.readexactly(self._chunk_bytes)
            except asyncio.IncompleteReadError:
                if self._closing.is_set():
                    return
                _LOG.warning("Audio fan-out stream ended prematurely; reconnecting")
                return
            except asyncio.CancelledError:
                raise
            frame = np.frombuffer(data, dtype=np.int16).astype(np.float32) * _INT16_SCALE
            yield frame

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def samples_per_chunk(self) -> int:
        return self._samples_per_chunk
