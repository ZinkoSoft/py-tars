from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import pytest

SRC_DIR = Path(__file__).resolve().parents[3] / "src"
if SRC_DIR.exists():
    src_path = str(SRC_DIR)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

from memory_worker.hyperdb import HyperConfig, HyperDB  # type: ignore[import]


class DummyEmbedder:
    def __call__(self, texts: Iterable[str]):
        arr = np.arange(len(texts) * 4, dtype=np.float32).reshape(len(texts), 4)
        return arr


def test_hyperdb_add_and_query_naive():
    embedder = DummyEmbedder()
    db = HyperDB(embedding_fn=embedder, cfg=HyperConfig(rag_strategy="naive", rerank_model=None))
    docs = [
        {"user_input": "Hello", "bot_response": "Hi"},
        {"user_input": "Goodbye", "bot_response": "See you"},
        {"user_input": "How are you?", "bot_response": "Great"},
    ]
    db.add(docs)

    results = db.query("hello", top_k=2)
    assert len(results) == 2
    # Should return tuples of (document, score)
    for doc, score in results:
        assert isinstance(doc, dict)
        assert isinstance(score, float)


def test_hyperdb_save_and_load_roundtrip(tmp_path: Path):
    embedder = DummyEmbedder()
    db = HyperDB(embedding_fn=embedder, cfg=HyperConfig(rag_strategy="naive", rerank_model=None))
    docs = ["alpha", "beta", "gamma"]
    db.add(docs)

    path = tmp_path / "memory.pickle.gz"
    db.save(str(path))

    restored = HyperDB(embedding_fn=embedder, cfg=HyperConfig(rag_strategy="naive", rerank_model=None))
    assert restored.load(str(path)) is True
    assert restored.documents == docs
    assert restored.vectors is not None
    assert restored.vectors.shape == (3, 4)


def test_hyperdb_query_empty_corpus_returns_empty():
    embedder = DummyEmbedder()
    db = HyperDB(embedding_fn=embedder, cfg=HyperConfig(rag_strategy="naive", rerank_model=None))
    assert db.query("anything") == []
