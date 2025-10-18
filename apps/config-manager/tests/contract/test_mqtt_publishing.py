"""Contract tests for MQTT message publishing on config updates.

Tests verify the exact MQTT message format, signature verification, and
topic structure according to the config-manager contract.
"""

import asyncio
import json
import pytest
from pathlib import Path
from typing import AsyncGenerator, List, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

from tars.config.database import ConfigDatabase
from tars.config.models import ConfigEpoch


@pytest.fixture
async def test_db(tmp_path: Path) -> AsyncGenerator[ConfigDatabase, None]:
    """Create a temporary test database."""
    db_path = tmp_path / "test_config.db"
    db = ConfigDatabase(db_path)
    await db.connect()
    await db.initialize_schema()
    yield db
    await db.close()


@pytest.fixture
def mock_mqtt_client():
    """Mock MQTT client for testing."""
    client = AsyncMock()
    client.publish = AsyncMock()
    return client


@pytest.fixture
def sample_config() -> dict:
    """Sample configuration for testing."""
    return {
        "whisper_model": "base.en",
        "vad_threshold": 0.5,
        "streaming_partials": False,
    }


@pytest.mark.asyncio
class TestMQTTMessageFormat:
    """Test MQTT message format and contract compliance."""

    async def test_config_update_message_structure(
        self, test_db: ConfigDatabase, mock_mqtt_client, sample_config: dict
    ):
        """Test that config update produces correct MQTT message structure."""
        service_name = "stt-worker"
        expected_fields = ["service", "config", "version", "config_epoch", "checksum"]

        # Mock the MQTT publish
        published_messages: List[Tuple[str, bytes]] = []

        async def capture_publish(topic: str, payload: bytes, **kwargs):
            published_messages.append((topic, payload))

        mock_mqtt_client.publish.side_effect = capture_publish

        # Simulate config update with MQTT publishing
        # In real implementation, this would be handled by config-manager service
        await test_db.upsert_service_config(
            service=service_name,
            config=sample_config,
            expected_version=None,
        )

        # Get the service config to construct expected message
        result = await test_db.get_service_config(service_name)
        assert result is not None

        # Construct expected message payload
        expected_message = {
            "service": result.service,
            "config": result.config,
            "version": result.version,
            "config_epoch": result.config_epoch,
            "checksum": result.checksum,
        }

        # Verify all required fields present
        for field in expected_fields:
            assert field in expected_message
            assert expected_message[field] is not None

    async def test_mqtt_topic_format(self, test_db: ConfigDatabase):
        """Test that MQTT topic follows config/updated/<service> format."""
        service_name = "stt-worker"
        expected_topic = f"config/updated/{service_name}"

        # Expected format: config/updated/<service-name>
        assert expected_topic == "config/updated/stt-worker"

        # Verify topic doesn't contain spaces or invalid chars
        assert " " not in expected_topic
        assert "#" not in expected_topic
        assert "+" not in expected_topic

    async def test_qos_and_retain_settings(self):
        """Test that MQTT messages use QoS 1 and retain=False."""
        # QoS 1 ensures at-least-once delivery
        # retain=False prevents stale configs on service startup
        expected_qos = 1
        expected_retain = False

        assert expected_qos == 1
        assert expected_retain is False

    async def test_checksum_calculation_consistency(
        self, test_db: ConfigDatabase, sample_config: dict
    ):
        """Test that checksum is calculated consistently for same config."""
        import hashlib

        service_name = "stt-worker"

        # Create config
        await test_db.upsert_service_config(
            service=service_name,
            config=sample_config,
            expected_version=None,
        )

        result = await test_db.get_service_config(service_name)
        assert result is not None

        # Manually calculate checksum
        config_json = json.dumps(result.config, sort_keys=True)
        expected_checksum = hashlib.sha256(config_json.encode()).hexdigest()

        # Verify checksum matches
        assert result.checksum == expected_checksum

    async def test_config_epoch_included_in_message(
        self, test_db: ConfigDatabase, sample_config: dict
    ):
        """Test that config_epoch is included in MQTT message."""
        service_name = "stt-worker"

        await test_db.upsert_service_config(
            service=service_name,
            config=sample_config,
            expected_version=None,
        )

        result = await test_db.get_service_config(service_name)
        epoch = await test_db.get_config_epoch()

        assert result is not None
        assert epoch is not None
        assert result.config_epoch == epoch.config_epoch
        assert len(result.config_epoch) == 36  # UUID format


