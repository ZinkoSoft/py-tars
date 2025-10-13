"""
Servo Controller for TARS Robot - MicroPython ESP32
Handles 9 servos via PCA9685 I2C servo driver
"""

import time
from pca9685 import PCA9685
import servo_config as config


class ServoController:
    """Main servo controller class"""
    
    def __init__(self):
        """Initialize the servo controller"""
        print("Initializing ServoController...")
        
        # Initialize PCA9685
        try:
            self.pca = PCA9685(
                address=config.PCA9685_ADDRESS,
                sda_pin=config.I2C_SDA_PIN,
                scl_pin=config.I2C_SCL_PIN
            )
            self.pca.set_pwm_freq(config.PWM_FREQ)
            print("PCA9685 initialized successfully")
        except Exception as e:
            print(f"ERROR: Failed to initialize PCA9685: {e}")
            raise
        
        # Track current positions
        self.positions = {}
        for ch in range(9):
            servo_range = config.get_servo_range(ch)
            self.positions[ch] = servo_range['default']
        
        print("ServoController ready")
    
    def set_servo_pulse(self, channel, pulse, speed=None):
        """
        Set servo to a specific pulse width with smooth movement
        
        Args:
            channel: Servo channel (0-8)
            pulse: Target pulse width (150-600)
            speed: Movement speed factor (0.1-1.0), None uses global speed
        """
        if channel < 0 or channel > 8:
            print(f"ERROR: Invalid channel {channel}, must be 0-8")
            return False
        
        servo_range = config.get_servo_range(channel)
        
        # Validate pulse range
        if pulse < servo_range['min'] or pulse > servo_range['max']:
            print(f"WARNING: Pulse {pulse} out of range [{servo_range['min']}-{servo_range['max']}] for channel {channel}")
            pulse = max(servo_range['min'], min(pulse, servo_range['max']))
        
        # Use global speed if not specified
        if speed is None:
            speed = config.GLOBAL_SPEED
        
        # Get current position
        current = self.positions.get(channel, servo_range['default'])
        
        # Smooth movement
        if current != pulse:
            step = 1 if pulse > current else -1
            delay_ms = int(20 * (1.0 - speed))
            
            for p in range(current, pulse + step, step):
                self.pca.set_pwm(channel, 0, p)
                if delay_ms > 0:
                    time.sleep_ms(delay_ms)
        else:
            # Already at position
            self.pca.set_pwm(channel, 0, pulse)
        
        # Update position
        self.positions[channel] = pulse
        return True
    
    def set_servo_percentage(self, channel, percentage, speed=None):
        """
        Set servo position using percentage (1-100)
        
        Args:
            channel: Servo channel (0-8)
            percentage: Position as percentage (1=min, 100=max, 50=middle)
            speed: Movement speed factor
        """
        if percentage == 0:
            return False
        
        servo_range = config.get_servo_range(channel)
        min_val = servo_range['min']
        max_val = servo_range['max']
        
        if percentage == 1:
            pulse = min_val
        elif percentage == 100:
            pulse = max_val
        else:
            # Linear interpolation
            if max_val > min_val:
                pulse = min_val + int((max_val - min_val) * (percentage - 1) / 99)
            else:
                pulse = min_val - int((min_val - max_val) * (percentage - 1) / 99)
        
        return self.set_servo_pulse(channel, pulse, speed)
    
    def set_preset(self, preset_name):
        """
        Move all servos to a preset position
        
        Args:
            preset_name: Name of preset in config.PRESET_POSITIONS
        """
        if preset_name not in config.PRESET_POSITIONS:
            print(f"ERROR: Unknown preset '{preset_name}'")
            return False
        
        preset = config.PRESET_POSITIONS[preset_name]
        print(f"Moving to preset: {preset_name}")
        
        for channel, pulse in preset.items():
            self.set_servo_pulse(channel, pulse, speed=0.5)
            time.sleep_ms(50)  # Small delay between servos
        
        print(f"Preset '{preset_name}' complete")
        return True
    
    def disable_all_servos(self):
        """Disable all servos (set PWM to 0)"""
        self.pca.disable_all_servos()
        print("All servos disabled")
    
    def test_servo(self, channel, delay_ms=1000):
        """
        Test a single servo by moving it through its range
        
        Args:
            channel: Servo channel to test
            delay_ms: Delay at each position
        """
        if channel < 0 or channel > 8:
            print(f"ERROR: Invalid channel {channel}")
            return False
        
        servo_range = config.get_servo_range(channel)
        print(f"\nTesting servo {channel}")
        print(f"Range: {servo_range['min']} - {servo_range['max']}")
        
        # Move to min
        print(f"Moving to MIN ({servo_range['min']})")
        self.set_servo_pulse(channel, servo_range['min'], speed=0.5)
        time.sleep_ms(delay_ms)
        
        # Move to middle
        mid = (servo_range['min'] + servo_range['max']) // 2
        print(f"Moving to MID ({mid})")
        self.set_servo_pulse(channel, mid, speed=0.5)
        time.sleep_ms(delay_ms)
        
        # Move to max
        print(f"Moving to MAX ({servo_range['max']})")
        self.set_servo_pulse(channel, servo_range['max'], speed=0.5)
        time.sleep_ms(delay_ms)
        
        # Return to default
        print(f"Returning to DEFAULT ({servo_range['default']})")
        self.set_servo_pulse(channel, servo_range['default'], speed=0.5)
        
        print(f"Servo {channel} test complete\n")
        return True
    
    def test_all_servos(self, delay_ms=1000):
        """Test all 9 servos sequentially"""
        print("\n=== Testing All Servos ===")
        for ch in range(9):
            self.test_servo(ch, delay_ms)
            time.sleep_ms(500)
        print("All servo tests complete")
    
    def sweep_servo(self, channel, duration_ms=2000):
        """
        Sweep a servo back and forth
        
        Args:
            channel: Servo channel
            duration_ms: Duration of one sweep direction
        """
        servo_range = config.get_servo_range(channel)
        steps = 50
        
        print(f"Sweeping servo {channel}...")
        
        # Forward sweep
        for i in range(steps + 1):
            pulse = servo_range['min'] + int((servo_range['max'] - servo_range['min']) * i / steps)
            self.pca.set_pwm(channel, 0, pulse)
            time.sleep_ms(duration_ms // steps)
        
        # Backward sweep
        for i in range(steps, -1, -1):
            pulse = servo_range['min'] + int((servo_range['max'] - servo_range['min']) * i / steps)
            self.pca.set_pwm(channel, 0, pulse)
            time.sleep_ms(duration_ms // steps)
        
        # Return to default
        self.set_servo_pulse(channel, servo_range['default'])
        print(f"Sweep complete")
    
    def get_position(self, channel):
        """Get current position of a servo"""
        return self.positions.get(channel, 0)
    
    def print_positions(self):
        """Print current positions of all servos"""
        print("\n=== Current Servo Positions ===")
        for ch in range(9):
            pos = self.positions.get(ch, 0)
            servo_range = config.get_servo_range(ch)
            print(f"Servo {ch}: {pos} (range: {servo_range['min']}-{servo_range['max']})")
        print()
    
    # ========================================
    # MOVEMENT SEQUENCES / POSES
    # ========================================
    
    def move_legs(self, height_percent, starboard_percent, port_percent, speed_factor=0.5):
        """Move the three leg servos: 0=height, 1=port rotation, 2=starboard rotation"""
        if height_percent is not None:
            self.set_servo_percentage(0, height_percent, speed_factor)
        if starboard_percent is not None:
            self.set_servo_percentage(2, starboard_percent, speed_factor)
        if port_percent is not None:
            self.set_servo_percentage(1, port_percent, speed_factor)
    
    def move_arm(self, port_main, port_forearm, port_hand, star_main, star_forearm, star_hand, speed_factor=0.5):
        """Move the six arm servos"""
        servos = [
            (3, port_main),      # Port main arm
            (4, port_forearm),   # Port forearm
            (5, port_hand),      # Port hand
            (6, star_main),      # Starboard main arm
            (7, star_forearm),   # Starboard forearm
            (8, star_hand),      # Starboard hand
        ]
        for channel, percent in servos:
            if percent is not None and percent != 0:
                self.set_servo_percentage(channel, percent, speed_factor)
    
    def reset_positions(self):
        """Reset to neutral position"""
        print("Resetting to neutral position...")
        self.move_legs(20, 50, 50, 0.2)
        time.sleep_ms(200)
        self.move_legs(30, 50, 50, 0.2)
        time.sleep_ms(200)
        self.move_legs(50, 50, 50, 0.2)
        time.sleep_ms(500)
        self.move_arm(1, 1, 1, 1, 1, 1, 0.3)
        time.sleep_ms(500)
        self.disable_all_servos()
        print("Reset complete")
    
    def step_forward(self):
        """Move forward one step"""
        print("Stepping forward...")
        self.move_legs(50, 50, 50, 0.4)
        time.sleep_ms(200)
        self.move_legs(22, 50, 50, 0.6)
        time.sleep_ms(200)
        self.move_legs(40, 17, 17, 0.65)
        time.sleep_ms(200)
        self.move_legs(85, 50, 50, 0.8)
        time.sleep_ms(200)
        self.move_legs(50, 50, 50, 1)
        time.sleep_ms(500)
        self.disable_all_servos()
        print("Step forward complete")
    
    def step_backward(self):
        """Move backward one step"""
        print("Stepping backward...")
        self.move_legs(50, 50, 50, 0.4)
        time.sleep_ms(200)
        self.move_legs(28, 0, 0, 0.6)
        time.sleep_ms(200)
        self.move_legs(35, 70, 70, 0.6)
        time.sleep_ms(200)
        self.move_legs(55, 40, 40, 0.2)
        time.sleep_ms(200)
        self.move_legs(50, 50, 50, 0.8)
        time.sleep_ms(200)
        self.disable_all_servos()
        print("Step backward complete")
    
    def turn_right(self):
        """Turn right"""
        print("Turning right...")
        self.move_legs(50, 50, 50, 0.4)
        time.sleep_ms(200)
        self.move_legs(100, 0, 0, 0.8)
        time.sleep_ms(300)
        self.move_legs(0, 70, 30, 0.6)
        time.sleep_ms(200)
        self.move_legs(50, 0, 0, 0.6)
        time.sleep_ms(200)
        self.move_legs(0, 50, 50, 0.3)
        time.sleep_ms(200)
        self.move_legs(50, 50, 50, 0.4)
        time.sleep_ms(200)
        self.disable_all_servos()
        print("Turn right complete")
    
    def turn_left(self):
        """Turn left"""
        print("Turning left...")
        self.move_legs(50, 50, 50, 0.4)
        time.sleep_ms(200)
        self.move_legs(100, 0, 0, 0.8)
        time.sleep_ms(300)
        self.move_legs(0, 30, 70, 0.3)
        time.sleep_ms(200)
        self.move_legs(50, 0, 0, 0.6)
        time.sleep_ms(200)
        self.move_legs(0, 50, 50, 0.3)
        time.sleep_ms(200)
        self.move_legs(50, 50, 50, 0.4)
        time.sleep_ms(200)
        self.disable_all_servos()
        print("Turn left complete")
    
    def greet(self):
        """Wave hello with right arm"""
        print("Greeting (wave)...")
        self.move_legs(50, 50, 50, 0.4)
        time.sleep_ms(200)
        self.move_legs(80, 50, 50, 0.8)
        time.sleep_ms(200)
        self.move_legs(80, 50, 70, 0.8)
        time.sleep_ms(200)
        self.move_legs(50, 50, 70, 0.8)
        time.sleep_ms(200)
        self.move_arm(1, 1, 1, 0, 0, 0, 0.5)
        time.sleep_ms(200)
        self.move_arm(1, 1, 1, 100, 1, 1, 0.8)
        time.sleep_ms(200)
        self.move_arm(1, 1, 1, 100, 100, 1, 1)
        time.sleep_ms(200)
        # Wave motion
        for _ in range(3):
            self.move_arm(1, 1, 1, 100, 50, 1, 1)
            time.sleep_ms(200)
            self.move_arm(1, 1, 1, 100, 100, 1, 1)
            time.sleep_ms(200)
        self.move_arm(1, 1, 1, 100, 1, 1, 1)
        time.sleep_ms(200)
        self.move_arm(1, 1, 1, 1, 1, 1, 0.6)
        time.sleep_ms(200)
        self.move_legs(80, 50, 70, 0.8)
        time.sleep_ms(200)
        self.move_legs(80, 50, 50, 0.8)
        time.sleep_ms(200)
        self.move_legs(50, 50, 50, 0.4)
        time.sleep_ms(200)
        self.disable_all_servos()
        print("Greet complete")
    
    def laugh(self):
        """Simulate laughter with bouncing"""
        print("Laughing...")
        for _ in range(5):
            self.move_legs(50, 50, 50, 1)
            time.sleep_ms(100)
            self.move_legs(1, 50, 50, 1)
            time.sleep_ms(100)
        self.move_legs(50, 50, 50, 1)
        time.sleep_ms(200)
        self.disable_all_servos()
        print("Laugh complete")
    
    def swing_legs(self):
        """Dynamic leg swinging motion"""
        print("Swinging legs...")
        self.move_legs(50, 50, 50, 1)
        time.sleep_ms(100)
        self.move_legs(100, 50, 50, 1)
        time.sleep_ms(100)
        for _ in range(3):
            self.move_legs(0, 20, 80, 0.6)
            time.sleep_ms(100)
            self.move_legs(0, 80, 20, 0.6)
            time.sleep_ms(100)
        self.move_legs(0, 50, 50, 0.6)
        time.sleep_ms(100)
        self.move_legs(50, 50, 50, 0.7)
        time.sleep_ms(200)
        self.disable_all_servos()
        print("Swing legs complete")
    
    def pezz_dispenser(self):
        """PEZZ dispenser pose"""
        print("PEZZ dispenser...")
        self.move_legs(50, 50, 50, 0.4)
        time.sleep_ms(200)
        self.move_legs(80, 50, 70, 0.6)
        self.move_arm(1, 1, 1, 1, 1, 1, 0.6)
        time.sleep_ms(200)
        self.move_legs(50, 50, 70, 0.6)
        time.sleep_ms(200)
        self.move_arm(1, 1, 1, 100, 1, 1, 0.8)
        time.sleep_ms(200)
        self.move_arm(1, 1, 1, 100, 100, 1, 0.8)
        time.sleep_ms(200)
        self.move_arm(1, 1, 1, 100, 100, 100, 0.8)
        time.sleep_ms(3000)  # Hold pose
        self.move_arm(1, 1, 1, 100, 100, 1, 0.8)
        time.sleep_ms(200)
        self.move_arm(1, 1, 1, 100, 1, 1, 0.8)
        time.sleep_ms(200)
        self.move_legs(80, 50, 70, 0.6)
        time.sleep_ms(200)
        self.move_arm(1, 1, 1, 1, 1, 1, 0.8)
        time.sleep_ms(200)
        self.move_legs(50, 50, 50, 0.4)
        time.sleep_ms(200)
        self.disable_all_servos()
        print("PEZZ dispenser complete")
    
    def now(self):
        """'Now!' pointing gesture"""
        print("Now! gesture...")
        self.move_legs(50, 50, 50, 0.4)
        time.sleep_ms(200)
        self.move_legs(80, 50, 50, 0.8)
        time.sleep_ms(200)
        self.move_legs(80, 50, 70, 0.8)
        time.sleep_ms(200)
        self.move_arm(1, 1, 1, 75, 1, 1, 1)
        time.sleep_ms(200)
        self.move_legs(50, 50, 65, 0.8)
        time.sleep_ms(200)
        self.move_arm(1, 1, 1, 75, 80, 1, 0.9)
        time.sleep_ms(200)
        self.move_arm(1, 1, 1, 60, 80, 0, 0.9)
        time.sleep_ms(200)
        # Point motion
        for _ in range(3):
            self.move_arm(1, 1, 1, 75, 80, 0, 0.9)
            time.sleep_ms(200)
            self.move_arm(1, 1, 1, 60, 80, 0, 0.9)
            time.sleep_ms(200)
        self.move_arm(1, 1, 1, 75, 1, 1, 1)
        time.sleep_ms(200)
        self.move_legs(50, 50, 80, 0.8)
        time.sleep_ms(200)
        self.move_arm(1, 1, 1, 1, 1, 1, 1)
        time.sleep_ms(200)
        self.move_legs(80, 50, 70, 0.8)
        time.sleep_ms(200)
        self.move_legs(80, 50, 50, 0.8)
        time.sleep_ms(200)
        self.move_legs(50, 50, 50, 0.4)
        time.sleep_ms(200)
        self.disable_all_servos()
        print("Now! complete")
    
    def balance(self):
        """Balance on one leg"""
        print("Balancing...")
        self.move_legs(50, 50, 50, 0.4)
        time.sleep_ms(200)
        self.move_legs(30, 50, 50, 0.8)
        time.sleep_ms(200)
        # Balance motion
        for _ in range(3):
            self.move_legs(30, 60, 60, 0.5)
            time.sleep_ms(200)
            self.move_legs(30, 40, 40, 0.5)
            time.sleep_ms(200)
        self.move_legs(30, 50, 50, 0.8)
        time.sleep_ms(200)
        self.move_legs(50, 50, 50, 0.8)
        time.sleep_ms(500)
        self.disable_all_servos()
        print("Balance complete")
    
    def mic_drop(self):
        """Mic drop gesture"""
        print("Mic drop...")
        self.move_legs(50, 50, 50, 0.4)
        time.sleep_ms(200)
        self.move_legs(80, 50, 50, 0.8)
        time.sleep_ms(200)
        self.move_legs(80, 50, 100, 0.8)
        time.sleep_ms(200)
        self.move_arm(1, 1, 1, 1, 1, 1, 1)
        time.sleep_ms(200)
        self.move_arm(1, 1, 1, 60, 50, 1, 1)
        time.sleep_ms(200)
        self.move_arm(1, 1, 1, 60, 70, 1, 1)
        time.sleep_ms(1000)
        self.move_arm(1, 1, 1, 60, 70, 100, 1)
        time.sleep_ms(2000)
        self.move_arm(1, 1, 1, 1, 1, 1, 1)
        time.sleep_ms(200)
        self.move_legs(80, 50, 50, 0.8)
        time.sleep_ms(200)
        self.move_legs(50, 50, 50, 0.8)
        time.sleep_ms(500)
        self.disable_all_servos()
        print("Mic drop complete")
    
    def defensive_posture(self):
        """Monster/defensive posture"""
        print("Defensive posture...")
        self.move_legs(50, 50, 50, 0.4)
        time.sleep_ms(200)
        self.move_legs(80, 50, 50, 0.4)
        time.sleep_ms(200)
        self.move_legs(80, 70, 70, 0.4)
        self.move_arm(1, 1, 1, 1, 1, 1, 0.8)
        time.sleep_ms(200)
        self.move_arm(100, 1, 1, 100, 1, 1, 0.8)
        time.sleep_ms(200)
        self.move_legs(50, 70, 70, 0.4)
        time.sleep_ms(200)
        self.move_arm(100, 100, 1, 100, 100, 1, 1)
        time.sleep_ms(200)
        self.move_arm(100, 100, 100, 100, 100, 100, 1)
        time.sleep_ms(200)
        # Claw motion
        for _ in range(3):
            self.move_arm(100, 50, 100, 100, 100, 100, 1)
            time.sleep_ms(200)
            self.move_arm(100, 100, 50, 100, 50, 50, 1)
            time.sleep_ms(200)
        self.move_arm(100, 100, 100, 100, 100, 100, 1)
        time.sleep_ms(200)
        self.move_arm(100, 100, 1, 100, 100, 1, 1)
        time.sleep_ms(200)
        self.move_arm(100, 1, 1, 100, 1, 1, 1)
        self.move_legs(50, 70, 70, 0.4)
        time.sleep_ms(200)
        self.move_arm(1, 1, 1, 1, 1, 1, 0.8)
        time.sleep_ms(200)
        self.move_legs(80, 50, 50, 0.4)
        time.sleep_ms(200)
        self.move_legs(50, 50, 50, 0.4)
        time.sleep_ms(200)
        self.disable_all_servos()
        print("Defensive posture complete")
    
    def pose(self):
        """Strike a pose"""
        print("Posing...")
        self.move_legs(50, 50, 50, 0.4)
        self.move_legs(30, 40, 40, 0.4)
        self.move_legs(100, 30, 30, 0.4)
        time.sleep_ms(3000)
        self.move_legs(100, 30, 30, 0.4)
        self.move_legs(30, 30, 30, 0.4)
        self.move_legs(30, 40, 40, 0.4)
        self.move_legs(50, 50, 50, 0.4)
        self.disable_all_servos()
        print("Pose complete")
    
    def bow(self):
        """Take a bow"""
        print("Bowing...")
        self.move_legs(50, 50, 50, 0.4)
        self.move_legs(15, 50, 50, 0.7)
        self.move_legs(15, 70, 70, 0.7)
        self.move_legs(60, 70, 70, 0.7)
        self.move_legs(95, 65, 65, 0.7)
        time.sleep_ms(3000)
        self.move_legs(15, 65, 65, 0.7)
        self.move_legs(50, 50, 50, 0.4)
        self.disable_all_servos()
        print("Bow complete")
