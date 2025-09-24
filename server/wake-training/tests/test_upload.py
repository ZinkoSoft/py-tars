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


def test_upload_wav_success(client: TestClient, tmp_path: Path):
    name = _create_dataset(client)
    wav_bytes = b"RIFF....WAVEfmt "  # minimal header marker; content not parsed yet
    files = {"file": ("sample.wav", io.BytesIO(wav_bytes), "audio/wav")}
    data = {"label": "positive", "speaker": "alice", "notes": "ok"}

    resp = client.post(f"/datasets/{name}/recordings", files=files, data=data)
    assert resp.status_code == 201, resp.text
    info = resp.json()
    assert info["dataset"] == name
    clip_id = info["clip_id"]

    # Verify file written and labels.json updated
    clips_dir = tmp_path / "datasets" / name / "clips"
    labels_path = tmp_path / "datasets" / name / "labels.json"
    assert (clips_dir / f"{clip_id}.wav").exists()
    assert labels_path.exists()
    labels = labels_path.read_text()
    assert clip_id in labels
    assert '"label": "positive"' in labels
    assert '"speaker": "alice"' in labels


def test_upload_wrong_mime(client: TestClient):
    name = _create_dataset(client)
    files = {"file": ("bad.mp3", io.BytesIO(b"\x00\x00"), "audio/mpeg")}
    resp = client.post(f"/datasets/{name}/recordings", files=files)
    assert resp.status_code == 415

def test_upload_missing_dataset(client: TestClient):
    files = {"file": ("s.wav", io.BytesIO(b"RIFF"), "audio/wav")}
    resp = client.post("/datasets/nope/recordings", files=files)
    assert resp.status_code == 404
