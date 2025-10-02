"""
Status message builder for MicroPython (ESP32).

Helpers for creating movement status messages that match the
tars-core MovementStatusUpdate contract.
"""

try:
    import utime as time
except ImportError:
    import time

try:
    import ujson as json
except ImportError:
    import json


def generate_message_id():
    """Generate a simple message ID (timestamp-based for MicroPython)."""
    try:
        # MicroPython: use ticks_ms
        import utime
        return f"esp32_{utime.ticks_ms()}"
    except ImportError:
        # CPython: use time
        return f"esp32_{int(time.time() * 1000)}"


def build_status_message(event, command=None, detail=None, request_id=None):
    """
    Build a movement status message matching tars-core contract.
    
    Args:
        event: Status event string (e.g. "command_started", "command_completed")
        command: Optional command name that triggered this status
        detail: Optional detail message
        request_id: Optional request ID for correlation
    
    Returns:
        dict: Status message ready for JSON serialization
    
    Example:
        >>> msg = build_status_message("command_started", command="wave", request_id="abc123")
        >>> msg["event"]
        'command_started'
        >>> msg["command"]
        'wave'
    """
    # Valid events (matching tars-core MovementStatusEvent enum)
    valid_events = [
        "connected",
        "disconnected",
        "command_started",
        "command_completed",
        "command_failed",
        "emergency_stop",
        "stop_cleared",
        "queue_full",
        "battery_low",
    ]
    
    if event not in valid_events:
        raise ValueError(f"Invalid event: {event}. Must be one of: {', '.join(valid_events)}")
    
    message = {
        "event": event,
        "message_id": generate_message_id(),
        "timestamp": time.time(),
    }
    
    if command is not None:
        message["command"] = command
    
    if detail is not None:
        message["detail"] = detail
    
    if request_id is not None:
        message["request_id"] = request_id
    
    return message


def build_command_started_status(command, request_id=None):
    """
    Build status message for command start.
    
    Args:
        command: Command name
        request_id: Optional request ID for correlation
    
    Returns:
        dict: Status message
    
    Example:
        >>> msg = build_command_started_status("wave", "abc123")
        >>> msg["event"]
        'command_started'
    """
    return build_status_message(
        event="command_started",
        command=command,
        request_id=request_id
    )


def build_command_completed_status(command, request_id=None):
    """
    Build status message for command completion.
    
    Args:
        command: Command name
        request_id: Optional request ID for correlation
    
    Returns:
        dict: Status message
    """
    return build_status_message(
        event="command_completed",
        command=command,
        request_id=request_id
    )


def build_command_failed_status(command, detail, request_id=None):
    """
    Build status message for command failure.
    
    Args:
        command: Command name
        detail: Error description
        request_id: Optional request ID for correlation
    
    Returns:
        dict: Status message
    """
    return build_status_message(
        event="command_failed",
        command=command,
        detail=detail,
        request_id=request_id
    )


def build_emergency_stop_status(detail=None):
    """
    Build status message for emergency stop.
    
    Args:
        detail: Optional reason for stop
    
    Returns:
        dict: Status message
    """
    return build_status_message(
        event="emergency_stop",
        detail=detail
    )


def build_stop_cleared_status():
    """
    Build status message for stop cleared.
    
    Returns:
        dict: Status message
    """
    return build_status_message(event="stop_cleared")


def build_queue_full_status(detail=None):
    """
    Build status message for queue full.
    
    Args:
        detail: Optional detail message
    
    Returns:
        dict: Status message
    """
    return build_status_message(
        event="queue_full",
        detail=detail
    )


def build_connected_status():
    """
    Build status message for connected.
    
    Returns:
        dict: Status message
    """
    return build_status_message(event="connected")


def build_disconnected_status(detail=None):
    """
    Build status message for disconnected.
    
    Args:
        detail: Optional reason for disconnection
    
    Returns:
        dict: Status message
    """
    return build_status_message(
        event="disconnected",
        detail=detail
    )


# Self-tests (run when imported in CPython, skip in MicroPython)
if __name__ == "__main__":
    print("Running status builder self-tests...")
    
    # Test 1: Basic status message
    msg = build_status_message("command_started", command="wave")
    assert msg["event"] == "command_started"
    assert msg["command"] == "wave"
    assert "message_id" in msg
    assert "timestamp" in msg
    print("✓ Basic status message")
    
    # Test 2: Status with all fields
    msg = build_status_message(
        "command_completed",
        command="wave",
        detail="Success",
        request_id="abc123"
    )
    assert msg["event"] == "command_completed"
    assert msg["command"] == "wave"
    assert msg["detail"] == "Success"
    assert msg["request_id"] == "abc123"
    print("✓ Status with all fields")
    
    # Test 3: Invalid event
    try:
        build_status_message("invalid_event")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Invalid event" in str(e)
    print("✓ Invalid event rejected")
    
    # Test 4: Command started helper
    msg = build_command_started_status("wave", "abc123")
    assert msg["event"] == "command_started"
    assert msg["command"] == "wave"
    assert msg["request_id"] == "abc123"
    print("✓ Command started helper")
    
    # Test 5: Command completed helper
    msg = build_command_completed_status("wave", "abc123")
    assert msg["event"] == "command_completed"
    assert msg["command"] == "wave"
    assert msg["request_id"] == "abc123"
    print("✓ Command completed helper")
    
    # Test 6: Command failed helper
    msg = build_command_failed_status("wave", "Timeout", "abc123")
    assert msg["event"] == "command_failed"
    assert msg["command"] == "wave"
    assert msg["detail"] == "Timeout"
    assert msg["request_id"] == "abc123"
    print("✓ Command failed helper")
    
    # Test 7: Emergency stop helper
    msg = build_emergency_stop_status("User requested")
    assert msg["event"] == "emergency_stop"
    assert msg["detail"] == "User requested"
    print("✓ Emergency stop helper")
    
    # Test 8: Stop cleared helper
    msg = build_stop_cleared_status()
    assert msg["event"] == "stop_cleared"
    print("✓ Stop cleared helper")
    
    # Test 9: Queue full helper
    msg = build_queue_full_status("Max 10 commands")
    assert msg["event"] == "queue_full"
    assert msg["detail"] == "Max 10 commands"
    print("✓ Queue full helper")
    
    # Test 10: Connected helper
    msg = build_connected_status()
    assert msg["event"] == "connected"
    print("✓ Connected helper")
    
    # Test 11: Disconnected helper
    msg = build_disconnected_status("Network error")
    assert msg["event"] == "disconnected"
    assert msg["detail"] == "Network error"
    print("✓ Disconnected helper")
    
    # Test 12: JSON serialization
    msg = build_command_started_status("wave", "abc123")
    json_str = json.dumps(msg)
    parsed = json.loads(json_str)
    assert parsed["event"] == "command_started"
    print("✓ JSON serialization")
    
    print("\n✓ All status builder self-tests passed!")
