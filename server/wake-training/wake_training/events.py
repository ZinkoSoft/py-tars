from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Iterable, Optional

from fastapi import WebSocket

from pydantic import BaseModel, ConfigDict, Field

from .models import DatasetMetrics
from .jobs import JobLogChunk
from .compat import StrEnum


class DatasetEventType(StrEnum):
    dataset_created = "dataset.created"
    dataset_updated = "dataset.updated"
    dataset_deleted = "dataset.deleted"
    recording_uploaded = "recording.uploaded"
    recording_deleted = "recording.deleted"
    recording_restored = "recording.restored"
    recording_updated = "recording.updated"
    job_queued = "job.queued"
    job_running = "job.running"
    job_completed = "job.completed"
    job_failed = "job.failed"
    job_log = "job.log"


class DatasetEvent(BaseModel):
    """Dataset change event delivered over WebSocket."""

    model_config = ConfigDict(extra="forbid")

    type: DatasetEventType
    dataset: str
    previous_dataset: Optional[str] = None
    metrics: DatasetMetrics
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    clip_id: Optional[str] = None
    job_id: Optional[str] = None
    log_chunk: Optional[JobLogChunk] = None


class EventHub:
    """In-memory broadcast hub for dataset events.

    Keeps a set of active WebSocket connections and fan-outs JSON payloads to
    each subscriber. Slow or disconnected clients are removed automatically.
    """

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._clients.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(websocket)

    async def publish(self, payload: DatasetEvent) -> None:
        data = payload.model_dump_json()
        async with self._lock:
            clients = list(self._clients)
        for ws in clients:
            try:
                await ws.send_text(data)
            except Exception:
                await self.disconnect(ws)

    async def broadcast_iterable(self, events: Iterable[DatasetEvent]) -> None:
        for event in events:
            await self.publish(event)