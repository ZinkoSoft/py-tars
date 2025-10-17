"""Tests for TTS MQTT contracts."""

import pytest
from pydantic import ValidationError

from tars.contracts.v1.tts import (
    TOPIC_TTS_CONTROL,
    TOPIC_TTS_SAY,
    TOPIC_TTS_STATUS,
    TtsControlCommand,
    TtsSay,
    TtsStatus,
)


class TestTTSTopicConstants:
    """Test TTS topic constants are defined correctly."""

    def test_topic_constants_exist(self):
        """Test all topic constants are defined."""
        assert TOPIC_TTS_SAY == "tts/say"
        assert TOPIC_TTS_STATUS == "tts/status"
        assert TOPIC_TTS_CONTROL == "tts/control"


class TestTtsSay:
    """Test TtsSay contract."""

    def test_valid_minimal(self):
        """Test valid say command with minimal fields."""
        msg = TtsSay(text="Hello world")
        assert msg.text == "Hello world"
        assert msg.message_id is not None

    def test_valid_full(self):
        """Test valid say command with all fields."""
        msg = TtsSay(
            text="Hello world",
            voice="en-US-1",
            lang="en",
            utt_id="test-utt-123",
            style="cheerful",
            stt_ts=1234567890.0,
            wake_ack=True,
            system_announce=False,
        )
        assert msg.text == "Hello world"
        assert msg.voice == "en-US-1"
        assert msg.utt_id == "test-utt-123"

    def test_extra_fields_forbidden(self):
        """Test extra fields are rejected."""
        with pytest.raises(ValidationError):
            TtsSay(text="Hello", extra_field="not allowed")


class TestTtsStatus:
    """Test TtsStatus contract."""

    def test_valid_speaking_start(self):
        """Test valid speaking_start status."""
        msg = TtsStatus(event="speaking_start", text="Hello world")
        assert msg.event == "speaking_start"
        assert msg.text == "Hello world"
        assert msg.message_id is not None
        assert msg.timestamp > 0

    def test_valid_speaking_end(self):
        """Test valid speaking_end status."""
        msg = TtsStatus(event="speaking_end", text="Hello world", utt_id="test-123")
        assert msg.event == "speaking_end"
        assert msg.utt_id == "test-123"

    def test_invalid_event(self):
        """Test invalid event type is rejected."""
        with pytest.raises(ValidationError):
            TtsStatus(event="invalid_event")

    def test_extra_fields_forbidden(self):
        """Test extra fields are rejected."""
        with pytest.raises(ValidationError):
            TtsStatus(event="speaking_start", extra_field="not allowed")


class TestTtsControlCommand:
    """Test TtsControlCommand contract."""

    def test_valid_pause(self):
        """Test valid pause command."""
        msg = TtsControlCommand(action="pause")
        assert msg.action == "pause"
        assert msg.message_id is not None
        assert msg.ts > 0

    def test_valid_resume(self):
        """Test valid resume command."""
        msg = TtsControlCommand(action="resume", reason="wake_event")
        assert msg.action == "resume"
        assert msg.reason == "wake_event"

    def test_valid_stop(self):
        """Test valid stop command."""
        msg = TtsControlCommand(action="stop")
        assert msg.action == "stop"

    def test_valid_mute(self):
        """Test valid mute command."""
        msg = TtsControlCommand(action="mute", reason="wake_detection")
        assert msg.action == "mute"
        assert msg.reason == "wake_detection"

    def test_valid_unmute(self):
        """Test valid unmute command."""
        msg = TtsControlCommand(action="unmute")
        assert msg.action == "unmute"

    def test_invalid_action(self):
        """Test invalid action type is rejected."""
        with pytest.raises(ValidationError):
            TtsControlCommand(action="invalid_action")

    def test_extra_fields_forbidden(self):
        """Test extra fields are rejected."""
        with pytest.raises(ValidationError):
            TtsControlCommand(action="pause", extra_field="not allowed")

    def test_json_round_trip(self):
        """Test JSON serialization round trip."""
        msg = TtsControlCommand(action="pause", reason="test")
        json_str = msg.model_dump_json()
        msg2 = TtsControlCommand.model_validate_json(json_str)
        assert msg.action == msg2.action
        assert msg.reason == msg2.reason
