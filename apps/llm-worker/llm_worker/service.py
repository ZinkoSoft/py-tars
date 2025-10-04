from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from .mqtt_client import MQTTClient
from .handlers import CharacterManager, ToolExecutor, RAGHandler, MessageRouter, RequestHandler
from .config import (
    MQTT_URL,
    LOG_LEVEL,
    LLM_PROVIDER,
    LLM_MODEL,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    LLM_TOP_P,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    RAG_ENABLED,
    RAG_TOP_K,
    RAG_PROMPT_TEMPLATE,
    TOPIC_LLM_REQUEST,
    TOPIC_LLM_RESPONSE,
    TOPIC_LLM_STREAM,
    TOPIC_LLM_CANCEL,
    TOPIC_HEALTH,
    TOPIC_MEMORY_QUERY,
    TOPIC_MEMORY_RESULTS,
    TOPIC_CHARACTER_CURRENT,
    TOPIC_CHARACTER_GET,
    TOPIC_CHARACTER_RESULT,
    TOOL_CALLING_ENABLED,
    TOPIC_TOOLS_REGISTRY,
    TOPIC_TOOL_CALL_RESULT,
    # TTS streaming config
    LLM_TTS_STREAM,
    TOPIC_TTS_SAY,
    STREAM_MIN_CHARS,
    STREAM_MAX_CHARS,
    STREAM_BOUNDARY_CHARS,
)
from .providers.openai import OpenAIProvider

from tars.contracts.registry import register  # type: ignore[import]
from tars.contracts.v1 import (  # type: ignore[import]
    EVENT_TYPE_LLM_CANCEL,
    EVENT_TYPE_LLM_REQUEST,
    EVENT_TYPE_LLM_RESPONSE,
    EVENT_TYPE_LLM_STREAM,
    EVENT_TYPE_SAY,
    EVENT_TYPE_TOOLS_REGISTRY,
    EVENT_TYPE_TOOL_CALL_REQUEST,
)


SOURCE_NAME = "llm-worker"


logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("llm-worker")


