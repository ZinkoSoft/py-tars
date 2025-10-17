"""Unit tests for HealthStatus and HeartbeatPayload models.

TDD Workflow: Write tests FIRST (RED), then implement (GREEN).
"""

import pytest
import time

from tars.adapters.mqtt_client import HealthStatus, HeartbeatPayload


class TestHealthStatus:
    """Tests for HealthStatus model."""

    def test_healthy_status_minimal(self):
        """Create healthy status with minimal fields."""
        health = HealthStatus(ok=True)
        
        assert health.ok is True
        assert health.event is None
        assert health.error is None

    def test_healthy_status_with_event(self):
        """Create healthy status with event name."""
        health = HealthStatus(ok=True, event="ready")
        
        assert health.ok is True
        assert health.event == "ready"
        assert health.error is None

    def test_unhealthy_status_with_error(self):
        """Create unhealthy status with error message."""
        health = HealthStatus(ok=False, error="Connection lost")
        
        assert health.ok is False
        assert health.error == "Connection lost"
        assert health.event is None

    def test_unhealthy_status_with_event(self):
        """Create unhealthy status with event (e.g., shutdown)."""
        health = HealthStatus(ok=False, event="shutdown")
        
        assert health.ok is False
        assert health.event == "shutdown"
        assert health.error is None

    def test_unhealthy_status_with_both(self):
        """Create unhealthy status with both event and error."""
        health = HealthStatus(ok=False, event="error", error="Broker unreachable")
        
        assert health.ok is False
        assert health.event == "error"
        assert health.error == "Broker unreachable"

    def test_healthy_with_error_logs_warning(self, caplog):
        """Warn if error is set when ok=True (unexpected)."""
        import logging
        caplog.set_level(logging.WARNING)
        
        health = HealthStatus(ok=True, error="Unexpected error")
        
        # Should create the object (not reject)
        assert health.ok is True
        assert health.error == "Unexpected error"
        
        # But should log a warning
        assert "Health status ok=True but error=" in caplog.text

    def test_serialization(self):
        """Serialize HealthStatus to dict."""
        health = HealthStatus(ok=True, event="ready")
        
        data = health.model_dump()
        
        assert data == {"ok": True, "event": "ready", "error": None}

    def test_serialization_excludes_none(self):
        """Serialize with exclude_none to omit null fields."""
        health = HealthStatus(ok=False, error="Connection lost")
        
        data = health.model_dump(exclude_none=True)
        
        assert data == {"ok": False, "error": "Connection lost"}
        assert "event" not in data


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
