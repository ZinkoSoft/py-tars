from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Tuple

import asyncio_mqtt as mqtt
import orjson as json
from pydantic import ValidationError

from .mqtt_client import MQTTClient
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
        # Character/persona state (loaded via MQTT retained message)
        self.character: Dict[str, Any] = {}
        # Tool registry and pending results
        self.tools: list[dict] = []
        self.pending_tool_results: Dict[str, dict] = {}  # Legacy - kept for compatibility
        # Pending RAG queries (keyed by correlation ID)
        self._pending_rag: Dict[str, asyncio.Future[str]] = {}
        # Pending tool calls (keyed by call_id) - uses futures for non-blocking wait
        self._tool_futures: Dict[str, asyncio.Future[dict]] = {}
        # MQTT client wrapper
        self.mqtt_client = MQTTClient(MQTT_URL, client_id="tars-llm", source_name="llm-worker")

    def _register_topics(self) -> None:
        register(EVENT_TYPE_LLM_CANCEL, TOPIC_LLM_CANCEL)
        register(EVENT_TYPE_LLM_REQUEST, TOPIC_LLM_REQUEST)
        register(EVENT_TYPE_LLM_RESPONSE, TOPIC_LLM_RESPONSE)
        register(EVENT_TYPE_LLM_STREAM, TOPIC_LLM_STREAM)
        register(EVENT_TYPE_SAY, TOPIC_TTS_SAY)
        register(EVENT_TYPE_TOOLS_REGISTRY, TOPIC_TOOLS_REGISTRY)
        register(EVENT_TYPE_TOOL_CALL_REQUEST, TOPIC_TOOL_CALL_REQUEST)
        register(EVENT_TYPE_TOOL_CALL_RESULT, TOPIC_TOOL_CALL_RESULT)

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
                
                # Process messages
                async for m in self.mqtt_client.message_stream(client):
                        topic = str(getattr(m, "topic", ""))
                        if topic == TOPIC_CHARACTER_CURRENT:
                            # Update persona from retained/current payload
                            try:
                                self.character = json.loads(m.payload)
                                logger.info("character/current updated: name=%s", self.character.get("name"))
                            except Exception:
                                logger.warning("Failed to parse character/current")
                            continue
                        if topic == TOPIC_CHARACTER_RESULT:
                            payload_data: Dict[str, Any]
                            try:
                                envelope = Envelope.model_validate_json(m.payload)
                                raw_data = envelope.data
                                payload_data = raw_data if isinstance(raw_data, dict) else {}
                            except ValidationError:
                                try:
                                    payload_data = json.loads(m.payload)
                                except Exception:
                                    payload_data = {}

                            if payload_data:
                                if "name" in payload_data:
                                    self.character = payload_data
                                elif "section" in payload_data and "value" in payload_data:
                                    section_key = payload_data.get("section")
                                    if isinstance(section_key, str):
                                        self.character.setdefault(section_key, payload_data.get("value"))
                                        self.character[section_key] = payload_data.get("value")
                                else:
                                    self.character.update(payload_data)
                                logger.info("character/result received: name=%s", self.character.get("name"))
                            continue
                        
                        # Handle tool registry
                        if topic == TOPIC_TOOLS_REGISTRY:
                            await self._load_tools(m.payload)
                            continue
                        
                        # Handle memory/results for RAG
                        if topic == TOPIC_MEMORY_RESULTS:
                            await self._handle_memory_results(m.payload)
                            continue
                        
                        # Handle tool results
                        if topic == TOPIC_TOOL_CALL_RESULT:
                            await self._handle_tool_result(m.payload)
                            continue
                        
                        if topic != TOPIC_LLM_REQUEST:
                            continue
                        request, envelope_id = self._decode_llm_request(m.payload)
                        if request is None:
                            continue
                        logger.info(
                            "llm/request received id=%s stream=%s use_rag=%s",
                            request.id,
                            request.stream,
                            request.use_rag,
                        )
                        text = (request.text or "").strip()
                        if not text:
                            logger.debug("llm/request ignored id=%s (empty text)", request.id)
                            continue
                        want_stream = bool(request.stream)
                        use_rag = RAG_ENABLED if request.use_rag is None else bool(request.use_rag)
                        rag_k = request.rag_k if (request.rag_k is not None and request.rag_k > 0) else RAG_TOP_K
                        system = request.system
                        params = request.params or {}
                        model = params.get("model", LLM_MODEL)
                        max_tokens = int(params.get("max_tokens", LLM_MAX_TOKENS))
                        temperature = float(params.get("temperature", LLM_TEMPERATURE))
                        top_p = float(params.get("top_p", LLM_TOP_P))

                        req_id = request.id
                        correlation_id = envelope_id or request.message_id

                        # Merge character persona into system prompt
                        system = self._build_system_prompt(system)

                        context = ""
                        if use_rag:
                            context = await self._do_rag(client, text, rag_k, correlation_id)
                        prompt = text
                        if context:
                            prompt = RAG_PROMPT_TEMPLATE.format(context=context, user=text)

                        # Format conversation history for chat completion
                        messages = []
                        if request.conversation_history:
                            for msg in request.conversation_history:
                                messages.append({
                                    "role": msg.role,
                                    "content": msg.content
                                })
                        # Add current user message
                        messages.append({
                            "role": "user", 
                            "content": prompt
                        })

                        # Include tools if available and enabled
                        tools = self.tools if TOOL_CALLING_ENABLED and self.tools else None

                        # Fast-fail when required creds are missing (avoid long HTTP timeouts)
                        if isinstance(self.provider, OpenAIProvider) and not OPENAI_API_KEY:
                            logger.warning("OPENAI_API_KEY not set; responding with error for id=%s", req_id)
                            error_resp = LLMResponse(
                                id=req_id,
                                error="OPENAI_API_KEY not set",
                                provider=self.provider.name,
                                model=model,
                            )
                            await self._publish_event(
                                client,
                                event_type=EVENT_TYPE_LLM_RESPONSE,
                                topic=TOPIC_LLM_RESPONSE,
                                payload=error_resp,
                                correlate=correlation_id,
                            )
                            continue

                        try:
                            if want_stream and getattr(self.provider, "name", "") == "openai":
                                seq = 0
                                full_chunks: list[str] = []
                                logger.info("Starting streaming for id=%s via provider=%s (system_len=%s, history_len=%d)", 
                                           req_id, self.provider.name, len(system or ""), len(messages) - 1)
                                tts_buf = ""
                                async for ch in self.provider.stream_chat(
                                    messages=messages,
                                    model=model,
                                    max_tokens=max_tokens,
                                    temperature=temperature,
                                    top_p=top_p,
                                    system=system,
                                    tools=tools,
                                ):
                                    seq += 1
                                    delta_text = ch.get("delta")
                                    out = LLMStreamDelta(
                                        id=req_id,
                                        seq=seq,
                                        delta=delta_text,
                                        done=False,
                                        provider=self.provider.name,
                                        model=model,
                                    )
                                    if delta_text:
                                        full_chunks.append(delta_text)
                                    logger.debug("llm/stream id=%s seq=%d len=%d", req_id, seq, len(delta_text or ""))
                                    await self._publish_event(
                                        client,
                                        event_type=EVENT_TYPE_LLM_STREAM,
                                        topic=TOPIC_LLM_STREAM,
                                        payload=out,
                                        correlate=correlation_id,
                                    )
                                    # Optional: accumulate and forward sentences to TTS.
                                    # Note: Router now bridges LLM -> TTS by default; this path remains behind LLM_TTS_STREAM flag for testing.
                                    if LLM_TTS_STREAM:
                                        delta = out.delta or ""
                                        if delta:
                                            tts_buf += delta
                                            # If multiple sentence boundaries arrived at once, flush repeatedly
                                            while self._should_flush(tts_buf, ""):
                                                sent, remainder = self._split_on_boundary(tts_buf)
                                                if not sent:
                                                    break
                                                logger.info("TTS chunk publish len=%d", len(sent))
                                                await self._publish_event(
                                                    client,
                                                    event_type=EVENT_TYPE_SAY,
                                                    topic=TOPIC_TTS_SAY,
                                                    payload=TtsSay(text=sent),
                                                    correlate=correlation_id,
                                                )
                                                tts_buf = remainder
                                # Stream end
                                done = LLMStreamDelta(id=req_id, seq=seq + 1, done=True, provider=self.provider.name, model=model)
                                logger.info("Streaming done for id=%s with %d chunks", req_id, seq)
                                await self._publish_event(
                                    client,
                                    event_type=EVENT_TYPE_LLM_STREAM,
                                    topic=TOPIC_LLM_STREAM,
                                    payload=done,
                                    correlate=correlation_id,
                                )
                                # Flush any remainder
                                if LLM_TTS_STREAM and tts_buf.strip():
                                    final_sent = tts_buf.strip()
                                    logger.info("TTS final chunk publish len=%d", len(final_sent))
                                    await self._publish_event(
                                        client,
                                        event_type=EVENT_TYPE_SAY,
                                        topic=TOPIC_TTS_SAY,
                                        payload=TtsSay(text=final_sent),
                                        correlate=correlation_id,
                                    )
                                # Publish final accumulated response for downstream consumers
                                final_text = "".join(full_chunks)
                                logger.info("Publishing llm/response for id=%s (len=%d)", req_id, len(final_text or ""))
                                resp = LLMResponse(
                                    id=req_id,
                                    reply=final_text or None,
                                    provider=self.provider.name,
                                    model=model,
                                )
                                logger.info("llm/response id=%s len=%d", req_id, len(final_text or ""))
                                logger.info("sending event to response topic %s with event type of %s: payload %s", TOPIC_LLM_RESPONSE, EVENT_TYPE_LLM_RESPONSE, resp)
                                await self._publish_event(
                                    client,
                                    event_type=EVENT_TYPE_LLM_RESPONSE,
                                    topic=TOPIC_LLM_RESPONSE,
                                    payload=resp,
                                    correlate=correlation_id,
                                )
                            else:
                                result = await self.provider.generate_chat(
                                    messages=messages,
                                    model=model,
                                    max_tokens=max_tokens,
                                    temperature=temperature,
                                    top_p=top_p,
                                    system=system,
                                    tools=tools,
                                )
                                
                                # Check for tool calls
                                tool_calls = self._extract_tool_calls(result)
                                if tool_calls and TOOL_CALLING_ENABLED:
                                    # Add assistant message with tool_calls to conversation history
                                    messages.append({
                                        "role": "assistant",
                                        "content": result.text,
                                        "tool_calls": tool_calls
                                    })
                                    # Handle tool calls and send follow-up response
                                    await self._handle_tool_calls_and_respond(
                                        client, tool_calls, messages, req_id, correlation_id,
                                        model, max_tokens, temperature, top_p, system, tools
                                    )
                                else:
                                    # Send direct response
                                    resp = LLMResponse(
                                        id=req_id,
                                        reply=result.text,
                                        provider=self.provider.name,
                                        model=model,
                                        tokens=result.usage or {},
                                    )
                                    logger.info("Publishing llm/response for id=%s (len=%d)", req_id, len(result.text or ""))
                                    await self._publish_event(
                                        client,
                                        event_type=EVENT_TYPE_LLM_RESPONSE,
                                        topic=TOPIC_LLM_RESPONSE,
                                        payload=resp,
                                        correlate=correlation_id,
                                    )
                        except Exception as e:
                            logger.exception("generation failed")
                            error_resp = LLMResponse(
                                id=req_id,
                                error=str(e),
                                provider=self.provider.name,
                                model=model,
                            )
                            await self._publish_event(
                                client,
                                event_type=EVENT_TYPE_LLM_RESPONSE,
                                topic=TOPIC_LLM_RESPONSE,
                                payload=error_resp,
                                correlate=correlation_id,
                            )
        except Exception as e:
            logger.info("MQTT disconnected or error: %s; shutting down gracefully", e)


def main() -> int:
    svc = LLMService()
    asyncio.run(svc.run())
    return 0
