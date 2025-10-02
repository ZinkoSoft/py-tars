"""
Lightweight validation helpers for MicroPython (ESP32).

Subset of Pydantic functionality that works on MicroPython.
For full validation, use tars-core contracts on the host.

This module provides validation for movement MQTT messages compatible
with both CPython and MicroPython environments.
"""

try:
    import ujson as json
except ImportError:
    import json


class ValidationError(Exception):
    """Validation failed."""
    pass


def validate_test_movement(data: dict) -> dict:
    """
    Validate movement/test command structure.
    
    Required fields:
    - command: str (one of valid commands)
    
    Optional fields:
    - speed: float (0.1-1.0, default 1.0)
    - params: dict (default {})
    - request_id: str
    - message_id: str
    - timestamp: float
    
    Returns:
        dict: Validated data with defaults applied
    
    Raises:
        ValidationError: If invalid
    
    Example:
        >>> data = {"command": "wave", "speed": 0.8}
        >>> validated = validate_test_movement(data)
        >>> validated["speed"]
        0.8
    """
    if not isinstance(data, dict):
        raise ValidationError("data must be dict")
    
    if "command" not in data:
        raise ValidationError("missing required field: command")
    
    command = data["command"]
    if not isinstance(command, str):
        raise ValidationError("command must be string")
    
    # Validate command is in supported list
    valid_commands = [
        # Basic
        "reset", "step_forward", "step_backward", "turn_left", "turn_right",
        # Expressive
        "wave", "laugh", "swing_legs", "pezz", "pezz_dispenser",
        "now", "balance", "mic_drop", "monster", "pose", "bow",
        # Control
        "disable", "stop",
        # Manual
        "move_legs", "move_arm"
    ]
    
    if command not in valid_commands:
        raise ValidationError(f"invalid command: {command}")
    
    # Apply defaults
    result = {
        "command": command,
        "speed": data.get("speed", 1.0),
        "params": data.get("params", {}),
    }
    
    # Validate speed
    speed = result["speed"]
    if not isinstance(speed, (int, float)):
        raise ValidationError("speed must be number")
    if speed < 0.1 or speed > 1.0:
        raise ValidationError("speed must be 0.1-1.0")
    
    # Validate params
    if not isinstance(result["params"], dict):
        raise ValidationError("params must be dict")
    
    # Pass through optional tracking fields
    if "request_id" in data:
        result["request_id"] = data["request_id"]
    if "message_id" in data:
        result["message_id"] = data["message_id"]
    if "timestamp" in data:
        result["timestamp"] = data["timestamp"]
    
    return result


def validate_emergency_stop(data: dict) -> dict:
    """
    Validate movement/stop command.
    
    All fields optional:
    - reason: str
    - message_id: str
    - timestamp: float
    
    Returns:
        dict: Validated data
    
    Raises:
        ValidationError: If invalid
    
    Example:
        >>> data = {"reason": "user requested"}
        >>> validated = validate_emergency_stop(data)
        >>> validated["reason"]
        'user requested'
    """
    if not isinstance(data, dict):
        raise ValidationError("data must be dict")
    
    result = {}
    
    if "reason" in data:
        if not isinstance(data["reason"], str):
            raise ValidationError("reason must be string")
        result["reason"] = data["reason"]
    
    if "message_id" in data:
        result["message_id"] = data["message_id"]
    if "timestamp" in data:
        result["timestamp"] = data["timestamp"]
    
    return result


def validate_move_legs_params(params: dict) -> dict:
    """
    Validate parameters for move_legs command.
    
    Required fields:
    - height_percent: float (1-100)
    - left_percent: float (1-100)
    - right_percent: float (1-100)
    
    Returns:
        dict: Validated params
    
    Raises:
        ValidationError: If invalid
    """
    if not isinstance(params, dict):
        raise ValidationError("params must be dict")
    
    required_fields = ["height_percent", "left_percent", "right_percent"]
    for field in required_fields:
        if field not in params:
            raise ValidationError(f"missing required field: {field}")
        
        value = params[field]
        if not isinstance(value, (int, float)):
            raise ValidationError(f"{field} must be number")
        if value < 1 or value > 100:
            raise ValidationError(f"{field} must be 1-100")
    
    return {
        "height_percent": float(params["height_percent"]),
        "left_percent": float(params["left_percent"]),
        "right_percent": float(params["right_percent"]),
    }


