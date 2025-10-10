"""Tests for MessageRouter."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import orjson as json
import pytest

from llm_worker.handlers.message_router import MessageRouter
from tars.contracts.envelope import Envelope


@pytest.fixture
def mock_handlers():
    """Create mock handlers."""
    character_handler = MagicMock()
    character_handler.update_from_current = MagicMock()
    character_handler.update_section = MagicMock()
    character_handler.merge_update = MagicMock()
    character_handler.get_name = MagicMock(return_value="TARS")
    
    tool_handler = MagicMock()
    tool_handler.load_tools_from_registry = AsyncMock()
    
    rag_handler = MagicMock()
    rag_handler.handle_results = MagicMock()
    
    request_handler = MagicMock()
    request_handler.process_request = AsyncMock()
    
    return {
        "character": character_handler,
        "tool": tool_handler,
        "rag": rag_handler,
        "request": request_handler,
    }


@pytest.fixture
def router(mock_handlers):
    """Create MessageRouter with mock handlers."""
    return MessageRouter(
        character_handler=mock_handlers["character"],
        tool_handler=mock_handlers["tool"],
        rag_handler=mock_handlers["rag"],
        request_handler=mock_handlers["request"],
    )


@pytest.fixture
def mock_client():
    """Create mock MQTT client."""
    return MagicMock()


def create_message(topic: str, payload: bytes):
    """Create a mock MQTT message."""
    msg = MagicMock()
    msg.topic = topic
    msg.payload = payload
    return msg


@pytest.mark.asyncio
async def test_route_character_current(router, mock_client, mock_handlers):
    """Test routing character/current message."""
    character_data = {"name": "TARS", "description": "Robot"}
    message = create_message("system/character/current", json.dumps(character_data))
    
    await router.route_message(
        mock_client,
        message,
        character_current_topic="system/character/current",
        character_result_topic="character/result",
        tools_registry_topic="tools/registry",
        tools_result_topic="tools/result",
        memory_results_topic="memory/results",
        llm_request_topic="llm/request",
    )
    
    mock_handlers["character"].update_from_current.assert_called_once_with(character_data)


@pytest.mark.asyncio
async def test_route_character_result_full_snapshot(router, mock_client, mock_handlers):
    """Test routing character/result with full snapshot."""
    character_data = {"name": "CASE", "description": "Another robot"}
    envelope = Envelope.new(event_type="character.update", data=character_data, source="test")
    message = create_message("character/result", envelope.model_dump_json().encode())
    
    await router.route_message(
        mock_client,
        message,
        character_current_topic="system/character/current",
        character_result_topic="character/result",
        tools_registry_topic="tools/registry",
        tools_result_topic="tools/result",
        memory_results_topic="memory/results",
        llm_request_topic="llm/request",
    )
    
    mock_handlers["character"].update_from_current.assert_called_once_with(character_data)


@pytest.mark.asyncio
async def test_route_character_result_section_update(router, mock_client, mock_handlers):
    """Test routing character/result with section update."""
    section_data = {"section": "voice", "value": {"model": "en_US"}}
    message = create_message("character/result", json.dumps(section_data))
    
    await router.route_message(
        mock_client,
        message,
        character_current_topic="system/character/current",
        character_result_topic="character/result",
        tools_registry_topic="tools/registry",
        tools_result_topic="tools/result",
        memory_results_topic="memory/results",
        llm_request_topic="llm/request",
    )
    
    mock_handlers["character"].update_section.assert_called_once_with("voice", {"model": "en_US"})


@pytest.mark.asyncio
async def test_route_character_result_partial_update(router, mock_client, mock_handlers):
    """Test routing character/result with partial update."""
    partial_data = {"traits": {"humor": "95%"}}
    message = create_message("character/result", json.dumps(partial_data))
    
    await router.route_message(
        mock_client,
        message,
        character_current_topic="system/character/current",
        character_result_topic="character/result",
        tools_registry_topic="tools/registry",
        tools_result_topic="tools/result",
        memory_results_topic="memory/results",
        llm_request_topic="llm/request",
    )
    
    mock_handlers["character"].merge_update.assert_called_once_with(partial_data)


@pytest.mark.asyncio
async def test_route_tools_registry(router, mock_client, mock_handlers):
    """Test routing tools/registry message."""
    tools_data = {"tools": [{"name": "get_weather"}]}
    message = create_message("tools/registry", json.dumps(tools_data))
    
    await router.route_message(
        mock_client,
        message,
        character_current_topic="system/character/current",
        character_result_topic="character/result",
        tools_registry_topic="tools/registry",
        tools_result_topic="tools/result",
        memory_results_topic="memory/results",
        llm_request_topic="llm/request",
    )
    
    mock_handlers["tool"].load_tools_from_registry.assert_called_once()


@pytest.mark.asyncio
async def test_route_memory_results(router, mock_client, mock_handlers):
    """Test routing memory/results message."""
    results_data = {"id": "corr-1", "results": [{"document": {"text": "Result"}}]}
    message = create_message("memory/results", json.dumps(results_data))
    
    await router.route_message(
        mock_client,
        message,
        character_current_topic="system/character/current",
        character_result_topic="character/result",
        tools_registry_topic="tools/registry",
        tools_result_topic="tools/result",
        memory_results_topic="memory/results",
        llm_request_topic="llm/request",
    )
    
    # RAGHandler.handle_results is sync and receives parsed dict
    mock_handlers["rag"].handle_results.assert_called_once_with(results_data)


@pytest.mark.asyncio
async def test_route_llm_request(router, mock_client, mock_handlers):
    """Test routing llm/request message."""
    request_data = {"id": "req-1", "text": "Hello"}
    message = create_message("llm/request", json.dumps(request_data))
    
    await router.route_message(
        mock_client,
        message,
        character_current_topic="system/character/current",
        character_result_topic="character/result",
        tools_registry_topic="tools/registry",
        tools_result_topic="tools/result",
        memory_results_topic="memory/results",
        llm_request_topic="llm/request",
    )
    
    mock_handlers["request"].process_request.assert_called_once_with(mock_client, message.payload)


@pytest.mark.asyncio
async def test_route_unknown_topic(router, mock_client, mock_handlers):
    """Test routing unknown topic does nothing."""
    message = create_message("unknown/topic", b"data")
    
    await router.route_message(
        mock_client,
        message,
        character_current_topic="system/character/current",
        character_result_topic="character/result",
        tools_registry_topic="tools/registry",
        tools_result_topic="tools/result",
        memory_results_topic="memory/results",
        llm_request_topic="llm/request",
    )
    
    # No handlers should be called
    mock_handlers["character"].update_from_current.assert_not_called()
    mock_handlers["tool"].load_tools.assert_not_called()
    mock_handlers["rag"].handle_results.assert_not_called()
    mock_handlers["request"].process_request.assert_not_called()


@pytest.mark.asyncio
async def test_handle_character_current_invalid_json(router, mock_client, mock_handlers):
    """Test handling character/current with invalid JSON."""
    message = create_message("system/character/current", b"invalid json")
    
    # Should not raise exception
    await router.route_message(
        mock_client,
        message,
        character_current_topic="system/character/current",
        character_result_topic="character/result",
        tools_registry_topic="tools/registry",
        tools_result_topic="tools/result",
        memory_results_topic="memory/results",
        llm_request_topic="llm/request",
    )
    
    mock_handlers["character"].update_from_current.assert_not_called()


@pytest.mark.asyncio
async def test_handle_character_result_invalid_envelope(router, mock_client, mock_handlers):
    """Test handling character/result with invalid envelope."""
    message = create_message("character/result", b"{}")
    
    # Should handle gracefully
    await router.route_message(
        mock_client,
        message,
        character_current_topic="system/character/current",
        character_result_topic="character/result",
        tools_registry_topic="tools/registry",
        tools_result_topic="tools/result",
        memory_results_topic="memory/results",
        llm_request_topic="llm/request",
    )
    
    # Empty dict should not trigger any updates
    mock_handlers["character"].update_from_current.assert_not_called()
    mock_handlers["character"].update_section.assert_not_called()
    mock_handlers["character"].merge_update.assert_not_called()
