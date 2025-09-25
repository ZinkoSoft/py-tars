import io

from fastapi.testclient import TestClient


def _create_dataset(client: TestClient, name: str = "dset") -> str:
    resp = client.post("/datasets", json={"name": name})
    assert resp.status_code == 201
    return name


def _upload(client: TestClient, name: str, label: str) -> str:
    wav_bytes = b"RIFF....WAVEfmt "
    files = {"file": ("s.wav", io.BytesIO(wav_bytes), "audio/wav")}
    data = {"label": label}
    resp = client.post(f"/datasets/{name}/recordings", files=files, data=data)
    assert resp.status_code == 201, resp.text
    return resp.json()["clip_id"]


def test_metrics_counts_and_zero_duration(client: TestClient) -> None:
    name = _create_dataset(client)

    # Upload various labels
    _upload(client, name, "positive")
    clip_neg = _upload(client, name, "negative")
    clip_noise = _upload(client, name, "noise")

    # Fetch metrics
    resp = client.get(f"/datasets/{name}/metrics")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == name
    assert body["clip_count"] == 3
    assert body["positives"] == 1
    assert body["negatives"] == 1
    assert body["noise"] == 1
    assert body["total_duration_sec"] == 0.0

    # Delete one and verify counts drop
    del_resp = client.delete(f"/datasets/{name}/recordings/{clip_neg}")
    assert del_resp.status_code == 200
    after_delete = client.get(f"/datasets/{name}/metrics").json()
    assert after_delete["clip_count"] == 2
    assert after_delete["negatives"] == 0

    # Restore and see counts back
    restore_resp = client.post(f"/datasets/{name}/recordings/{clip_neg}/restore")
    assert restore_resp.status_code == 200
    after_restore = client.get(f"/datasets/{name}/metrics").json()
    assert after_restore["clip_count"] == 3
    assert after_restore["negatives"] == 1

    # Patch label and verify redistribution
    patch_resp = client.patch(
        f"/datasets/{name}/recordings/{clip_noise}",
        json={"label": "positive"},
    )
    assert patch_resp.status_code == 200
    after_patch = client.get(f"/datasets/{name}/metrics").json()
    assert after_patch["positives"] == 2
    assert after_patch["noise"] == 0
