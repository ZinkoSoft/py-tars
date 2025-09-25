from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Path,
    File,
    UploadFile,
    Form,
    WebSocket,
    WebSocketDisconnect,
    Query,
    Response,
)
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings, load_settings
from .models import (
    DatasetCreateRequest,
    DatasetDetail,
    DatasetSummary,
    HealthResponse,
    DatasetMetrics,
    DatasetUpdateRequest,
    RecordingMetadata,
    RecordingResponse,
    RecordingUpdate,
)
from .storage import DatasetStorage
from .events import EventHub, DatasetEvent, DatasetEventType
from .jobs import JobStorage, TrainingJob, TrainingJobCreateRequest, JobLogChunk
from .runner import TrainingJobRunner

logger = logging.getLogger(__name__)

app = FastAPI(title="TARS Wake Training API", version="0.1.0")
app.state.event_hub = EventHub()
app.state.job_runner = None


def _load_and_configure_settings() -> Settings:
    settings = load_settings()
    settings.ensure_directories()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    return settings


app.state.settings = _load_and_configure_settings()
logger.info(
    "Wake Training settings loaded data_root=%s log_level=%s cors_allow_origins=%s",
    app.state.settings.data_root,
    app.state.settings.log_level,
    app.state.settings.cors_allow_origins,
)

if app.state.settings.cors_allow_origins:
    origins = app.state.settings.cors_allow_origins
    allow_credentials = origins != ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def get_settings() -> Settings:
    settings = getattr(app.state, "settings", None)
    if settings is None:
        settings = _load_and_configure_settings()
        app.state.settings = settings
    return settings


def get_storage(settings: Annotated[Settings, Depends(get_settings)]) -> DatasetStorage:
    return DatasetStorage(settings.data_root)


def get_job_storage(settings: Annotated[Settings, Depends(get_settings)]) -> JobStorage:
    return JobStorage(settings.data_root)


def get_event_hub() -> EventHub:
    return app.state.event_hub


async def get_job_runner(
    storage: Annotated[DatasetStorage, Depends(get_storage)],
    job_storage: Annotated[JobStorage, Depends(get_job_storage)],
    event_hub: Annotated[EventHub, Depends(get_event_hub)],
) -> TrainingJobRunner:
    runner = getattr(app.state, "job_runner", None)
    if runner is None:
        runner = TrainingJobRunner(storage=storage, job_storage=job_storage, event_hub=event_hub)
        app.state.job_runner = runner
        await runner.resume_queued_jobs()
    else:
        runner.update_handles(storage=storage, job_storage=job_storage, event_hub=event_hub)
    return runner


@app.get("/health", response_model=HealthResponse)
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(data_root=settings.data_root)


@app.get("/datasets", response_model=list[DatasetSummary])
async def list_datasets(storage: Annotated[DatasetStorage, Depends(get_storage)]) -> list[DatasetSummary]:
    return storage.list_datasets()


@app.post("/datasets", response_model=DatasetDetail, status_code=201)
async def create_dataset(
    payload: DatasetCreateRequest,
    storage: Annotated[DatasetStorage, Depends(get_storage)],
    event_hub: Annotated[EventHub, Depends(get_event_hub)],
) -> DatasetDetail:
    try:
        created = storage.create_dataset(payload)
    except FileExistsError:
        raise HTTPException(status_code=409, detail="Dataset already exists")
    metrics = storage.get_metrics(created.name)
    await event_hub.publish(
        DatasetEvent(
            type=DatasetEventType.dataset_created,
            dataset=created.name,
            metrics=metrics,
        )
    )
    return created


