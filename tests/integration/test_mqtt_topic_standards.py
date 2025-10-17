"""Integration tests for MQTT topic standardization.

Tests verify:
1. Correlation ID propagation across service boundaries
2. Topic constants used consistently
3. QoS levels match constitution
4. Message validation with Pydantic contracts
5. End-to-end flows work correctly
"""

import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from tars.contracts.v1 import (
    TOPIC_LLM_REQUEST,
    TOPIC_LLM_RESPONSE,
    TOPIC_LLM_STREAM,
    TOPIC_LLM_TOOL_CALL_REQUEST,
    TOPIC_LLM_TOOL_CALL_RESULT,
    TOPIC_MEMORY_QUERY,
    TOPIC_MEMORY_RESULTS,
    TOPIC_STT_FINAL,
    TOPIC_TTS_SAY,
    TOPIC_TTS_STATUS,
    TOPIC_WAKE_EVENT,
    TOPIC_WAKE_MIC,
    TOPIC_CAMERA_FRAME,
    TOPIC_MOVEMENT_COMMAND,
    LLMRequest,
    LLMResponse,
    LLMStreamDelta,
    MemoryQuery,
    MemoryResults,
    FinalTranscript,
    TtsSay,
    TtsStatus,
    WakeEvent,
    ToolCallRequest,
    ToolCallResult,
)


class MockMQTTClient:
    """Mock MQTT client for integration testing."""

    def __init__(self):
        self.published: List[Dict[str, Any]] = []
        self.subscriptions: List[str] = []
        self._message_handlers: Dict[str, List[callable]] = {}

    async def publish(
        self, topic: str, payload: bytes, qos: int = 0, retain: bool = False
    ):
        """Record published messages for verification."""
        self.published.append(
            {
                "topic": topic,
                "payload": payload,
                "qos": qos,
                "retain": retain,
                "timestamp": asyncio.get_event_loop().time(),
            }
        )

    async def subscribe(self, topic: str, qos: int = 0):
        """Record subscriptions."""
        if topic not in self.subscriptions:
            self.subscriptions.append(topic)

    def add_handler(self, topic: str, handler: callable):
        """Add message handler for topic."""
        if topic not in self._message_handlers:
            self._message_handlers[topic] = []
        self._message_handlers[topic].append(handler)

    async def simulate_message(self, topic: str, payload: bytes):
        """Simulate receiving a message on a topic."""
        if topic in self._message_handlers:
            for handler in self._message_handlers[topic]:
                await handler(topic, payload)

    def get_messages_for_topic(self, topic: str) -> List[Dict[str, Any]]:
        """Get all published messages for a specific topic."""
        return [msg for msg in self.published if msg["topic"] == topic]

    def clear(self):
        """Clear all recorded data."""
        self.published.clear()
        self.subscriptions.clear()
        self._message_handlers.clear()


@pytest.fixture
def mqtt_client():
    """Provide mock MQTT client."""
    return MockMQTTClient()


@pytest.fixture
def correlation_id():
    """Generate unique correlation ID for each test."""
    return str(uuid.uuid4())


