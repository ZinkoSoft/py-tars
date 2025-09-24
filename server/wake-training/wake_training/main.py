from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path, File, UploadFile, Form, Response
from typing import Optional

from .config import Settings, load_settings
from .models import (
    DatasetCreateRequest,
    DatasetDetail,
    DatasetSummary,
    HealthResponse,
    RecordingMetadata,
    RecordingResponse,
    RecordingUpdate,
)
from .storage import DatasetStorage

logger = logging.getLogger(__name__)

app = FastAPI(title="TARS Wake Training API", version="0.1.0")


def get_settings() -> Settings:
    settings = load_settings()
    settings.ensure_directories()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    return settings


def get_storage(settings: Annotated[Settings, Depends(get_settings)]) -> DatasetStorage:
    return DatasetStorage(settings.data_root)


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
) -> DatasetDetail:
    try:
        return storage.create_dataset(payload)
    except FileExistsError:
        raise HTTPException(status_code=409, detail="Dataset already exists")


@app.get("/datasets/{name}", response_model=DatasetDetail)
async def get_dataset(
    name: Annotated[str, Path(pattern=r"^[A-Za-z0-9._-]+$", title="Dataset name")],
    storage: Annotated[DatasetStorage, Depends(get_storage)],
) -> DatasetDetail:
    try:
        return storage.get_dataset(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dataset not found")


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
) -> RecordingResponse:
    if file.content_type not in ("audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave"):
        raise HTTPException(status_code=415, detail="Unsupported media type; expected WAV")
    try:
        data = await file.read()
        meta = RecordingMetadata(label=label, speaker=speaker, notes=notes)
        return storage.save_recording(name, data, file.filename, meta)
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
) -> dict:
    try:
        storage.delete_recording(name, clip_id)
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
) -> dict:
    try:
        storage.restore_recording(name, clip_id)
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
) -> dict:
    try:
        storage.update_recording(name, clip_id, patch)
        return {"status": "ok"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Not found")
