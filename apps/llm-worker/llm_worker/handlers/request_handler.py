"""LLM request processing handler."""
from __future__ import annotations

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
    
    def _extract_request_params(self, request: LLMRequest, envelope_id: Optional[str]) -> Dict[str, Any]:
        """Extract and prepare all request parameters."""
        text = request.text or ""
        want_stream = bool(request.stream)
        
        # RAG configuration
        rag_enabled = self.config.get("RAG_ENABLED", False)
        use_rag = rag_enabled if request.use_rag is None else bool(request.use_rag)
        rag_k = request.rag_k if (request.rag_k is not None and request.rag_k > 0) else self.config.get("RAG_TOP_K", 5)
        
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
        tools = self.tool_executor.tools if tool_calling_enabled and self.tool_executor.tools else None
        
        return {
            "text": text,
            "want_stream": want_stream,
            "use_rag": use_rag,
            "rag_k": rag_k,
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
            logger.warning("OPENAI_API_KEY not set; responding with error for id=%s", params["req_id"])
            asyncio.create_task(self._publish_error(
                client,
                params,
                "OPENAI_API_KEY not set"
            ))
            return False
        return True
    
    async def _prepare_prompt_with_rag(
        self,
        client: mqtt.Client,
        params: Dict[str, Any]
    ) -> Tuple[str, list[dict]]:
        """Prepare prompt with optional RAG context and conversation history."""
        text = params["text"]
        context = ""
        
        # RAG query if enabled
        if params["use_rag"]:
            context = await self.rag_handler.query(
                client,
                text,
                params["rag_k"],
                params["correlation_id"]
            )
        
        # Format prompt with context
        prompt = text
        if context:
            rag_template = self.config.get("RAG_PROMPT_TEMPLATE", "Context:\n{context}\n\nUser: {user}")
            prompt = rag_template.format(context=context, user=text)
        
        # Build messages list
        messages = []
        if params.get("conversation_history"):
            for msg in params["conversation_history"]:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        return prompt, messages
    
    async def _handle_streaming_request(self, client: mqtt.Client, params: Dict[str, Any]) -> None:
        """Handle streaming LLM request with optional TTS forwarding."""
        prompt, messages = await self._prepare_prompt_with_rag(client, params)
        
        seq = 0
        full_chunks: list[str] = []
        tts_buf = ""
        
        logger.info(
            "Starting streaming for id=%s via provider=%s (system_len=%s, history_len=%d)",
            params["req_id"],
            self.provider.name,
            len(params["system"] or ""),
            len(messages) - 1
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
            
            logger.debug("llm/stream id=%s seq=%d len=%d", params["req_id"], seq, len(delta_text or ""))
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
    
    async def _handle_non_streaming_request(self, client: mqtt.Client, params: Dict[str, Any]) -> None:
        """Handle non-streaming LLM request with optional tool calling."""
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
        if tool_calls and self.config.get("TOOL_CALLING_ENABLED", False):
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
        tool_calls: list[dict]
    ) -> None:
        """Execute tool calls and generate follow-up response."""
        # Add assistant message with tool_calls
        messages.append({
            "role": "assistant",
            "content": result.text,
            "tool_calls": tool_calls
        })
        
        # Execute tools
        tool_results = await self.tool_executor.execute_tool_calls(tool_calls)
        
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
    
    async def _publish_stream_end(self, client: mqtt.Client, params: Dict[str, Any], seq: int) -> None:
        """Publish stream end marker."""
        done = LLMStreamDelta(
            id=params["req_id"],
            seq=seq + 1,
            done=True,
            provider=self.provider.name,
            model=params["model"]
        )
        logger.info("Streaming done for id=%s with %d chunks", params["req_id"], seq)
        await self.mqtt_client.publish_event(
            client,
            event_type=self.config.get("EVENT_TYPE_LLM_STREAM", "llm.stream"),
            topic=self.config.get("TOPIC_LLM_STREAM", "llm/stream"),
            payload=done,
            correlate=params["correlation_id"],
        )
    
    async def _publish_tts_chunk(self, client: mqtt.Client, params: Dict[str, Any], text: str) -> None:
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
        usage: Optional[Dict[str, Any]] = None
    ) -> None:
        """Publish LLM response."""
        logger.info("Publishing llm/response for id=%s (len=%d)", params["req_id"], len(reply or ""))
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
