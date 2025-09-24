import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from wake_training.main import app


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("WAKE_TRAINING_DATA_DIR", str(tmp_path))
    return TestClient(app)


def _create_dataset(client: TestClient, name: str = "dset"):
    resp = client.post("/datasets", json={"name": name})
    assert resp.status_code == 201
    return name


def _upload(client: TestClient, name: str, label: str):
    wav_bytes = b"RIFF....WAVEfmt "
    files = {"file": ("s.wav", io.BytesIO(wav_bytes), "audio/wav")}
    data = {"label": label}
    r = client.post(f"/datasets/{name}/recordings", files=files, data=data)
    assert r.status_code == 201, r.text
    return r.json()["clip_id"]


def test_metrics_counts_and_zero_duration(client: TestClient, tmp_path: Path):
    name = _create_dataset(client)
    # upload various labels
    c1 = _upload(client, name, "positive")
    c2 = _upload(client, name, "negative")
    c3 = _upload(client, name, "noise")

    # fetch metrics
    m = client.get(f"/datasets/{name}/metrics")
    assert m.status_code == 200, m.text
    body = m.json()
    assert body["name"] == name
    assert body["clip_count"] == 3
    assert body["positives"] == 1
    assert body["negatives"] == 1
    assert body["noise"] == 1
    assert body["total_duration_sec"] == 0.0

    # delete one and verify counts drop
    del_resp = client.delete(f"/datasets/{name}/recordings/{c2}")
    assert del_resp.status_code == 200
    m2 = client.get(f"/datasets/{name}/metrics").json()
    assert m2["clip_count"] == 2
    assert m2["negatives"] == 0

    # restore and see counts back
    res = client.post(f"/datasets/{name}/recordings/{c2}/restore")
    assert res.status_code == 200
    m3 = client.get(f"/datasets/{name}/metrics").json()
    assert m3["clip_count"] == 3
    assert m3["negatives"] == 1

    # patch label and verify redistribution
    patch = client.patch(f"/datasets/{name}/recordings/{c3}", json={"label": "positive"})
    assert patch.status_code == 200
    m4 = client.get(f"/datasets/{name}/metrics").json()
    assert m4["positives"] == 2
    assert m4["noise"] == 0