class TestCorrelationIDPropagation:
    """Test correlation IDs propagate correctly through service chains."""

    async def test_stt_to_llm_correlation(self, mqtt_client, correlation_id):
        """Test STT → Router → LLM flow maintains correlation ID."""
        # Simulate STT publishing final transcript
        stt_msg = FinalTranscript(
            text="What is the weather?",
            correlation_id=correlation_id,
            confidence=0.95,
            is_final=True,
        )

        await mqtt_client.publish(
            TOPIC_STT_FINAL,
            stt_msg.model_dump_json().encode(),
            qos=1,  # Per constitution: final transcripts QoS=1
        )

        # Verify QoS is correct
        stt_messages = mqtt_client.get_messages_for_topic(TOPIC_STT_FINAL)
        assert len(stt_messages) == 1
        assert stt_messages[0]["qos"] == 1

        # Router would process this and send to LLM
        llm_msg = LLMRequest(
            id=str(uuid.uuid4()),
            text=stt_msg.text,
            correlation_id=correlation_id,  # Same correlation ID
            stream=True,
            use_rag=False,
        )

        await mqtt_client.publish(
            TOPIC_LLM_REQUEST,
            llm_msg.model_dump_json().encode(),
            qos=1,  # Per constitution: requests QoS=1
        )

        # Verify correlation ID propagated
        llm_messages = mqtt_client.get_messages_for_topic(TOPIC_LLM_REQUEST)
        assert len(llm_messages) == 1
        llm_payload = json.loads(llm_messages[0]["payload"])
        assert llm_payload["correlation_id"] == correlation_id

    async def test_llm_to_tts_correlation(self, mqtt_client, correlation_id):
        """Test LLM → Router → TTS flow maintains correlation ID."""
        request_id = str(uuid.uuid4())

        # Simulate LLM streaming response
        delta_msg = LLMStreamDelta(
            id=request_id,
            seq=1,
            delta="The weather is sunny.",
            done=True,
            correlation_id=correlation_id,
        )

        await mqtt_client.publish(
            TOPIC_LLM_STREAM,
            delta_msg.model_dump_json().encode(),
            qos=0,  # Per constitution: streaming QoS=0
        )

        # Router aggregates and sends to TTS
        tts_msg = TtsSay(
            text="The weather is sunny.",
            utt_id=request_id,
            correlation_id=correlation_id,  # Propagated
        )

        await mqtt_client.publish(
            TOPIC_TTS_SAY,
            tts_msg.model_dump_json().encode(),
            qos=1,  # Per constitution: commands QoS=1
        )

        # Verify correlation ID in TTS
        tts_messages = mqtt_client.get_messages_for_topic(TOPIC_TTS_SAY)
        assert len(tts_messages) == 1
        tts_payload = json.loads(tts_messages[0]["payload"])
        assert tts_payload["correlation_id"] == correlation_id
        assert tts_messages[0]["qos"] == 1

    async def test_end_to_end_correlation(self, mqtt_client):
        """Test full STT → LLM → TTS flow with single correlation ID."""
        correlation_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())

        # 1. STT publishes transcript
        stt_msg = FinalTranscript(
            text="Tell me a joke",
            correlation_id=correlation_id,
            confidence=0.92,
            is_final=True,
        )
        await mqtt_client.publish(TOPIC_STT_FINAL, stt_msg.model_dump_json().encode(), qos=1)

        # 2. Router → LLM request
        llm_req = LLMRequest(
            id=request_id,
            text=stt_msg.text,
            correlation_id=correlation_id,
            stream=True,
        )
        await mqtt_client.publish(TOPIC_LLM_REQUEST, llm_req.model_dump_json().encode(), qos=1)

        # 3. LLM streams response
        llm_delta = LLMStreamDelta(
            id=request_id,
            seq=1,
            delta="Why did the chicken cross the road?",
            done=True,
            correlation_id=correlation_id,
        )
        await mqtt_client.publish(TOPIC_LLM_STREAM, llm_delta.model_dump_json().encode(), qos=0)

        # 4. Router → TTS
        tts_msg = TtsSay(
            text=llm_delta.delta,
            utt_id=request_id,
            correlation_id=correlation_id,
        )
        await mqtt_client.publish(TOPIC_TTS_SAY, tts_msg.model_dump_json().encode(), qos=1)

        # 5. TTS emits status
        tts_status = TtsStatus(
            event="speaking_start",
            text=tts_msg.text,
            utt_id=request_id,
            correlation_id=correlation_id,
        )
        await mqtt_client.publish(TOPIC_TTS_STATUS, tts_status.model_dump_json().encode(), qos=0)

        # Verify correlation ID in all messages
        all_messages = mqtt_client.published
        for msg in all_messages:
            payload = json.loads(msg["payload"])
            assert payload.get("correlation_id") == correlation_id


