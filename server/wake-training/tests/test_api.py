import math
from pathlib import Path

import pytest

from fastapi.testclient import TestClient

from wake_training.jobs import JobStorage, TrainingJobStatus
from wake_training.trainer import TrainingConfig, _WakeWordNet

pytest.importorskip("torch")
import torch


def test_health(client: TestClient, tmp_path: Path) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    returned_root = Path(data["data_root"]).resolve()
    assert returned_root == tmp_path.resolve()


def test_list_datasets_empty(client: TestClient) -> None:
    resp = client.get("/datasets")
    assert resp.status_code == 200
    assert resp.json() == []

def test_create_and_get_dataset(client: TestClient) -> None:
    # Create
    resp = client.post("/datasets", json={"name": "testset"})
    assert resp.status_code == 201
    detail = resp.json()
    assert detail["name"] == "testset"
    # List
    resp = client.get("/datasets")
    assert resp.status_code == 200
    datasets = resp.json()
    assert any(d["name"] == "testset" for d in datasets)
    # Get detail
    resp = client.get("/datasets/testset")
    assert resp.status_code == 200
    detail2 = resp.json()
    assert detail2["name"] == "testset"
    # Duplicate create
    resp = client.post("/datasets", json={"name": "testset"})
    assert resp.status_code == 409

def test_get_dataset_not_found(client: TestClient) -> None:
    resp = client.get("/datasets/doesnotexist")
    assert resp.status_code == 404


def test_infer_recording_with_latest_job(client: TestClient, make_wav) -> None:
    resp = client.post("/datasets", json={"name": "wake"})
    assert resp.status_code == 201

    wav_bytes = make_wav().getvalue()
    resp = client.post(
        "/datasets/wake/recordings",
        files={"file": ("sample.wav", wav_bytes, "audio/wav")},
        data={"label": "positive"},
    )
    assert resp.status_code == 201
    clip_id = resp.json()["clip_id"]

    job_id = _create_completed_job(client.app, dataset="wake", probability=0.85)

    resp = client.post(
        f"/datasets/wake/recordings/{clip_id}/infer",
        json={},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["dataset"] == "wake"
    assert data["clip_id"] == clip_id
    assert data["job_id"] == job_id
    assert data["is_wake"] is True
    assert data["trained_at"] is not None
    assert data["sample_rate"] == TrainingConfig().sample_rate
    assert data["clip_duration_sec"] == pytest.approx(TrainingConfig().clip_duration_sec)
    assert data["probability"] == pytest.approx(0.85, rel=1e-3)


def test_infer_recording_with_specific_job(client: TestClient, make_wav) -> None:
    resp = client.post("/datasets", json={"name": "wake"})
    assert resp.status_code == 201

    wav_bytes = make_wav(duration=1.2).getvalue()
    resp = client.post(
        "/datasets/wake/recordings",
        files={"file": ("sample.wav", wav_bytes, "audio/wav")},
        data={"label": "positive"},
    )
    assert resp.status_code == 201
    clip_id = resp.json()["clip_id"]

    job_id = _create_completed_job(client.app, dataset="wake", probability=0.3)

    resp = client.post(
        f"/datasets/wake/recordings/{clip_id}/infer",
        json={"job_id": job_id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == job_id
    assert data["is_wake"] is False
    assert data["probability"] == pytest.approx(0.3, rel=1e-3)
    assert data["threshold"] == pytest.approx(0.5)


def test_infer_requires_completed_job(client: TestClient, make_wav) -> None:
    resp = client.post("/datasets", json={"name": "wake"})
    assert resp.status_code == 201

    wav_bytes = make_wav().getvalue()
    resp = client.post(
        "/datasets/wake/recordings",
        files={"file": ("sample.wav", wav_bytes, "audio/wav")},
        data={"label": "positive"},
    )
    assert resp.status_code == 201
    clip_id = resp.json()["clip_id"]

    resp = client.post(
        f"/datasets/wake/recordings/{clip_id}/infer",
        json={},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "No completed training jobs for dataset"


def _create_completed_job(app, *, dataset: str, probability: float) -> str:
    data_root = Path(app.state.settings.data_root)
    job_storage = JobStorage(data_root)
    job, _ = job_storage.create_job(dataset)
    job_dir = job_storage.get_job_dir(job.id)
    export_dir = job_dir / "export"
    export_dir.mkdir(parents=True, exist_ok=True)

    config = TrainingConfig()
    model = _WakeWordNet()

    with torch.no_grad():
        for param in model.parameters():
            param.zero_()
        bias = model.classifier[-1].bias
        logit = math.log(probability / (1.0 - probability))
        bias.data.fill_(logit)

    model_path = export_dir / "wake_model.pt"
    torch.save(
        {
            "state_dict": model.state_dict(),
            "config": config.model_dump(),
            "threshold": 0.5,
            "trained_at": "2024-01-01T00:00:00+00:00",
            "best_epoch": 7,
        },
        model_path,
    )

    metadata = {
        "export_dir": str(export_dir),
        "threshold": 0.5,
        "artifacts": {"state_dict": str(model_path)},
        "hyperparameters": config.model_dump(),
        "best_epoch": 7,
        "trained_at": "2024-01-01T00:00:00+00:00",
    }
    job_storage.update_status(job.id, TrainingJobStatus.completed, metadata=metadata)
    return job.id
