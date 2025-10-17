"""Tests for STT MQTT contracts."""

import pytest
from pydantic import ValidationError

from tars.contracts.v1.stt import (
    AudioFFTData,
    FinalTranscript,
    PartialTranscript,
    TOPIC_STT_AUDIO_FFT,
    TOPIC_STT_FINAL,
    TOPIC_STT_PARTIAL,
)


class TestSTTTopicConstants:
    """Test STT topic constants are defined correctly."""

    def test_topic_constants_exist(self):
        """Test all topic constants are defined."""
        assert TOPIC_STT_FINAL == "stt/final"
        assert TOPIC_STT_PARTIAL == "stt/partial"
        assert TOPIC_STT_AUDIO_FFT == "stt/audio_fft"


class TestFinalTranscript:
    """Test FinalTranscript contract."""

    def test_valid_minimal(self):
        """Test valid transcript with minimal fields."""
        msg = FinalTranscript(text="Hello world")
        assert msg.text == "Hello world"
        assert msg.lang == "en"
        assert msg.is_final is True
        assert msg.message_id is not None
        assert msg.ts > 0

    def test_valid_full(self):
        """Test valid transcript with all fields."""
        msg = FinalTranscript(
            text="Hello world",
            lang="fr",
            confidence=0.95,
            utt_id="test-utt-123",
        )
        assert msg.text == "Hello world"
        assert msg.lang == "fr"
        assert msg.confidence == 0.95
        assert msg.utt_id == "test-utt-123"

    def test_confidence_validation(self):
        """Test confidence must be between 0 and 1."""
        with pytest.raises(ValidationError):
            FinalTranscript(text="Hello", confidence=1.5)

    def test_extra_fields_forbidden(self):
        """Test extra fields are rejected."""
        with pytest.raises(ValidationError):
            FinalTranscript(text="Hello", extra_field="not allowed")

    def test_json_round_trip(self):
        """Test JSON serialization round trip."""
        msg = FinalTranscript(text="Hello world", confidence=0.95)
        json_str = msg.model_dump_json()
        msg2 = FinalTranscript.model_validate_json(json_str)
        assert msg.text == msg2.text
        assert msg.confidence == msg2.confidence


class TestPartialTranscript:
    """Test PartialTranscript contract."""

    def test_valid_minimal(self):
        """Test valid partial with minimal fields."""
        msg = PartialTranscript(text="Hello")
        assert msg.text == "Hello"
        assert msg.is_final is False
        assert msg.message_id is not None

    def test_extra_fields_forbidden(self):
        """Test extra fields are rejected."""
        with pytest.raises(ValidationError):
            PartialTranscript(text="Hello", unknown="field")


class TestAudioFFTData:
    """Test AudioFFTData contract."""

    def test_valid_minimal(self):
        """Test valid FFT data with minimal fields."""
        fft_values = [10.0, 20.0, 30.0, 40.0]
        msg = AudioFFTData(fft_data=fft_values, sample_rate=16000)
        assert msg.fft_data == fft_values
        assert msg.sample_rate == 16000
        assert msg.message_id is not None
        assert msg.ts > 0

    def test_valid_empty_fft(self):
        """Test empty FFT data is allowed."""
        msg = AudioFFTData(fft_data=[], sample_rate=16000)
        assert msg.fft_data == []

    def test_invalid_sample_rate(self):
        """Test sample rate must be positive."""
        with pytest.raises(ValidationError):
            AudioFFTData(fft_data=[1.0, 2.0], sample_rate=0)

    def test_extra_fields_forbidden(self):
        """Test extra fields are rejected."""
        with pytest.raises(ValidationError):
            AudioFFTData(
                fft_data=[1.0, 2.0],
                sample_rate=16000,
                extra_field="not allowed",
            )

    def test_json_round_trip(self):
        """Test JSON serialization round trip."""
        fft_values = [10.0, 20.0, 30.0]
        msg = AudioFFTData(fft_data=fft_values, sample_rate=16000)
        json_str = msg.model_dump_json()
        msg2 = AudioFFTData.model_validate_json(json_str)
        assert msg.fft_data == msg2.fft_data
        assert msg.sample_rate == msg2.sample_rate
