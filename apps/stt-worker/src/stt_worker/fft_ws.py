from __future__ import annotations

"""Lightweight WebSocket hub for streaming FFT telemetry."""

import asyncio
import logging
from typing import TYPE_CHECKING, Set

import orjson
from websockets.server import WebSocketServerProtocol, serve

if TYPE_CHECKING:  # pragma: no cover - typing only
    from websockets.server import Serve

logger = logging.getLogger("stt-worker.fft-ws")


class FFTWebSocketServer:
    """Manage a small WebSocket fan-out for FFT telemetry frames."""

    def __init__(self, host: str, port: int, path: str, *, ping_interval: float = 20.0) -> None:
        self._host = host
        self._port = port
        self._path = path
        self._ping_interval = ping_interval
        self._server: Serve | None = None
        self._clients: Set[WebSocketServerProtocol] = set()
        self._lock = asyncio.Lock()
        self._cache: bytes | None = None

    @property
    def port(self) -> int:
        if self._server and self._server.sockets:
            sock = self._server.sockets[0]
            return sock.getsockname()[1]
        return self._port

    async def start(self) -> None:
        if self._server is not None:
            return

        async def handler(websocket: WebSocketServerProtocol, path: str) -> None:
            if path != self._path:
                await websocket.close(code=1008, reason="Invalid path")
                return
            await self._register(websocket)
            try:
                await websocket.wait_closed()
            finally:
                await self._unregister(websocket)

        self._server = await serve(
            handler, self._host, self._port, ping_interval=self._ping_interval
        )
        actual_port = self.port
        logger.info("FFT websocket listening on ws://%s:%s%s", self._host, actual_port, self._path)

    async def stop(self) -> None:
        server = self._server
        self._server = None
        if server:
            server.close()
        async with self._lock:
            clients = list(self._clients)
            self._clients.clear()
        await asyncio.gather(*(self._safe_close(ws) for ws in clients), return_exceptions=True)
        if server:
            await server.wait_closed()
        self._cache = None

    async def _register(self, websocket: WebSocketServerProtocol) -> None:
        logger.info("FFT websocket client connected: %s", websocket.remote_address)
        async with self._lock:
            self._clients.add(websocket)
            cache = self._cache
        if cache:
            try:
                await websocket.send(cache)
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("Failed to send cached FFT frame: %s", exc)

    async def _unregister(self, websocket: WebSocketServerProtocol) -> None:
        logger.info("FFT websocket client disconnected: %s", websocket.remote_address)
        async with self._lock:
            self._clients.discard(websocket)

    async def broadcast(self, payload: dict[str, object]) -> None:
        message = orjson.dumps(payload)
        async with self._lock:
            self._cache = message
            clients = list(self._clients)
        if not clients:
            return
        await asyncio.gather(*(self._send(ws, message) for ws in clients), return_exceptions=True)

    async def _send(self, websocket: WebSocketServerProtocol, message: bytes) -> None:
        try:
            await websocket.send(message)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("FFT websocket send failed: %s", exc)
            await self._safe_close(websocket)

    async def _safe_close(self, websocket: WebSocketServerProtocol) -> None:
        try:
            await websocket.close()
        except Exception:  # pragma: no cover - best effort
            pass
        async with self._lock:
            self._clients.discard(websocket)
