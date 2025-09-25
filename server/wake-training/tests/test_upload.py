from __future__ import annotations

import io
from pathlib import Path

from fastapi.testclient import TestClient


def _create_dataset(client: TestClient, name: str = "dset") -> str:
    resp = client.post("/datasets", json={"name": name})
    assert resp.status_code == 201
    return name


def test_upload_wav_success(client: TestClient, tmp_path: Path, make_wav) -> None:
    name = _create_dataset(client)
    files = {"file": ("sample.wav", make_wav(freq=420.0), "audio/wav")}
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


def test_upload_wrong_mime(client: TestClient) -> None:
    name = _create_dataset(client)
    files = {"file": ("bad.mp3", io.BytesIO(b"\x00\x00"), "audio/mpeg")}
    resp = client.post(f"/datasets/{name}/recordings", files=files)
    assert resp.status_code == 415


def test_upload_missing_dataset(client: TestClient, make_wav) -> None:
    files = {"file": ("s.wav", make_wav(freq=330.0), "audio/wav")}
    resp = client.post("/datasets/nope/recordings", files=files)
    assert resp.status_code == 404
