"""Tests for ToolExecutor."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import orjson as json
import pytest

from llm_worker.handlers.tools import ToolExecutor
from llm_worker.providers.base import LLMResult


@pytest.fixture
def tool_executor():
    """Create a ToolExecutor instance."""
    return ToolExecutor()


@pytest.fixture
def mock_mcp_client():
    """Create a mocked MCP client."""
    client = MagicMock()
    client.initialize_from_registry = AsyncMock()
    client.connect_to_server = AsyncMock()
    client.execute_tool = AsyncMock()
    return client


def test_initial_state(tool_executor):
    """Test initial state."""
    assert tool_executor.tools == []
    assert tool_executor._initialized is False


@pytest.mark.asyncio
async def test_load_tools_from_registry(tool_executor, mock_mcp_client):
    """Test loading tools from registry."""
    registry_payload = {
        "tools": [
            {
                "name": "get_weather",
                "description": "Get weather for city",
                "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
            },
            {
                "name": "search",
                "description": "Search the web",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
            },
        ]
    }
    
    with patch("llm_worker.handlers.tools.get_mcp_client", return_value=mock_mcp_client):
        await tool_executor.load_tools_from_registry(registry_payload)
    
    assert len(tool_executor.tools) == 2
    assert tool_executor.tools[0]["name"] == "get_weather"
    assert tool_executor._initialized is True
    mock_mcp_client.initialize_from_registry.assert_called_once_with(registry_payload)
    # Note: Servers connect on-demand, not during initialization


@pytest.mark.asyncio
async def test_load_tools_empty_registry(tool_executor, mock_mcp_client):
    """Test loading empty tools registry."""
    with patch("llm_worker.handlers.tools.get_mcp_client", return_value=mock_mcp_client):
        await tool_executor.load_tools_from_registry({"tools": []})
    
    assert tool_executor.tools == []
    assert tool_executor._initialized is False


@pytest.mark.asyncio
async def test_load_tools_error_handling(tool_executor, mock_mcp_client):
    """Test error handling during tool loading."""
    mock_mcp_client.initialize_from_registry.side_effect = Exception("Connection failed")
    
    with patch("llm_worker.handlers.tools.get_mcp_client", return_value=mock_mcp_client):
        await tool_executor.load_tools_from_registry({"tools": [{"name": "test"}]})
    
    # Should log error but not crash
    assert tool_executor.tools == [{"name": "test"}]


def test_extract_tool_calls_with_calls(tool_executor):
    """Test extracting tool calls from LLM result."""
    result = LLMResult(
        text="Using tool",
        tool_calls=[
            {"id": "call-1", "function": {"name": "get_weather", "arguments": '{"city":"Paris"}'}},
            {"id": "call-2", "function": {"name": "search", "arguments": '{"query":"Python"}'}},
        ],
    )
    
    calls = tool_executor.extract_tool_calls(result)
    assert len(calls) == 2
    assert calls[0]["id"] == "call-1"
    assert calls[1]["function"]["name"] == "search"


def test_extract_tool_calls_no_calls(tool_executor):
    """Test extracting when no tool calls present."""
    result = LLMResult(text="Just text response")
    calls = tool_executor.extract_tool_calls(result)
    assert calls == []


def test_extract_tool_calls_none(tool_executor):
    """Test extracting when tool_calls is None."""
    result = LLMResult(text="Response", tool_calls=None)
    calls = tool_executor.extract_tool_calls(result)
    assert calls == []


@pytest.mark.asyncio
async def test_execute_tool_calls_success(tool_executor, mock_mcp_client):
    """Test successful tool execution."""
    tool_executor._initialized = True
    mock_mcp_client.execute_tool.return_value = {"content": "Weather: Sunny"}
    
    tool_calls = [
        {"id": "call-1", "function": {"name": "get_weather", "arguments": '{"city":"Paris"}'}},
    ]
    
    with patch("llm_worker.handlers.tools.get_mcp_client", return_value=mock_mcp_client):
        results = await tool_executor.execute_tool_calls(tool_calls)
    
    assert len(results) == 1
    assert results[0]["call_id"] == "call-1"
    assert results[0]["content"] == "Weather: Sunny"
    mock_mcp_client.execute_tool.assert_called_once_with("get_weather", {"city": "Paris"})


@pytest.mark.asyncio
async def test_execute_tool_calls_error(tool_executor, mock_mcp_client):
    """Test tool execution with error response."""
    tool_executor._initialized = True
    mock_mcp_client.execute_tool.return_value = {"error": "City not found"}
    
    tool_calls = [
        {"id": "call-1", "function": {"name": "get_weather", "arguments": '{"city":"InvalidCity"}'}},
    ]
    
    with patch("llm_worker.handlers.tools.get_mcp_client", return_value=mock_mcp_client):
        results = await tool_executor.execute_tool_calls(tool_calls)
    
    assert len(results) == 1
    assert results[0]["call_id"] == "call-1"
    assert results[0]["error"] == "City not found"


@pytest.mark.asyncio
async def test_execute_tool_calls_exception(tool_executor, mock_mcp_client):
    """Test tool execution with exception."""
    tool_executor._initialized = True
    mock_mcp_client.execute_tool.side_effect = Exception("Network error")
    
    tool_calls = [
        {"id": "call-1", "function": {"name": "get_weather", "arguments": '{"city":"Paris"}'}},
    ]
    
    with patch("llm_worker.handlers.tools.get_mcp_client", return_value=mock_mcp_client):
        results = await tool_executor.execute_tool_calls(tool_calls)
    
    assert len(results) == 1
    assert results[0]["call_id"] == "call-1"
    assert "Network error" in results[0]["error"]


@pytest.mark.asyncio
async def test_execute_tool_calls_multiple(tool_executor, mock_mcp_client):
    """Test executing multiple tool calls."""
    tool_executor._initialized = True
    mock_mcp_client.execute_tool.side_effect = [
        {"content": "Weather: Sunny"},
        {"content": "Search results: ..."},
    ]
    
    tool_calls = [
        {"id": "call-1", "function": {"name": "get_weather", "arguments": '{"city":"Paris"}'}},
        {"id": "call-2", "function": {"name": "search", "arguments": '{"query":"Python"}'}},
    ]
    
    with patch("llm_worker.handlers.tools.get_mcp_client", return_value=mock_mcp_client):
        results = await tool_executor.execute_tool_calls(tool_calls)
    
    assert len(results) == 2
    assert results[0]["call_id"] == "call-1"
    assert results[1]["call_id"] == "call-2"


@pytest.mark.asyncio
async def test_execute_tool_calls_missing_id(tool_executor, mock_mcp_client):
    """Test tool call without ID is skipped."""
    tool_executor._initialized = True
    
    tool_calls = [
        {"function": {"name": "get_weather", "arguments": '{"city":"Paris"}'}},  # Missing id
    ]
    
    with patch("llm_worker.handlers.tools.get_mcp_client", return_value=mock_mcp_client):
        results = await tool_executor.execute_tool_calls(tool_calls)
    
    assert len(results) == 0


@pytest.mark.asyncio
async def test_execute_tool_calls_not_initialized(tool_executor):
    """Test executing tools when not initialized."""
    tool_calls = [
        {"id": "call-1", "function": {"name": "get_weather", "arguments": '{"city":"Paris"}'}},
    ]
    
    results = await tool_executor.execute_tool_calls(tool_calls)
    assert results == []


@pytest.mark.asyncio
async def test_execute_tool_calls_invalid_json(tool_executor, mock_mcp_client):
    """Test tool call with invalid JSON arguments."""
    tool_executor._initialized = True
    
    tool_calls = [
        {"id": "call-1", "function": {"name": "get_weather", "arguments": "invalid json"}},
    ]
    
    with patch("llm_worker.handlers.tools.get_mcp_client", return_value=mock_mcp_client):
        results = await tool_executor.execute_tool_calls(tool_calls)
    
    assert len(results) == 1
    assert "error" in results[0]