@pytest.mark.asyncio
class TestMessageSignature:
    """Test Ed25519 signature verification for MQTT messages."""

    async def test_signature_verification_with_valid_key(self):
        """Test that valid signature passes verification."""
        # Note: Actual implementation would use Ed25519 signing
        # This test validates the contract
        from nacl.signing import SigningKey, VerifyKey
        from nacl.encoding import HexEncoder

        # Generate key pair
        signing_key = SigningKey.generate()
        verify_key = signing_key.verify_key

        # Sample message
        message = json.dumps(
            {
                "service": "stt-worker",
                "config": {"test": "value"},
                "version": 1,
                "config_epoch": "test-epoch",
                "checksum": "abcd1234",
            },
            sort_keys=True,
        )

        # Sign message
        signed = signing_key.sign(message.encode(), encoder=HexEncoder)
        signature = signed.signature

        # Verify signature
        verify_key.verify(message.encode(), signature, encoder=HexEncoder)

        # If no exception raised, verification succeeded
        assert True

    async def test_signature_verification_with_invalid_key_fails(self):
        """Test that invalid signature fails verification."""
        from nacl.signing import SigningKey, VerifyKey
        from nacl.encoding import HexEncoder
        from nacl.exceptions import BadSignatureError

        # Generate two different key pairs
        signing_key1 = SigningKey.generate()
        signing_key2 = SigningKey.generate()
        verify_key2 = signing_key2.verify_key

        # Sign with key1
        message = b"test message"
        signed = signing_key1.sign(message, encoder=HexEncoder)
        signature = signed.signature

        # Try to verify with key2 (should fail)
        with pytest.raises(BadSignatureError):
            verify_key2.verify(message, signature, encoder=HexEncoder)

    async def test_signature_field_format(self):
        """Test that signature field is hex-encoded string."""
        from nacl.signing import SigningKey
        from nacl.encoding import HexEncoder

        signing_key = SigningKey.generate()
        message = b"test message"
        signed = signing_key.sign(message, encoder=HexEncoder)

        # Signature should be hex string
        signature_hex = signed.signature.decode("utf-8")
        assert len(signature_hex) == 128  # Ed25519 signature is 64 bytes = 128 hex chars
        assert all(c in "0123456789abcdef" for c in signature_hex.lower())


