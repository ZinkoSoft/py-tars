"""Contract tests for MQTT message parsing."""

import json

import pytest
from pydantic import ValidationError

from tars.contracts.v1.stt import FinalTranscript
from tars.contracts.v1.llm import LLMResponse
from tars.contracts.v1.wake import WakeEvent


class TestFinalTranscriptContract:
    """Test suite for FinalTranscript contract validation."""

    def test_parse_valid_final_transcript(self):
        """Test parsing a valid FinalTranscript from MQTT payload."""
        payload = json.dumps({
            "message_id": "test123",
            "text": "What is the weather today?",
            "lang": "en",
            "confidence": 0.95,
            "ts": 1699999999.0,
            "is_final": True,
        })

        data = json.loads(payload)
        transcript = FinalTranscript(**data)

        assert transcript.message_id == "test123"
        assert transcript.text == "What is the weather today?"
        assert transcript.lang == "en"
        assert transcript.confidence == 0.95
        assert transcript.is_final is True

    def test_parse_minimal_final_transcript(self):
        """Test parsing FinalTranscript with only required fields."""
        payload = json.dumps({
            "text": "Hello TARS",
        })

        data = json.loads(payload)
        transcript = FinalTranscript(**data)

        assert transcript.text == "Hello TARS"
        assert transcript.lang == "en"  # Default
        assert transcript.is_final is True  # Default
        assert transcript.message_id is not None  # Auto-generated

    def test_reject_extra_fields(self):
        """Test that extra fields are forbidden (extra='forbid')."""
        payload = json.dumps({
            "text": "Hello TARS",
            "unknown_field": "should_fail",
        })

        data = json.loads(payload)

        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            FinalTranscript(**data)

    def test_reject_invalid_confidence(self):
        """Test that confidence must be between 0 and 1."""
        # Confidence > 1
        payload = json.dumps({
            "text": "Test",
            "confidence": 1.5,
        })

        data = json.loads(payload)

        with pytest.raises(ValidationError):
            FinalTranscript(**data)

        # Confidence < 0
        payload = json.dumps({
            "text": "Test",
            "confidence": -0.1,
        })

        data = json.loads(payload)

        with pytest.raises(ValidationError):
            FinalTranscript(**data)

    def test_parse_with_utt_id(self):
        """Test parsing with utterance ID."""
        payload = json.dumps({
            "text": "Test message",
            "utt_id": "utt_12345",
        })

        data = json.loads(payload)
        transcript = FinalTranscript(**data)

        assert transcript.text == "Test message"
        assert transcript.utt_id == "utt_12345"


class TestLLMResponseContract:
    """Test suite for LLMResponse contract validation."""

    def test_parse_valid_llm_response(self):
        """Test parsing a valid LLMResponse from MQTT payload."""
        payload = json.dumps({
            "message_id": "llm123",
            "id": "req456",
            "reply": "The weather is sunny with a high of 75 degrees.",
            "provider": "openai",
            "model": "gpt-4",
            "tokens": {"prompt": 15, "completion": 12, "total": 27},
        })

        data = json.loads(payload)
        response = LLMResponse(**data)

        assert response.message_id == "llm123"
        assert response.id == "req456"
        assert response.reply == "The weather is sunny with a high of 75 degrees."
        assert response.provider == "openai"
        assert response.model == "gpt-4"
        assert response.tokens["total"] == 27

    def test_parse_minimal_llm_response(self):
        """Test parsing LLMResponse with only required fields."""
        payload = json.dumps({
            "id": "req789",
        })

        data = json.loads(payload)
        response = LLMResponse(**data)

        assert response.id == "req789"
        assert response.reply is None
        assert response.error is None
        assert response.message_id is not None  # Auto-generated

    def test_parse_llm_error_response(self):
        """Test parsing LLMResponse with error."""
        payload = json.dumps({
            "id": "req999",
            "error": "API rate limit exceeded",
        })

        data = json.loads(payload)
        response = LLMResponse(**data)

        assert response.id == "req999"
        assert response.error == "API rate limit exceeded"
        assert response.reply is None

    def test_reject_extra_fields_llm(self):
        """Test that extra fields are forbidden in LLMResponse."""
        payload = json.dumps({
            "id": "req123",
            "reply": "Test",
            "extra_field": "should_fail",
        })

        data = json.loads(payload)

        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            LLMResponse(**data)

    def test_parse_with_all_optional_fields(self):
        """Test parsing LLMResponse with all optional fields set."""
        payload = json.dumps({
            "id": "req_full",
            "reply": "Complete response",
            "error": None,
            "provider": "anthropic",
            "model": "claude-3",
            "tokens": {"prompt": 10, "completion": 20},
        })

        data = json.loads(payload)
        response = LLMResponse(**data)

        assert response.reply == "Complete response"
        assert response.provider == "anthropic"
        assert response.model == "claude-3"


