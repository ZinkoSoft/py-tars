from __future__ import annotations

import asyncio

import orjson
import pytest
import websockets

from stt_worker.fft_ws import FFTWebSocketServer


@pytest.mark.asyncio
async def test_fft_websocket_broadcast_reaches_clients() -> None:
    server = FFTWebSocketServer("127.0.0.1", 0, "/fft")
    await server.start()
    try:
        uri = f"ws://127.0.0.1:{server.port}/fft"
        async with websockets.connect(uri) as ws:
            await server.broadcast({"fft": [1.0, 0.5], "ts": 0.1})
            message = await asyncio.wait_for(ws.recv(), timeout=1.0)
            payload = orjson.loads(message)

        assert payload["fft"] == [1.0, 0.5]
        assert payload["ts"] == pytest.approx(0.1)
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_fft_websocket_caches_last_frame_for_new_clients() -> None:
    server = FFTWebSocketServer("127.0.0.1", 0, "/fft")
    await server.start()
    try:
        await server.broadcast({"fft": [0.25], "ts": 2.0})

        uri = f"ws://127.0.0.1:{server.port}/fft"
        async with websockets.connect(uri) as ws:
            message = await asyncio.wait_for(ws.recv(), timeout=1.0)
            payload = orjson.loads(message)

        assert payload["fft"] == [0.25]
        assert payload["ts"] == pytest.approx(2.0)
    finally:
        await server.stop()
