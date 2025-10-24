"""
Movement Presets for TARS Servo Controller
Preset sequences adapted from tars-community-movement-original/module_servoctl_v2.py
"""

from servo_config import SERVO_CALIBRATION


def percent_to_pulse(percent, min_val, max_val):
    """
    Convert percentage (1-100) to pulse width value
    Matches the logic from original code
    
    Args:
        percent: Percentage value (1-100, or 0 for no change)
        min_val: Minimum pulse width
        max_val: Maximum pulse width
    
    Returns:
        Pulse width value, or None if percent is 0
    """
    if percent == 0:
        return None
    if percent == 1:
        return min_val
    if percent == 100:
        return max_val
    
    if max_val > min_val:
        value = min_val + ((max_val - min_val) * (percent - 1) / 99)
    else:
        value = min_val - ((min_val - max_val) * (percent - 1) / 99)
    
    return int(round(value))


def make_leg_targets(height_pct, left_pct, right_pct):
    """Convert leg percentages to target dict"""
    targets = {}
    
    if height_pct is not None and height_pct != 0:
        targets[0] = percent_to_pulse(height_pct, 
                                      SERVO_CALIBRATION[0]["min"],  # upHeight
                                      SERVO_CALIBRATION[0]["max"])  # downHeight
    
    if left_pct is not None and left_pct != 0:
        targets[1] = percent_to_pulse(left_pct,
                                      SERVO_CALIBRATION[1]["min"],  # forwardStarboard (left leg forward)
                                      SERVO_CALIBRATION[1]["max"])  # backStarboard (left leg back)
    
    if right_pct is not None and right_pct != 0:
        targets[2] = percent_to_pulse(right_pct,
                                      SERVO_CALIBRATION[2]["min"],  # forwardPort (right leg forward)
                                      SERVO_CALIBRATION[2]["max"])  # backPort (right leg back)
    
    return targets


def make_arm_targets(port_main, port_fore, port_hand, star_main, star_fore, star_hand):
    """Convert arm percentages to target dict"""
    targets = {}
    
    # Right arm (port)
    if port_main is not None and port_main != 0:
        targets[3] = percent_to_pulse(port_main,
                                      SERVO_CALIBRATION[3]["min"],
                                      SERVO_CALIBRATION[3]["max"])
    
    if port_fore is not None and port_fore != 0:
        targets[4] = percent_to_pulse(port_fore,
                                      SERVO_CALIBRATION[4]["min"],
                                      SERVO_CALIBRATION[4]["max"])
    
    if port_hand is not None and port_hand != 0:
        targets[5] = percent_to_pulse(port_hand,
                                      SERVO_CALIBRATION[5]["min"],
                                      SERVO_CALIBRATION[5]["max"])
    
    # Left arm (starboard)  
    if star_main is not None and star_main != 0:
        targets[6] = percent_to_pulse(star_main,
                                      SERVO_CALIBRATION[6]["min"],
                                      SERVO_CALIBRATION[6]["max"])
    
    if star_fore is not None and star_fore != 0:
        targets[7] = percent_to_pulse(star_fore,
                                      SERVO_CALIBRATION[7]["min"],
                                      SERVO_CALIBRATION[7]["max"])
    
    if star_hand is not None and star_hand != 0:
        targets[8] = percent_to_pulse(star_hand,
                                      SERVO_CALIBRATION[8]["min"],
                                      SERVO_CALIBRATION[8]["max"])
    
    return targets


