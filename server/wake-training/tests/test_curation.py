import io
from pathlib import Path

from fastapi.testclient import TestClient


def _create_dataset(client: TestClient, name: str = "dset"):
    resp = client.post("/datasets", json={"name": name})
    assert resp.status_code == 201
    return name


def _upload_clip(client: TestClient, name: str) -> str:
    wav_bytes = b"RIFF....WAVEfmt "
    files = {"file": ("s.wav", io.BytesIO(wav_bytes), "audio/wav")}
    r = client.post(f"/datasets/{name}/recordings", files=files, data={"label": "positive"})
    assert r.status_code == 201, r.text
    return r.json()["clip_id"]


def test_delete_and_restore_flow(client: TestClient, tmp_path: Path):
    name = _create_dataset(client)
    clip_id = _upload_clip(client, name)

    # Ensure file exists in clips
    clip_path = tmp_path / "datasets" / name / "clips" / f"{clip_id}.wav"
    trash_path = tmp_path / "datasets" / name / "trash" / f"{clip_id}.wav"
    assert clip_path.exists()
    assert not trash_path.exists()

    # Delete it
    resp = client.delete(f"/datasets/{name}/recordings/{clip_id}")
    assert resp.status_code == 200
    assert not clip_path.exists()
    assert trash_path.exists()

    # Restore it
    resp = client.post(f"/datasets/{name}/recordings/{clip_id}/restore")
    assert resp.status_code == 200
    assert clip_path.exists()
    assert not trash_path.exists()


def test_patch_metadata(client: TestClient, tmp_path: Path):
    name = _create_dataset(client)
    clip_id = _upload_clip(client, name)

    # Patch label and speaker
    resp = client.patch(
        f"/datasets/{name}/recordings/{clip_id}",
        json={"label": "negative", "speaker": "bob", "notes": "noisy"},
    )
    assert resp.status_code == 200

    labels_path = tmp_path / "datasets" / name / "labels.json"
    text = labels_path.read_text()
    assert f'"{clip_id}":' in text
    assert '"label": "negative"' in text
    assert '"speaker": "bob"' in text
    assert '"notes": "noisy"' in text


def test_delete_missing(client: TestClient):
    resp = client.delete("/datasets/nope/recordings/00000000000000000000000000000000")
    assert resp.status_code == 404


def test_restore_missing(client: TestClient):
    resp = client.post("/datasets/nope/recordings/00000000000000000000000000000000/restore")
    assert resp.status_code == 404


def test_patch_missing(client: TestClient):
    resp = client.patch(
        "/datasets/nope/recordings/00000000000000000000000000000000",
        json={"label": "noise"},
    )
    assert resp.status_code == 404
