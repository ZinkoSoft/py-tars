"""Pytest configuration for tars-mcp-movement tests."""
import pytest


@pytest.fixture
def mock_env(monkeypatch):
    """Mock environment variables."""
    monkeypatch.setenv("TOPIC_MOVEMENT_TEST", "movement/test")
    monkeypatch.setenv("TOPIC_MOVEMENT_STOP", "movement/stop")
    return {
        "TOPIC_MOVEMENT_TEST": "movement/test",
        "TOPIC_MOVEMENT_STOP": "movement/stop",
    }
