from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path

from .config import Settings, load_settings
from .models import DatasetCreateRequest, DatasetDetail, DatasetSummary, HealthResponse
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
