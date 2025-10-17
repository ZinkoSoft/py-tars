"""Contract tests for MQTT message Envelope schemas.

These tests validate that all messages published via MQTTClient conform to
the Envelope contract defined in tars.contracts.envelope.

Contract validation ensures:
- All published messages are valid JSON
- All messages follow Envelope structure
- Required fields are present (id, type, timestamp, data, source)
- Optional fields follow correct types when present
- Envelope.new() and publish_event() produce consistent structures

TDD Workflow: Write tests FIRST (RED), verify they fail, then ensure GREEN.
"""

import time
import pytest
import orjson
from pydantic import ValidationError

from tars.adapters.mqtt_client import MQTTClient
from tars.contracts.envelope import Envelope


@pytest.mark.contract
class TestEnvelopeContract:
    """Contract tests for Envelope message structure."""

    def test_envelope_new_required_fields(self):
        """Envelope.new() creates message with all required fields."""
        envelope = Envelope.new(
            event_type="test.event",
            data={"key": "value"},
        )
        
        # Required fields must be present
        assert envelope.id is not None
        assert envelope.type == "test.event"
        assert envelope.ts is not None  # ts, not timestamp
        assert envelope.data == {"key": "value"}
        assert envelope.source is not None
        
        # Validate structure
        envelope_dict = envelope.model_dump()
        assert "id" in envelope_dict
        assert "type" in envelope_dict
        assert "ts" in envelope_dict  # ts, not timestamp
        assert "data" in envelope_dict
        assert "source" in envelope_dict

    def test_envelope_new_optional_fields(self):
        """Envelope.new() handles optional fields correctly."""
        envelope = Envelope.new(
            event_type="test.event",
            data={"key": "value"},
            source="custom-source",
            correlate="parent-id-123",
        )
        
        # Optional fields set correctly
        assert envelope.source == "custom-source"
        assert envelope.id == "parent-id-123"  # correlate sets id field
        
        # Serialization excludes None values
        envelope_dict = envelope.model_dump(exclude_none=True)
        serialized = orjson.dumps(envelope_dict)
        parsed = orjson.loads(serialized)
        
        # All fields preserved through serialization
        assert parsed["source"] == "custom-source"
        assert parsed["id"] == "parent-id-123"

    def test_envelope_timestamp_is_float(self):
        """Envelope timestamp (ts) is a valid float (Unix epoch)."""
        before = time.time()
        envelope = Envelope.new(event_type="test.event", data={})
        after = time.time()
        
        # ts is a float
        assert isinstance(envelope.ts, float)
        
        # ts is reasonable (within test execution window)
        assert before <= envelope.ts <= after

    def test_envelope_id_is_unique(self):
        """Each Envelope.new() call generates unique ID."""
        envelope1 = Envelope.new(event_type="test.event", data={})
        envelope2 = Envelope.new(event_type="test.event", data={})
        
        # Different envelopes have different IDs
        assert envelope1.id != envelope2.id

    def test_envelope_serialization_roundtrip(self):
        """Envelope can be serialized and deserialized without loss."""
        original = Envelope.new(
            event_type="test.event",
            data={"key": "value", "nested": {"a": 1}},
            source="test-source",
        )
        
        # Serialize to JSON
        serialized = orjson.dumps(original.model_dump())
        
        # Deserialize back to Envelope
        parsed_dict = orjson.loads(serialized)
        reconstructed = Envelope(**parsed_dict)
        
        # All fields match
        assert reconstructed.id == original.id
        assert reconstructed.type == original.type
        assert reconstructed.ts == original.ts  # ts, not timestamp
        assert reconstructed.data == original.data
        assert reconstructed.source == original.source

    def test_envelope_rejects_invalid_data(self):
        """Envelope validation rejects invalid structures."""
        # Missing required field 'type'
        with pytest.raises(ValidationError):
            Envelope(
                id="test-id",
                ts=time.time(),  # ts, not timestamp
                data={"key": "value"},
                source="test",
            )
        
        # Missing required field 'data'
        with pytest.raises(ValidationError):
            Envelope(
                id="test-id",
                type="test.event",
                ts=time.time(),  # ts, not timestamp
                source="test",
            )
        
        # Invalid ts type
        with pytest.raises(ValidationError):
            Envelope(
                id="test-id",
                type="test.event",
                ts="not-a-number",  # Should be float
                data={"key": "value"},
                source="test",
            )


