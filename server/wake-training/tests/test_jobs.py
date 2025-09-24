import time

import pytest
from fastapi.testclient import TestClient

from wake_training.main import app


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("WAKE_TRAINING_DATA_DIR", str(tmp_path))
    return TestClient(app)


def wait_for_status(client: TestClient, job_id: str, *, timeout: float = 1.0) -> dict:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        resp = client.get(f"/jobs/{job_id}")
        assert resp.status_code == 200
        last = resp.json()
        if last["status"] != "queued":
            return last
        time.sleep(0.01)
    return last


def test_training_job_lifecycle_completes(client):
    resp = client.post("/datasets", json={"name": "demo"})
    assert resp.status_code == 201

    enqueue = client.post("/train", json={"dataset_id": "demo", "config_overrides": {"epochs": 1}})
    assert enqueue.status_code == 202
    job_id = enqueue.json()["id"]

    result = wait_for_status(client, job_id)
    assert result is not None
    assert result["status"] == "completed"
    assert result["error"] is None
    assert result["config"] == {"epochs": 1}

    logs_resp = client.get(f"/jobs/{job_id}/logs")
    assert logs_resp.status_code == 200
    payload = logs_resp.json()
    assert payload["offset"] == 0
    assert payload["next_offset"] == payload["total_size"]
    assert payload["has_more"] is False
    messages = [entry["message"] for entry in payload["entries"]]
    assert "Job created and queued" in messages
    assert "Job started; transitioning to running" in messages
    assert "Job completed successfully" in messages

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