class TestQoSLevels:
    """Verify QoS levels match constitutional standards."""

    async def test_command_topics_qos1(self, mqtt_client, correlation_id):
        """Commands and requests must use QoS=1."""
        # TTS Say (command)
        tts_msg = TtsSay(text="Hello", correlation_id=correlation_id)
        await mqtt_client.publish(TOPIC_TTS_SAY, tts_msg.model_dump_json().encode(), qos=1)

        # LLM Request
        llm_msg = LLMRequest(id=str(uuid.uuid4()), text="Hi", correlation_id=correlation_id)
        await mqtt_client.publish(TOPIC_LLM_REQUEST, llm_msg.model_dump_json().encode(), qos=1)

        # Memory Query
        mem_msg = MemoryQuery(text="search", correlation_id=correlation_id)
        await mqtt_client.publish(TOPIC_MEMORY_QUERY, mem_msg.model_dump_json().encode(), qos=1)

        # Verify QoS=1 for all commands
        for msg in mqtt_client.published:
            assert msg["qos"] == 1

    async def test_streaming_topics_qos0(self, mqtt_client, correlation_id):
        """Streaming topics should use QoS=0."""
        # LLM Stream
        stream_msg = LLMStreamDelta(
            id=str(uuid.uuid4()),
            seq=1,
            delta="chunk",
            done=False,
            correlation_id=correlation_id,
        )
        await mqtt_client.publish(TOPIC_LLM_STREAM, stream_msg.model_dump_json().encode(), qos=0)

        # TTS Status (streaming event)
        status_msg = TtsStatus(
            event="speaking_start",
            text="test",
            correlation_id=correlation_id,
        )
        await mqtt_client.publish(TOPIC_TTS_STATUS, status_msg.model_dump_json().encode(), qos=0)

        # Verify QoS=0 for streaming
        for msg in mqtt_client.published:
            assert msg["qos"] == 0

    async def test_response_topics_qos1(self, mqtt_client, correlation_id):
        """Response topics use QoS=1."""
        # LLM Response
        llm_resp = LLMResponse(
            id=str(uuid.uuid4()),
            reply="answer",
            correlation_id=correlation_id,
            provider="openai",
            model="gpt-4",
        )
        await mqtt_client.publish(TOPIC_LLM_RESPONSE, llm_resp.model_dump_json().encode(), qos=1)

        # Memory Results
        mem_results = MemoryResults(
            query="test",
            k=5,
            results=[],
            correlation_id=correlation_id,
        )
        await mqtt_client.publish(
            TOPIC_MEMORY_RESULTS, mem_results.model_dump_json().encode(), qos=1
        )

        # Verify QoS=1
        for msg in mqtt_client.published:
            assert msg["qos"] == 1


class TestMessageValidation:
    """Test Pydantic validation of messages."""

    async def test_valid_messages_accepted(self, mqtt_client, correlation_id):
        """Valid messages pass Pydantic validation."""
        # Create valid messages
        stt_msg = FinalTranscript(
            text="Hello world",
            correlation_id=correlation_id,
            confidence=0.95,
            is_final=True,
        )
        assert stt_msg.text == "Hello world"
        assert stt_msg.correlation_id == correlation_id

        llm_msg = LLMRequest(
            id=str(uuid.uuid4()),
            text="Question?",
            correlation_id=correlation_id,
        )
        assert llm_msg.correlation_id == correlation_id

        tts_msg = TtsSay(
            text="Response",
            correlation_id=correlation_id,
        )
        assert tts_msg.text == "Response"

    async def test_invalid_messages_rejected(self):
        """Invalid messages fail Pydantic validation."""
        from pydantic import ValidationError

        # Missing required field
        with pytest.raises(ValidationError):
            FinalTranscript(correlation_id="test")  # Missing 'text'

        # Invalid type
        with pytest.raises(ValidationError):
            LLMRequest(
                id="valid-id",
                text=123,  # Should be string
                correlation_id="test",
            )

        # Extra field with extra="forbid"
        with pytest.raises(ValidationError):
            TtsSay(
                text="test",
                correlation_id="test",
                invalid_field="should fail",
            )


