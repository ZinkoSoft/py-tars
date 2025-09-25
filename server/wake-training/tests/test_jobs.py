from __future__ import annotations

import time
from pathlib import Path

import pytest

from fastapi.testclient import TestClient


def _upload_clip(
    client: TestClient,
    dataset: str,
    make_wav,
    *,
    label: str,
    name: str,
    **wave_kwargs,
) -> None:
    wav_file = make_wav(**wave_kwargs)
    files = {"file": (f"{name}.wav", wav_file, "audio/wav")}
    data = {"label": label}
    resp = client.post(f"/datasets/{dataset}/recordings", files=files, data=data)
    assert resp.status_code == 201, resp.text


def _populate_dataset(client: TestClient, dataset: str, make_wav) -> None:
    for idx in range(6):
        _upload_clip(
            client,
            dataset,
            make_wav,
            label="positive",
            name=f"pos-{idx}",
            freq=420.0 + idx * 12.0,
            duration=1.0,
            amplitude=0.45,
        )
    for idx in range(6):
        _upload_clip(
            client,
            dataset,
            make_wav,
            label="negative",
            name=f"neg-{idx}",
            freq=700.0 + idx * 17.0,
            duration=1.0,
            amplitude=0.35,
        )
    for idx in range(2):
        _upload_clip(
            client,
            dataset,
            make_wav,
            label="noise",
            name=f"noise-{idx}",
            freq=180.0 + idx * 10.0,
            duration=1.0,
            amplitude=0.25,
            noise=True,
            seed=idx,
        )


def wait_for_status(client: TestClient, job_id: str, *, timeout: float = 60.0) -> dict:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        resp = client.get(f"/jobs/{job_id}")
        assert resp.status_code == 200
        last = resp.json()
        if last["status"] not in {"queued", "running"}:
            return last
        time.sleep(0.01)
    return last


def test_training_job_lifecycle_completes(client: TestClient, make_wav, tmp_path: Path) -> None:
    pytest.importorskip("torch", reason="PyTorch required for wake training pipeline")
    resp = client.post("/datasets", json={"name": "demo"})
    assert resp.status_code == 201

    _populate_dataset(client, "demo", make_wav)

    overrides = {
        "epochs": 3,
        "batch_size": 4,
        "patience": 2,
        "clip_duration_sec": 1.0,
        "learning_rate": 5e-3,
    }

    enqueue = client.post(
        "/train",
        json={"dataset_id": "demo", "config_overrides": overrides},
    )
    assert enqueue.status_code == 202
    job_id = enqueue.json()["id"]

    result = wait_for_status(client, job_id)
    assert result is not None
    assert result["status"] == "completed"
    assert result["error"] is None
    job_config = result["config"]
    for key, value in overrides.items():
        assert job_config[key] == value
    assert "hyperparameters" in job_config
    resolved = job_config["hyperparameters"]
    assert resolved["epochs"] == overrides["epochs"]
    export_dir = Path(job_config["export_dir"])
    assert export_dir.exists()
    assert export_dir.is_dir()
    assert export_dir.is_relative_to(tmp_path)
    artifacts = job_config["artifacts"]
    for path in artifacts.values():
        assert Path(path).exists()
    metrics = job_config["metrics"]
    assert 0.0 <= metrics["accuracy"] <= 1.0
    assert 0.0 <= metrics["balanced_accuracy"] <= 1.0

    logs_resp = client.get(f"/jobs/{job_id}/logs")
    assert logs_resp.status_code == 200
    payload = logs_resp.json()
    assert payload["offset"] == 0
    assert payload["next_offset"] == payload["total_size"]
    assert payload["has_more"] is False
    messages = [entry["message"] for entry in payload["entries"]]
    assert "Job created and queued" in messages
    assert "Job started; transitioning to running" in messages
    assert any(message.startswith("Job completed successfully") for message in messages)
    assert any(message.startswith("Validation metrics:") for message in messages)

    follow_up = client.get(
        f"/jobs/{job_id}/logs",
        params={"offset": payload["next_offset"]},
    )
    assert follow_up.status_code == 200
    subsequent = follow_up.json()
    assert subsequent["offset"] == payload["next_offset"]
    assert subsequent["entries"] == []
    assert subsequent["has_more"] is False


def test_training_job_missing_dataset_404(client):
    resp = client.post("/train", json={"dataset_id": "missing"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Dataset not found"


def test_get_unknown_job_404(client):
    resp = client.get("/jobs/" + "0" * 32)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Job not found"


def test_get_unknown_job_logs_404(client):
    resp = client.get("/jobs/" + "0" * 32 + "/logs")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Job not found"


def test_training_job_fails_with_insufficient_data(client: TestClient, make_wav) -> None:
    pytest.importorskip("torch", reason="PyTorch required for wake training pipeline")
    resp = client.post("/datasets", json={"name": "tiny"})
    assert resp.status_code == 201

    for idx in range(2):
        _upload_clip(
            client,
            "tiny",
            make_wav,
            label="positive",
            name=f"tiny-pos-{idx}",
            freq=440.0,
            duration=1.0,
            amplitude=0.4,
        )

    for idx in range(2):
        _upload_clip(
            client,
            "tiny",
            make_wav,
            label="negative",
            name=f"tiny-neg-{idx}",
            freq=660.0,
            duration=1.0,
            amplitude=0.3,
        )

    enqueue = client.post(
        "/train",
        json={"dataset_id": "tiny"},
    )
    assert enqueue.status_code == 202
    job_id = enqueue.json()["id"]

    result = wait_for_status(client, job_id)
    assert result["status"] == "failed"
    assert "requires at least" in result["error"]

    logs_resp = client.get(f"/jobs/{job_id}/logs")
    assert logs_resp.status_code == 200
    messages = [entry["message"] for entry in logs_resp.json()["entries"]]
    assert any("Job failed" in message for message in messages)
