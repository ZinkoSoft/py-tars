"""Unit tests for MQTTClientConfig environment parsing.

TDD Workflow: Write tests FIRST (RED), then implement (GREEN).
"""

import pytest

from tars.adapters.mqtt_client import MQTTClientConfig


class TestMQTTClientConfig:
    """Tests for MQTTClientConfig model and environment parsing."""

    def test_from_env_valid(self, monkeypatch):
        """Parse all environment variables correctly."""
        monkeypatch.setenv("MQTT_URL", "mqtt://user:pass@localhost:1883")
        monkeypatch.setenv("MQTT_CLIENT_ID", "test-client")
        monkeypatch.setenv("MQTT_SOURCE_NAME", "test-source")
        monkeypatch.setenv("MQTT_KEEPALIVE", "30")
        monkeypatch.setenv("MQTT_ENABLE_HEALTH", "true")
        monkeypatch.setenv("MQTT_ENABLE_HEARTBEAT", "true")
        monkeypatch.setenv("MQTT_HEARTBEAT_INTERVAL", "10.0")
        monkeypatch.setenv("MQTT_DEDUPE_TTL", "60.0")
        monkeypatch.setenv("MQTT_DEDUPE_MAX_ENTRIES", "4096")
        monkeypatch.setenv("MQTT_RECONNECT_MIN_DELAY", "1.0")
        monkeypatch.setenv("MQTT_RECONNECT_MAX_DELAY", "10.0")
        
        config = MQTTClientConfig.from_env()
        
        assert config.mqtt_url == "mqtt://user:pass@localhost:1883"
        assert config.client_id == "test-client"
        assert config.source_name == "test-source"
        assert config.keepalive == 30
        assert config.enable_health is True
        assert config.enable_heartbeat is True
        assert config.heartbeat_interval == 10.0
        assert config.dedupe_ttl == 60.0
        assert config.dedupe_max_entries == 4096
        assert config.reconnect_min_delay == 1.0
        assert config.reconnect_max_delay == 10.0

    def test_from_env_minimal(self, monkeypatch):
        """Parse with only required environment variables (use defaults)."""
        monkeypatch.setenv("MQTT_URL", "mqtt://localhost:1883")
        monkeypatch.setenv("MQTT_CLIENT_ID", "minimal-client")
        
        config = MQTTClientConfig.from_env()
        
        assert config.mqtt_url == "mqtt://localhost:1883"
        assert config.client_id == "minimal-client"
        assert config.source_name is None
        assert config.keepalive == 60  # default
        assert config.enable_health is False  # default
        assert config.enable_heartbeat is False  # default
        assert config.heartbeat_interval == 5.0  # default
        assert config.dedupe_ttl == 0.0  # default (disabled)
        assert config.dedupe_max_entries == 0  # default
        assert config.reconnect_min_delay == 0.5  # default
        assert config.reconnect_max_delay == 5.0  # default

    def test_from_env_missing_mqtt_url(self, monkeypatch):
        """Fail with clear error when MQTT_URL missing."""
        monkeypatch.setenv("MQTT_CLIENT_ID", "test-client")
        # MQTT_URL intentionally not set
        
        with pytest.raises(KeyError, match="MQTT_URL"):
            MQTTClientConfig.from_env()

    def test_from_env_missing_client_id(self, monkeypatch):
        """Fail with clear error when MQTT_CLIENT_ID missing."""
        monkeypatch.setenv("MQTT_URL", "mqtt://localhost:1883")
        # MQTT_CLIENT_ID intentionally not set
        
        with pytest.raises(KeyError, match="MQTT_CLIENT_ID"):
            MQTTClientConfig.from_env()

    def test_from_env_boolean_parsing(self, monkeypatch):
        """Parse boolean environment variables correctly."""
        monkeypatch.setenv("MQTT_URL", "mqtt://localhost:1883")
        monkeypatch.setenv("MQTT_CLIENT_ID", "test-client")
        
        # Test "true" (lowercase)
        monkeypatch.setenv("MQTT_ENABLE_HEALTH", "true")
        assert MQTTClientConfig.from_env().enable_health is True
        
        # Test "True" (capitalized)
        monkeypatch.setenv("MQTT_ENABLE_HEALTH", "True")
        assert MQTTClientConfig.from_env().enable_health is True
        
        # Test "false"
        monkeypatch.setenv("MQTT_ENABLE_HEALTH", "false")
        assert MQTTClientConfig.from_env().enable_health is False
        
        # Test empty string (should be False)
        monkeypatch.setenv("MQTT_ENABLE_HEALTH", "")
        assert MQTTClientConfig.from_env().enable_health is False
        
        # Test "1" (should be False, not "true")
        monkeypatch.setenv("MQTT_ENABLE_HEALTH", "1")
        assert MQTTClientConfig.from_env().enable_health is False

    def test_reconnect_delay_validation(self):
        """Reject when reconnect_max_delay < reconnect_min_delay."""
        with pytest.raises(ValueError, match="reconnect_max_delay.*must be >=.*reconnect_min_delay"):
            MQTTClientConfig(
                mqtt_url="mqtt://localhost:1883",
                client_id="test-client",
                reconnect_min_delay=5.0,
                reconnect_max_delay=1.0,  # Invalid: max < min
            )

    def test_reconnect_delay_equal_valid(self):
        """Allow reconnect_max_delay == reconnect_min_delay (constant backoff)."""
        config = MQTTClientConfig(
            mqtt_url="mqtt://localhost:1883",
            client_id="test-client",
            reconnect_min_delay=2.0,
            reconnect_max_delay=2.0,  # Valid: max == min
        )
        
        assert config.reconnect_min_delay == 2.0
        assert config.reconnect_max_delay == 2.0

    def test_dedupe_validation_requires_max_entries(self):
        """Require dedupe_max_entries > 0 when dedupe_ttl > 0."""
        with pytest.raises(ValueError, match="dedupe_max_entries must be > 0 when dedupe_ttl"):
            MQTTClientConfig(
                mqtt_url="mqtt://localhost:1883",
                client_id="test-client",
                dedupe_ttl=30.0,  # Enabled
                dedupe_max_entries=0,  # Invalid: must be > 0
            )

    def test_dedupe_disabled_valid(self):
        """Allow dedupe_ttl=0 with dedupe_max_entries=0 (dedup disabled)."""
        config = MQTTClientConfig(
            mqtt_url="mqtt://localhost:1883",
            client_id="test-client",
            dedupe_ttl=0.0,  # Disabled
            dedupe_max_entries=0,  # Valid when ttl=0
        )
        
        assert config.dedupe_ttl == 0.0
        assert config.dedupe_max_entries == 0

    def test_heartbeat_interval_validation(self):
        """Require heartbeat_interval >= 1.0."""
        with pytest.raises(ValueError, match="heartbeat_interval"):
            MQTTClientConfig(
                mqtt_url="mqtt://localhost:1883",
                client_id="test-client",
                heartbeat_interval=0.5,  # Invalid: < 1.0
            )

    def test_keepalive_validation(self):
        """Require keepalive in range [1, 3600]."""
        # Too low
        with pytest.raises(ValueError, match="keepalive"):
            MQTTClientConfig(
                mqtt_url="mqtt://localhost:1883",
                client_id="test-client",
                keepalive=0,  # Invalid: < 1
            )
        
        # Too high
        with pytest.raises(ValueError, match="keepalive"):
            MQTTClientConfig(
                mqtt_url="mqtt://localhost:1883",
                client_id="test-client",
                keepalive=4000,  # Invalid: > 3600
            )
        
        # Valid boundaries
        config_min = MQTTClientConfig(
            mqtt_url="mqtt://localhost:1883",
            client_id="test-client",
            keepalive=1,
        )
        assert config_min.keepalive == 1
        
        config_max = MQTTClientConfig(
            mqtt_url="mqtt://localhost:1883",
            client_id="test-client",
            keepalive=3600,
        )
        assert config_max.keepalive == 3600
