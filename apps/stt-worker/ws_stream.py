from __future__ import annotations

"""WebSocket streaming client for partial and final STT results."""

import asyncio
import logging
from typing import Callable, Optional, Awaitable

import orjson
import websockets

logger = logging.getLogger("stt-worker.ws-stream")


class WebSocketStreamClient:
    """Maintain a streaming WS session to send audio and receive partials.

    Public methods: connect, send_audio, end, close.
    """
    def __init__(
        self,
        ws_url: str,
        sample_rate: int,
        enable_partials: bool,
        on_partial: Optional[Callable[[str, Optional[float], int], Awaitable[None]]] = None,
    ):
        self.ws_url = ws_url
        self.sample_rate = sample_rate
        self.enable_partials = enable_partials
        self.on_partial = on_partial
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._final_future: Optional[asyncio.Future] = None
        self._lock = asyncio.Lock()

    async def connect(self):
        async with self._lock:
            if self._ws and not self._ws.closed:
                return
            logger.info(f"Connecting WS stream: {self.ws_url}")
            self._ws = await websockets.connect(self.ws_url, max_size=None)
            # Send init
            await self._ws.send(orjson.dumps({
                "type": "init",
                "sample_rate": self.sample_rate,
                "lang": "en",
                "enable_partials": bool(self.enable_partials),
            }).decode())
            # Prime reader
            self._reader_task = asyncio.create_task(self._reader_loop())

    async def _reader_loop(self):
        try:
            while self._ws and not self._ws.closed:
                msg = await self._ws.recv()
                if isinstance(msg, (bytes, bytearray)):
                    continue
                try:
                    data = orjson.loads(msg)
                except Exception:
                    continue
                mtype = data.get("type")
                if mtype == "partial" and self.on_partial:
                    text = data.get("text", "") or ""
                    conf = data.get("confidence")
                    t_ms = int(data.get("t_ms") or 0)
                    try:
                        await self.on_partial(text, conf, t_ms)
                    except Exception as e:
                        logger.debug(f"partial callback error: {e}")
                elif mtype == "final":
                    # Fulfill the current future if waiting
                    if self._final_future and not self._final_future.done():
                        self._final_future.set_result((data.get("text", "") or "", data.get("confidence")))
                elif mtype == "health":
                    # ignore
                    pass
        except websockets.ConnectionClosed:
            logger.info("WS reader closed")
        except Exception as e:
            logger.warning(f"WS reader error: {e}")

    async def send_audio(self, pcm_chunk: bytes):
        if not self._ws or self._ws.closed:
            await self.connect()
        assert self._ws
        await self._ws.send(pcm_chunk)

    async def end(self) -> tuple[str, Optional[float]]:
        # Prepare future, signal end, await final
        if not self._ws or self._ws.closed:
            await self.connect()
        assert self._ws
        self._final_future = asyncio.get_event_loop().create_future()
        await self._ws.send(orjson.dumps({"type": "end"}).decode())
        try:
            text, conf = await asyncio.wait_for(self._final_future, timeout=30.0)
        except asyncio.TimeoutError:
            text, conf = "", None
        finally:
            self._final_future = None
        return text, conf

    async def close(self):
        if self._reader_task:
            self._reader_task.cancel()
        if self._ws and not self._ws.closed:
            try:
                await self._ws.close()
            except Exception:
                pass
        self._ws = None
