"""
Servo Configuration - TARS-AI Servo Definitions

This module handles servo configuration and percentage-to-pulse conversion
as defined in TARS_INTEGRATION_PLAN.md.

Key features:
- Percentage-based API (1-100) for intuitive control
- Servo channel mappings for legs and arms
- Pulse range definitions with min/max safety limits
- TARS variant support (V2 Standard, V2 LDX-227, Custom)
"""


class ServoConfig:
    """
    Servo configuration manager with percentage-to-pulse conversion.
    
    Supports TARS-AI servo layout:
    - Legs (3 servos): height, left, right
    - Arms (6 servos): right (main, forearm, hand), left (main, forearm, hand)
    
    Usage:
        config = ServoConfig.from_dict(config_dict)
        pulse = config.percentage_to_pulse("legs", "height", 50)  # 50% height
        pulse = config.percentage_to_pulse("arms", "right_main", 75)  # 75% right arm
    """
    
    # Default TARS V2 Standard configuration (MG996R servos, ±108 range)
    DEFAULT_LEGS = {
        "height": {
            "channel": 0,
            "up": 220,
            "neutral": 300,
            "down": 350,
            "min": 200,
            "max": 400,
        },
        "left": {
            "channel": 1,
            "forward": 220,
            "neutral": 300,
            "back": 380,
            "offset": 0,
            "min": 200,
            "max": 400,
        },
        "right": {
            "channel": 2,
            "forward": 380,
            "neutral": 300,
            "back": 220,
            "offset": 0,
            "min": 200,
            "max": 400,
        },
    }
    
    DEFAULT_ARMS = {
        "right_main": {
            "channel": 3,
            "min": 135,
            "max": 440,
            "neutral": 287,  # midpoint
        },
        "right_forearm": {
            "channel": 4,
            "min": 200,
            "max": 380,
            "neutral": 290,
        },
        "right_hand": {
            "channel": 5,
            "min": 200,
            "max": 280,
            "neutral": 240,
        },
        "left_main": {
            "channel": 6,
            "min": 135,
            "max": 440,
            "neutral": 287,
        },
        "left_forearm": {
            "channel": 7,
            "min": 200,
            "max": 380,
            "neutral": 290,
        },
        "left_hand": {
            "channel": 8,
            "min": 280,
            "max": 380,
            "neutral": 330,
        },
    }
    
    def __init__(self, legs_config=None, arms_config=None):
        """
        Initialize servo configuration.
        
        Args:
            legs_config: Dict with 'height', 'left', 'right' servo definitions
            arms_config: Dict with 'right_*' and 'left_*' servo definitions
        """
        self.legs = legs_config or self.DEFAULT_LEGS.copy()
        self.arms = arms_config or self.DEFAULT_ARMS.copy()
    
    @classmethod
    def from_dict(cls, config_dict):
        """
        Create ServoConfig from configuration dictionary.
        
        Expected structure:
        {
            "servos": {
                "legs": { ... },
                "arms": { ... }
            }
        }
        """
        servos = config_dict.get("servos", {})
        legs = servos.get("legs", cls.DEFAULT_LEGS)
        arms = servos.get("arms", cls.DEFAULT_ARMS)
        
        # Flatten arms config (TARS format has nested structure)
        flat_arms = {}
        if "right" in arms:
            for part in ("main", "forearm", "hand"):
                if part in arms["right"]:
                    flat_arms[f"right_{part}"] = arms["right"][part]
        if "left" in arms:
            for part in ("main", "forearm", "hand"):
                if part in arms["left"]:
                    flat_arms[f"left_{part}"] = arms["left"][part]
        
        # Use flat_arms if available, otherwise use arms as-is
        arms_config = flat_arms if flat_arms else arms
        
        return cls(legs, arms_config)
    
    def percentage_to_pulse(self, group, servo_name, percentage):
        """
        Convert percentage (1-100) to pulse width.
        
        For legs, uses specific positions (up/neutral/down or forward/neutral/back).
        For arms, uses min/max range.
        
        Args:
            group: "legs" or "arms"
            servo_name: Servo identifier (e.g., "height", "left", "right_main")
            percentage: 1-100 value
        
        Returns:
            Pulse width (int) clamped to min/max range
        
        Examples:
            >>> config.percentage_to_pulse("legs", "height", 1)
            220  # up position
            >>> config.percentage_to_pulse("legs", "height", 100)
            350  # down position
            >>> config.percentage_to_pulse("legs", "height", 50)
            285  # middle
        """
        if group == "legs":
            servo_cfg = self.legs.get(servo_name)
        elif group == "arms":
            servo_cfg = self.arms.get(servo_name)
        else:
            raise ValueError(f"Unknown servo group: {group}")
        
        if servo_cfg is None:
            raise ValueError(f"Servo '{servo_name}' not found in {group}")
        
        # Clamp percentage to 1-100
        percentage = max(1, min(100, percentage))
        
        # For legs, use specific positions if available
        if group == "legs":
            if servo_name == "height":
                # 1 = up, 100 = down
                min_val = servo_cfg.get("up", servo_cfg.get("min", 200))
                max_val = servo_cfg.get("down", servo_cfg.get("max", 400))
            else:  # left or right leg
                # 1 = forward, 100 = back
                min_val = servo_cfg.get("forward", servo_cfg.get("min", 200))
                max_val = servo_cfg.get("back", servo_cfg.get("max", 400))
        else:  # arms
            min_val = servo_cfg.get("min", 150)
            max_val = servo_cfg.get("max", 600)
        
        # Convert percentage to pulse (1 = min, 100 = max)
        pulse = min_val + ((max_val - min_val) * (percentage - 1) / 99.0)
        
        # Clamp to safety range
        safety_min = servo_cfg.get("min", min_val)
        safety_max = servo_cfg.get("max", max_val)
        return int(max(safety_min, min(safety_max, pulse)))
    
    def get_neutral(self, group, servo_name):
        """
        Get neutral position for a servo.
        
        Args:
            group: "legs" or "arms"
            servo_name: Servo identifier
        
        Returns:
            Neutral pulse width (int)
        """
        if group == "legs":
            servo_cfg = self.legs.get(servo_name)
        elif group == "arms":
            servo_cfg = self.arms.get(servo_name)
        else:
            raise ValueError(f"Unknown servo group: {group}")
        
        if servo_cfg is None:
            raise ValueError(f"Servo '{servo_name}' not found in {group}")
        
        return servo_cfg.get("neutral", 300)
    
    def get_channel(self, group, servo_name):
        """
        Get PWM channel for a servo.
        
        Args:
            group: "legs" or "arms"
            servo_name: Servo identifier
        
        Returns:
            Channel number (int)
        """
        if group == "legs":
            servo_cfg = self.legs.get(servo_name)
        elif group == "arms":
            servo_cfg = self.arms.get(servo_name)
        else:
            raise ValueError(f"Unknown servo group: {group}")
        
        if servo_cfg is None:
            raise ValueError(f"Servo '{servo_name}' not found in {group}")
        
        return servo_cfg.get("channel", 0)
    
    def get_all_channels(self):
        """
        Get all active servo channels.
        
        Returns:
            List of (group, servo_name, channel) tuples
        """
        channels = []
        
        # Legs channels
        for name, cfg in self.legs.items():
            channels.append(("legs", name, cfg.get("channel", 0)))
        
        # Arms channels
        for name, cfg in self.arms.items():
            channels.append(("arms", name, cfg.get("channel", 0)))
        
        return channels


