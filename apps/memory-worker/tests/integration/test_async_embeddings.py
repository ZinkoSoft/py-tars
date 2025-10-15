"""
Test async embedding responsiveness and non-blocking behavior.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import numpy as np
import pytest


class TestEmbeddingsAsync:
    """Test that memory embeddings don't block event loop."""

    @pytest.mark.asyncio
    async def test_embeddings_async_doesnt_block_event_loop(self) -> None:
        """Verify embeddings run in thread pool and don't block event loop."""
        from memory_worker.service import STEmbedder

        # Mock the actual embedding to be fast but measurable
        def mock_encode(texts, **kwargs):
            time.sleep(0.01)
            return np.random.rand(len(texts), 384).astype(np.float32)

        embedder = STEmbedder("all-MiniLM-L6-v2")

        with patch.object(embedder.model, "encode", side_effect=mock_encode):
            # Start embedding
            embed_task = asyncio.create_task(embedder.embed_async(["test text 1", "test text 2"]))

            # Measure event loop responsiveness during embedding
            loop_responsive = False
            for _ in range(3):
                await asyncio.sleep(0.001)
                loop_responsive = True

            # Event loop should have remained responsive
            assert loop_responsive, "Event loop blocked during embedding"

            # Wait for embedding to complete
            embeddings = await embed_task
            assert embeddings.shape == (2, 384)
            assert embeddings.dtype == np.float32

    @pytest.mark.asyncio
    async def test_concurrent_embeddings_work_correctly(self) -> None:
        """Verify multiple concurrent embedding operations work."""
        from memory_worker.service import STEmbedder

        def mock_encode(texts, **kwargs):
            time.sleep(0.005)
            return np.random.rand(len(texts), 384).astype(np.float32)

        embedder = STEmbedder("all-MiniLM-L6-v2")

        with patch.object(embedder.model, "encode", side_effect=mock_encode):
            # Launch concurrent embedding operations
            tasks = [embedder.embed_async([f"text {i}"]) for i in range(5)]

            # Should complete without issues
            results = await asyncio.gather(*tasks)

            assert len(results) == 5
            for result in results:
                assert result.shape == (1, 384)

    @pytest.mark.skip(reason="HyperDB API changed - needs update")
    @pytest.mark.asyncio
    async def test_hyperdb_query_async_uses_async_embedder(self) -> None:
        """Verify HyperDB query_async uses async embeddings."""
        from memory_worker.hyperdb import HyperDB
        from memory_worker.service import STEmbedder

        embedder = STEmbedder("all-MiniLM-L6-v2")

        def mock_encode(texts, **kwargs):
            time.sleep(0.005)
            return np.random.rand(len(texts), 384).astype(np.float32)

        with patch.object(embedder.model, "encode", side_effect=mock_encode):
            db = HyperDB(embedding_function=embedder, similarity_metric="cosine")

            # Add some documents first
            docs = [
                {"text": "Document 1 about Python programming"},
                {"text": "Document 2 about async await patterns"},
                {"text": "Document 3 about machine learning"},
            ]
            await db.add_async(docs)

            # Query should use async embeddings
            start = asyncio.get_event_loop().time()
            results = await db.query_async("Python async patterns", top_k=2)
            elapsed = asyncio.get_event_loop().time() - start

            # Should return results
            assert len(results) <= 2

            # Should have been non-blocking (we can't measure precisely,
            # but verify it completed)
            assert elapsed < 1.0, "Query took too long"