# Preset Movement Sequences
PRESETS = {
    "reset_positions": {
        "description": "Reset all servos to neutral positions",
        "steps": [
            # Step 1: Raise torso up first
            {"targets": make_leg_targets(50, 0, 0), "speed": 0.8, "delay_after": 0.2},
            # Step 2: Move hands to neutral
            {"targets": make_arm_targets(0, 0, 1, 0, 0, 1), "speed": 0.7, "delay_after": 0.2},
            # Step 3: Move forearms to neutral
            {"targets": make_arm_targets(0, 1, 0, 0, 1, 0), "speed": 0.7, "delay_after": 0.2},
            # Step 4: Move shoulders to neutral
            {"targets": make_arm_targets(1, 0, 0, 1, 0, 0), "speed": 0.7, "delay_after": 0.2},
            # Step 5: Move legs to neutral
            {"targets": make_leg_targets(30, 50, 50), "speed": 0.8, "delay_after": 0.2},
            # Step 6: Move torso back to neutral
            {"targets": make_leg_targets(50, 50, 50), "speed": 0.8, "delay_after": 0.5},
        ]
    },
    
    "step_forward": {
        "description": "Walk forward one step",
        "steps": [
            {"targets": make_leg_targets(50, 50, 50), "speed": 0.4, "delay_after": 0.2, "description": "Start from neutral"},
            {"targets": make_leg_targets(22, 50, 50), "speed": 0.6, "delay_after": 0.2, "description": "Lower legs for weight shift"},
            {"targets": make_leg_targets(40, 17, 17), "speed": 0.65, "delay_after": 0.2, "description": "Shift weight forward"},
            {"targets": make_leg_targets(85, 50, 50), "speed": 0.8, "delay_after": 0.2, "description": "Lift legs to advance"},
            {"targets": make_leg_targets(50, 50, 50), "speed": 1.0, "delay_after": 0.5, "description": "Return to neutral position"},
        ]
    },
    
    "step_backward": {
        "description": "Walk backward one step",
        "steps": [
            {"targets": make_leg_targets(50, 50, 50), "speed": 0.6, "delay_after": 0.2},
            {"targets": make_leg_targets(28, 0, 0), "speed": 0.4, "delay_after": 0.2},
            {"targets": make_leg_targets(35, 15, 15), "speed": 0.4, "delay_after": 0.2},
            {"targets": make_leg_targets(55, 40, 40), "speed": 0.8, "delay_after": 0.2},
            {"targets": make_leg_targets(50, 50, 50), "speed": 0.2, "delay_after": 0.2},
        ]
    },
    
    "turn_right": {
        "description": "Turn 90 degrees to the right",
        "steps": [
            {"targets": make_leg_targets(50, 50, 50), "speed": 0.6, "delay_after": 0.2},
            {"targets": make_leg_targets(100, 0, 0), "speed": 0.2, "delay_after": 0.3},
            {"targets": make_leg_targets(0, 30, 70), "speed": 0.7, "delay_after": 0.2},
            {"targets": make_leg_targets(50, 0, 0), "speed": 0.4, "delay_after": 0.2},
            {"targets": make_leg_targets(0, 50, 50), "speed": 0.7, "delay_after": 0.2},
            {"targets": make_leg_targets(50, 50, 50), "speed": 0.6, "delay_after": 0.2},
        ]
    },
    
    "turn_left": {
        "description": "Turn 90 degrees to the left",
        "steps": [
            {"targets": make_leg_targets(50, 50, 50), "speed": 0.6, "delay_after": 0.2},
            {"targets": make_leg_targets(100, 0, 0), "speed": 0.2, "delay_after": 0.3},
            {"targets": make_leg_targets(0, 70, 30), "speed": 0.4, "delay_after": 0.2},
            {"targets": make_leg_targets(50, 0, 0), "speed": 0.4, "delay_after": 0.2},
            {"targets": make_leg_targets(0, 50, 50), "speed": 0.7, "delay_after": 0.2},
            {"targets": make_leg_targets(50, 50, 50), "speed": 0.6, "delay_after": 0.2},        
        ]
    },
    
    "right_hi": {
        "description": "Wave/greet with right arm",
        "steps": [
            {"targets": make_leg_targets(50, 50, 50), "speed": 0.6, "delay_after": 0.2},
            {"targets": make_leg_targets(80, 50, 50), "speed": 0.2, "delay_after": 0.2},
            {"targets": make_leg_targets(80, 50, 15), "speed": 0.2, "delay_after": 0.2},
            {"targets": make_leg_targets(50, 50, 15), "speed": 0.2, "delay_after": 0.2},
            {"targets": make_arm_targets(1, 1, 1, 0, 0, 0), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_arm_targets(100, 1, 1, 0, 0, 0), "speed": 0.2, "delay_after": 0.2},
            {"targets": make_arm_targets(100, 100, 1, 0, 0, 0), "speed": 0.5, "delay_after": 0.2},
            # Wave 3 times
            {"targets": make_arm_targets(100, 50, 1, 0, 0, 0), "speed": 1, "delay_after": 0.2},
            {"targets": make_arm_targets(100, 100, 1, 0, 0, 0), "speed": 1, "delay_after": 0.2},
            {"targets": make_arm_targets(100, 50, 1, 0, 0, 0), "speed": 1, "delay_after": 0.2},
            {"targets": make_arm_targets(100, 100, 1, 0, 0, 0), "speed": 1, "delay_after": 0.2},
            {"targets": make_arm_targets(100, 50, 1, 0, 0, 0), "speed": 1, "delay_after": 0.2},
            {"targets": make_arm_targets(100, 1, 1, 0, 0, 0), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_arm_targets(1, 1, 1, 0, 0, 0), "speed": 0.4, "delay_after": 0.2},
            {"targets": make_leg_targets(80, 50, 50), "speed": 0.2, "delay_after": 0.2},
            {"targets": make_leg_targets(50, 50, 50), "speed": 0.6, "delay_after": 0.2},
        ]
    },
    
    "laugh": {
        "description": "Bouncing laugh motion",
        "steps": [
            {"targets": make_leg_targets(50, 50, 50), "speed": 1, "delay_after": 0.1},
            {"targets": make_leg_targets(1, 50, 50), "speed": 1, "delay_after": 0.1},
            {"targets": make_leg_targets(50, 50, 50), "speed": 1, "delay_after": 0.1},
            {"targets": make_leg_targets(1, 50, 50), "speed": 1, "delay_after": 0.1},
            {"targets": make_leg_targets(50, 50, 50), "speed": 1, "delay_after": 0.1},
            {"targets": make_leg_targets(1, 50, 50), "speed": 1, "delay_after": 0.1},
            {"targets": make_leg_targets(50, 50, 50), "speed": 1, "delay_after": 0.1},
            {"targets": make_leg_targets(1, 50, 50), "speed": 1, "delay_after": 0.1},
            {"targets": make_leg_targets(50, 50, 50), "speed": 1, "delay_after": 0.1},
            {"targets": make_leg_targets(1, 50, 50), "speed": 1, "delay_after": 0.1},
            {"targets": make_leg_targets(50, 50, 50), "speed": 1, "delay_after": 0.2},
        ]
    },
    
    "swing_legs": {
        "description": "Side-to-side leg swinging",
        "steps": [
            {"targets": make_leg_targets(50, 50, 50), "speed": 0.5, "delay_after": 0.1},
            {"targets": make_leg_targets(100, 50, 50), "speed": 0.5, "delay_after": 0.1},
            {"targets": make_leg_targets(0, 20, 80), "speed": 0.4, "delay_after": 0.1},
            {"targets": make_leg_targets(0, 80, 20), "speed": 0.4, "delay_after": 0.1},
            {"targets": make_leg_targets(0, 20, 80), "speed": 0.4, "delay_after": 0.1},
            {"targets": make_leg_targets(0, 80, 20), "speed": 0.4, "delay_after": 0.1},
            {"targets": make_leg_targets(0, 20, 80), "speed": 0.4, "delay_after": 0.1},
            {"targets": make_leg_targets(0, 80, 20), "speed": 0.4, "delay_after": 0.1},
            {"targets": make_leg_targets(0, 50, 50), "speed": 0.4, "delay_after": 0.1},
            {"targets": make_leg_targets(50, 50, 50), "speed": 0.3, "delay_after": 0.2},
        ]
    },
    
    "balance": {
        "description": "Balancing motion on one leg",
        "steps": [
            {"targets": make_leg_targets(50, 50, 50), "speed": 0.6, "delay_after": 0.2},
            {"targets": make_leg_targets(30, 50, 50), "speed": 0.2, "delay_after": 0.2},
            # Balance wobble
            {"targets": make_leg_targets(30, 40, 40), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_leg_targets(30, 60, 60), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_leg_targets(30, 40, 40), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_leg_targets(30, 60, 60), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_leg_targets(30, 40, 40), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_leg_targets(30, 60, 60), "speed": 0.5, "delay_after": 0.2},
            # Back down
            {"targets": make_leg_targets(30, 50, 50), "speed": 0.2, "delay_after": 0.2},
            {"targets": make_leg_targets(50, 50, 50), "speed": 0.2, "delay_after": 0.5},
        ]
    },
    
    "mic_drop": {
        "description": "Dramatic mic drop gesture",
        "steps": [
            {"targets": make_leg_targets(50, 50, 50), "speed": 0.6, "delay_after": 0.2},
            {"targets": make_leg_targets(80, 50, 50), "speed": 0.2, "delay_after": 0.2},
            {"targets": make_leg_targets(80, 50, 10), "speed": 0.2, "delay_after": 0.2},
            {"targets": make_arm_targets(1, 1, 1, 0, 0, 0), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_arm_targets(60, 50, 1, 0, 0, 0), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_arm_targets(60, 70, 1, 0, 0, 0), "speed": 0.5, "delay_after": 1.0},
            {"targets": make_arm_targets(60, 70, 100, 0, 0, 0), "speed": 0.5, "delay_after": 2.0},
            {"targets": make_arm_targets(1, 1, 1, 0, 0, 0), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_leg_targets(80, 50, 50), "speed": 0.2, "delay_after": 0.2},
            {"targets": make_leg_targets(50, 50, 50), "speed": 0.2, "delay_after": 0.5},
        ]
    },
    
    "monster": {
        "description": "Defensive monster posture",
        "steps": [
            {"targets": make_leg_targets(50, 50, 50), "speed": 0.6, "delay_after": 0.2},
            {"targets": make_leg_targets(80, 50, 50), "speed": 0.6, "delay_after": 0.2},
            {"targets": make_leg_targets(80, 25, 25), "speed": 0.6, "delay_after": 0.2},
            {"targets": make_arm_targets(1, 1, 1, 1, 1, 1), "speed": 0.2, "delay_after": 0.2},
            {"targets": make_arm_targets(100, 1, 1, 100, 1, 1), "speed": 0.2, "delay_after": 0.2},
            {"targets": make_leg_targets(50, 24, 24), "speed": 0.6, "delay_after": 0.2},
            {"targets": make_arm_targets(100, 100, 1, 100, 100, 1), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_arm_targets(100, 100, 100, 100, 100, 100), "speed": 0.5, "delay_after": 0.2},
            # Claw motions
            {"targets": make_arm_targets(100, 50, 100, 100, 100, 100), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_arm_targets(100, 100, 50, 100, 50, 50), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_arm_targets(100, 50, 100, 100, 100, 100), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_arm_targets(100, 100, 50, 100, 50, 50), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_arm_targets(100, 100, 100, 100, 100, 100), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_arm_targets(100, 100, 1, 100, 100, 1), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_arm_targets(100, 100, 100, 100, 100, 100), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_arm_targets(100, 100, 1, 100, 100, 1), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_arm_targets(100, 100, 100, 100, 100, 100), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_arm_targets(100, 100, 1, 100, 100, 1), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_arm_targets(100, 100, 100, 100, 100, 100), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_arm_targets(100, 100, 1, 100, 100, 1), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_arm_targets(100, 1, 1, 100, 1, 1), "speed": 0.5, "delay_after": 0.2},
            {"targets": make_leg_targets(50, 10, 10), "speed": 0.6, "delay_after": 0.2},
            {"targets": make_arm_targets(1, 1, 1, 1, 1, 1), "speed": 0.2, "delay_after": 0.2},
            {"targets": make_leg_targets(80, 50, 50), "speed": 0.6, "delay_after": 0.2},
            {"targets": make_leg_targets(50, 50, 50), "speed": 0.6, "delay_after": 0.2},
        ]
    },
    
    "pose": {
        "description": "Strike a pose",
        "steps": [
            {"targets": make_leg_targets(50, 50, 50), "speed": 0.6, "delay_after": 0.0},
            {"targets": make_leg_targets(30, 40, 40), "speed": 0.6, "delay_after": 0.0},
            {"targets": make_leg_targets(100, 30, 30), "speed": 0.6, "delay_after": 3.0},
            {"targets": make_leg_targets(100, 30, 30), "speed": 0.6, "delay_after": 0.0},
            {"targets": make_leg_targets(30, 30, 30), "speed": 0.6, "delay_after": 0.0},
            {"targets": make_leg_targets(30, 40, 40), "speed": 0.6, "delay_after": 0.0},
            {"targets": make_leg_targets(50, 50, 50), "speed": 0.6, "delay_after": 0.0},
        ]
    },
    
    "bow": {
        "description": "Bow forward politely",
        "steps": [
            {"targets": make_leg_targets(50, 50, 50), "speed": 0.6, "delay_after": 0.0},
            {"targets": make_leg_targets(15, 50, 50), "speed": 0.3, "delay_after": 0.0},
            {"targets": make_leg_targets(15, 25, 25), "speed": 0.3, "delay_after": 0.0},
            {"targets": make_leg_targets(60, 25, 25), "speed": 0.3, "delay_after": 0.0},
            {"targets": make_leg_targets(95, 35, 35), "speed": 0.3, "delay_after": 3.0},
            {"targets": make_leg_targets(15, 35, 35), "speed": 0.3, "delay_after": 0.0},
            {"targets": make_leg_targets(50, 50, 50), "speed": 0.6, "delay_after": 0.0},
        ]
    },
}
