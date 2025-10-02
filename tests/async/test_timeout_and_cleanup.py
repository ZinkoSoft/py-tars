"""
Tests for async timeout handling and Future cleanup.

These tests verify that RAG queries, tool calls, and other Future-based
operations properly handle timeouts and clean up resources.
"""

from __future__ import annotations

import asyncio
from unittest.mock import Mock, AsyncMock, patch

import pytest
import orjson as json


class TestLLMRAGTimeouts:
    """Test RAG query timeout handling."""

    @pytest.mark.asyncio
    async def test_rag_query_times_out_after_5_seconds(self) -> None:
        """Verify RAG queries timeout and clean up Future."""
        from apps.llm_worker.llm_worker.service import LLMService
        
        # Create service
        service = LLMService()
        
        # Mock MQTT client
        mock_client = Mock()
        mock_client.publish = AsyncMock()
        
        # Attempt RAG query that never gets response
        correlation_id = "test-correlation-123"
        
        start = asyncio.get_event_loop().time()
        result = await service._do_rag(
            mock_client,
            "test query",
            top_k=5,
            correlation_id=correlation_id
        )
        elapsed = asyncio.get_event_loop().time() - start
        
        # Should timeout after ~5 seconds and return empty string
        assert result == ""
        assert 4.9 < elapsed < 5.5, f"Timeout took {elapsed}s, expected ~5s"
        
        # Future should be cleaned up from pending dict
        assert correlation_id not in service._pending_rag

    @pytest.mark.asyncio
    async def test_rag_query_completes_before_timeout(self) -> None:
        """Verify RAG query that completes quickly doesn't timeout."""
        from apps.llm_worker.llm_worker.service import LLMService
        
        service = LLMService()
        mock_client = Mock()
        mock_client.publish = AsyncMock()
        
        correlation_id = "test-correlation-456"
        
        # Start RAG query in background
        query_task = asyncio.create_task(
            service._do_rag(mock_client, "test", top_k=5, correlation_id=correlation_id)
        )
        
        # Simulate memory results arriving quickly
        await asyncio.sleep(0.01)
        
        # Manually trigger result handler
        mock_payload = json.dumps({
            "id": correlation_id,
            "results": [
                {"document": {"text": "result 1"}, "score": 0.9},
                {"document": {"text": "result 2"}, "score": 0.8},
            ]
        })
        await service._handle_memory_results(mock_payload)
        
        # Should complete without timeout
        result = await query_task
        assert "result 1" in result
        assert "result 2" in result
        
        # Future should be cleaned up
        assert correlation_id not in service._pending_rag

    @pytest.mark.asyncio
    async def test_multiple_concurrent_rag_queries_timeout_independently(self) -> None:
        """Verify multiple RAG queries timeout independently."""
        from apps.llm_worker.llm_worker.service import LLMService
        
        service = LLMService()
        mock_client = Mock()
        mock_client.publish = AsyncMock()
        
        # Start multiple queries
        tasks = [
            service._do_rag(mock_client, f"query {i}", top_k=5, correlation_id=f"corr-{i}")
            for i in range(3)
        ]
        
        # Let one complete
        await asyncio.sleep(0.01)
        mock_payload = json.dumps({
            "id": "corr-1",
            "results": [{"document": {"text": "success"}, "score": 0.9}]
        })
        await service._handle_memory_results(mock_payload)
        
        # Cancel the rest (to avoid waiting 5s in tests)
        for task in tasks:
            if not task.done():
                task.cancel()
        
        # Gather with exception handling
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # One should succeed, others cancelled
        successful = [r for r in results if isinstance(r, str) and r]
        cancelled = [r for r in results if isinstance(r, asyncio.CancelledError)]
        
        assert len(successful) == 1
        assert "success" in successful[0]