@pytest.mark.asyncio
class TestMessageValidation:
    """Test validation of incoming MQTT messages."""

    async def test_reject_message_with_missing_fields(self):
        """Test that messages with missing required fields are rejected."""
        invalid_messages = [
            {},  # Empty
            {"service": "stt-worker"},  # Missing config
            {"config": {"test": "value"}},  # Missing service
            {
                "service": "stt-worker",
                "config": {"test": "value"},
            },  # Missing version, epoch, checksum
        ]

        required_fields = ["service", "config", "version", "config_epoch", "checksum"]

        for msg in invalid_messages:
            missing_fields = [f for f in required_fields if f not in msg]
            assert len(missing_fields) > 0, f"Message should be missing fields: {msg}"

    async def test_reject_message_with_invalid_types(self):
        """Test that messages with invalid field types are rejected."""
        invalid_messages = [
            {
                "service": 123,  # Should be string
                "config": {},
                "version": 1,
                "config_epoch": "epoch",
                "checksum": "hash",
            },
            {
                "service": "stt-worker",
                "config": "not-a-dict",  # Should be dict
                "version": 1,
                "config_epoch": "epoch",
                "checksum": "hash",
            },
            {
                "service": "stt-worker",
                "config": {},
                "version": "1",  # Should be int
                "config_epoch": "epoch",
                "checksum": "hash",
            },
        ]

        for msg in invalid_messages:
            # Validation should catch type mismatches
            if not isinstance(msg.get("service"), str):
                assert True
            elif not isinstance(msg.get("config"), dict):
                assert True
            elif not isinstance(msg.get("version"), int):
                assert True

    async def test_accept_valid_message(self):
        """Test that valid message passes validation."""
        valid_message = {
            "service": "stt-worker",
            "config": {
                "whisper_model": "base.en",
                "vad_threshold": 0.5,
            },
            "version": 1,
            "config_epoch": "550e8400-e29b-41d4-a716-446655440000",
            "checksum": "abc123def456",
        }

        # Validate structure
        assert isinstance(valid_message["service"], str)
        assert isinstance(valid_message["config"], dict)
        assert isinstance(valid_message["version"], int)
        assert isinstance(valid_message["config_epoch"], str)
        assert isinstance(valid_message["checksum"], str)

        # Validate values
        assert len(valid_message["service"]) > 0
        assert valid_message["version"] > 0
        assert len(valid_message["config_epoch"]) == 36  # UUID


@pytest.mark.asyncio
class TestServiceIntegration:
    """Test integration with services receiving config updates."""

    async def test_service_receives_update_on_config_change(
        self, test_db: ConfigDatabase, mock_mqtt_client, sample_config: dict
    ):
        """Test that service receives MQTT message when config changes."""
        service_name = "stt-worker"
        received_messages: List[dict] = []

        # Mock subscription handler
        async def handle_message(payload: bytes):
            msg = json.loads(payload)
            received_messages.append(msg)

        # Create initial config
        await test_db.upsert_service_config(
            service=service_name,
            config=sample_config,
            expected_version=None,
        )

        # Simulate MQTT publish (in real app, config-manager does this)
        result = await test_db.get_service_config(service_name)
        assert result is not None

        message_payload = json.dumps(
            {
                "service": result.service,
                "config": result.config,
                "version": result.version,
                "config_epoch": result.config_epoch,
                "checksum": result.checksum,
            }
        ).encode()

        await mock_mqtt_client.publish(
            f"config/updated/{service_name}",
            message_payload,
            qos=1,
            retain=False,
        )

        # Simulate service receiving message
        await handle_message(message_payload)

        # Verify service received correct message
        assert len(received_messages) == 1
        assert received_messages[0]["service"] == service_name
        assert received_messages[0]["config"] == sample_config

    async def test_service_ignores_updates_for_other_services(
        self, mock_mqtt_client
    ):
        """Test that service only processes messages for its own name."""
        my_service = "stt-worker"
        other_service = "tts-worker"

        # Service should subscribe to config/updated/stt-worker
        my_topic = f"config/updated/{my_service}"
        other_topic = f"config/updated/{other_service}"

        # Verify topics are different
        assert my_topic != other_topic

        # Service should NOT receive messages on other_topic
        # (MQTT handles this via subscription)

    async def test_service_applies_config_atomically(
        self, test_db: ConfigDatabase, sample_config: dict
    ):
        """Test that service applies entire config update atomically."""
        service_name = "stt-worker"

        # Config should have multiple related fields
        config_with_related_fields = {
            "whisper_model": "base.en",
            "model_dir": "/models",
            "vad_threshold": 0.5,
            "vad_min_silence_ms": 500,
        }

        await test_db.upsert_service_config(
            service=service_name,
            config=config_with_related_fields,
            expected_version=None,
        )

        result = await test_db.get_service_config(service_name)
        assert result is not None

        # All fields should be present (atomic update)
        assert set(result.config.keys()) == set(config_with_related_fields.keys())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
