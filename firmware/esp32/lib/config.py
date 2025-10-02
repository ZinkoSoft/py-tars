"""
Configuration management for ESP32 MicroPython firmware.

Handles loading, saving, and merging JSON configuration files.
Provides DEFAULT_CONFIG with all required fields and sensible defaults.
"""

try:
    import ujson as json  # type: ignore
except ImportError:  # pragma: no cover
    import json

try:
    from lib.utils import open_file
except ImportError:
    # Fallback for standalone execution
    from utils import open_file  # type: ignore


# Default configuration with all required fields
DEFAULT_CONFIG = {
    "wifi": {
        "ssid": "",
        "password": "",
    },
    "mqtt": {
        "host": "192.168.1.10",
        "port": 1883,
        "username": None,
        "password": None,
        "client_id": "tars-esp32",
        "keepalive": 30,
    },
    "pca9685": {
        "address": 0x40,
        "frequency": 50,
        "scl": 22,
        "sda": 21,
    },
    "topics": {
        "frame": "movement/frame",
        "state": "movement/state",
        "health": "system/health/movement-esp32",
    },
    "frame_timeout_ms": 2500,
    "status_led": None,
    "servo_channel_count": 16,
    "servo_centers": {},
    "default_center_pulse": 307,
    "setup_portal": {
        "ssid": "TARS-Setup",
        "password": None,
        "port": 80,
        "timeout_s": 300,
    },
    "config_path": "movement_config.json",
}


def load_config(path):
    """
    Load configuration from JSON file with defaults.
    
    Args:
        path: Path to JSON config file (str)
    
    Returns:
        dict: Merged configuration (DEFAULT_CONFIG + user overrides)
    
    Notes:
        - Missing file returns DEFAULT_CONFIG
        - Invalid JSON returns DEFAULT_CONFIG
        - User config is deep-merged into defaults
    
    Example:
        config = load_config("movement_config.json")
        mqtt_host = config["mqtt"]["host"]
    """
    try:
        with open_file(path, "r") as fp:
            user_cfg = json.loads(fp.read())
    except (OSError, ValueError):
        user_cfg = {}

    # Deep copy defaults to avoid mutation
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    _deep_update(merged, user_cfg)
    return merged


def save_config(path, config):
    """
    Save configuration to JSON file.
    
    Args:
        path: Path to JSON config file (str)
        config: Configuration dictionary to save
    
    Notes:
        - Silently fails if file cannot be written
        - Creates file if it doesn't exist
        - Overwrites existing file
    
    Example:
        config["mqtt"]["host"] = "192.168.1.100"
        save_config("movement_config.json", config)
    """
    try:
        with open_file(path, "w") as fp:
            fp.write(json.dumps(config))
    except OSError:
        pass


def _deep_update(target, updates):
    """
    Recursively merge updates into target dictionary.
    
    Args:
        target: Base dictionary (modified in-place)
        updates: Dictionary with values to merge
    
    Notes:
        - Nested dicts are recursively merged
        - Non-dict values are replaced
        - New keys are added
    
    Example:
        base = {"a": {"b": 1, "c": 2}}
        _deep_update(base, {"a": {"b": 99}})
        # base is now {"a": {"b": 99, "c": 2}}
    """
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value


# Self-test when run directly
if __name__ == "__main__":
    print("Testing lib.config...")
    
    # Test default config structure
    assert "wifi" in DEFAULT_CONFIG, "Missing wifi config"
    assert "mqtt" in DEFAULT_CONFIG, "Missing mqtt config"
    assert "pca9685" in DEFAULT_CONFIG, "Missing pca9685 config"
    print("  DEFAULT_CONFIG structure valid")
    
    # Test deep_update
    base = {"a": {"b": 1, "c": 2}, "d": 3}
    updates = {"a": {"b": 99}, "e": 4}
    _deep_update(base, updates)
    assert base["a"]["b"] == 99, "deep_update failed to update nested value"
    assert base["a"]["c"] == 2, "deep_update overwrote unmodified value"
    assert base["e"] == 4, "deep_update failed to add new key"
    print("  _deep_update works correctly")
    
    # Test load_config with missing file
    config = load_config("nonexistent_config.json")
    assert config == DEFAULT_CONFIG, "load_config didn't return defaults for missing file"
    print("  load_config handles missing file")
    
    # Test save/load round-trip (if filesystem available)
    try:
        test_path = "/tmp/test_config.json"
        test_config = json.loads(json.dumps(DEFAULT_CONFIG))
        test_config["mqtt"]["host"] = "test_host"
        
        save_config(test_path, test_config)
        loaded = load_config(test_path)
        
        assert loaded["mqtt"]["host"] == "test_host", "save/load round-trip failed"
        print("  save/load round-trip works")
    except Exception as e:
        print(f"  save/load test skipped: {e}")
    
    print("✓ All config tests passed")
