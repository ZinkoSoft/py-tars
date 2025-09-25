from pathlib import Path

from fastapi.testclient import TestClient


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