def validate_move_arm_params(params: dict) -> dict:
    """
    Validate parameters for move_arm command.
    
    Optional fields (at least one required):
    - port_main, port_forearm, port_hand: float (1-100)
    - star_main, star_forearm, star_hand: float (1-100)
    
    Returns:
        dict: Validated params
    
    Raises:
        ValidationError: If invalid
    """
    if not isinstance(params, dict):
        raise ValidationError("params must be dict")
    
    optional_fields = [
        "port_main", "port_forearm", "port_hand",
        "star_main", "star_forearm", "star_hand"
    ]
    
    result = {}
    has_any_field = False
    
    for field in optional_fields:
        if field in params:
            has_any_field = True
            value = params[field]
            if not isinstance(value, (int, float)):
                raise ValidationError(f"{field} must be number")
            if value < 1 or value > 100:
                raise ValidationError(f"{field} must be 1-100")
            result[field] = float(value)
    
    if not has_any_field:
        raise ValidationError("at least one arm joint must be specified")
    
    return result


# Self-tests (run when imported in CPython, skip in MicroPython)
if __name__ == "__main__":
    print("Running validation self-tests...")
    
    # Test 1: Valid command
    data = {"command": "wave", "speed": 0.8}
    validated = validate_test_movement(data)
    assert validated["command"] == "wave"
    assert validated["speed"] == 0.8
    assert validated["params"] == {}
    print("✓ Valid command")
    
    # Test 2: Command with defaults
    data = {"command": "reset"}
    validated = validate_test_movement(data)
    assert validated["speed"] == 1.0
    assert validated["params"] == {}
    print("✓ Command with defaults")
    
    # Test 3: Invalid command
    try:
        validate_test_movement({"command": "invalid"})
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        assert "invalid command" in str(e)
    print("✓ Invalid command rejected")
    
    # Test 4: Missing command
    try:
        validate_test_movement({"speed": 0.8})
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        assert "missing required field" in str(e)
    print("✓ Missing command rejected")
    
    # Test 5: Speed out of range
    try:
        validate_test_movement({"command": "wave", "speed": 1.5})
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        assert "speed must be 0.1-1.0" in str(e)
    print("✓ Speed validation works")
    
    # Test 6: Emergency stop valid
    data = {"reason": "user requested"}
    validated = validate_emergency_stop(data)
    assert validated["reason"] == "user requested"
    print("✓ Emergency stop valid")
    
    # Test 7: Emergency stop empty
    data = {}
    validated = validate_emergency_stop(data)
    assert validated == {}
    print("✓ Emergency stop empty")
    
    # Test 8: Move legs params valid
    params = {"height_percent": 50, "left_percent": 50, "right_percent": 50}
    validated = validate_move_legs_params(params)
    assert validated["height_percent"] == 50.0
    print("✓ Move legs params valid")
    
    # Test 9: Move legs params invalid
    try:
        validate_move_legs_params({"height_percent": 101, "left_percent": 50, "right_percent": 50})
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        assert "must be 1-100" in str(e)
    print("✓ Move legs params validation works")
    
    # Test 10: Move arm params valid
    params = {"port_main": 50}
    validated = validate_move_arm_params(params)
    assert validated["port_main"] == 50.0
    print("✓ Move arm params valid")
    
    # Test 11: Move arm params empty
    try:
        validate_move_arm_params({})
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        assert "at least one arm joint" in str(e)
    print("✓ Move arm params requires at least one field")
    
    # Test 12: Request ID passthrough
    data = {"command": "wave", "request_id": "abc123"}
    validated = validate_test_movement(data)
    assert validated["request_id"] == "abc123"
    print("✓ Request ID passthrough")
    
    print("\n✓ All validation self-tests passed!")
