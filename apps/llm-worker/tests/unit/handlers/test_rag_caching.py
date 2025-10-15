"""Tests for RAG handler caching and metrics functionality."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from llm_worker.handlers.rag import RAGContext, RAGHandler


@pytest.fixture
def rag_handler():
    """Create RAG handler with short cache TTL for testing."""
    return RAGHandler(memory_query_topic="memory/query", cache_ttl=2)


@pytest.fixture
def mock_mqtt_client():
    """Create mock MQTT client."""
    client = MagicMock()
    mqtt_wrapper = MagicMock()
    mqtt_wrapper.publish_event = AsyncMock()
    return mqtt_wrapper, client


@pytest.mark.asyncio
async def test_cache_key_generation(rag_handler):
    """Test that cache keys are generated consistently."""
    key1 = rag_handler._generate_cache_key(
        prompt="test query",
        top_k=5,
        max_tokens=1000,
        include_context=True,
        context_window=1,
        retrieval_strategy="hybrid",
    )

    key2 = rag_handler._generate_cache_key(
        prompt="test query",
        top_k=5,
        max_tokens=1000,
        include_context=True,
        context_window=1,
        retrieval_strategy="hybrid",
    )

    # Same parameters should generate same key
    assert key1 == key2

    # Different parameters should generate different key
    key3 = rag_handler._generate_cache_key(
        prompt="different query",
        top_k=5,
        max_tokens=1000,
        include_context=True,
        context_window=1,
        retrieval_strategy="hybrid",
    )
    assert key1 != key3


@pytest.mark.asyncio
async def test_cache_add_and_retrieve(rag_handler):
    """Test adding and retrieving from cache."""
    cache_key = "test_cache_key"
    test_context = RAGContext(
        content="test content", token_count=100, truncated=False, strategy_used="hybrid"
    )

    # Add to cache
    rag_handler._add_to_cache(cache_key, test_context)

    # Should be retrievable
    retrieved = rag_handler._get_from_cache(cache_key)
    assert retrieved is not None
    assert retrieved.content == "test content"
    assert retrieved.token_count == 100


@pytest.mark.asyncio
async def test_cache_expiration(rag_handler):
    """Test that cache entries expire after TTL."""
    cache_key = "test_expiring_key"
    test_context = RAGContext(
        content="expiring content", token_count=50, truncated=False, strategy_used="hybrid"
    )

    # Add to cache
    rag_handler._add_to_cache(cache_key, test_context)

    # Should be retrievable immediately
    retrieved = rag_handler._get_from_cache(cache_key)
    assert retrieved is not None

    # Wait for expiration (TTL is 2 seconds in fixture)
    await asyncio.sleep(2.5)

    # Should now be expired
    retrieved = rag_handler._get_from_cache(cache_key)
    assert retrieved is None


@pytest.mark.asyncio
async def test_cache_size_limit(rag_handler):
    """Test that cache is pruned when it exceeds size limit."""
    # Add 105 entries (limit is 100)
    for i in range(105):
        cache_key = f"key_{i}"
        context = RAGContext(
            content=f"content_{i}", token_count=10, truncated=False, strategy_used="hybrid"
        )
        rag_handler._add_to_cache(cache_key, context)

    # Cache should be pruned to 100 entries
    assert len(rag_handler._cache) == 100

    # Oldest entries should be removed (keys 0-4)
    assert rag_handler._get_from_cache("key_0") is None
    assert rag_handler._get_from_cache("key_4") is None

    # Newer entries should still exist
    assert rag_handler._get_from_cache("key_100") is not None
    assert rag_handler._get_from_cache("key_104") is not None


@pytest.mark.asyncio
async def test_metrics_initialization(rag_handler):
    """Test that metrics are initialized correctly."""
    metrics = rag_handler.get_metrics()

    assert metrics["queries_total"] == 0
    assert metrics["queries_success"] == 0
    assert metrics["queries_timeout"] == 0
    assert metrics["queries_error"] == 0
    assert metrics["cache_hits"] == 0
    assert metrics["cache_misses"] == 0
    assert metrics["cache_hit_rate"] == 0.0
    assert metrics["success_rate"] == 0.0


@pytest.mark.asyncio
async def test_metrics_tracking(rag_handler, mock_mqtt_client):
    """Test that metrics are tracked correctly during queries."""
    mqtt_wrapper, client = mock_mqtt_client

    # Mock the memory results to resolve the query
    async def mock_handle_results():
        await asyncio.sleep(0.1)
        rag_handler.handle_results(
            {
                "correlate": "test_corr_1",
                "results": [{"document": {"text": "test"}, "context_type": "target"}],
                "total_tokens": 100,
                "truncated": False,
                "strategy_used": "hybrid",
            }
        )

    # Start background task to resolve the query
    asyncio.create_task(mock_handle_results())

    # Execute query
    await rag_handler.query(
        mqtt_client=mqtt_wrapper,
        client=client,
        prompt="test query",
        top_k=5,
        correlation_id="test_corr_1",
        use_cache=True,
    )

    # Check metrics
    metrics = rag_handler.get_metrics()
    assert metrics["queries_total"] == 1
    assert metrics["queries_success"] == 1
    assert metrics["cache_misses"] == 1  # First query is cache miss
    assert metrics["tokens_retrieved_sum"] == 100


@pytest.mark.asyncio
async def test_cache_hit_metrics(rag_handler, mock_mqtt_client):
    """Test that cache hits are tracked in metrics."""
    mqtt_wrapper, client = mock_mqtt_client

    # Pre-populate cache
    cache_key = rag_handler._generate_cache_key(
        prompt="cached query",
        top_k=5,
        max_tokens=None,
        include_context=False,
        context_window=1,
        retrieval_strategy="hybrid",
    )
    cached_context = RAGContext(
        content="cached content", token_count=50, truncated=False, strategy_used="hybrid"
    )
    rag_handler._add_to_cache(cache_key, cached_context)

    # Query with same parameters (should hit cache)
    result = await rag_handler.query(
        mqtt_client=mqtt_wrapper,
        client=client,
        prompt="cached query",
        top_k=5,
        correlation_id="test_corr_2",
        use_cache=True,
    )

    # Verify cache hit
    assert result.content == "cached content"

    # Check metrics
    metrics = rag_handler.get_metrics()
    assert metrics["queries_total"] == 1
    assert metrics["cache_hits"] == 1
    assert metrics["cache_hit_rate"] == 1.0


@pytest.mark.asyncio
async def test_clear_cache(rag_handler):
    """Test clearing the cache."""
    # Add some entries
    for i in range(5):
        cache_key = f"key_{i}"
        context = RAGContext(
            content=f"content_{i}", token_count=10, truncated=False, strategy_used="hybrid"
        )
        rag_handler._add_to_cache(cache_key, context)

    assert len(rag_handler._cache) == 5

    # Clear cache
    cleared = rag_handler.clear_cache()

    assert cleared == 5
    assert len(rag_handler._cache) == 0


@pytest.mark.asyncio
async def test_query_timeout_metrics(rag_handler, mock_mqtt_client):
    """Test that timeouts are tracked in metrics."""
    mqtt_wrapper, client = mock_mqtt_client

    # Don't resolve the query - let it timeout
    result = await rag_handler.query(
        mqtt_client=mqtt_wrapper,
        client=client,
        prompt="timeout query",
        top_k=5,
        correlation_id="test_timeout",
        use_cache=False,
    )

    # Should return empty context on timeout
    assert result.content == ""
    assert result.token_count == 0

    # Check metrics
    metrics = rag_handler.get_metrics()
    assert metrics["queries_total"] == 1
    assert metrics["queries_timeout"] == 1
    assert metrics["timeout_rate"] == 1.0


@pytest.mark.asyncio
async def test_cache_disabled_query(rag_handler, mock_mqtt_client):
    """Test that queries with use_cache=False don't cache."""
    mqtt_wrapper, client = mock_mqtt_client

    # Mock the memory results
    async def mock_handle_results():
        await asyncio.sleep(0.1)
        rag_handler.handle_results(
            {
                "correlate": "no_cache_corr",
                "results": [{"document": {"text": "uncached"}, "context_type": "target"}],
                "total_tokens": 75,
                "truncated": False,
                "strategy_used": "hybrid",
            }
        )

    asyncio.create_task(mock_handle_results())

    # Execute query with caching disabled
    result = await rag_handler.query(
        mqtt_client=mqtt_wrapper,
        client=client,
        prompt="no cache query",
        top_k=5,
        correlation_id="no_cache_corr",
        use_cache=False,
    )

    # Result should be returned but not cached
    assert result.token_count == 75

    # Cache should be empty
    assert len(rag_handler._cache) == 0

    # Metrics should not track cache operations
    metrics = rag_handler.get_metrics()
    assert metrics["cache_hits"] == 0
    assert metrics["cache_misses"] == 0
