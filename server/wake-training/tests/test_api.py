import os
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from wake_training.main import app
from wake_training.config import Settings

@pytest.fixture(scope="session")
def temp_data_root():
    tmpdir = tempfile.mkdtemp(prefix="waketraining-test-")
    yield Path(tmpdir)
    shutil.rmtree(tmpdir)

@pytest.fixture(autouse=True)
def patch_env(monkeypatch, temp_data_root):
    monkeypatch.setenv("WAKE_TRAINING_DATA_DIR", str(temp_data_root))
    yield

@pytest.fixture
def client():
    return TestClient(app)

def test_health(client, temp_data_root):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert str(temp_data_root) in str(data["data_root"])

def test_list_datasets_empty(client):
    resp = client.get("/datasets")
    assert resp.status_code == 200
    assert resp.json() == []

def test_create_and_get_dataset(client):
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

def test_get_dataset_not_found(client):
    resp = client.get("/datasets/doesnotexist")
    assert resp.status_code == 404