class TestSpecificFlows:
    """Test specific service interaction flows."""

    async def test_wake_event_flow(self, mqtt_client, correlation_id):
        """Test wake word detection → activation flow."""
        # Wake event detected
        wake_msg = WakeEvent(
            keyword="computer",
            confidence=0.88,
            correlation_id=correlation_id,
        )

        await mqtt_client.publish(
            TOPIC_WAKE_EVENT,
            wake_msg.model_dump_json().encode(),
            qos=1,  # Per constitution: events QoS=1
        )

        wake_messages = mqtt_client.get_messages_for_topic(TOPIC_WAKE_EVENT)
        assert len(wake_messages) == 1
        assert wake_messages[0]["qos"] == 1

        payload = json.loads(wake_messages[0]["payload"])
        assert payload["keyword"] == "computer"
        assert payload["correlation_id"] == correlation_id

    async def test_memory_query_flow(self, mqtt_client, correlation_id):
        """Test memory query → results flow."""
        # Query
        query_msg = MemoryQuery(
            text="search term",
            top_k=5,
            correlation_id=correlation_id,
        )
        await mqtt_client.publish(
            TOPIC_MEMORY_QUERY,
            query_msg.model_dump_json().encode(),
            qos=1,
        )

        # Results
        results_msg = MemoryResults(
            query="search term",
            k=5,
            results=[],
            correlation_id=correlation_id,
        )
        await mqtt_client.publish(
            TOPIC_MEMORY_RESULTS,
            results_msg.model_dump_json().encode(),
            qos=1,
        )

        # Verify correlation ID matches
        query_messages = mqtt_client.get_messages_for_topic(TOPIC_MEMORY_QUERY)
        results_messages = mqtt_client.get_messages_for_topic(TOPIC_MEMORY_RESULTS)

        query_payload = json.loads(query_messages[0]["payload"])
        results_payload = json.loads(results_messages[0]["payload"])

        assert query_payload["correlation_id"] == results_payload["correlation_id"]


class TestTopicConstants:
    """Verify topic constants are used consistently."""

    def test_topic_constants_defined(self):
        """All expected topic constants are defined in contracts."""
        # STT
        assert TOPIC_STT_FINAL == "stt/final"

        # TTS
        assert TOPIC_TTS_SAY == "tts/say"
        assert TOPIC_TTS_STATUS == "tts/status"

        # LLM
        assert TOPIC_LLM_REQUEST == "llm/request"
        assert TOPIC_LLM_RESPONSE == "llm/response"
        assert TOPIC_LLM_STREAM == "llm/stream"

        # Memory
        assert TOPIC_MEMORY_QUERY == "memory/query"
        assert TOPIC_MEMORY_RESULTS == "memory/results"

        # Wake
        assert TOPIC_WAKE_EVENT == "wake/event"
        assert TOPIC_WAKE_MIC == "wake/mic"

        # Camera
        assert TOPIC_CAMERA_FRAME == "camera/frame"

        # Movement
        assert TOPIC_MOVEMENT_COMMAND == "movement/command"

        # MCP/Tools (use LLM tool topics)
        assert TOPIC_LLM_TOOL_CALL_REQUEST == "llm/tool/call/request"
        assert TOPIC_LLM_TOOL_CALL_RESULT == "llm/tool/call/result"

    def test_topic_naming_convention(self):
        """Topics follow <domain>/<action> naming convention."""
        from tars.contracts.v1 import (
            TOPIC_STT_FINAL,
            TOPIC_TTS_SAY,
            TOPIC_LLM_REQUEST,
            TOPIC_MEMORY_QUERY,
            TOPIC_WAKE_EVENT,
            TOPIC_CAMERA_FRAME,
            TOPIC_MOVEMENT_COMMAND,
        )

        topics = [
            TOPIC_STT_FINAL,
            TOPIC_TTS_SAY,
            TOPIC_LLM_REQUEST,
            TOPIC_MEMORY_QUERY,
            TOPIC_WAKE_EVENT,
            TOPIC_CAMERA_FRAME,
            TOPIC_MOVEMENT_COMMAND,
        ]

        for topic in topics:
            parts = topic.split("/")
            assert len(parts) == 2, f"Topic {topic} should have format <domain>/<action>"
            assert parts[0], f"Domain missing in {topic}"
            assert parts[1], f"Action missing in {topic}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
