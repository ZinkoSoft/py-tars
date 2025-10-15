from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

import types

if "sentence_transformers" not in sys.modules:
    sentence_transformers_stub = types.ModuleType("sentence_transformers")

    class _PlaceholderSentenceTransformer:  # pragma: no cover - fallback stub
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def encode(
            self, texts, show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True
        ):
            import numpy as np

            return np.zeros((len(list(texts)), 4), dtype=np.float32)

    sentence_transformers_stub.SentenceTransformer = _PlaceholderSentenceTransformer
    sys.modules["sentence_transformers"] = sentence_transformers_stub

from tars.contracts.envelope import Envelope  # type: ignore[import]
from tars.contracts.v1.memory import (  # type: ignore[import]
    EVENT_TYPE_CHARACTER_RESULT,
    CharacterGetRequest,
    CharacterSnapshot,
)

import memory_worker.service as service  # type: ignore[import]


class DummySentenceTransformer:
    def __init__(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - init is trivial
        self.calls: list[Any] = []

    def encode(
        self, texts, show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True
    ):
        # Return deterministic embeddings without requiring the real model download
        import numpy as np

        return np.ones((len(list(texts)), 4), dtype=np.float32)


class StubHyperDB:
    def __init__(
        self, *args: Any, **kwargs: Any
    ) -> None:  # pragma: no cover - initialization trivial
        self.documents: list[Any] = []
        self.vectors = None

    def load(self, path: str) -> bool:
        return False

    def add(self, docs):
        self.documents.extend(docs)

    def save(self, path: str) -> None:
        return None

    def query(self, query_text: str, top_k: int | None = None):
        return []

    def _doc_to_text(self, doc: Any) -> str:
        return str(doc)

    def _ensure_bm25(self) -> None:
        return None


class StubClient:
    def __init__(self) -> None:
        self.published: list[tuple[str, bytes, int, bool]] = []

    async def publish(self, topic: str, payload: bytes, qos: int = 0, retain: bool = False) -> None:
        self.published.append((topic, payload, qos, retain))


@pytest.fixture(autouse=True)
def _patch_dependencies(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(service, "SentenceTransformer", DummySentenceTransformer)
    monkeypatch.setattr(service, "HyperDB", StubHyperDB)
    monkeypatch.setattr(service, "MEMORY_DIR", str(tmp_path))
    monkeypatch.setattr(service, "MEMORY_FILE", "memory.pickle.gz")


def test_load_character_defaults_when_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(service, "CHARACTER_DIR", str(tmp_path))
    monkeypatch.setattr(service, "CHARACTER_NAME", "MissingCharacter")

    svc = service.MemoryService()
    assert svc.character.name == "MissingCharacter"
    assert svc.character.traits == {}
    assert svc.character.voice == {}


def test_load_character_from_toml(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    char_dir = tmp_path / "CharacterA"
    char_dir.mkdir()
    monkeypatch.setattr(service, "CHARACTER_DIR", str(tmp_path))
    monkeypatch.setattr(service, "CHARACTER_NAME", "CharacterA")

    toml = """
[info]
name = "Aurora"
description = "A helpful guide"
[traits]
energy = "calm"
[voice]
style = "warm"
"""
    (char_dir / "character.toml").write_text(toml)

    svc = service.MemoryService()
    assert svc.character.name == "Aurora"
    assert svc.character.traits == {"energy": "calm"}
    assert svc.character.voice == {"style": "warm"}
    assert svc.character.description == "A helpful guide"


@pytest.mark.asyncio
async def test_handle_char_get_returns_full_snapshot(monkeypatch: pytest.MonkeyPatch):
    svc = service.MemoryService()
    svc.character = CharacterSnapshot(name="Nova", traits={"kind": "very"})
    dummy_client = StubClient()

    await svc._handle_char_get(dummy_client, CharacterGetRequest(), None)

    assert len(dummy_client.published) == 1
    topic, payload, qos, retain = dummy_client.published[0]
    assert topic == service.TOPIC_CHAR_RESULT
    assert qos == 0
    assert retain is False

    envelope = Envelope.model_validate_json(payload)
    assert envelope.type == EVENT_TYPE_CHARACTER_RESULT
    data = envelope.data
    assert data["name"] == "Nova"
    assert data["traits"] == {"kind": "very"}


@pytest.mark.asyncio
async def test_handle_char_get_section(monkeypatch: pytest.MonkeyPatch):
    svc = service.MemoryService()
    svc.character = CharacterSnapshot(name="Nova", traits={"kind": "very"})
    dummy_client = StubClient()

    await svc._handle_char_get(dummy_client, CharacterGetRequest(section="traits"), None)

    envelope = Envelope.model_validate_json(dummy_client.published[0][1])
    payload = envelope.data
    assert payload["section"] == "traits"
    assert payload["value"] == {"kind": "very"}