class TestWakeEventContract:
    """Test suite for WakeEvent contract validation."""

    def test_parse_valid_wake_event(self):
        """Test parsing a valid WakeEvent from MQTT payload."""
        payload = json.dumps({
            "message_id": "wake123",
            "type": "wake",
            "confidence": 0.87,
            "energy": 0.65,
            "ts": 1699999999.0,
        })

        data = json.loads(payload)
        wake_event = WakeEvent(**data)

        assert wake_event.message_id == "wake123"
        assert wake_event.type == "wake"
        assert wake_event.confidence == 0.87
        assert wake_event.energy == 0.65

    def test_parse_minimal_wake_event(self):
        """Test parsing WakeEvent with only required fields."""
        payload = json.dumps({
            "type": "wake",
        })

        data = json.loads(payload)
        wake_event = WakeEvent(**data)

        assert wake_event.type == "wake"
        assert wake_event.message_id is not None  # Auto-generated
        assert wake_event.confidence is None
        assert wake_event.energy is None

    def test_parse_wake_end_event(self):
        """Test parsing wake end event."""
        payload = json.dumps({
            "type": "end",
            "cause": "timeout",
        })

        data = json.loads(payload)
        wake_event = WakeEvent(**data)

        assert wake_event.type == "end"
        assert wake_event.cause == "timeout"

    def test_reject_extra_fields_wake(self):
        """Test that extra fields are forbidden in WakeEvent."""
        payload = json.dumps({
            "type": "wake",
            "unexpected_field": "fail",
        })

        data = json.loads(payload)

        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            WakeEvent(**data)

    def test_reject_invalid_confidence_wake(self):
        """Test that confidence must be between 0 and 1."""
        # Confidence > 1
        payload = json.dumps({
            "type": "wake",
            "confidence": 1.2,
        })

        data = json.loads(payload)

        with pytest.raises(ValidationError):
            WakeEvent(**data)

        # Confidence < 0
        payload = json.dumps({
            "type": "wake",
            "confidence": -0.1,
        })

        data = json.loads(payload)

        with pytest.raises(ValidationError):
            WakeEvent(**data)

    def test_reject_invalid_energy(self):
        """Test that energy must be >= 0."""
        payload = json.dumps({
            "type": "wake",
            "energy": -0.5,
        })

        data = json.loads(payload)

        with pytest.raises(ValidationError):
            WakeEvent(**data)

    def test_parse_with_tts_id(self):
        """Test parsing WakeEvent with TTS suppression ID."""
        payload = json.dumps({
            "type": "wake",
            "tts_id": "tts_abc123",
        })

        data = json.loads(payload)
        wake_event = WakeEvent(**data)

        assert wake_event.type == "wake"
        assert wake_event.tts_id == "tts_abc123"


class TestContractIntegration:
    """Integration tests for contract parsing in realistic scenarios."""

    def test_full_conversation_flow_contracts(self):
        """Test parsing contracts for a complete conversation flow."""
        # 1. Wake event
        wake_payload = json.dumps({
            "type": "wake",
            "confidence": 0.85,
        })
        wake_data = json.loads(wake_payload)
        wake_event = WakeEvent(**wake_data)
        assert wake_event.type == "wake"

        # 2. STT final transcript
        stt_payload = json.dumps({
            "text": "What is the weather?",
            "confidence": 0.92,
        })
        stt_data = json.loads(stt_payload)
        transcript = FinalTranscript(**stt_data)
        assert transcript.text == "What is the weather?"

        # 3. LLM response
        llm_payload = json.dumps({
            "id": "req123",
            "reply": "The weather is sunny.",
        })
        llm_data = json.loads(llm_payload)
        response = LLMResponse(**llm_data)
        assert response.reply == "The weather is sunny."

    def test_error_handling_in_contracts(self):
        """Test that malformed contracts raise appropriate errors."""
        # Missing required field
        with pytest.raises(ValidationError):
            FinalTranscript(**{})

        with pytest.raises(ValidationError):
            LLMResponse(**{})

        with pytest.raises(ValidationError):
            WakeEvent(**{})

        # Invalid types
        with pytest.raises(ValidationError):
            FinalTranscript(**{"text": 123})  # text should be string

        with pytest.raises(ValidationError):
            LLMResponse(**{"id": None})  # id is required

        with pytest.raises(ValidationError):
            WakeEvent(**{"type": None})  # type is required
