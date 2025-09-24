import tempfile
import shutil
from pathlib import Path

import pytest

from wake_training.storage import DatasetStorage
from wake_training.models import DatasetCreateRequest

def make_storage(tmp_path: Path) -> DatasetStorage:
    return DatasetStorage(tmp_path)

@pytest.fixture
def temp_root():
    tmpdir = tempfile.mkdtemp(prefix="waketraining-storage-")
    yield Path(tmpdir)
    shutil.rmtree(tmpdir)

def test_create_and_list_dataset(temp_root):
    storage = make_storage(temp_root)
    req = DatasetCreateRequest(name="foo")
    detail = storage.create_dataset(req)
    assert detail.name == "foo"
    assert (temp_root / "datasets" / "foo").exists()
    # List
    summaries = storage.list_datasets()
    assert any(d.name == "foo" for d in summaries)
    # Get detail
    detail2 = storage.get_dataset("foo")
    assert detail2.name == "foo"
    # Not found
    with pytest.raises(FileNotFoundError):
        storage.get_dataset("bar")
    # Duplicate
    with pytest.raises(FileExistsError):
        storage.create_dataset(req)
