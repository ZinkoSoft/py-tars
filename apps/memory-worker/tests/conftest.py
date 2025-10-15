"""
Shared pytest fixtures for memory-worker tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pytest


class DummyEmbedder:
    """Simple embedder for testing that returns sequential float arrays."""

    def __call__(self, texts: Iterable[str]) -> np.ndarray:
        arr = np.arange(len(texts) * 4, dtype=np.float32).reshape(len(texts), 4)
        return arr

    def encode(
        self,
        texts: Iterable[str],
        show_progress_bar: bool = False,
        convert_to_numpy: bool = True,
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        """Compatible with SentenceTransformer interface."""
        return self(texts)


@pytest.fixture
def dummy_embedder() -> DummyEmbedder:
    """Provide a simple embedder for tests."""
    return DummyEmbedder()


@pytest.fixture
def sample_documents() -> list[dict[str, str]]:
    """Provide sample conversation documents for testing."""
    return [
        {"user_input": "Hello", "bot_response": "Hi there!"},
        {"user_input": "Goodbye", "bot_response": "See you later!"},
        {"user_input": "How are you?", "bot_response": "I'm doing great, thanks!"},
    ]


@pytest.fixture
def sample_texts() -> list[str]:
    """Provide simple text samples for testing."""
    return ["alpha", "beta", "gamma", "delta"]


@pytest.fixture
def temp_memory_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for memory storage."""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    return memory_dir
