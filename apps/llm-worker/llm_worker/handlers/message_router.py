"""Message routing and topic-based dispatch for LLM worker."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import asyncio_mqtt as mqtt
import orjson as json
from pydantic import ValidationError

from tars.contracts.envelope import Envelope  # type: ignore[import]

logger = logging.getLogger("llm-worker.router")


class MessageRouter:
    """Routes MQTT messages to appropriate handlers based on topic."""
    
    def __init__(
        self,
        *,
        character_handler,
        tool_handler,
        rag_handler,
        request_handler,
    ):
        """Initialize router with all required handlers.
        
        Args:
            character_handler: Handler for character/persona messages
            tool_handler: Handler for tool registry messages
            rag_handler: Handler for RAG/memory results
            request_handler: Handler for LLM request processing
        """
        self.character_handler = character_handler
        self.tool_handler = tool_handler
        self.rag_handler = rag_handler
        self.request_handler = request_handler
    
    async def route_message(
        self,
        client: mqtt.Client,
        message,
        *,
        character_current_topic: str,
        character_result_topic: str,
        tools_registry_topic: str,
        tools_result_topic: str,
        memory_results_topic: str,
        llm_request_topic: str,
    ) -> None:
        """Route a single MQTT message to the appropriate handler.
        
        Args:
            client: MQTT client for publishing responses
            message: MQTT message to route
            *_topic: Topic names for routing decisions
        """
        topic = str(getattr(message, "topic", ""))
        
        # Debug: log all received topics
        logger.debug("Received message on topic: %s", topic)
        
        # Character updates
        if topic == character_current_topic:
            await self._handle_character_current(message)
            return
        
        if topic == character_result_topic:
            await self._handle_character_result(message)
            return
        
        # Tool registry
        if topic == tools_registry_topic:
            logger.debug("Received tool registry message on topic: %s", topic)
            try:
                registry_data = json.loads(message.payload)
                logger.debug("Parsed registry data with %d tools", len(registry_data.get("tools", [])))
                await self.tool_handler.load_tools_from_registry(registry_data)
            except Exception as e:
                logger.warning("Failed to load tools from registry: %s", e, exc_info=True)
            return
        
        # Tool results
        if topic == tools_result_topic:
            logger.debug("Received tool result on topic: %s", topic)
            try:
                result_data = json.loads(message.payload)
                call_id = result_data.get("call_id")
                content = result_data.get("content")
                error = result_data.get("error")
                if call_id:
                    self.tool_handler.handle_tool_result(call_id, content, error)
                else:
                    logger.warning("Tool result missing call_id: %s", result_data)
            except Exception as e:
                logger.warning("Failed to handle tool result: %s", e, exc_info=True)
            return
        
        # Memory/RAG results
        if topic == memory_results_topic:
            logger.info("MEMORY RESULTS MESSAGE RECEIVED: topic=%s, payload_size=%d", topic, len(message.payload))
            try:
                # Parse envelope to extract data and correlation ID
                envelope = Envelope.model_validate_json(message.payload)
                data = envelope.data if isinstance(envelope.data, dict) else {}
                # Add correlation ID to data for RAG handler
                data["correlate"] = envelope.id
                logger.debug("Memory results received: envelope_id=%s, data_keys=%s", envelope.id, list(data.keys()))
                self.rag_handler.handle_results(data)
            except ValidationError:
                # Fallback to direct JSON parsing for backward compatibility
                try:
                    data = json.loads(message.payload)
                    logger.info("MEMORY RESULTS FALLBACK PARSING: data_keys=%s", list(data.keys()) if isinstance(data, dict) else "not_dict")
                    self.rag_handler.handle_results(data)
                except Exception as e:
                    logger.warning("Failed to parse memory/results payload: %s", e)
            except Exception as e:
                logger.warning("Failed to handle memory/results: %s", e)
            return
        
        # LLM requests
        if topic == llm_request_topic:
            await self.request_handler.process_request(client, message.payload)
    
    async def _handle_character_current(self, message) -> None:
        """Handle character/current retained message with envelope support."""
        payload_data: Dict[str, Any] = {}
        
        try:
            envelope = Envelope.model_validate_json(message.payload)
            raw_data = envelope.data
            payload_data = raw_data if isinstance(raw_data, dict) else {}
        except ValidationError:
            try:
                payload_data = json.loads(message.payload)
            except Exception:
                payload_data = {}
        
        if not payload_data:
            return
        
        self.character_handler.update_from_current(payload_data)
        logger.info("character/current updated: name=%s", payload_data.get("name"))
    
    async def _handle_character_result(self, message) -> None:
        """Handle character/result message with envelope support."""
        payload_data: Dict[str, Any] = {}
        
        try:
            envelope = Envelope.model_validate_json(message.payload)
            raw_data = envelope.data
            payload_data = raw_data if isinstance(raw_data, dict) else {}
        except ValidationError:
            try:
                payload_data = json.loads(message.payload)
            except Exception:
                payload_data = {}
        
        if not payload_data:
            return
        
        # Update character based on payload structure
        if "name" in payload_data:
            # Full character snapshot
            self.character_handler.update_from_current(payload_data)
        elif "section" in payload_data and "value" in payload_data:
            # Section update
            section_key = payload_data.get("section")
            if isinstance(section_key, str):
                self.character_handler.update_section(section_key, payload_data.get("value"))
        else:
            # Partial update
            self.character_handler.merge_update(payload_data)
        
        logger.info("character/result received: name=%s", self.character_handler.get_name())
