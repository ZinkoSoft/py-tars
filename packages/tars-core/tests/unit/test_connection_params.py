"""Unit tests for ConnectionParams URL parsing.

TDD Workflow: Write tests FIRST (RED), then implement (GREEN).
"""

import pytest

from tars.adapters.mqtt_client import ConnectionParams, parse_mqtt_url


class TestConnectionParams:
    """Tests for ConnectionParams model and URL parsing."""

    def test_parse_mqtt_url_full(self):
        """Parse MQTT URL with all components (user, password, host, port)."""
        url = "mqtt://user:password@broker.example.com:1883"
        
        params = parse_mqtt_url(url)
        
        assert params.hostname == "broker.example.com"
        assert params.port == 1883
        assert params.username == "user"
        assert params.password == "password"

    def test_parse_mqtt_url_no_credentials(self):
        """Parse MQTT URL without credentials."""
        url = "mqtt://localhost:1883"
        
        params = parse_mqtt_url(url)
        
        assert params.hostname == "localhost"
        assert params.port == 1883
        assert params.username is None
        assert params.password is None

    def test_parse_mqtt_url_default_port(self):
        """Parse MQTT URL without port (should default to 1883)."""
        url = "mqtt://broker.example.com"
        
        params = parse_mqtt_url(url)
        
        assert params.hostname == "broker.example.com"
        assert params.port == 1883

    def test_parse_mqtt_url_default_host(self):
        """Parse MQTT URL without hostname (should default to localhost)."""
        url = "mqtt://:1883"
        
        params = parse_mqtt_url(url)
        
        assert params.hostname == "localhost"
        assert params.port == 1883

    def test_parse_mqtt_url_minimal(self):
        """Parse minimal MQTT URL (scheme only)."""
        url = "mqtt://"
        
        params = parse_mqtt_url(url)
        
        assert params.hostname == "localhost"
        assert params.port == 1883
        assert params.username is None
        assert params.password is None

    def test_parse_mqtt_url_invalid_scheme(self):
        """Reject URL with non-mqtt scheme."""
        url = "http://localhost:1883"
        
        with pytest.raises(ValueError, match="Invalid MQTT URL scheme"):
            parse_mqtt_url(url)

    def test_parse_mqtt_url_with_path(self):
        """Parse MQTT URL with path component (should ignore path)."""
        url = "mqtt://localhost:1883/some/path"
        
        params = parse_mqtt_url(url)
        
        assert params.hostname == "localhost"
        assert params.port == 1883

    def test_password_not_in_repr(self):
        """Ensure password is redacted in string representation."""
        params = ConnectionParams(
            hostname="localhost",
            port=1883,
            username="user",
            password="secret123",
        )
        
        repr_str = repr(params)
        str_str = str(params)
        
        assert "secret123" not in repr_str
        assert "secret123" not in str_str
        assert "***" in repr_str or "REDACTED" in repr_str or "****" in repr_str