@app.get("/datasets/{name}", response_model=DatasetDetail)
async def get_dataset(
    name: Annotated[str, Path(pattern=r"^[A-Za-z0-9._-]+$", title="Dataset name")],
    storage: Annotated[DatasetStorage, Depends(get_storage)],
) -> DatasetDetail:
    try:
        return storage.get_dataset(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset not found")


@app.patch("/datasets/{name}", response_model=DatasetDetail)
async def update_dataset(
    name: Annotated[str, Path(pattern=r"^[A-Za-z0-9._-]+$", title="Dataset name")],
    payload: DatasetUpdateRequest,
    storage: Annotated[DatasetStorage, Depends(get_storage)] = None,
    event_hub: Annotated[EventHub, Depends(get_event_hub)] = None,
) -> DatasetDetail:
    try:
        updated = storage.update_dataset(name, payload)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset not found")
    except FileExistsError:
        raise HTTPException(status_code=409, detail="Dataset name already exists")

    metrics = storage.get_metrics(updated.name)
    await event_hub.publish(
        DatasetEvent(
            type=DatasetEventType.dataset_updated,
            dataset=updated.name,
            previous_dataset=name if name != updated.name else None,
            metrics=metrics,
        )
    )
    return updated


@app.delete("/datasets/{name}", status_code=204)
async def delete_dataset(
    name: Annotated[str, Path(pattern=r"^[A-Za-z0-9._-]+$", title="Dataset name")],
    storage: Annotated[DatasetStorage, Depends(get_storage)] = None,
    event_hub: Annotated[EventHub, Depends(get_event_hub)] = None,
) -> Response:
    try:
        metrics = storage.get_metrics(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset not found")

    try:
        storage.delete_dataset(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset not found")

    await event_hub.publish(
        DatasetEvent(
            type=DatasetEventType.dataset_deleted,
            dataset=name,
            metrics=metrics,
            previous_dataset=name,
        )
    )
    return Response(status_code=204)


@app.post(
    "/datasets/{name}/recordings",
    response_model=RecordingResponse,
    status_code=201,
)
async def upload_recording(
    name: Annotated[str, Path(pattern=r"^[A-Za-z0-9._-]+$", title="Dataset name")],
    file: UploadFile = File(..., description="WAV audio file"),
    label: Optional[str] = Form(default="positive"),
    speaker: Optional[str] = Form(default=None),
    notes: Optional[str] = Form(default=None),
    storage: Annotated[DatasetStorage, Depends(get_storage)] = None,
    event_hub: Annotated[EventHub, Depends(get_event_hub)] = None,
) -> RecordingResponse:
    if file.content_type not in ("audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave"):
        raise HTTPException(status_code=415, detail="Unsupported media type; expected WAV")
    try:
        data = await file.read()
        meta = RecordingMetadata(label=label, speaker=speaker, notes=notes)
        recording = storage.save_recording(name, data, file.filename, meta)
        metrics = storage.get_metrics(name)
        await event_hub.publish(
            DatasetEvent(
                type=DatasetEventType.recording_uploaded,
                dataset=name,
                clip_id=recording.clip_id,
                metrics=metrics,
            )
        )
        return recording
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset not found")


@app.delete(
    "/datasets/{name}/recordings/{clip_id}",
    status_code=200,
)
async def delete_recording(
    name: Annotated[str, Path(pattern=r"^[A-Za-z0-9._-]+$", title="Dataset name")],
    clip_id: Annotated[str, Path(pattern=r"^[a-f0-9]{32}$", title="Clip ID")],
    storage: Annotated[DatasetStorage, Depends(get_storage)] = None,
    event_hub: Annotated[EventHub, Depends(get_event_hub)] = None,
) -> dict:
    try:
        storage.delete_recording(name, clip_id)
        metrics = storage.get_metrics(name)
        await event_hub.publish(
            DatasetEvent(
                type=DatasetEventType.recording_deleted,
                dataset=name,
                clip_id=clip_id,
                metrics=metrics,
            )
        )
        return {"status": "ok"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Not found")


@app.post(
    "/datasets/{name}/recordings/{clip_id}/restore",
    status_code=200,
)
async def restore_recording(
    name: Annotated[str, Path(pattern=r"^[A-Za-z0-9._-]+$", title="Dataset name")],
    clip_id: Annotated[str, Path(pattern=r"^[a-f0-9]{32}$", title="Clip ID")],
    storage: Annotated[DatasetStorage, Depends(get_storage)] = None,
    event_hub: Annotated[EventHub, Depends(get_event_hub)] = None,
) -> dict:
    try:
        storage.restore_recording(name, clip_id)
        metrics = storage.get_metrics(name)
        await event_hub.publish(
            DatasetEvent(
                type=DatasetEventType.recording_restored,
                dataset=name,
                clip_id=clip_id,
                metrics=metrics,
            )
        )
        return {"status": "ok"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Not found")


@app.patch(
    "/datasets/{name}/recordings/{clip_id}",
)
async def patch_recording(
    name: Annotated[str, Path(pattern=r"^[A-Za-z0-9._-]+$", title="Dataset name")],
    clip_id: Annotated[str, Path(pattern=r"^[a-f0-9]{32}$", title="Clip ID")],
    patch: RecordingUpdate,
    storage: Annotated[DatasetStorage, Depends(get_storage)] = None,
    event_hub: Annotated[EventHub, Depends(get_event_hub)] = None,
) -> dict:
    try:
        storage.update_recording(name, clip_id, patch)
        metrics = storage.get_metrics(name)
        await event_hub.publish(
            DatasetEvent(
                type=DatasetEventType.recording_updated,
                dataset=name,
                clip_id=clip_id,
                metrics=metrics,
            )
        )
        return {"status": "ok"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Not found")


@app.get("/datasets/{name}/metrics", response_model=DatasetMetrics)
async def get_dataset_metrics(
    name: Annotated[str, Path(pattern=r"^[A-Za-z0-9._-]+$", title="Dataset name")],
    storage: Annotated[DatasetStorage, Depends(get_storage)] = None,
) -> DatasetMetrics:
    try:
        return storage.get_metrics(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset not found")


@app.post("/train", response_model=TrainingJob, status_code=202)
async def enqueue_training_job(
    payload: TrainingJobCreateRequest,
    storage: Annotated[DatasetStorage, Depends(get_storage)] = None,
    job_storage: Annotated[JobStorage, Depends(get_job_storage)] = None,
    event_hub: Annotated[EventHub, Depends(get_event_hub)] = None,
    job_runner: Annotated[TrainingJobRunner, Depends(get_job_runner)] = None,
) -> TrainingJob:
    try:
        storage.get_dataset(payload.dataset_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset not found")
    try:
        job, initial_log_chunk = job_storage.create_job(
            payload.dataset_id,
            config=payload.config_overrides or {},
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset not found")
    metrics = storage.get_metrics(payload.dataset_id)
    await event_hub.publish(
        DatasetEvent(
            type=DatasetEventType.job_queued,
            dataset=payload.dataset_id,
            job_id=job.id,
            metrics=metrics,
        )
    )
    if initial_log_chunk.entries:
        await event_hub.publish(
            DatasetEvent(
                type=DatasetEventType.job_log,
                dataset=payload.dataset_id,
                job_id=job.id,
                metrics=metrics,
                log_chunk=initial_log_chunk,
            )
        )
    await job_runner.enqueue(job)
    return job


@app.get("/jobs/{job_id}", response_model=TrainingJob)
async def get_training_job(
    job_id: Annotated[str, Path(pattern=r"^[a-f0-9]{32}$", title="Job ID")],
    job_storage: Annotated[JobStorage, Depends(get_job_storage)] = None,
) -> TrainingJob:
    try:
        return job_storage.get_job(job_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Job not found")


@app.get("/jobs/{job_id}/logs", response_model=JobLogChunk)
async def get_training_job_logs(
    job_id: Annotated[str, Path(pattern=r"^[a-f0-9]{32}$", title="Job ID")],
    offset: Annotated[int, Query(ge=0, description="Byte offset to start reading from")] = 0,
    limit: Annotated[int, Query(ge=128, le=65536, description="Maximum number of bytes to read")] = 16384,
    job_storage: Annotated[JobStorage, Depends(get_job_storage)] = None,
) -> JobLogChunk:
    try:
        return job_storage.read_log_chunk(job_id, offset=offset, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Job not found")


@app.websocket("/ws/events")
async def dataset_events_ws(
    websocket: WebSocket,
    event_hub: Annotated[EventHub, Depends(get_event_hub)],
) -> None:
    await event_hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await event_hub.disconnect(websocket)
