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
        
        # Character updates
        if topic == character_current_topic:
            await self._handle_character_current(message)
            return
        
        if topic == character_result_topic:
            await self._handle_character_result(message)
            return
        
        # Tool registry
        if topic == tools_registry_topic:
            await self.tool_handler.load_tools(message.payload)
            return
        
        # Memory/RAG results
        if topic == memory_results_topic:
            try:
                data = json.loads(message.payload)
                self.rag_handler.handle_results(data)
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
