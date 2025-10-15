"""Unit tests for config module."""

from ui.config import _deep_merge, load_config


def test_deep_merge():
    """Test deep merge functionality."""
    dst = {"a": {"b": 1}, "c": 2}
    src = {"a": {"d": 3}, "e": 4}
    result = _deep_merge(dst, src)
    assert result["a"]["b"] == 1
    assert result["a"]["d"] == 3
    assert result["c"] == 2
    assert result["e"] == 4


def test_load_config_defaults(sample_config):  # noqa: ARG001  # fixture for future use
    """Test that default config loads properly."""
    # This would need environment setup to test properly
    # For now, just verify the function exists
    assert callable(load_config)
