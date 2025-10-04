"""Tests for LLMService integration."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from llm_worker.service import LLMService


@pytest.fixture
def mock_openai_provider():
    """Mock OpenAI provider."""
    provider = MagicMock()
    provider.name = "openai"
    return provider


@pytest.fixture
def mock_mqtt_client():
    """Mock MQTT client."""
    client = MagicMock()
    return client


def test_service_initialization(mock_openai_provider):
    """Test LLMService initialization."""
    with patch("llm_worker.service.OpenAIProvider", return_value=mock_openai_provider):
        service = LLMService()
        
        # Check handlers initialized
        assert service.character_mgr is not None
        assert service.tool_executor is not None
        assert service.rag_handler is not None
        assert service.request_handler is not None
        assert service.router is not None
        
        # Check provider
        assert service.provider == mock_openai_provider
        
        # Check MQTT client
        assert service.mqtt_client is not None


def test_build_config(mock_openai_provider):
    """Test _build_config returns correct structure."""
    with patch("llm_worker.service.OpenAIProvider", return_value=mock_openai_provider):
        service = LLMService()
        config = service.config
        
        # Check LLM settings present
        assert "LLM_MODEL" in config
        assert "LLM_MAX_TOKENS" in config
        assert "LLM_TEMPERATURE" in config
        assert "LLM_TOP_P" in config
        
        # Check RAG settings
        assert "RAG_ENABLED" in config
        assert "RAG_TOP_K" in config
        
        # Check Tool settings
        assert "TOOL_CALLING_ENABLED" in config
        
        # Check TTS settings
        assert "LLM_TTS_STREAM" in config
        assert "STREAM_MIN_CHARS" in config
        assert "STREAM_MAX_CHARS" in config
        
        # Check topics
        assert "TOPIC_LLM_STREAM" in config
        assert "TOPIC_LLM_RESPONSE" in config
        assert "TOPIC_TTS_SAY" in config


def test_handler_wiring(mock_openai_provider):
    """Test that handlers are properly wired together."""
    with patch("llm_worker.service.OpenAIProvider", return_value=mock_openai_provider):
        service = LLMService()
        
        # Check RequestHandler has correct dependencies
        assert service.request_handler.provider == mock_openai_provider
        assert service.request_handler.character_mgr == service.character_mgr
        assert service.request_handler.tool_executor == service.tool_executor
        assert service.request_handler.rag_handler == service.rag_handler
        
        # Check MessageRouter has correct handlers
        assert service.router.character_handler == service.character_mgr
        assert service.router.tool_handler == service.tool_executor
        assert service.router.rag_handler == service.rag_handler
        assert service.router.request_handler == service.request_handler


def test_register_topics_called(mock_openai_provider):
    """Test that topics are registered on initialization."""
    with patch("llm_worker.service.OpenAIProvider", return_value=mock_openai_provider), \
         patch("llm_worker.service.register") as mock_register:
        
        service = LLMService()
        
        # Verify register was called for various event types
        assert mock_register.call_count >= 5  # At least 5 event types registered


def test_provider_selection_openai(mock_openai_provider):
    """Test provider selection for OpenAI."""
    with patch("llm_worker.service.OpenAIProvider", return_value=mock_openai_provider), \
         patch("llm_worker.service.LLM_PROVIDER", "openai"):
        
        service = LLMService()
        assert service.provider == mock_openai_provider


def test_provider_selection_fallback(mock_openai_provider):
    """Test provider selection fallback to OpenAI."""
    with patch("llm_worker.service.OpenAIProvider", return_value=mock_openai_provider), \
         patch("llm_worker.service.LLM_PROVIDER", "unsupported-provider"):
        
        service = LLMService()
        # Should fallback to OpenAI
        assert service.provider == mock_openai_provider


def test_config_passed_to_request_handler(mock_openai_provider):
    """Test that config is passed to RequestHandler."""
    with patch("llm_worker.service.OpenAIProvider", return_value=mock_openai_provider):
        service = LLMService()
        
        # Config should be available in request handler
        assert service.request_handler.config is not None
        assert isinstance(service.request_handler.config, dict)


def test_mqtt_client_initialization(mock_openai_provider):
    """Test MQTT client is initialized with correct parameters."""
    with patch("llm_worker.service.OpenAIProvider", return_value=mock_openai_provider):
        service = LLMService()
        
        # Check MQTT client has correct client_id and source_name
        assert service.mqtt_client.client_id == "tars-llm"
        assert service.mqtt_client.source_name == "llm-worker"


def test_rag_handler_topic_configuration(mock_openai_provider):
    """Test RAGHandler is configured with correct topic."""
    with patch("llm_worker.service.OpenAIProvider", return_value=mock_openai_provider), \
         patch("llm_worker.service.TOPIC_MEMORY_QUERY", "custom/memory/query"):
        
        service = LLMService()
        
        # RAGHandler should use the configured topic
        assert service.rag_handler.memory_query_topic == "custom/memory/query"
