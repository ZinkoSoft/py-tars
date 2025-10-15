"""Tests for RAGHandler."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from llm_worker.handlers.rag import RAGHandler


@pytest.fixture
def rag_handler():
    """Create a RAGHandler instance."""
    return RAGHandler(memory_query_topic="memory/query")


@pytest.fixture
def mock_client():
    """Create a mocked MQTT client."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_mqtt_client():
    """Create a mocked MQTT client wrapper."""
    mqtt_wrapper = MagicMock()
    mqtt_wrapper.publish_event = AsyncMock()
    return mqtt_wrapper


@pytest.mark.asyncio
async def test_query_successful(rag_handler, mock_mqtt_client, mock_client):
    """Test successful RAG query with results."""
    correlation_id = "test-corr-1"

    # Start query in background
    query_task = asyncio.create_task(
        rag_handler.query(
            mock_mqtt_client, mock_client, "What is Python?", 5, correlation_id, use_cache=False
        )
    )

    # Wait a bit for query to be published
    await asyncio.sleep(0.1)

    # Simulate results arriving
    results_data = {
        "id": correlation_id,
        "results": [
            {"document": {"text": "Python is a programming language"}, "context_type": "target"},
            {"document": {"text": "Python is easy to learn"}, "context_type": "target"},
        ],
        "total_tokens": 50,
        "truncated": False,
        "strategy_used": "hybrid",
    }
    rag_handler.handle_results(results_data)

    # Get result (now returns RAGContext object)
    context = await query_task
    assert "Python is a programming language" in context.content
    assert "Python is easy to learn" in context.content
    assert correlation_id not in rag_handler._pending_queries


@pytest.mark.asyncio
async def test_query_timeout(rag_handler, mock_mqtt_client, mock_client):
    """Test RAG query timeout."""
    correlation_id = "test-corr-timeout"

    # Query should timeout after 5 seconds
    context = await rag_handler.query(
        mock_mqtt_client, mock_client, "test query", 5, correlation_id, use_cache=False
    )

    assert context.content == ""
    assert context.token_count == 0
    assert correlation_id not in rag_handler._pending_queries


@pytest.mark.asyncio
async def test_query_publishes_correctly(rag_handler, mock_mqtt_client, mock_client):
    """Test that query publishes correct payload."""
    correlation_id = "test-corr-2"

    # Start query and immediately resolve to avoid timeout
    query_task = asyncio.create_task(
        rag_handler.query(
            mock_mqtt_client, mock_client, "test prompt", 3, correlation_id, use_cache=False
        )
    )
    await asyncio.sleep(0.05)

    # Resolve immediately
    rag_handler.handle_results(
        {
            "id": correlation_id,
            "results": [],
            "total_tokens": 0,
            "truncated": False,
            "strategy_used": "hybrid",
        }
    )
    await query_task

    # Verify publish_event was called
    mock_mqtt_client.publish_event.assert_called_once()


@pytest.mark.asyncio
async def test_handle_results_with_correlate_field(rag_handler, mock_mqtt_client, mock_client):
    """Test handle_results using 'correlate' field."""
    correlation_id = "test-corr-3"

    query_task = asyncio.create_task(
        rag_handler.query(mock_mqtt_client, mock_client, "test", 5, correlation_id, use_cache=False)
    )
    await asyncio.sleep(0.05)

    # Use 'correlate' instead of 'id'
    results_data = {
        "correlate": correlation_id,
        "results": [{"document": {"text": "Result text"}, "context_type": "target"}],
        "total_tokens": 10,
        "truncated": False,
        "strategy_used": "hybrid",
    }
    rag_handler.handle_results(results_data)

    context = await query_task
    assert "Result text" in context.content


@pytest.mark.asyncio
async def test_handle_results_no_matching_query(rag_handler):
    """Test handle_results with no matching pending query."""
    results_data = {
        "id": "unknown-id",
        "results": [{"document": {"text": "Result"}}],
    }

    # Should not raise any errors
    rag_handler.handle_results(results_data)


@pytest.mark.asyncio
async def test_handle_results_already_resolved(rag_handler, mock_mqtt_client, mock_client):
    """Test handle_results when future already resolved."""
    correlation_id = "test-corr-4"

    query_task = asyncio.create_task(
        rag_handler.query(mock_mqtt_client, mock_client, "test", 5, correlation_id, use_cache=False)
    )
    await asyncio.sleep(0.05)

    # Resolve twice
    rag_handler.handle_results(
        {
            "id": correlation_id,
            "results": [],
            "total_tokens": 0,
            "truncated": False,
            "strategy_used": "hybrid",
        }
    )
    rag_handler.handle_results(
        {
            "id": correlation_id,
            "results": [],
            "total_tokens": 0,
            "truncated": False,
            "strategy_used": "hybrid",
        }
    )  # Second call should be no-op

    await query_task


