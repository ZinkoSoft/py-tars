"""
Servo Configuration for TARS Robot
Defines pulse width ranges and positions for 9 servos
"""

# I2C Configuration - YD-ESP32-S3 board
I2C_SDA_PIN = 8   # GPIO pin for SDA (data) - YD-ESP32-S3 labeled SDA pin
I2C_SCL_PIN = 9   # GPIO pin for SCL (clock) - YD-ESP32-S3 labeled SCL pin
I2C_FREQ = 100000  # I2C frequency in Hz (100kHz - confirmed working by scanner)
PCA9685_ADDRESS = 0x40

# PWM Configuration
PWM_FREQ = 50  # 50Hz for servos

# Global speed settings
GLOBAL_SPEED = 1.0  # 1.0 = fastest, 0.1 = slowest
MIN_PULSE = 150    # Minimum safe pulse width
MAX_PULSE = 600    # Maximum safe pulse width

# Servo Channel Assignments
SERVO_CHANNELS = {
    'MAIN_LEGS': 0,      # Raises/lowers legs
    'LEFT_LEG_ROT': 1,   # Left leg rotation
    'RIGHT_LEG_ROT': 2,  # Right leg rotation
    'RIGHT_MAIN': 3,     # Right arm main
    'RIGHT_FOREARM': 4,  # Right arm forearm
    'RIGHT_HAND': 5,     # Right arm hand
    'LEFT_MAIN': 6,      # Left arm main
    'LEFT_FOREARM': 7,   # Left arm forearm
    'LEFT_HAND': 8,      # Left arm hand
}

# Servo Ranges (calibrate these for your servos)
# Format: (min_pulse, max_pulse, default_pulse, invert)
SERVO_RANGES = {
    # Leg servos
    0: {'min': 220, 'max': 350, 'default': 300},  # Main legs (upHeight=220, downHeight=350)
    1: {'min': 220, 'max': 380, 'default': 300, 'invert': True},  # Left leg rotation (starboard) - REVERSED
    2: {'min': 220, 'max': 380, 'default': 300},  # Right leg rotation (port)
    
    # Right arm
    3: {'min': 135, 'max': 500, 'default': 135},  # Right main
    4: {'min': 200, 'max': 500, 'default': 200},  # Right forearm
    5: {'min': 200, 'max': 500, 'default': 200},  # Right hand
    
    # Left arm (inverted to mirror right arm movement)
    6: {'min': 200, 'max': 500, 'default': 440, 'invert': False},  # Left main - REVERSED
    7: {'min': 200, 'max': 500, 'default': 380, 'invert': False},  # Left forearm - REVERSED
    8: {'min': 200, 'max': 500, 'default': 380, 'invert': False},  # Left hand - REVERSED
}

# Preset positions for testing
PRESET_POSITIONS = {
    'neutral': {
        0: 300,
        1: 300,
        2: 300,
        3: 135,
        4: 200,
        5: 200,
        6: 440,
        7: 380,
        8: 380,
    },
    'test_1': {
        0: 350,
        1: 350,
        2: 350,
        3: 200,
        4: 300,
        5: 300,
        6: 400,
        7: 350,
        8: 350,
    }
}

# Movement configuration (from original V2 config)
# These values should be calibrated for your robot
MOVEMENT_CONFIG = {
    # Main legs height control (servo 0)
    'up_height': 220,
    'neutral_height': 300,
    'down_height': 350,
    
    # Left leg rotation (servo 1) - Port (right leg in code)
    'forward_port': 380,
    'neutral_port': 300,
    'back_port': 220,
    'perfect_port_offset': 0,
    
    # Right leg rotation (servo 2) - Starboard (left leg in code)
    'forward_starboard': 220,
    'neutral_starboard': 300,
    'back_starboard': 380,
    'perfect_star_offset': 0,
    
    # Arm ranges
    'port_main_min': 135,
    'port_main_max': 500,
    'port_forearm_min': 200,
    'port_forearm_max': 500,
    'port_hand_min': 200,
    'port_hand_max': 500,
    
    'star_main_min': 200,
    'star_main_max': 500,
    'star_forearm_min': 200,
    'star_forearm_max': 500,
    'star_hand_min': 200,
    'star_hand_max': 500,
}

def reverse_servo(pulse, min_pulse, max_pulse):
    """
    Reverse servo direction by flipping pulse value within range
    Formula: reversed_pulse = max - (pulse - min)
    """
    return max_pulse - (pulse - min_pulse)

def get_servo_range(channel):
    """Get the min/max/default for a servo channel"""
    if channel in SERVO_RANGES:
        return SERVO_RANGES[channel]
    return {'min': MIN_PULSE, 'max': MAX_PULSE, 'default': (MIN_PULSE + MAX_PULSE) // 2}