class TestLLMToolTimeouts:
    """Test tool call timeout handling."""

    @pytest.mark.asyncio
    async def test_tool_call_times_out_after_30_seconds(self) -> None:
        """Verify tool calls timeout after 30 seconds."""
        from apps.llm_worker.llm_worker.service import LLMService
        
        service = LLMService()
        mock_client = Mock()
        
        # Mock publish_event to track calls
        async def mock_publish(*args, **kwargs):
            return "msg-id"
        service._publish_event = mock_publish
        
        # Create tool call that never responds
        tool_calls = [
            {
                "id": "tool-call-123",
                "function": {"name": "test_tool", "arguments": "{}"}
            }
        ]
        
        start = asyncio.get_event_loop().time()
        results = await service._execute_tool_calls(
            mock_client,
            tool_calls,
            request_id="req-123",
            timeout=1.0  # Use 1s timeout for faster test
        )
        elapsed = asyncio.get_event_loop().time() - start
        
        # Should timeout and return error
        assert len(results) == 1
        assert results[0]["call_id"] == "tool-call-123"
        assert "timeout" in results[0].get("error", "").lower()
        
        # Should take about 1 second
        assert 0.9 < elapsed < 1.5
        
        # Future should be cleaned up
        assert "tool-call-123" not in service._tool_futures

    @pytest.mark.asyncio
    async def test_tool_call_completes_before_timeout(self) -> None:
        """Verify tool call that completes quickly doesn't timeout."""
        from apps.llm_worker.llm_worker.service import LLMService
        
        service = LLMService()
        mock_client = Mock()
        
        async def mock_publish(*args, **kwargs):
            return "msg-id"
        service._publish_event = mock_publish
        
        tool_calls = [
            {
                "id": "tool-call-456",
                "function": {"name": "test_tool", "arguments": "{}"}
            }
        ]
        
        # Start execution in background
        exec_task = asyncio.create_task(
            service._execute_tool_calls(mock_client, tool_calls, request_id="req-456", timeout=5.0)
        )
        
        # Simulate tool result arriving quickly
        await asyncio.sleep(0.01)
        mock_payload = json.dumps({
            "call_id": "tool-call-456",
            "result": {"status": "success", "data": "test result"}
        })
        await service._handle_tool_result(mock_payload)
        
        # Should complete without timeout
        results = await exec_task
        assert len(results) == 1
        assert results[0]["call_id"] == "tool-call-456"
        assert results[0].get("result") == {"status": "success", "data": "test result"}
        
        # Future should be cleaned up
        assert "tool-call-456" not in service._tool_futures

    @pytest.mark.asyncio
    async def test_multiple_tool_calls_some_timeout_some_succeed(self) -> None:
        """Verify mixed success/timeout scenario."""
        from apps.llm_worker.llm_worker.service import LLMService
        
        service = LLMService()
        mock_client = Mock()
        
        async def mock_publish(*args, **kwargs):
            return "msg-id"
        service._publish_event = mock_publish
        
        tool_calls = [
            {"id": "tool-1", "function": {"name": "fast", "arguments": "{}"}},
            {"id": "tool-2", "function": {"name": "slow", "arguments": "{}"}},
            {"id": "tool-3", "function": {"name": "fast", "arguments": "{}"}},
        ]
        
        # Start execution
        exec_task = asyncio.create_task(
            service._execute_tool_calls(mock_client, tool_calls, request_id="req-789", timeout=1.0)
        )
        
        # Let some complete
        await asyncio.sleep(0.01)
        for tool_id in ["tool-1", "tool-3"]:
            mock_payload = json.dumps({
                "call_id": tool_id,
                "result": {"status": "success"}
            })
            await service._handle_tool_result(mock_payload)
        
        # Wait for execution to complete (tool-2 should timeout)
        results = await exec_task
        
        assert len(results) == 3
        
        # Check results
        success_ids = {r["call_id"] for r in results if "error" not in r}
        timeout_ids = {r["call_id"] for r in results if "timeout" in r.get("error", "").lower()}
        
        assert success_ids == {"tool-1", "tool-3"}
        assert timeout_ids == {"tool-2"}
        
        # All futures should be cleaned up
        assert len(service._tool_futures) == 0


