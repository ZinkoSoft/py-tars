"""
Servo Configuration and Calibration
V2 Configuration from tars-community-movement-original/config.ini
"""

# Servo calibration data per channel
# Format: {channel: {"min": pulse_width, "max": pulse_width, "neutral": pulse_width, "label": name}}
# Pulse widths are in microseconds * 4.096 (for PCA9685 12-bit resolution at 50Hz)
# Example: 1.5ms pulse = 1500us = 307.2 ≈ 307 in 12-bit units
# For servos: typically 1ms (204) to 2ms (409) range

SERVO_CALIBRATION = {
    # Leg Servos (LDX-227) - Channels 0-2
    0: {
        "min": 220,        # upHeight (raised position)
        "max": 360,        # downHeight (lowered position)
        "neutral": 300,    # neutralHeight
        "label": "Main Legs Lift",
        "servo_type": "LDX-227",
        "reverse": False
    },
    1: {
        "min": 192,        # forwardStarboard (left leg forward)
        "max": 408,        # backStarboard (left leg back)
        "neutral": 300,    # neutralStarboard
        "label": "Left Leg Rotation",
        "servo_type": "LDX-227",
        "reverse": False    # Reverse direction for left leg
    },
    2: {
        "min": 408,        # forwardPort (right leg forward)
        "max": 192,        # backPort (right leg back)
        "neutral": 300,    # neutralPort
        "label": "Right Leg Rotation",
        "servo_type": "LDX-227",
        "reverse": False
    },
    
    # Right Arm (MG996R shoulder, MG90S forearm/hand) - Channels 3-5
    3: {
        "min": 135,        # portMainMin
        "max": 440,        # portMainMax
        "neutral": 135,    # Calculated midpoint
        "label": "Right Shoulder",
        "servo_type": "MG996R",
        "reverse": False
    },
    4: {
        "min": 200,        # portForarmMin
        "max": 380,        # portForarmMax
        "neutral": 200,    # Calculated midpoint
        "label": "Right Elbow",
        "servo_type": "MG90S",
        "reverse": False
    },
    5: {
        "min": 200,        # portHandMin
        "max": 280,        # portHandMax (NOT 380 - prevents over-extension)
        "neutral": 200,    # Calculated midpoint
        "label": "Right Hand",
        "servo_type": "MG90S",
        "reverse": False
    },
    
    # Left Arm (MG996R shoulder, MG90S forearm/hand) - Channels 6-8
    # Note: Left arm values are INVERTED from right arm due to mirrored mounting
    6: {
        "min": 135,        # starMainMax (inverted)
        "max": 440,        # starMainMin (inverted)
        "neutral": 135,    # Calculated midpoint
        "label": "Left Shoulder",
        "servo_type": "MG996R",
        "reverse": False
    },
    7: {
        "min": 190,        # starForarmMax (inverted)
        "max": 380,        # starForarmMin (inverted)
        "neutral": 190,    # Calculated midpoint
        "label": "Left Elbow",
        "servo_type": "MG90S",
        "reverse": False
    },
    8: {
        "min": 280,        # starHandMax (inverted)
        "max": 380,        # starHandMin (inverted)
        "neutral": 280,    # Calculated midpoint
        "label": "Left Hand",
        "servo_type": "MG90S",
        "reverse": False
    }
}

# Servo labels for quick reference
SERVO_LABELS = [
    "Main Legs Lift",      # Channel 0
    "Left Leg Rotation",   # Channel 1
    "Right Leg Rotation",  # Channel 2
    "Right Shoulder",      # Channel 3
    "Right Elbow",         # Channel 4
    "Right Hand",          # Channel 5
    "Left Shoulder",       # Channel 6
    "Left Elbow",          # Channel 7
    "Left Hand"            # Channel 8
]


def reverse_servo(pulse, min_pulse, max_pulse):
    """
    Reverse servo direction by inverting the pulse width within the range.
    
    Args:
        pulse: Current pulse width value
        min_pulse: Minimum pulse width for this servo
        max_pulse: Maximum pulse width for this servo
    
    Returns:
        int: Reversed pulse width value
    
    Example:
        If range is 192-408 (min-max):
        - Input 192 (min) -> Output 408 (max)
        - Input 300 (middle) -> Output 300 (middle)
        - Input 408 (max) -> Output 192 (min)
    """
    return max_pulse - (pulse - min_pulse)


def apply_reverse_if_needed(channel, pulse):
    """
    Apply reverse transformation if configured for this channel.
    
    Args:
        channel: Servo channel (0-8)
        pulse: Target pulse width
    
    Returns:
        int: Pulse width (reversed if needed)
    """
    calibration = SERVO_CALIBRATION[channel]
    
    if calibration.get("reverse", False):
        min_pulse = calibration["min"]
        max_pulse = calibration["max"]
        return reverse_servo(pulse, min_pulse, max_pulse)
    
    return pulse


def validate_channel(channel):
    """
    Validate servo channel number
    
    Args:
        channel: Channel number to validate
    
    Raises:
        ValueError: If channel is invalid
    """
    if not isinstance(channel, int):
        raise ValueError(f"Channel must be an integer, got {type(channel).__name__}")
    if not 0 <= channel <= 8:
        raise ValueError(f"Invalid channel {channel}. Must be 0-8.")
    return True


def validate_pulse_width(channel, pulse):
    """
    Validate pulse width for a specific channel
    
    Args:
        channel: Channel number (0-8)
        pulse: Pulse width value to validate
    
    Raises:
        ValueError: If pulse width is out of range for the channel
    """
    validate_channel(channel)
    
    if not isinstance(pulse, (int, float)):
        raise ValueError(f"Pulse width must be numeric, got {type(pulse).__name__}")
    
    pulse = int(pulse)
    calibration = SERVO_CALIBRATION[channel]
    min_pulse = calibration["min"]
    max_pulse = calibration["max"]
    
    if not min_pulse <= pulse <= max_pulse:
        raise ValueError(
            f"Pulse width {pulse} out of range for channel {channel} "
            f"({calibration['label']}). Valid range: {min_pulse}-{max_pulse}"
        )
    
    return True


def validate_speed(speed):
    """
    Validate movement speed
    
    Args:
        speed: Speed value to validate (0.1 to 1.0)
    
    Raises:
        ValueError: If speed is out of range
    """
    if not isinstance(speed, (int, float)):
        raise ValueError(f"Speed must be numeric, got {type(speed).__name__}")
    
    if not 0.1 <= speed <= 1.0:
        raise ValueError(f"Speed {speed} out of range. Must be 0.1-1.0 (0.1=slowest, 1.0=fastest)")
    
    return True


def validate_targets(targets):
    """
    Validate a dictionary of target positions
    
    Args:
        targets: Dictionary of {channel: pulse_width}
    
    Raises:
        ValueError: If any channel or pulse width is invalid
    """
    if not isinstance(targets, dict):
        raise ValueError(f"Targets must be a dictionary, got {type(targets).__name__}")
    
    for channel, pulse in targets.items():
        validate_channel(channel)
        validate_pulse_width(channel, pulse)
    
    return True


def get_neutral_positions():
    """
    Get all neutral positions as a dictionary
    
    Returns:
        dict: {channel: neutral_pulse_width}
    """
    return {ch: cal["neutral"] for ch, cal in SERVO_CALIBRATION.items()}