def test_handle_results_empty_results(rag_handler):
    """Test handle_results with empty results list."""
    from llm_worker.handlers.rag import RAGContext

    correlation_id = "test-corr-5"
    future = asyncio.Future()
    rag_handler._pending_queries[correlation_id] = future

    results_data = {
        "id": correlation_id,
        "results": [],
        "total_tokens": 0,
        "truncated": False,
        "strategy_used": "hybrid",
    }
    rag_handler.handle_results(results_data)

    assert future.done()
    result = future.result()
    assert isinstance(result, RAGContext)
    assert result.content == ""


def test_handle_results_malformed_documents(rag_handler):
    """Test handle_results with malformed document structure."""
    from llm_worker.handlers.rag import RAGContext

    correlation_id = "test-corr-6"
    future = asyncio.Future()
    rag_handler._pending_queries[correlation_id] = future

    results_data = {
        "id": correlation_id,
        "results": [
            {"document": {"text": "Good text"}, "context_type": "target"},
            {"document": {}, "context_type": "target"},  # No text field
            {"context_type": "target"},  # No document field
        ],
        "total_tokens": 10,
        "truncated": False,
        "strategy_used": "hybrid",
    }
    rag_handler.handle_results(results_data)

    assert future.done()
    context = future.result()
    assert isinstance(context, RAGContext)
    assert "Good text" in context.content


def test_handle_results_json_serializable_doc(rag_handler):
    """Test handle_results with complex document (falls back to JSON)."""
    from llm_worker.handlers.rag import RAGContext

    correlation_id = "test-corr-7"
    future = asyncio.Future()
    rag_handler._pending_queries[correlation_id] = future

    results_data = {
        "id": correlation_id,
        "results": [
            {"document": {"key": "value", "nested": {"data": 123}}, "context_type": "target"},
        ],
        "total_tokens": 5,
        "truncated": False,
        "strategy_used": "hybrid",
    }
    rag_handler.handle_results(results_data)

    assert future.done()
    context = future.result()
    assert isinstance(context, RAGContext)
    # Should contain extracted text from document
    assert "value" in context.content or "123" in context.content


@pytest.mark.asyncio
async def test_multiple_concurrent_queries(rag_handler, mock_mqtt_client, mock_client):
    """Test multiple concurrent RAG queries."""
    # Start multiple queries
    query1 = asyncio.create_task(
        rag_handler.query(mock_mqtt_client, mock_client, "query1", 5, "corr-1", use_cache=False)
    )
    query2 = asyncio.create_task(
        rag_handler.query(mock_mqtt_client, mock_client, "query2", 5, "corr-2", use_cache=False)
    )
    query3 = asyncio.create_task(
        rag_handler.query(mock_mqtt_client, mock_client, "query3", 5, "corr-3", use_cache=False)
    )

    await asyncio.sleep(0.05)

    # Resolve out of order
    rag_handler.handle_results(
        {
            "id": "corr-2",
            "results": [{"document": {"text": "Result 2"}, "context_type": "target"}],
            "total_tokens": 5,
            "truncated": False,
            "strategy_used": "hybrid",
        }
    )
    rag_handler.handle_results(
        {
            "id": "corr-1",
            "results": [{"document": {"text": "Result 1"}, "context_type": "target"}],
            "total_tokens": 5,
            "truncated": False,
            "strategy_used": "hybrid",
        }
    )
    rag_handler.handle_results(
        {
            "id": "corr-3",
            "results": [{"document": {"text": "Result 3"}, "context_type": "target"}],
            "total_tokens": 5,
            "truncated": False,
            "strategy_used": "hybrid",
        }
    )

    result1 = await query1
    result2 = await query2
    result3 = await query3

    assert "Result 1" in result1.content
    assert "Result 2" in result2.content
    assert "Result 3" in result3.content
    assert len(rag_handler._pending_queries) == 0


@pytest.mark.asyncio
async def test_query_exception_cleanup(rag_handler, mock_mqtt_client, mock_client):
    """Test that pending query is cleaned up on exception."""
    correlation_id = "test-corr-error"

    # Make publish fail
    mock_mqtt_client.publish_event.side_effect = Exception("Network error")

    context = await rag_handler.query(
        mock_mqtt_client, mock_client, "test", 5, correlation_id, use_cache=False
    )

    assert context.content == ""
    assert context.token_count == 0
    assert correlation_id not in rag_handler._pending_queries


def test_handle_results_missing_correlation_id(rag_handler):
    """Test handle_results with missing correlation ID."""
    results_data = {"results": [{"document": {"text": "Result"}}]}

    # Should not raise errors
    rag_handler.handle_results(results_data)