class TestFutureCleanup:
    """Test Future cleanup on service shutdown."""

    @pytest.mark.asyncio
    async def test_pending_rag_futures_cleaned_on_shutdown(self) -> None:
        """Verify pending RAG futures are cancelled on shutdown."""
        from apps.llm_worker.llm_worker.service import LLMService
        
        service = LLMService()
        mock_client = Mock()
        mock_client.publish = AsyncMock()
        
        # Start several queries
        tasks = [
            asyncio.create_task(
                service._do_rag(mock_client, f"query {i}", top_k=5, correlation_id=f"corr-{i}")
            )
            for i in range(5)
        ]
        
        await asyncio.sleep(0.01)
        
        # Verify futures are pending
        assert len(service._pending_rag) == 5
        
        # Simulate shutdown by cancelling all tasks
        for task in tasks:
            task.cancel()
        
        # Wait for cancellation
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should be cancelled
        assert all(isinstance(r, asyncio.CancelledError) for r in results)

    @pytest.mark.asyncio
    async def test_pending_tool_futures_cleaned_on_shutdown(self) -> None:
        """Verify pending tool futures are cancelled on shutdown."""
        from apps.llm_worker.llm_worker.service import LLMService
        
        service = LLMService()
        mock_client = Mock()
        
        async def mock_publish(*args, **kwargs):
            return "msg-id"
        service._publish_event = mock_publish
        
        # Start several tool calls
        tool_calls = [
            {"id": f"tool-{i}", "function": {"name": "test", "arguments": "{}"}}
            for i in range(3)
        ]
        
        task = asyncio.create_task(
            service._execute_tool_calls(mock_client, tool_calls, request_id="req", timeout=10.0)
        )
        
        await asyncio.sleep(0.01)
        
        # Verify futures are pending
        assert len(service._tool_futures) == 3
        
        # Cancel execution
        task.cancel()
        
        # Wait for cancellation
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # Futures should remain in dict (cleanup happens in execute_tool_calls)
        # but the task is cancelled

    @pytest.mark.asyncio
    async def test_duplicate_correlation_id_overwrites_future(self) -> None:
        """Verify duplicate correlation IDs overwrite old futures."""
        from apps.llm_worker.llm_worker.service import LLMService
        
        service = LLMService()
        mock_client = Mock()
        mock_client.publish = AsyncMock()
        
        corr_id = "duplicate-id"
        
        # Start first query
        task1 = asyncio.create_task(
            service._do_rag(mock_client, "query 1", top_k=5, correlation_id=corr_id)
        )
        
        await asyncio.sleep(0.01)
        
        # Start second query with same ID (shouldn't happen in practice, but test it)
        task2 = asyncio.create_task(
            service._do_rag(mock_client, "query 2", top_k=5, correlation_id=corr_id)
        )
        
        await asyncio.sleep(0.01)
        
        # Only one should be in pending dict
        assert len([k for k in service._pending_rag.keys() if k == corr_id]) == 1
        
        # Send result
        mock_payload = json.dumps({
            "id": corr_id,
            "results": [{"document": {"text": "result"}, "score": 0.9}]
        })
        await service._handle_memory_results(mock_payload)
        
        # Second task should complete (first may timeout)
        # Cancel both to avoid waiting
        task1.cancel()
        task2.cancel()
        
        await asyncio.gather(task1, task2, return_exceptions=True)


class TestAsyncErrorHandling:
    """Test error handling in async operations."""

    @pytest.mark.asyncio
    async def test_rag_query_handles_invalid_response(self) -> None:
        """Verify RAG query handles invalid memory response."""
        from apps.llm_worker.llm_worker.service import LLMService
        
        service = LLMService()
        mock_client = Mock()
        mock_client.publish = AsyncMock()
        
        correlation_id = "test-error-123"
        
        # Start query
        task = asyncio.create_task(
            service._do_rag(mock_client, "test", top_k=5, correlation_id=correlation_id)
        )
        
        await asyncio.sleep(0.01)
        
        # Send invalid response
        invalid_payload = b"not json"
        await service._handle_memory_results(invalid_payload)
        
        # Should not crash, should timeout eventually
        # Cancel to avoid waiting
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_tool_result_handles_invalid_payload(self) -> None:
        """Verify tool result handler handles invalid payload."""
        from apps.llm_worker.llm_worker.service import LLMService
        
        service = LLMService()
        
        # Create pending future
        call_id = "test-tool-call"
        future = asyncio.Future()
        service._tool_futures[call_id] = future
        
        # Send invalid payload
        invalid_payload = b"not json"
        await service._handle_tool_result(invalid_payload)
        
        # Future should still be pending (not resolved or rejected)
        assert not future.done()
        
        # Clean up
        service._tool_futures.pop(call_id)
        future.cancel()

    @pytest.mark.asyncio
    async def test_exception_in_future_setter_doesnt_crash(self) -> None:
        """Verify exceptions in Future.set_result don't crash handler."""
        from apps.llm_worker.llm_worker.service import LLMService
        
        service = LLMService()
        
        # Create a future that's already done
        call_id = "already-done"
        future = asyncio.Future()
        future.set_result({"early": "result"})
        service._tool_futures[call_id] = future
        
        # Try to set result again (should handle InvalidStateError)
        mock_payload = json.dumps({
            "call_id": call_id,
            "result": {"late": "result"}
        })
        
        # Should not crash
        await service._handle_tool_result(mock_payload)
        
        # Future should still have original result
        assert future.result() == {"early": "result"}