class LLMService:
    def __init__(self):
        self._register_topics()
        
        # Provider selection (only OpenAI for now)
        provider = LLM_PROVIDER.lower()
        if provider == "openai":
            self.provider = OpenAIProvider(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL or None)
        else:
            logger.warning("Unsupported provider '%s', defaulting to openai", provider)
            self.provider = OpenAIProvider(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL or None)
        
        # MQTT client wrapper
        self.mqtt_client = MQTTClient(MQTT_URL, client_id="tars-llm", source_name="llm-worker")
        
        # Handlers for different responsibilities
        self.character_mgr = CharacterManager()
        self.tool_executor = ToolExecutor()
        self.rag_handler = RAGHandler(TOPIC_MEMORY_QUERY)
        
        # Build config dict for request handler
        self.config = self._build_config()
        
        # Request handler for LLM processing
        self.request_handler = RequestHandler(
            provider=self.provider,
            character_mgr=self.character_mgr,
            tool_executor=self.tool_executor,
            rag_handler=self.rag_handler,
            mqtt_client=self.mqtt_client,
            config=self.config,
        )
        
        # Message router to dispatch MQTT messages
        self.router = MessageRouter(
            character_handler=self.character_mgr,
            tool_handler=self.tool_executor,
            rag_handler=self.rag_handler,
            request_handler=self.request_handler,
        )

    def _register_topics(self) -> None:
        register(EVENT_TYPE_LLM_CANCEL, TOPIC_LLM_CANCEL)
        register(EVENT_TYPE_LLM_REQUEST, TOPIC_LLM_REQUEST)
        register(EVENT_TYPE_LLM_RESPONSE, TOPIC_LLM_RESPONSE)
        register(EVENT_TYPE_LLM_STREAM, TOPIC_LLM_STREAM)
        register(EVENT_TYPE_SAY, TOPIC_TTS_SAY)
        register(EVENT_TYPE_TOOLS_REGISTRY, TOPIC_TOOLS_REGISTRY)
    
    def _build_config(self) -> Dict[str, Any]:
        """Build configuration dictionary for handlers."""
        return {
            # LLM settings
            "LLM_MODEL": LLM_MODEL,
            "LLM_MAX_TOKENS": LLM_MAX_TOKENS,
            "LLM_TEMPERATURE": LLM_TEMPERATURE,
            "LLM_TOP_P": LLM_TOP_P,
            "OPENAI_API_KEY": OPENAI_API_KEY,
            # RAG settings
            "RAG_ENABLED": RAG_ENABLED,
            "RAG_TOP_K": RAG_TOP_K,
            "RAG_PROMPT_TEMPLATE": RAG_PROMPT_TEMPLATE,
            # Tool settings
            "TOOL_CALLING_ENABLED": TOOL_CALLING_ENABLED,
            # TTS streaming settings
            "LLM_TTS_STREAM": LLM_TTS_STREAM,
            "STREAM_MIN_CHARS": STREAM_MIN_CHARS,
            "STREAM_MAX_CHARS": STREAM_MAX_CHARS,
            "STREAM_BOUNDARY_CHARS": STREAM_BOUNDARY_CHARS,
            # Topics
            "TOPIC_LLM_STREAM": TOPIC_LLM_STREAM,
            "TOPIC_LLM_RESPONSE": TOPIC_LLM_RESPONSE,
            "TOPIC_TTS_SAY": TOPIC_TTS_SAY,
            # Event types
            "EVENT_TYPE_LLM_STREAM": EVENT_TYPE_LLM_STREAM,
            "EVENT_TYPE_LLM_RESPONSE": EVENT_TYPE_LLM_RESPONSE,
            "EVENT_TYPE_SAY": EVENT_TYPE_SAY,
        }

    async def run(self):
        """Main service loop: connect to MQTT, subscribe, and route messages to handlers."""
        try:
            async with await self.mqtt_client.connect() as client:
                await self.mqtt_client.publish_health(client, TOPIC_HEALTH)
                
                # Subscribe to all topics
                await self.mqtt_client.subscribe_all(
                    client,
                    llm_request_topic=TOPIC_LLM_REQUEST,
                    character_current_topic=TOPIC_CHARACTER_CURRENT,
                    character_result_topic=TOPIC_CHARACTER_RESULT,
                    character_get_topic=TOPIC_CHARACTER_GET,
                    rag_enabled=RAG_ENABLED,
                    memory_results_topic=TOPIC_MEMORY_RESULTS,
                    tool_calling_enabled=TOOL_CALLING_ENABLED,
                    tools_registry_topic=TOPIC_TOOLS_REGISTRY,
                    tools_result_topic=TOPIC_TOOL_CALL_RESULT,
                )
                
                # CRITICAL: Small delay to allow retained messages to arrive before starting message loop
                # This ensures tool registry and character state are received before processing requests
                await asyncio.sleep(0.5)
                logger.info("Starting message processing loop")
                
                # Process messages via router
                async for m in self.mqtt_client.message_stream(client):
                    logger.debug("Message received: topic=%s payload_size=%d", m.topic, len(m.payload))
                    await self.router.route_message(
                        client,
                        m,
                        character_current_topic=TOPIC_CHARACTER_CURRENT,
                        character_result_topic=TOPIC_CHARACTER_RESULT,
                        tools_registry_topic=TOPIC_TOOLS_REGISTRY,
                        tools_result_topic=TOPIC_TOOL_CALL_RESULT,
                        memory_results_topic=TOPIC_MEMORY_RESULTS,
                        llm_request_topic=TOPIC_LLM_REQUEST,
                    )
        except Exception as e:
            logger.info("MQTT disconnected or error: %s; shutting down gracefully", e)


def main() -> int:
    svc = LLMService()
    asyncio.run(svc.run())
    return 0
