from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Tuple

import asyncio_mqtt as mqtt
import orjson as json
from pydantic import ValidationError

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
    # TTS streaming config
    LLM_TTS_STREAM,
    TOPIC_TTS_SAY,
    STREAM_MIN_CHARS,
    STREAM_MAX_CHARS,
    STREAM_BOUNDARY_CHARS,
    # Tool calling config
    TOOL_CALLING_ENABLED,
    TOPIC_TOOLS_REGISTRY,
    TOPIC_TOOL_CALL_REQUEST,
    TOPIC_TOOL_CALL_RESULT,
)
from .providers.openai import OpenAIProvider
from .mcp_client import get_mcp_client

from tars.contracts.envelope import Envelope  # type: ignore[import]
from tars.contracts.registry import register  # type: ignore[import]
from tars.contracts.v1 import (  # type: ignore[import]
    EVENT_TYPE_LLM_CANCEL,
    EVENT_TYPE_LLM_REQUEST,
    EVENT_TYPE_LLM_RESPONSE,
    EVENT_TYPE_LLM_STREAM,
    EVENT_TYPE_SAY,
    EVENT_TYPE_TOOLS_REGISTRY,
    EVENT_TYPE_TOOL_CALL_REQUEST,
    EVENT_TYPE_TOOL_CALL_RESULT,
    LLMRequest,
    LLMResponse,
    LLMStreamDelta,
    TtsSay,
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
        register(EVENT_TYPE_TOOL_CALL_REQUEST, TOPIC_TOOL_CALL_REQUEST)
        register(EVENT_TYPE_TOOL_CALL_RESULT, TOPIC_TOOL_CALL_RESULT)
    
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

    def _decode_llm_request(self, payload: bytes) -> Tuple[Optional[LLMRequest], Optional[str]]:
        envelope: Optional[Envelope] = None
        try:
            envelope = Envelope.model_validate_json(payload)
            data = envelope.data
        except ValidationError:
            try:
                data = json.loads(payload)
            except Exception:
                logger.warning("Invalid llm/request payload (unable to parse JSON)")
                return None, None
        try:
            request = LLMRequest.model_validate(data)
        except ValidationError as exc:
            logger.warning("Invalid llm/request payload: %s", exc)
            return None, envelope.id if envelope else None
        return request, envelope.id if envelope else None

    async def _publish_event(self, client: mqtt.Client, *, event_type: str, topic: str, payload: Any, correlate: Optional[str] = None, qos: int = 1, retain: bool = False) -> None:
        envelope = Envelope.new(event_type=event_type, data=payload, correlate=correlate, source=SOURCE_NAME)
        await client.publish(topic, envelope.model_dump_json().encode(), qos=qos, retain=retain)

    def _build_system_prompt(self, base_system: str | None = None) -> str | None:
        """Combine character persona and optional base system prompt.

        Expected character snapshot schema:
        { name, description, systemprompt, traits: { ... }, voice: { ... }, meta: { ... } }
        Priority:
        1) If character.systemprompt is provided, use it, and also append a compact traits line when traits exist.
        2) Otherwise, render compact persona from traits and description.
        Then append any base_system provided by the caller.
        """
        persona = None
        try:
            logger.debug("Building system prompt from character/current: %s", self.character or "<none>")
            if self.character:
                logger.info("Building system prompt from character/current: name=%s", self.character.get("name"))
                name = self.character.get("name") or "Assistant"
                sys_prompt = (self.character.get("systemprompt") or "").strip()
                traits = self.character.get("traits") or {}
                desc = self.character.get("description") or (self.character.get("meta") or {}).get("description")

                parts: list[str] = []
                if sys_prompt:
                    parts.append(sys_prompt)

                # Always append traits line if traits exist
                if traits:
                    trait_pairs = [f"{k}: {v}" for k, v in traits.items()]
                    trait_line = f"You are {name}. Traits: " + "; ".join(trait_pairs) + "."
                    if desc:
                        trait_line = (trait_line + " " + str(desc)).strip()
                    parts.append(trait_line)
                elif not sys_prompt:
                    # No systemprompt and no traits: fallback minimal persona (optionally with description)
                    fallback = f"You are {name}."
                    if desc:
                        fallback = (fallback + " " + str(desc)).strip()
                    parts.append(fallback)

                persona = "\n".join(p for p in parts if p).strip() or None
        except Exception:
            logger.warning("Failed to build system prompt from character/current")
            persona = None
        logger.debug("Built system prompt from character: %s", persona or "<none>")
        if base_system and persona:
            logger.debug("Combining with base system prompt of length %d", len(base_system or ""))
            return persona + "\n\n" + base_system
        logger.debug("Final system prompt set to %s", base_system or persona or "<none>")
        return base_system or persona

    def _should_flush(self, buf: str, incoming: str) -> bool:
        # Flush when boundary punctuation present (no min length),
        # or when adding incoming would exceed max
        if any(ch in buf for ch in STREAM_BOUNDARY_CHARS):
            return True
        return len(buf) + len(incoming) >= STREAM_MAX_CHARS

    def _split_on_boundary(self, text: str) -> tuple[str, str]:
        # Split at last boundary in text; return (sentence, remainder)
        idx = max((text.rfind(ch) for ch in STREAM_BOUNDARY_CHARS), default=-1)
        if idx >= 0:
            return text[: idx + 1].strip(), text[idx + 1 :].lstrip()
        return "", text

    async def _load_tools(self, payload: bytes) -> None:
        """Load tools from MCP bridge registry and initialize MCP client."""
        try:
            data = json.loads(payload)
            self.tools = data.get("tools", [])
            logger.info("Loaded %d tools from registry", len(self.tools))
            
            # Initialize MCP client with registry data
            if TOOL_CALLING_ENABLED:
                mcp_client = get_mcp_client()
                await mcp_client.initialize_from_registry(data)
                
                # Connect to known servers (hardcoded for now, could be from config)
                # TODO: Get server URLs from registry metadata or config
                await mcp_client.connect_to_server("test-server", "http://mcp-test-server:8080/mcp")
                logger.info("MCP client initialized and connected")
        except Exception as e:
            logger.error("Failed to load tools: %s", e)

    async def _handle_memory_results(self, payload: bytes) -> None:
        """Handle memory/results messages using correlation ID."""
        try:
            envelope: Optional[Envelope] = None
            try:
                envelope = Envelope.model_validate_json(payload)
                data = envelope.data if isinstance(envelope.data, dict) else {}
            except ValidationError:
                data = json.loads(payload)
            
            # Extract correlation ID to match with pending RAG query
            corr_id = envelope.correlate if envelope else data.get("correlate") or data.get("id")
            if corr_id and corr_id in self._pending_rag:
                future = self._pending_rag.pop(corr_id)
                results = data.get("results") or []
                snippets = []
                for r in results:
                    doc = r.get("document") or {}
                    t = doc.get("text") or json.dumps(doc)
                    snippets.append(t)
                context = "\n".join(snippets)
                if not future.done():
                    future.set_result(context)
                logger.debug("Resolved RAG query %s with %d results", corr_id, len(results))
        except Exception as e:
            logger.warning("Failed to handle memory/results: %s", e)

    async def _handle_tool_result(self, payload: bytes) -> None:
        """Handle tool call result and resolve pending futures."""
        try:
            data = json.loads(payload)
            call_id = data.get("call_id")
            if call_id:
                # Legacy dict storage for compatibility
                self.pending_tool_results[call_id] = data
                # Resolve future if present (non-blocking pattern)
                if call_id in self._tool_futures:
                    future = self._tool_futures.pop(call_id)
                    if not future.done():
                        future.set_result(data)
                    logger.debug("Resolved tool call future for call_id=%s", call_id)
                else:
                    logger.debug("Received tool result for call_id=%s (no pending future)", call_id)
        except Exception as e:
            logger.error("Failed to handle tool result: %s", e)

    async def _execute_tool_calls(self, client, tool_calls: list[dict], req_id: str, correlation_id: str) -> list[dict]:
        """Execute tool calls directly via MCP client.
        
        No MQTT round-trip - calls MCP servers directly for lower latency.
        
        Args:
            client: MQTT client (unused, kept for signature compatibility)
            tool_calls: List of tool call objects from LLM
            req_id: Request ID
            correlation_id: Correlation ID for tracing
            
        Returns:
            List of tool results with call_id and content/error
        """
        results = []
        mcp_client = get_mcp_client()
        
        for call in tool_calls:
            call_id = call.get("id")
            if not call_id:
                continue
            
            tool_name = call.get("function", {}).get("name")
            arguments_str = call.get("function", {}).get("arguments", "{}")
            
            try:
                arguments = json.loads(arguments_str)
                logger.info(f"Executing tool: {tool_name} with args: {arguments}")
                
                # Execute directly via MCP client
                result = await mcp_client.execute_tool(tool_name, arguments)
                
                # Format result for OpenAI
                if "error" in result and result.get("error"):
                    results.append({
                        "call_id": call_id,
                        "error": result["error"]
                    })
                    logger.error(f"Tool {tool_name} failed: {result['error']}")
                else:
                    results.append({
                        "call_id": call_id,
                        "content": result.get("content", "")
                    })
                    logger.info(f"Tool {tool_name} succeeded: {result.get('content', '')[:100]}")
                    
            except Exception as e:
                logger.error(f"Failed to execute tool call {call_id}: {e}", exc_info=True)
                results.append({"call_id": call_id, "error": str(e)})
        
        return results

    def _extract_tool_calls(self, result: LLMResult) -> list[dict]:
        """Extract tool calls from LLM result."""
        if hasattr(result, 'tool_calls') and result.tool_calls:
            return result.tool_calls
        return []

    async def _handle_tool_calls_and_respond(self, client, tool_calls: list[dict], messages: list[dict], 
                                            req_id: str, correlation_id: str, model: str, 
                                            max_tokens: int, temperature: float, top_p: float, system: str,
                                            tools: list[dict] | None) -> None:
        """Execute tool calls and send follow-up response."""
        if not tool_calls:
            return
        
        # Execute tool calls
        tool_results = await self._execute_tool_calls(client, tool_calls, req_id, correlation_id)
        
        # Add tool result messages to conversation
        for result in tool_results:
            # Use content if successful, otherwise error message
            error = result.get("error")
            content = result.get("content") if not error else error
            tool_msg = {
                "role": "tool",
                "content": content or "",
                "tool_call_id": result["call_id"]
            }
            messages.append(tool_msg)
        
        # Generate follow-up response with tool results
        followup_result = await self.provider.generate_chat(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            system=system,
            tools=tools,
        )
        
        # Send follow-up response
        resp = LLMResponse(
            id=req_id,
            reply=followup_result.text,
            provider=self.provider.name,
            model=model,
            tokens=followup_result.usage or {},
        )
        await self._publish_event(
            client,
            event_type=EVENT_TYPE_LLM_RESPONSE,
            topic=TOPIC_LLM_RESPONSE,
            payload=resp,
            correlate=correlation_id,
        )

    async def _do_rag(self, client, prompt: str, top_k: int, correlation_id: str) -> str:
        """Non-blocking RAG query using correlation ID and asyncio.Future.
        
        Creates a future keyed by correlation ID, publishes the query, and waits
        for memory-worker to respond. Uses timeout to prevent indefinite blocking.
        
        Args:
            client: MQTT client
            prompt: Query text
            top_k: Number of results to retrieve
            correlation_id: Unique ID to correlate request and response
            
        Returns:
            RAG context string (empty on timeout/error)
        """
        future: asyncio.Future[str] = asyncio.Future()
        self._pending_rag[correlation_id] = future
        
        try:
            payload = {"text": prompt, "top_k": top_k, "id": correlation_id}
            await client.publish(TOPIC_MEMORY_QUERY, json.dumps(payload))
            logger.debug("Published RAG query with correlation_id=%s", correlation_id)
            
            # Wait for memory/results with timeout
            context = await asyncio.wait_for(future, timeout=5.0)
            return context
        except asyncio.TimeoutError:
            self._pending_rag.pop(correlation_id, None)
            logger.warning("RAG query timeout for correlation_id=%s", correlation_id)
            return ""
        except Exception as e:
            self._pending_rag.pop(correlation_id, None)
            logger.warning("RAG failed: %s", e)
            return ""

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
                )
                
                # Process messages via router
                async for m in self.mqtt_client.message_stream(client):
                    await self.router.route_message(
                        client,
                        m,
                        character_current_topic=TOPIC_CHARACTER_CURRENT,
                        character_result_topic=TOPIC_CHARACTER_RESULT,
                        tools_registry_topic=TOPIC_TOOLS_REGISTRY,
                        memory_results_topic=TOPIC_MEMORY_RESULTS,
                        tool_call_result_topic=TOPIC_TOOL_CALL_RESULT,
                        llm_request_topic=TOPIC_LLM_REQUEST,
                    )
        except Exception as e:
            logger.info("MQTT disconnected or error: %s; shutting down gracefully", e)


def main() -> int:
    svc = LLMService()
    asyncio.run(svc.run())
    return 0
