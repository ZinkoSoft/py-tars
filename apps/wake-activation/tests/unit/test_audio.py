import asyncio
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from wake_activation.audio import AudioFanoutClient


@pytest.mark.asyncio
async def test_audio_client_streams_frames(tmp_path: Path) -> None:
    socket_path = tmp_path / "fanout.sock"
    samples_per_chunk = 4

    int_frames = [
        np.array([0, 8192, -8192, 16384], dtype=np.int16),
        np.array([16384, -16384, 0, 0], dtype=np.int16),
    ]
    payloads = [frame.tobytes() for frame in int_frames]

    async def client_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        for payload in payloads:
            writer.write(payload)
            await writer.drain()
        await asyncio.sleep(0.01)
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_unix_server(client_handler, path=str(socket_path))

    client = AudioFanoutClient(socket_path, samples_per_chunk=samples_per_chunk)

    async def collect_frames() -> list[NDArray[np.float32]]:
        frames = []
        async for frame in client.frames():
            frames.append(frame)
            if len(frames) >= len(int_frames):
                await client.close()
        return frames

    try:
        collected = await asyncio.wait_for(collect_frames(), timeout=1.0)
    finally:
        server.close()
        await server.wait_closed()

    assert len(collected) == len(int_frames)
    for output, expected in zip(collected, int_frames, strict=True):
        np.testing.assert_allclose(
            output, expected.astype(np.float32) / 32768.0, rtol=1e-6, atol=1e-6
        )
        assert output.dtype == np.float32
        assert output.shape == (samples_per_chunk,)
