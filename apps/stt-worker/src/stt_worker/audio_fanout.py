from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

__all__ = ["AudioFanoutPublisher"]

_LOG = logging.getLogger("stt-worker.fanout")


class AudioFanoutPublisher:
    """Broadcast PCM frames over a Unix domain socket to wake-activation."""

    def __init__(
        self,
        socket_path: str | os.PathLike[str],
        *,
        target_sample_rate: int = 16_000,
        max_queue: int = 256,
    ) -> None:
        self._path = Path(socket_path)
        self._target_rate = target_sample_rate
        self._queue: asyncio.Queue[Tuple[bytes, int]] = asyncio.Queue(maxsize=max_queue)
        self._loop = asyncio.get_running_loop()
        self._server: Optional[asyncio.AbstractServer] = None
        self._broadcast_task: Optional[asyncio.Task[None]] = None
        self._clients: set[asyncio.StreamWriter] = set()
        self._closing = False
        self._residual = bytearray()
        self._healthcheck_counter = 0  # Track healthcheck connections

    async def start(self) -> None:
        if self._server is not None:
            return
        if self._path.exists():
            with contextlib.suppress(OSError):
                self._path.unlink()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._server = await asyncio.start_unix_server(self._handle_client, path=str(self._path))
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())
        _LOG.info("Audio fan-out server listening at %s", self._path)

    async def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        if self._broadcast_task is not None:
            self._loop.call_soon_threadsafe(self._signal_shutdown)
            await self._broadcast_task
        for writer in list(self._clients):
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
        self._clients.clear()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        with contextlib.suppress(OSError):
            if self._path.exists():
                self._path.unlink()
        _LOG.info("Audio fan-out server stopped")

    def push(self, chunk: bytes, sample_rate: int) -> None:
        if self._closing or not chunk:
            return
        try:
            self._loop.call_soon_threadsafe(self._enqueue, chunk, sample_rate)
        except RuntimeError:  # pragma: no cover - loop closed
            pass

    def _enqueue(self, chunk: bytes, sample_rate: int) -> None:
        if self._closing:
            return
        if self._queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                self._queue.get_nowait()
        with contextlib.suppress(asyncio.QueueFull):
            self._queue.put_nowait((chunk, sample_rate))

    def _signal_shutdown(self) -> None:
        if self._closing:
            try:
                self._queue.put_nowait((b"", -1))
            except asyncio.QueueFull:
                with contextlib.suppress(asyncio.QueueEmpty):
                    self._queue.get_nowait()
                with contextlib.suppress(asyncio.QueueFull):
                    self._queue.put_nowait((b"", -1))

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = self._describe_peer(writer)
        connect_time = time.time()

        # Only log every 10th connection to reduce healthcheck noise
        self._healthcheck_counter += 1
        if self._healthcheck_counter % 10 == 1:  # Log 1st, 11th, 21st, etc.
            _LOG.info("Audio fan-out client connected: %s", peer)
        else:
            _LOG.debug(
                "Audio fan-out client connected: %s (connection #%d)",
                peer,
                self._healthcheck_counter,
            )

        self._clients.add(writer)
        try:
            # Keep connection open and read data until client disconnects
            await reader.read()
        except Exception:  # pragma: no cover - best effort
            pass
        finally:
            self._clients.discard(writer)
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

            # Log disconnect with duration info, reduced frequency for short connections
            connection_duration = time.time() - connect_time
            if connection_duration < 0.5:  # Less than 500ms = probably healthcheck
                _LOG.debug(
                    "Audio fan-out client disconnected: %s (duration: %.3fs)",
                    peer,
                    connection_duration,
                )
            else:
                _LOG.info(
                    "Audio fan-out client disconnected: %s (duration: %.3fs)",
                    peer,
                    connection_duration,
                )
            connection_duration = time.time() - connect_time
            if connection_duration >= 0.2:  # 200ms+ = probably real connection
                _LOG.debug(
                    "Audio fan-out client disconnected: %s (duration: %.3fs)",
                    peer,
                    connection_duration,
                )

    async def _broadcast_loop(self) -> None:
        while True:
            chunk, sample_rate = await self._queue.get()
            if self._closing and sample_rate == -1:
                break
            data = self._prepare_chunk(chunk, sample_rate)
            if not data:
                continue
            dead: list[asyncio.StreamWriter] = []
            for writer in self._clients:
                try:
                    writer.write(data)
                except Exception:
                    dead.append(writer)
                    continue
            for writer in dead:
                self._clients.discard(writer)
            if not self._clients:
                continue
            await asyncio.gather(
                *[self._drain(writer) for writer in self._clients],
                return_exceptions=True,
            )

    async def _drain(self, writer: asyncio.StreamWriter) -> None:
        with contextlib.suppress(Exception):
            await asyncio.wait_for(writer.drain(), timeout=0.5)

    def _prepare_chunk(self, chunk: bytes, sample_rate: int) -> bytes:
        if sample_rate <= 0:
            return b""
        if sample_rate == self._target_rate:
            return chunk
        if sample_rate % self._target_rate == 0:
            return self._decimate(chunk, sample_rate)
        return self._interp(chunk, sample_rate)

    def _decimate(self, chunk: bytes, sample_rate: int) -> bytes:
        factor = sample_rate // self._target_rate
        if factor <= 1:
            return chunk
        self._residual.extend(chunk)
        buf = np.frombuffer(self._residual, dtype=np.int16)
        usable = (buf.size // factor) * factor
        if usable == 0:
            return b""
        trimmed = buf[:usable].astype(np.int32).reshape(-1, factor)
        averaged = np.clip(np.mean(trimmed, axis=1), -32768, 32767).astype(np.int16)
        self._residual = bytearray(buf[usable:].tobytes())
        return averaged.tobytes()

    def _interp(self, chunk: bytes, sample_rate: int) -> bytes:
        self._residual.extend(chunk)
        data = np.frombuffer(self._residual, dtype=np.int16).astype(np.float32)
        if data.size < 2:
            return b""
        ratio = self._target_rate / sample_rate
        if ratio <= 0:
            return b""
        length = int(data.size * ratio)
        if length < 2:
            return b""
        resampled = np.interp(
            np.linspace(0, data.size - 1, num=length, endpoint=True),
            np.arange(data.size),
            data,
        )
        resampled = np.clip(resampled, -32768, 32767).astype(np.int16)
        keep = min(sample_rate // 100, data.size)
        self._residual = bytearray(data[-keep:].astype(np.int16).tobytes())
        return resampled.tobytes()

    @staticmethod
    def _describe_peer(writer: asyncio.StreamWriter) -> str:
        transport = writer.transport
        sock = transport.get_extra_info("socket") if transport else None
        if sock is None:
            return "unknown"
        try:
            return str(sock.getsockname())
        except OSError:
            return "unknown"