@pytest.mark.contract
@pytest.mark.asyncio
class TestMQTTClientEnvelopeContract:
    """Contract tests for MQTTClient publish_event() Envelope creation."""

    async def test_publish_event_creates_valid_envelope(self, mqtt_url, mock_mqtt_client):
        """publish_event() creates valid Envelope structure."""
        from unittest.mock import patch
        
        client = MQTTClient(mqtt_url, "test-client")
        
        published_payload = None
        
        async def capture_publish(topic, payload, **kwargs):
            nonlocal published_payload
            published_payload = payload
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            mock_mqtt_client.publish.side_effect = capture_publish
            
            await client.connect()
            await client.publish_event(
                topic="test/topic",
                event_type="test.event",
                data={"key": "value"},
            )
        
        # Verify payload was captured
        assert published_payload is not None
        
        # Parse as Envelope
        envelope_dict = orjson.loads(published_payload)
        envelope = Envelope(**envelope_dict)
        
        # Validate Envelope fields
        assert envelope.type == "test.event"
        assert envelope.data == {"key": "value"}
        assert envelope.id is not None
        assert envelope.ts is not None  # ts, not timestamp
        assert envelope.source is not None

    async def test_publish_event_respects_correlation_id(self, mqtt_url, mock_mqtt_client):
        """publish_event() with correlation_id sets Envelope.id correctly."""
        from unittest.mock import patch
        
        client = MQTTClient(mqtt_url, "test-client")
        
        published_payload = None
        
        async def capture_publish(topic, payload, **kwargs):
            nonlocal published_payload
            published_payload = payload
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            mock_mqtt_client.publish.side_effect = capture_publish
            
            await client.connect()
            await client.publish_event(
                topic="test/topic",
                event_type="test.event",
                data={"key": "value"},
                correlation_id="parent-123",
            )
        
        # Parse as Envelope
        envelope_dict = orjson.loads(published_payload)
        envelope = Envelope(**envelope_dict)
        
        # correlation_id becomes Envelope.id
        assert envelope.id == "parent-123"

    async def test_publish_event_with_pydantic_model(self, mqtt_url, mock_mqtt_client):
        """publish_event() accepts Pydantic models and serializes correctly."""
        from unittest.mock import patch
        from pydantic import BaseModel
        
        class TestData(BaseModel):
            message: str
            count: int
        
        client = MQTTClient(mqtt_url, "test-client")
        
        published_payload = None
        
        async def capture_publish(topic, payload, **kwargs):
            nonlocal published_payload
            published_payload = payload
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            mock_mqtt_client.publish.side_effect = capture_publish
            
            await client.connect()
            await client.publish_event(
                topic="test/topic",
                event_type="test.model",
                data=TestData(message="hello", count=42),
            )
        
        # Parse as Envelope
        envelope_dict = orjson.loads(published_payload)
        envelope = Envelope(**envelope_dict)
        
        # Pydantic model serialized correctly
        assert envelope.data == {"message": "hello", "count": 42}

    async def test_publish_health_creates_valid_envelope(self, mqtt_url, mock_mqtt_client):
        """publish_health() creates valid Envelope with HealthPing."""
        from unittest.mock import patch
        from tars.contracts.v1.health import HealthPing
        
        client = MQTTClient(mqtt_url, "test-client", enable_health=True)
        
        published_payload = None
        
        async def capture_publish(topic, payload, **kwargs):
            nonlocal published_payload
            published_payload = payload
        
        with patch("tars.adapters.mqtt_client.mqtt.Client", return_value=mock_mqtt_client):
            mock_mqtt_client.publish.side_effect = capture_publish
            
            await client.connect()
            await client.publish_health(
                ok=True,
                event="startup_complete",
            )
        
        # Parse as Envelope
        envelope_dict = orjson.loads(published_payload)
        envelope = Envelope(**envelope_dict)
        
        # Envelope structure is valid
        assert envelope.type == "health.status"  # health.status, not system.health
        assert "ok" in envelope.data
        assert envelope.data["ok"] is True
        assert "event" in envelope.data
        assert envelope.data["event"] == "startup_complete"


@pytest.mark.contract
class TestEnvelopeJSONCompatibility:
    """Contract tests for JSON serialization compatibility."""

    def test_envelope_uses_orjson_compatible_types(self):
        """Envelope uses types compatible with orjson serialization."""
        envelope = Envelope.new(
            event_type="test.event",
            data={
                "string": "value",
                "int": 42,
                "float": 3.14,
                "bool": True,
                "none": None,
                "list": [1, 2, 3],
                "dict": {"nested": "value"},
            },
        )
        
        # Serialize with orjson
        serialized = orjson.dumps(envelope.model_dump())
        
        # Deserialize and validate
        parsed = orjson.loads(serialized)
        
        # All types preserved
        assert parsed["data"]["string"] == "value"
        assert parsed["data"]["int"] == 42
        assert parsed["data"]["float"] == 3.14
        assert parsed["data"]["bool"] is True
        assert parsed["data"]["none"] is None
        assert parsed["data"]["list"] == [1, 2, 3]
        assert parsed["data"]["dict"] == {"nested": "value"}

    def test_envelope_model_dump_excludes_none(self):
        """Envelope.model_dump(exclude_none=True) removes None fields."""
        envelope = Envelope.new(
            event_type="test.event",
            data={"key": "value"},
        )
        
        # model_dump with exclude_none
        dumped = envelope.model_dump(exclude_none=True)
        
        # Only non-None fields present
        assert "id" in dumped
        assert "type" in dumped
        assert "ts" in dumped  # ts, not timestamp
        assert "data" in dumped
        assert "source" in dumped
        
        # No None values in dump
        for key, value in dumped.items():
            assert value is not None, f"Field {key} should not be None"

    def test_envelope_json_field_names(self):
        """Envelope uses correct field names in JSON (not Python aliases)."""
        envelope = Envelope.new(
            event_type="test.event",
            data={"key": "value"},
        )
        
        serialized = orjson.dumps(envelope.model_dump())
        parsed = orjson.loads(serialized)
        
        # Field names match contract (ts, not timestamp)
        expected_fields = {"id", "type", "ts", "data", "source"}
        actual_fields = set(parsed.keys())
        
        assert expected_fields.issubset(actual_fields), \
            f"Missing fields: {expected_fields - actual_fields}"