# Self-tests (run when module is executed directly)
if __name__ == "__main__":
    print("Running servo config self-tests...")
    
    # Test 1: Default configuration
    config = ServoConfig()
    assert config.legs is not None
    assert config.arms is not None
    print("✓ Default configuration")
    
    # Test 2: Percentage conversion (legs)
    pulse_min = config.percentage_to_pulse("legs", "height", 1)
    pulse_max = config.percentage_to_pulse("legs", "height", 100)
    pulse_mid = config.percentage_to_pulse("legs", "height", 50)
    assert pulse_min == 220  # up position
    assert pulse_max == 350  # down position
    assert 280 <= pulse_mid <= 290  # roughly middle
    print("✓ Percentage conversion (legs height)")
    
    # Test 3: Percentage conversion (arms)
    pulse_min = config.percentage_to_pulse("arms", "right_main", 1)
    pulse_max = config.percentage_to_pulse("arms", "right_main", 100)
    assert pulse_min == 135
    assert pulse_max == 440
    print("✓ Percentage conversion (arms)")
    
    # Test 4: Get neutral position
    neutral_height = config.get_neutral("legs", "height")
    assert neutral_height == 300
    print("✓ Get neutral position")
    
    # Test 5: Get channel
    channel = config.get_channel("legs", "height")
    assert channel == 0
    channel = config.get_channel("arms", "right_main")
    assert channel == 3
    print("✓ Get channel")
    
    # Test 6: Get all channels
    channels = config.get_all_channels()
    assert len(channels) == 9  # 3 legs + 6 arms
    print("✓ Get all channels")
    
    # Test 7: from_dict constructor
    config_dict = {
        "servos": {
            "legs": ServoConfig.DEFAULT_LEGS,
            "arms": {
                "right": {
                    "main": {"channel": 3, "min": 135, "max": 440},
                    "forearm": {"channel": 4, "min": 200, "max": 380},
                    "hand": {"channel": 5, "min": 200, "max": 280},
                },
                "left": {
                    "main": {"channel": 6, "min": 135, "max": 440},
                    "forearm": {"channel": 7, "min": 200, "max": 380},
                    "hand": {"channel": 8, "min": 280, "max": 380},
                },
            },
        }
    }
    config2 = ServoConfig.from_dict(config_dict)
    assert config2.get_channel("arms", "right_main") == 3
    print("✓ from_dict constructor")
    
    # Test 8: Clamping (safety)
    pulse = config.percentage_to_pulse("legs", "height", 0)  # Below min
    assert pulse == 220  # Should clamp to min
    pulse = config.percentage_to_pulse("legs", "height", 101)  # Above max
    assert pulse == 350  # Should clamp to max
    print("✓ Percentage clamping")
    
    print("\n✓ All servo config tests passed!")
