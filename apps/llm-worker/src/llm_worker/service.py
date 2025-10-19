from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict

import orjson
from pydantic import ValidationError

from tars.adapters.mqtt_client import MQTTClient
from tars.contracts.envelope import Envelope
from .handlers import CharacterManager, ToolExecutor, RAGHandler, MessageRouter, RequestHandler
from .config import (
    MQTT_URL,
    LOG_LEVEL,
    LLM_PROVIDER,
    LLM_MODEL,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    LLM_TOP_P,
    LLM_CTX_WINDOW,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    RAG_ENABLED,
    RAG_TOP_K,
    RAG_PROMPT_TEMPLATE,
    RAG_MAX_TOKENS,
    RAG_INCLUDE_CONTEXT,
    RAG_CONTEXT_WINDOW,
    RAG_STRATEGY,
    RAG_DYNAMIC_PROMPTS,
    RAG_CACHE_TTL,
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

        # MQTT client wrapper (centralized)
        self.mqtt_client = MQTTClient(
            MQTT_URL,
            client_id="tars-llm",
            source_name="llm-worker",
            enable_health=True,
            enable_heartbeat=True,
        )

        # Handlers for different responsibilities
        self.character_mgr = CharacterManager()
        self.tool_executor = ToolExecutor()
        self.rag_handler = RAGHandler(TOPIC_MEMORY_QUERY, cache_ttl=RAG_CACHE_TTL)

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
            "LLM_CTX_WINDOW": LLM_CTX_WINDOW,
            "OPENAI_API_KEY": OPENAI_API_KEY,
            # RAG settings
            "RAG_ENABLED": RAG_ENABLED,
            "RAG_TOP_K": RAG_TOP_K,
            "RAG_PROMPT_TEMPLATE": RAG_PROMPT_TEMPLATE,
            "RAG_MAX_TOKENS": RAG_MAX_TOKENS,
            "RAG_INCLUDE_CONTEXT": RAG_INCLUDE_CONTEXT,
            "RAG_CONTEXT_WINDOW": RAG_CONTEXT_WINDOW,
            "RAG_STRATEGY": RAG_STRATEGY,
            "RAG_DYNAMIC_PROMPTS": RAG_DYNAMIC_PROMPTS,
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
        """Main service loop with automatic MQTT reconnection."""
        backoff = 1.0
        max_backoff = 30.0
        
        while True:
            try:
                # Connect to MQTT broker
                await self.mqtt_client.connect()
                logger.info("Connected to MQTT broker")

                # Subscribe to all topics with individual handlers
                await self.mqtt_client.subscribe(TOPIC_CHARACTER_CURRENT, self._handle_character_current)
                await self.mqtt_client.subscribe(TOPIC_CHARACTER_RESULT, self._handle_character_result)
                await self.mqtt_client.subscribe(TOPIC_LLM_REQUEST, self._handle_llm_request)

                if RAG_ENABLED:
                    await self.mqtt_client.subscribe(TOPIC_MEMORY_RESULTS, self._handle_memory_results, qos=1)
                    logger.info("RAG enabled - subscribed to memory/results")

                if TOOL_CALLING_ENABLED:
                    await self.mqtt_client.subscribe(TOPIC_TOOLS_REGISTRY, self._handle_tools_registry)
                    await self.mqtt_client.subscribe(TOPIC_TOOL_CALL_RESULT, self._handle_tool_result)
                    logger.info("Tool calling enabled - subscribed to tool topics")

                # Request initial character state
                try:
                    await self.mqtt_client.publish_event(
                        topic=TOPIC_CHARACTER_GET,
                        event_type="memory.character.get",
                        data={"section": None},
                        qos=0,
                    )
                    logger.info("Requested character/get on startup")
                except Exception:
                    logger.debug("character/get publish failed (may be offline)")

                # CRITICAL: Small delay to allow retained messages to arrive
                await asyncio.sleep(0.5)

                # Warm up memory service if RAG is enabled
                if RAG_ENABLED:
                    asyncio.create_task(self._warmup_memory())
                    asyncio.create_task(self._periodic_metrics_logging())

                logger.info("LLM worker ready - processing messages via subscription handlers")

                # Reset backoff on successful connection
                backoff = 1.0

                # Keep service running until connection fails
                await self.mqtt_client.wait_for_disconnect()

            except asyncio.CancelledError:
                logger.info("LLM worker shutdown requested")
                raise
            except Exception as e:
                logger.warning("MQTT disconnected: %s; reconnecting in %.1fs...", e, backoff)
            finally:
                await self.mqtt_client.shutdown()
            
            # Exponential backoff before reconnect
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2.0, max_backoff)
        
        logger.info("LLM worker shutdown complete")

    # --- Subscription Handlers ---

    async def _handle_character_current(self, payload: bytes) -> None:
        """Handle character/current retained message."""
        await self.router._handle_character_current(type("Message", (), {"payload": payload})())

    async def _handle_character_result(self, payload: bytes) -> None:
        """Handle character/result message."""
        await self.router._handle_character_result(type("Message", (), {"payload": payload})())

    async def _handle_llm_request(self, payload: bytes) -> None:
        """Handle llm/request message."""
        await self.request_handler.process_request(self.mqtt_client.client, payload)

    async def _handle_memory_results(self, payload: bytes) -> None:
        """Handle memory/results message."""
        logger.info("Memory results received: payload_size=%d", len(payload))
        try:
            # Parse envelope to extract data and correlation ID
            envelope = Envelope.model_validate_json(payload)
            data = envelope.data if isinstance(envelope.data, dict) else {}
            # Add correlation ID to data for RAG handler
            data["correlate"] = envelope.id
            logger.debug("Memory results: envelope_id=%s, data_keys=%s", envelope.id, list(data.keys()))
            self.rag_handler.handle_results(data)
        except ValidationError:
            # Fallback to direct JSON parsing for backward compatibility
            try:
                data = orjson.loads(payload)
                logger.info("Memory results fallback parsing: data_keys=%s", list(data.keys()) if isinstance(data, dict) else "not_dict")
                self.rag_handler.handle_results(data)
            except Exception as e:
                logger.warning("Failed to parse memory/results payload: %s", e)
        except Exception as e:
            logger.warning("Failed to handle memory/results: %s", e)

    async def _handle_tools_registry(self, payload: bytes) -> None:
        """Handle tools/registry message."""
        logger.debug("Tool registry message received")
        try:
            registry_data = orjson.loads(payload)
            logger.debug("Parsed registry with %d tools", len(registry_data.get("tools", [])))
            await self.tool_executor.load_tools_from_registry(registry_data)
        except Exception as e:
            logger.warning("Failed to load tools from registry: %s", e, exc_info=True)

    async def _handle_tool_result(self, payload: bytes) -> None:
        """Handle tools/result message."""
        logger.debug("Tool result received")
        try:
            result_data = orjson.loads(payload)
            call_id = result_data.get("call_id")
            content = result_data.get("content")
            error = result_data.get("error")
            if call_id:
                self.tool_executor.handle_tool_result(call_id, content, error)
            else:
                logger.warning("Tool result missing call_id: %s", result_data)
        except Exception as e:
            logger.warning("Failed to handle tool result: %s", e, exc_info=True)

    async def _warmup_memory(self) -> None:
        """Warm up memory service to eliminate cold start penalty (Priority 3).

        Sends a dummy query to pre-load embedder and ensure fast first real query.
        Runs in background without blocking startup.
        """
        try:
            # Wait a bit longer for memory service to be ready
            await asyncio.sleep(1.0)

            import uuid

            warmup_id = f"warmup-{uuid.uuid4().hex[:8]}"

            logger.info("Starting memory service warm-up...")
            start_time = time.time()

            # Send a simple warm-up query (won't cache due to unique correlation ID)
            await self.rag_handler.query(
                mqtt_client=self.mqtt_client,
                client=self.mqtt_client.client,
                prompt="system initialization",
                top_k=1,
                correlation_id=warmup_id,
                use_cache=False,  # Don't cache warmup queries
            )

            elapsed = time.time() - start_time
            logger.info("Memory service warmed up successfully: %.3fs", elapsed)

        except asyncio.TimeoutError:
            logger.warning("Memory warm-up timeout (service may not be ready yet)")
        except Exception as e:
            logger.warning("Memory warm-up failed (non-critical): %s", e)

    async def _periodic_metrics_logging(self) -> None:
        """Periodically log RAG metrics for observability (Priority 4).

        Runs in background and logs metrics every 5 minutes.
        """
        try:
            while True:
                await asyncio.sleep(300)  # Log every 5 minutes
                self.rag_handler.log_metrics()
        except asyncio.CancelledError:
            logger.debug("Metrics logging task cancelled")
            raise
        except Exception as e:
            logger.warning("Metrics logging error: %s", e)


def main() -> int:
    svc = LLMService()
    asyncio.run(svc.run())
    return 0
