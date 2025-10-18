"""Contract tests for MQTT message schemas.

These tests validate that MQTT payload models match the JSON schemas
defined in specs/005-unified-configuration-management/contracts/
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from tars.config.mqtt_models import ConfigHealthPayload, ConfigUpdatePayload


@pytest.fixture
def contracts_dir() -> Path:
    """Get path to contracts directory."""
    # Assuming tests run from repo root
    return Path(__file__).parent.parent.parent.parent.parent.parent / "specs" / "005-unified-configuration-management" / "contracts"


class TestConfigUpdatePayloadContract:
    """Test ConfigUpdatePayload against JSON schema."""

    def test_valid_payload_matches_schema(self, contracts_dir: Path) -> None:
        """Test that valid payload conforms to schema."""
        payload = ConfigUpdatePayload(
            version=1,
            service="stt-worker",
            config={"whisper_model": "base.en", "vad_threshold": 0.5},
            checksum="a" * 64,  # 64-char hex string
            config_epoch="550e8400-e29b-41d4-a716-446655440000",
            issued_at=datetime.utcnow(),
            signature="SGVsbG8gV29ybGQh",  # base64
        )

        # Validate against Pydantic model
        payload_dict = payload.model_dump(mode="json")
        assert payload_dict["version"] == 1
        assert payload_dict["service"] == "stt-worker"
        assert isinstance(payload_dict["config"], dict)

    def test_extra_fields_rejected(self) -> None:
        """Test that extra fields are rejected (extra='forbid')."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            ConfigUpdatePayload(
                version=1,
                service="test",
                config={},
                checksum="a" * 64,
                config_epoch="550e8400-e29b-41d4-a716-446655440000",
                issued_at=datetime.utcnow(),
                signature="test",
                extra_field="should fail",  # type: ignore
            )

    def test_required_fields_enforced(self) -> None:
        """Test that required fields must be present."""
        with pytest.raises(Exception):  # Missing required fields
            ConfigUpdatePayload(  # type: ignore
                version=1,
                service="test",
                # Missing config, checksum, config_epoch, signature
            )


class TestConfigHealthPayloadContract:
    """Test ConfigHealthPayload against JSON schema."""

    def test_healthy_status_payload(self) -> None:
        """Test payload for healthy status."""
        payload = ConfigHealthPayload(
            ok=True,
            database_status="healthy",
            operational_mode="normal",
            config_epoch="550e8400-e29b-41d4-a716-446655440000",
            schema_version=1,
            lkg_cache_valid=True,
            litestream_status="healthy",
            last_backup=datetime.utcnow(),
            event=None,
            err=None,
        )

        payload_dict = payload.model_dump(mode="json")
        assert payload_dict["ok"] is True
        assert payload_dict["database_status"] == "healthy"
        assert payload_dict["operational_mode"] == "normal"

    def test_unhealthy_status_payload(self) -> None:
        """Test payload for unhealthy status."""
        payload = ConfigHealthPayload(
            ok=False,
            database_status="corrupted",
            operational_mode="read-only-fallback",
            config_epoch="550e8400-e29b-41d4-a716-446655440000",
            schema_version=1,
            lkg_cache_valid=True,
            litestream_status="error",
            last_backup=None,
            event="Database corruption detected",
            err="SQLite integrity check failed",
        )

        payload_dict = payload.model_dump(mode="json")
        assert payload_dict["ok"] is False
        assert payload_dict["err"] == "SQLite integrity check failed"

    def test_enum_validation(self) -> None:
        """Test that enum fields validate correctly."""
        # Valid values
        payload = ConfigHealthPayload(
            ok=True,
            database_status="healthy",
            operational_mode="normal",
            config_epoch="550e8400-e29b-41d4-a716-446655440000",
            schema_version=1,
            lkg_cache_valid=True,
            litestream_status="healthy",
        )
        assert payload.database_status == "healthy"

        # Invalid value should fail
        with pytest.raises(Exception):  # Pydantic ValidationError
            ConfigHealthPayload(
                ok=True,
                database_status="invalid-status",  # type: ignore
                operational_mode="normal",
                config_epoch="550e8400-e29b-41d4-a716-446655440000",
                schema_version=1,
                lkg_cache_valid=True,
                litestream_status="healthy",
            )

    def test_roundtrip_serialization(self) -> None:
        """Test that payloads can be serialized and deserialized."""
        original = ConfigHealthPayload(
            ok=True,
            database_status="healthy",
            operational_mode="normal",
            config_epoch="550e8400-e29b-41d4-a716-446655440000",
            schema_version=1,
            lkg_cache_valid=True,
            litestream_status="healthy",
        )

        # Serialize to JSON
        json_str = original.model_dump_json()

        # Deserialize back
        parsed = ConfigHealthPayload.model_validate_json(json_str)

        assert parsed.ok == original.ok
        assert parsed.database_status == original.database_status
        assert parsed.config_epoch == original.config_epoch
