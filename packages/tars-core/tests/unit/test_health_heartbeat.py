"""Unit tests for HeartbeatPayload model.

TDD Workflow: Write tests FIRST (RED), then implement (GREEN).

Note: HealthPing is now a contract model (tars.contracts.v1.health.HealthPing)
and should be tested in the contracts package, not here.
"""

import pytest
import time

from tars.adapters.mqtt_client import HeartbeatPayload


class TestHeartbeatPayload:
    """Tests for HeartbeatPayload model."""

    def test_heartbeat_creation(self):
        """Create heartbeat payload with timestamp."""
        now = time.time()
        heartbeat = HeartbeatPayload(timestamp=now)
        
        assert heartbeat.ok is True
        assert heartbeat.event == "heartbeat"
        assert heartbeat.timestamp == now

    def test_heartbeat_defaults(self):
        """Verify default values for ok and event."""
        heartbeat = HeartbeatPayload(timestamp=123456.789)
        
        assert heartbeat.ok is True  # Always True for heartbeat
        assert heartbeat.event == "heartbeat"  # Always "heartbeat"

    def test_heartbeat_serialization(self):
        """Serialize heartbeat to dict."""
        heartbeat = HeartbeatPayload(timestamp=1234567890.123)
        
        data = heartbeat.model_dump()
        
        assert data == {
            "ok": True,
            "event": "heartbeat",
            "timestamp": 1234567890.123,
        }

    def test_heartbeat_from_dict(self):
        """Deserialize heartbeat from dict."""
        data = {"ok": True, "event": "heartbeat", "timestamp": 987654321.456}
        
        heartbeat = HeartbeatPayload(**data)
        
        assert heartbeat.ok is True
        assert heartbeat.event == "heartbeat"
        assert heartbeat.timestamp == 987654321.456
