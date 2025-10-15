"""LLM request processing handler."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Tuple

import asyncio_mqtt as mqtt
import orjson as json
from pydantic import ValidationError

from tars.contracts.envelope import Envelope  # type: ignore[import]
from tars.contracts.v1 import (  # type: ignore[import]
    LLMRequest,
    LLMResponse,
    LLMStreamDelta,
    TtsSay,
)

logger = logging.getLogger("llm-worker.handlers.request")


class RequestHandler:
    """Handles LLM request processing: parsing, execution, and response publishing."""

    def __init__(
        self,
        *,
        provider,
        character_mgr,
        tool_executor,
        rag_handler,
        mqtt_client,
        config: Dict[str, Any],
    ):
        """Initialize request handler with dependencies.

        Args:
            provider: LLM provider (e.g., OpenAIProvider)
            character_mgr: Character manager for system prompts
            tool_executor: Tool execution handler
            rag_handler: RAG query handler
            mqtt_client: MQTT client wrapper for publishing
            config: Configuration dict with all LLM/RAG/TTS settings
        """
        self.provider = provider
        self.character_mgr = character_mgr
        self.tool_executor = tool_executor
        self.rag_handler = rag_handler
        self.mqtt_client = mqtt_client
        self.config = config

    def _decode_llm_request(self, payload: bytes) -> Tuple[Optional[LLMRequest], Optional[str]]:
        """Decode LLM request from payload with envelope support."""
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

    def _should_flush(self, buf: str, incoming: str = "") -> bool:
        """Check if streaming buffer should be flushed."""
        boundary_chars = self.config.get("STREAM_BOUNDARY_CHARS", ".!?")
        max_chars = self.config.get("STREAM_MAX_CHARS", 200)

        if any(ch in buf for ch in boundary_chars):
            return True
        return len(buf) + len(incoming) >= max_chars

    def _split_on_boundary(self, text: str) -> Tuple[str, str]:
        """Split text at last sentence boundary."""
        boundary_chars = self.config.get("STREAM_BOUNDARY_CHARS", ".!?")
        idx = max((text.rfind(ch) for ch in boundary_chars), default=-1)
        if idx >= 0:
            return text[: idx + 1].strip(), text[idx + 1 :].lstrip()
        return "", text

    async def process_request(self, client: mqtt.Client, payload: bytes) -> None:
        """Process a complete LLM request: decode, prepare, execute, and respond.

        Args:
            client: MQTT client for publishing responses
            payload: Raw MQTT message payload
        """
        request, envelope_id = self._decode_llm_request(payload)
        if request is None:
            return

        logger.info(
            "llm/request received id=%s stream=%s use_rag=%s",
            request.id,
            request.stream,
            request.use_rag,
        )

        text = (request.text or "").strip()
        if not text:
            logger.debug("llm/request ignored id=%s (empty text)", request.id)
            return

        # Extract parameters
        params = self._extract_request_params(request, envelope_id)

        # Fast-fail on missing credentials
        if not self._check_credentials(client, params):
            return

        # Execute request (streaming or non-streaming)
        try:
            if params["want_stream"] and getattr(self.provider, "name", "") == "openai":
                await self._handle_streaming_request(client, params)
            else:
                await self._handle_non_streaming_request(client, params)
        except Exception as e:
            await self._publish_error(client, params, str(e))

    def _extract_request_params(
        self, request: LLMRequest, envelope_id: Optional[str]
    ) -> Dict[str, Any]:
        """Extract and prepare all request parameters."""
        text = request.text or ""
        want_stream = bool(request.stream)

        # RAG configuration
        rag_enabled = self.config.get("RAG_ENABLED", False)
        use_rag = rag_enabled if request.use_rag is None else bool(request.use_rag)
        rag_k = (
            request.rag_k
            if (request.rag_k is not None and request.rag_k > 0)
            else self.config.get("RAG_TOP_K", 5)
        )

        # Enhanced RAG parameters
        rag_max_tokens = self.config.get("RAG_MAX_TOKENS", 2000)
        rag_include_context = self.config.get("RAG_INCLUDE_CONTEXT", True)
        rag_context_window = self.config.get("RAG_CONTEXT_WINDOW", 1)
        rag_strategy = self.config.get("RAG_STRATEGY", "hybrid")

        # LLM parameters
        params = request.params or {}
        model = params.get("model", self.config.get("LLM_MODEL", "gpt-4o-mini"))
        max_tokens = int(params.get("max_tokens", self.config.get("LLM_MAX_TOKENS", 512)))
        temperature = float(params.get("temperature", self.config.get("LLM_TEMPERATURE", 0.7)))
        top_p = float(params.get("top_p", self.config.get("LLM_TOP_P", 1.0)))

        req_id = request.id
        correlation_id = envelope_id or request.message_id

        # Build system prompt with character
        system = self.character_mgr.build_system_prompt(request.system)

        # Tools
        tool_calling_enabled = self.config.get("TOOL_CALLING_ENABLED", False)
        tools = (
            self.tool_executor.tools if tool_calling_enabled and self.tool_executor.tools else None
        )

        # Debug: log tool status
        logger.info(
            "Tool calling: enabled=%s, tools_available=%d",
            tool_calling_enabled,
            len(self.tool_executor.tools) if self.tool_executor.tools else 0,
        )

        return {
            "text": text,
            "want_stream": want_stream,
            "use_rag": use_rag,
            "rag_k": rag_k,
            "rag_max_tokens": rag_max_tokens,
            "rag_include_context": rag_include_context,
            "rag_context_window": rag_context_window,
            "rag_strategy": rag_strategy,
            "system": system,
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "req_id": req_id,
            "correlation_id": correlation_id,
            "tools": tools,
            "conversation_history": request.conversation_history,
        }

    def _check_credentials(self, client: mqtt.Client, params: Dict[str, Any]) -> bool:
        """Check if required credentials are present. Publish error if missing."""
        from ..providers.openai import OpenAIProvider

        openai_key = self.config.get("OPENAI_API_KEY")
        if isinstance(self.provider, OpenAIProvider) and not openai_key:
            logger.warning(
                "OPENAI_API_KEY not set; responding with error for id=%s", params["req_id"]
            )
            asyncio.create_task(self._publish_error(client, params, "OPENAI_API_KEY not set"))
            return False
        return True

    async def _prepare_prompt_with_rag(
        self, client: mqtt.Client, params: Dict[str, Any]
    ) -> Tuple[str, list[dict]]:
        """Prepare prompt with enhanced RAG context and conversation history."""
        text = params["text"]
        context = ""
        rag_metadata = {}

        # Enhanced RAG query if enabled
        if params["use_rag"]:
            # Use enhanced RAG with context expansion and token awareness
            # Enhanced RAG query with context expansion and token awareness
            rag_context = await self.rag_handler.query(
                self.mqtt_client,  # MQTT wrapper for proper envelope publishing
                client,  # Raw MQTT client
                text,
                top_k=params["rag_k"],
                correlation_id=params["correlation_id"],
                max_tokens=params.get("rag_max_tokens"),  # Optional token budget
                include_context=params.get(
                    "rag_include_context", True
                ),  # Include surrounding context
                context_window=params.get("rag_context_window", 1),
                retrieval_strategy=params.get("rag_strategy", "hybrid"),
            )
            context = rag_context.content
            rag_metadata = {
                "token_count": rag_context.token_count,
                "truncated": rag_context.truncated,
                "strategy": rag_context.strategy_used,
            }

            logger.info(
                "RAG context retrieved: %d tokens, truncated=%s, strategy=%s",
                rag_context.token_count,
                rag_context.truncated,
                rag_context.strategy_used,
            )

        # Format prompt with context
        prompt = text
        if context:
            rag_template = self.config.get(
                "RAG_PROMPT_TEMPLATE", "Context:\n{context}\n\nUser: {user}"
            )
            prompt = rag_template.format(context=context, user=text)

        # Store RAG metadata for logging
        params["rag_metadata"] = rag_metadata

        # Build messages list
        messages = []
        if params.get("conversation_history"):
            for msg in params["conversation_history"]:
                messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": prompt})

        return prompt, messages

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (can be improved with tiktoken later)."""
        return int(len(text.split()) * 1.3)

    async def _build_context_aware_prompt(
        self, client: mqtt.Client, params: Dict[str, Any], available_tokens: int
    ) -> Tuple[str, list[dict]]:
        """Build prompt with dynamic token management (community pattern).

        Implements hierarchical content prioritization:
        1. Base prompt structure (system, user message) - reserved
        2. RAG context - high priority
        3. Conversation history - medium priority
        4. Additional context - low priority

        Args:
            client: MQTT client
            params: Request parameters
            available_tokens: Total token budget for the prompt

        Returns:
            Tuple of (formatted_prompt, messages_list)
        """
        text = params["text"]

        # Reserve tokens for base prompt structure (system prompt, user message, assistant prefix)
        base_tokens = 300  # Conservative estimate
        system_prompt = params.get("system", "")
        if system_prompt:
            base_tokens += self._estimate_tokens(system_prompt)

        base_tokens += self._estimate_tokens(text)

        if available_tokens <= base_tokens:
            logger.warning(
                "Available tokens (%d) insufficient for base prompt (%d), proceeding with minimal prompt",
                available_tokens,
                base_tokens,
            )
            return text, [{"role": "user", "content": text}]

        memory_budget = available_tokens - base_tokens
        logger.info(
            "Dynamic prompt building: %d total tokens, %d base, %d available for context",
            available_tokens,
            base_tokens,
            memory_budget,
        )

        # Get RAG context with token budget (highest priority)
        context = ""
        context_tokens = 0
        rag_metadata = {}

        if params["use_rag"] and memory_budget > 100:  # Minimum viable RAG budget
            rag_budget = min(
                memory_budget // 2, params.get("rag_max_tokens", 2000)
            )  # Up to half the budget

            rag_context = await self.rag_handler.query(
                self.mqtt_client,  # MQTT wrapper
                client,  # Raw MQTT client
                text,
                top_k=params["rag_k"],
                correlation_id=params["correlation_id"],
                max_tokens=rag_budget,
                include_context=params.get("rag_include_context", True),
                context_window=params.get("rag_context_window", 1),
                retrieval_strategy=params.get("rag_strategy", "hybrid"),
            )

            context = rag_context.content
            context_tokens = rag_context.token_count
            rag_metadata = {
                "token_count": rag_context.token_count,
                "truncated": rag_context.truncated,
                "strategy": rag_context.strategy_used,
            }

            logger.info(
                "RAG context: %d tokens (budget: %d), truncated=%s",
                context_tokens,
                rag_budget,
                rag_context.truncated,
            )

        # Add conversation history if space allows (medium priority)
        messages = []
        remaining_budget = memory_budget - context_tokens

        if params.get("conversation_history") and remaining_budget > 50:
            history_tokens = 0

            # Add history in reverse order (most recent first) until budget exhausted
            for msg in reversed(params["conversation_history"]):
                msg_tokens = self._estimate_tokens(msg.content)
                if history_tokens + msg_tokens > remaining_budget:
                    break

                messages.insert(0, {"role": msg.role, "content": msg.content})
                history_tokens += msg_tokens

            logger.info(
                "Conversation history: %d messages, %d tokens (budget: %d)",
                len(messages),
                history_tokens,
                remaining_budget,
            )

        # Build final prompt with hierarchical structure
        if context:
            rag_template = self.config.get(
                "RAG_PROMPT_TEMPLATE", "Context:\n{context}\n\nUser: {user}"
            )
            prompt = rag_template.format(context=context, user=text)
        else:
            prompt = text

        # Add final user message
        messages.append({"role": "user", "content": prompt})

        # Store metadata for logging
        params["rag_metadata"] = rag_metadata
        params["prompt_metadata"] = {
            "total_budget": available_tokens,
            "base_tokens": base_tokens,
            "context_tokens": context_tokens,
            "history_messages": len(messages) - 1,  # Exclude final user message
            "final_tokens": sum(self._estimate_tokens(m["content"]) for m in messages),
        }

        return prompt, messages

    async def _handle_streaming_request(self, client: mqtt.Client, params: Dict[str, Any]) -> None:
        """Handle streaming LLM request with optional TTS forwarding and dynamic prompts."""
        # Choose prompt building strategy
        if self.config.get("RAG_DYNAMIC_PROMPTS", True):
            # Use token-aware dynamic prompt building
            context_size = self.config.get("LLM_CTX_WINDOW", 8192)
            # Reserve space for max_tokens response
            available_tokens = context_size - params["max_tokens"] - 100  # Small buffer
            prompt, messages = await self._build_context_aware_prompt(
                client, params, available_tokens
            )

            # Log prompt metadata
            if "prompt_metadata" in params:
                meta = params["prompt_metadata"]
                logger.info(
                    "Dynamic prompt: %d/%d tokens used, %d history messages",
                    meta["final_tokens"],
                    meta["total_budget"],
                    meta["history_messages"],
                )
        else:
            # Use standard prompt building
            prompt, messages = await self._prepare_prompt_with_rag(client, params)

        seq = 0
        full_chunks: list[str] = []
        tts_buf = ""

        logger.info(
            "Starting streaming for id=%s via provider=%s (system_len=%s, history_len=%d)",
            params["req_id"],
            self.provider.name,
            len(params["system"] or ""),
            len(messages) - 1,
        )

        # Stream from provider
        async for ch in self.provider.stream_chat(
            messages=messages,
            model=params["model"],
            max_tokens=params["max_tokens"],
            temperature=params["temperature"],
            top_p=params["top_p"],
            system=params["system"],
            tools=params["tools"],
        ):
            seq += 1
            delta_text = ch.get("delta")

            # Publish stream delta
            out = LLMStreamDelta(
                id=params["req_id"],
                seq=seq,
                delta=delta_text,
                done=False,
                provider=self.provider.name,
                model=params["model"],
            )

            if delta_text:
                full_chunks.append(delta_text)

            logger.debug(
                "llm/stream id=%s seq=%d len=%d", params["req_id"], seq, len(delta_text or "")
            )
            await self.mqtt_client.publish_event(
                client,
                event_type=self.config.get("EVENT_TYPE_LLM_STREAM", "llm.stream"),
                topic=self.config.get("TOPIC_LLM_STREAM", "llm/stream"),
                payload=out,
                correlate=params["correlation_id"],
            )

            # Optional TTS forwarding
            if self.config.get("LLM_TTS_STREAM", False) and delta_text:
                tts_buf += delta_text
                while self._should_flush(tts_buf):
                    sent, remainder = self._split_on_boundary(tts_buf)
                    if not sent:
                        break
                    logger.info("TTS chunk publish len=%d", len(sent))
                    await self.mqtt_client.publish_event(
                        client,
                        event_type=self.config.get("EVENT_TYPE_SAY", "tts.say"),
                        topic=self.config.get("TOPIC_TTS_SAY", "tts/say"),
                        payload=TtsSay(text=sent),
                        correlate=params["correlation_id"],
                    )
                    tts_buf = remainder

        # Publish stream end marker
        await self._publish_stream_end(client, params, seq)

        # Flush remaining TTS buffer
        if self.config.get("LLM_TTS_STREAM", False) and tts_buf.strip():
            await self._publish_tts_chunk(client, params, tts_buf.strip())

        # Publish final accumulated response
        final_text = "".join(full_chunks)
        await self._publish_response(client, params, final_text)

    async def _handle_non_streaming_request(
        self, client: mqtt.Client, params: Dict[str, Any]
    ) -> None:
        """Handle non-streaming LLM request with optional tool calling and dynamic prompts."""
        # Choose prompt building strategy
        if self.config.get("RAG_DYNAMIC_PROMPTS", True):
            # Use token-aware dynamic prompt building
            context_size = self.config.get("LLM_CTX_WINDOW", 8192)
            # Reserve space for max_tokens response
            available_tokens = context_size - params["max_tokens"] - 100  # Small buffer
            prompt, messages = await self._build_context_aware_prompt(
                client, params, available_tokens
            )

            # Log prompt metadata
            if "prompt_metadata" in params:
                meta = params["prompt_metadata"]
                logger.info(
                    "Dynamic prompt: %d/%d tokens used, %d history messages",
                    meta["final_tokens"],
                    meta["total_budget"],
                    meta["history_messages"],
                )
        else:
            # Use standard prompt building
            prompt, messages = await self._prepare_prompt_with_rag(client, params)

        # Generate response
        result = await self.provider.generate_chat(
            messages=messages,
            model=params["model"],
            max_tokens=params["max_tokens"],
            temperature=params["temperature"],
            top_p=params["top_p"],
            system=params["system"],
            tools=params["tools"],
        )

        # Check for tool calls
        tool_calls = self.tool_executor.extract_tool_calls(result)
        logger.info(
            "Tool calls extracted: %s (count=%d)",
            "yes" if tool_calls else "no",
            len(tool_calls) if tool_calls else 0,
        )
        if tool_calls:
            logger.info("Tool calls: %s", tool_calls)
        if tool_calls and self.config.get("TOOL_CALLING_ENABLED", False):
            logger.info("Handling %d tool call(s) for id=%s", len(tool_calls), params["req_id"])
            await self._handle_tool_calls(client, params, messages, result, tool_calls)
        else:
            # Direct response
            await self._publish_response(client, params, result.text, result.usage)

    async def _handle_tool_calls(
        self,
        client: mqtt.Client,
        params: Dict[str, Any],
        messages: list[dict],
        result: Any,
        tool_calls: list[dict],
    ) -> None:
        """Execute tool calls and generate follow-up response."""
        # Add assistant message with tool_calls
        messages.append({"role": "assistant", "content": result.text, "tool_calls": tool_calls})

        # Execute tools (pass client for tool MQTT publishing)
        tool_results = await self.tool_executor.execute_tool_calls(
            tool_calls, self.mqtt_client, client
        )

        # Add tool result messages
        tool_messages = self.tool_executor.format_tool_messages(tool_results)
        messages.extend(tool_messages)

        # Generate follow-up response
        followup_result = await self.provider.generate_chat(
            messages=messages,
            model=params["model"],
            max_tokens=params["max_tokens"],
            temperature=params["temperature"],
            top_p=params["top_p"],
            system=params["system"],
            tools=params["tools"],
        )

        # Publish follow-up response
        await self._publish_response(client, params, followup_result.text, followup_result.usage)

    async def _publish_stream_end(
        self, client: mqtt.Client, params: Dict[str, Any], seq: int
    ) -> None:
        """Publish stream end marker."""
        done = LLMStreamDelta(
            id=params["req_id"],
            seq=seq + 1,
            done=True,
            provider=self.provider.name,
            model=params["model"],
        )
        logger.info("Streaming done for id=%s with %d chunks", params["req_id"], seq)
        await self.mqtt_client.publish_event(
            client,
            event_type=self.config.get("EVENT_TYPE_LLM_STREAM", "llm.stream"),
            topic=self.config.get("TOPIC_LLM_STREAM", "llm/stream"),
            payload=done,
            correlate=params["correlation_id"],
        )

    async def _publish_tts_chunk(
        self, client: mqtt.Client, params: Dict[str, Any], text: str
    ) -> None:
        """Publish TTS chunk."""
        logger.info("TTS final chunk publish len=%d", len(text))
        await self.mqtt_client.publish_event(
            client,
            event_type=self.config.get("EVENT_TYPE_SAY", "tts.say"),
            topic=self.config.get("TOPIC_TTS_SAY", "tts/say"),
            payload=TtsSay(text=text),
            correlate=params["correlation_id"],
        )

    async def _publish_response(
        self,
        client: mqtt.Client,
        params: Dict[str, Any],
        reply: str,
        usage: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Publish LLM response."""
        logger.info(
            "Publishing llm/response for id=%s (len=%d)", params["req_id"], len(reply or "")
        )
        resp = LLMResponse(
            id=params["req_id"],
            reply=reply or None,
            provider=self.provider.name,
            model=params["model"],
            tokens=usage or {},
        )
        await self.mqtt_client.publish_event(
            client,
            event_type=self.config.get("EVENT_TYPE_LLM_RESPONSE", "llm.response"),
            topic=self.config.get("TOPIC_LLM_RESPONSE", "llm/response"),
            payload=resp,
            correlate=params["correlation_id"],
        )

    async def _publish_error(self, client: mqtt.Client, params: Dict[str, Any], error: str) -> None:
        """Publish error response."""
        logger.exception("generation failed")
        error_resp = LLMResponse(
            id=params["req_id"],
            error=error,
            provider=self.provider.name,
            model=params.get("model", "unknown"),
        )
        await self.mqtt_client.publish_event(
            client,
            event_type=self.config.get("EVENT_TYPE_LLM_RESPONSE", "llm.response"),
            topic=self.config.get("TOPIC_LLM_RESPONSE", "llm/response"),
            payload=error_resp,
            correlate=params.get("correlation_id"),
        )
