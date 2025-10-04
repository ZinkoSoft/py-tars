"""Tests for RAGHandler."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import orjson as json
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
    client.publish = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_query_successful(rag_handler, mock_client):
    """Test successful RAG query with results."""
    correlation_id = "test-corr-1"
    
    # Start query in background
    query_task = asyncio.create_task(
        rag_handler.query(mock_client, "What is Python?", 5, correlation_id)
    )
    
    # Wait a bit for query to be published
    await asyncio.sleep(0.1)
    
    # Simulate results arriving
    results_data = {
        "id": correlation_id,
        "results": [
            {"document": {"text": "Python is a programming language"}},
            {"document": {"text": "Python is easy to learn"}},
        ],
    }
    rag_handler.handle_results(results_data)
    
    # Get result
    context = await query_task
    assert "Python is a programming language" in context
    assert "Python is easy to learn" in context
    assert correlation_id not in rag_handler._pending_queries


@pytest.mark.asyncio
async def test_query_timeout(rag_handler, mock_client):
    """Test RAG query timeout."""
    correlation_id = "test-corr-timeout"
    
    # Query should timeout after 5 seconds
    context = await rag_handler.query(mock_client, "test query", 5, correlation_id)
    
    assert context == ""
    assert correlation_id not in rag_handler._pending_queries


@pytest.mark.asyncio
async def test_query_publishes_correctly(rag_handler, mock_client):
    """Test that query publishes correct payload."""
    correlation_id = "test-corr-2"
    
    # Start query and immediately resolve to avoid timeout
    query_task = asyncio.create_task(
        rag_handler.query(mock_client, "test prompt", 3, correlation_id)
    )
    await asyncio.sleep(0.05)
    
    # Resolve immediately
    rag_handler.handle_results({"id": correlation_id, "results": []})
    await query_task
    
    # Verify publish was called
    mock_client.publish.assert_called_once()
    call_args = mock_client.publish.call_args
    assert call_args[0][0] == "memory/query"
    
    payload = json.loads(call_args[0][1])
    assert payload["text"] == "test prompt"
    assert payload["top_k"] == 3
    assert payload["id"] == correlation_id


@pytest.mark.asyncio
async def test_handle_results_with_correlate_field(rag_handler, mock_client):
    """Test handle_results using 'correlate' field."""
    correlation_id = "test-corr-3"
    
    query_task = asyncio.create_task(
        rag_handler.query(mock_client, "test", 5, correlation_id)
    )
    await asyncio.sleep(0.05)
    
    # Use 'correlate' instead of 'id'
    results_data = {
        "correlate": correlation_id,
        "results": [{"document": {"text": "Result text"}}],
    }
    rag_handler.handle_results(results_data)
    
    context = await query_task
    assert "Result text" in context


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
async def test_handle_results_already_resolved(rag_handler, mock_client):
    """Test handle_results when future already resolved."""
    correlation_id = "test-corr-4"
    
    query_task = asyncio.create_task(
        rag_handler.query(mock_client, "test", 5, correlation_id)
    )
    await asyncio.sleep(0.05)
    
    # Resolve twice
    rag_handler.handle_results({"id": correlation_id, "results": []})
    rag_handler.handle_results({"id": correlation_id, "results": []})  # Second call should be no-op
    
    await query_task


def test_handle_results_empty_results(rag_handler):
    """Test handle_results with empty results list."""
    correlation_id = "test-corr-5"
    future = asyncio.Future()
    rag_handler._pending_queries[correlation_id] = future
    
    results_data = {"id": correlation_id, "results": []}
    rag_handler.handle_results(results_data)
    
    assert future.done()
    assert future.result() == ""


def test_handle_results_malformed_documents(rag_handler):
    """Test handle_results with malformed document structure."""
    correlation_id = "test-corr-6"
    future = asyncio.Future()
    rag_handler._pending_queries[correlation_id] = future
    
    results_data = {
        "id": correlation_id,
        "results": [
            {"document": {"text": "Good text"}},
            {"document": {}},  # No text field
            {},  # No document field
        ],
    }
    rag_handler.handle_results(results_data)
    
    assert future.done()
    context = future.result()
    assert "Good text" in context


def test_handle_results_json_serializable_doc(rag_handler):
    """Test handle_results with complex document (falls back to JSON)."""
    correlation_id = "test-corr-7"
    future = asyncio.Future()
    rag_handler._pending_queries[correlation_id] = future
    
    results_data = {
        "id": correlation_id,
        "results": [
            {"document": {"key": "value", "nested": {"data": 123}}},
        ],
    }
    rag_handler.handle_results(results_data)
    
    assert future.done()
    context = future.result()
    # Should contain JSON serialization
    assert "key" in context or "value" in context


@pytest.mark.asyncio
async def test_multiple_concurrent_queries(rag_handler, mock_client):
    """Test multiple concurrent RAG queries."""
    # Start multiple queries
    query1 = asyncio.create_task(rag_handler.query(mock_client, "query1", 5, "corr-1"))
    query2 = asyncio.create_task(rag_handler.query(mock_client, "query2", 5, "corr-2"))
    query3 = asyncio.create_task(rag_handler.query(mock_client, "query3", 5, "corr-3"))
    
    await asyncio.sleep(0.05)
    
    # Resolve out of order
    rag_handler.handle_results({"id": "corr-2", "results": [{"document": {"text": "Result 2"}}]})
    rag_handler.handle_results({"id": "corr-1", "results": [{"document": {"text": "Result 1"}}]})
    rag_handler.handle_results({"id": "corr-3", "results": [{"document": {"text": "Result 3"}}]})
    
    result1 = await query1
    result2 = await query2
    result3 = await query3
    
    assert "Result 1" in result1
    assert "Result 2" in result2
    assert "Result 3" in result3
    assert len(rag_handler._pending_queries) == 0


@pytest.mark.asyncio
async def test_query_exception_cleanup(rag_handler, mock_client):
    """Test that pending query is cleaned up on exception."""
    correlation_id = "test-corr-error"
    
    # Make publish fail
    mock_client.publish.side_effect = Exception("Network error")
    
    context = await rag_handler.query(mock_client, "test", 5, correlation_id)
    
    assert context == ""
    assert correlation_id not in rag_handler._pending_queries


def test_handle_results_missing_correlation_id(rag_handler):
    """Test handle_results with missing correlation ID."""
    results_data = {"results": [{"document": {"text": "Result"}}]}
    
    # Should not raise errors
    rag_handler.handle_results(results_data)
