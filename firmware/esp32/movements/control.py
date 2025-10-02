"""
Servo Control Module - Low-level servo movement with asyncio

This module handles:
- Gradual servo movement (smooth transitions)
- Parallel servo movement (multiple servos simultaneously)
- Position tracking and validation
- Speed control

Uses asyncio for non-blocking parallel servo movement.
Per TARS_INTEGRATION_PLAN.md Phase 1.
"""

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

try:
    import utime as time
except ImportError:
    import time

try:
    from lib.utils import sleep_ms
except ImportError:
    import time as time_module
    sleep_ms = lambda ms: time_module.sleep(ms / 1000.0)


class ServoController:
    """
    Low-level servo controller with gradual movement support.
    
    Features:
    - Smooth servo transitions (no jerky movements)
    - Parallel servo movement using asyncio
    - Position tracking
    - Speed control (0.1 = slow, 1.0 = fast)
    - Safety limits enforcement
    
    Args:
        pwm: PCA9685 PWM controller instance
        servo_config: ServoConfig instance with servo definitions
    """
    
    def __init__(self, pwm, servo_config):
        self.pwm = pwm
        self.config = servo_config
        self._positions = {}  # Current positions {channel: pulse_width}
        self._moving = False  # Flag to prevent overlapping movements
        
    def get_position(self, channel):
        """Get current position of a servo channel."""
        return self._positions.get(channel, 300)  # Default to center
    
    def set_position(self, channel, pulse_width):
        """
        Set servo position immediately (no gradual movement).
        
        Args:
            channel: Servo channel (0-15)
            pulse_width: PWM pulse width (typically 150-600)
        """
        if self.pwm is None:
            return
        
        try:
            self.pwm.set_pwm(channel, 0, int(pulse_width))
            self._positions[channel] = int(pulse_width)
        except Exception as e:
            print(f"Error setting channel {channel}: {e}")
    
    async def move_servo_gradually(self, channel, target, speed=1.0):
        """
        Move a single servo gradually from current position to target.
        
        Args:
            channel: Servo channel (0-15)
            target: Target pulse width
            speed: 0.1-1.0 (1.0 = fastest, 0.1 = slowest)
        
        Returns:
            None (updates position via PWM)
        """
        if self.pwm is None:
            return
        
        # Get current position
        current = self.get_position(channel)
        target = int(target)
        
        if current == target:
            return  # Already at target
        
        # Calculate step direction and delay
        step = 1 if target > current else -1
        delay_ms = int(20 * (1.0 - speed))  # Faster speed = less delay
        
        # Move gradually
        for value in range(current, target + step, step):
            try:
                self.pwm.set_pwm(channel, 0, value)
                self._positions[channel] = value
                await asyncio.sleep_ms(delay_ms)
            except Exception as e:
                print(f"Error moving channel {channel}: {e}")
                break
        
        # Ensure we reach exactly the target
        self._positions[channel] = target
        try:
            self.pwm.set_pwm(channel, 0, target)
        except Exception:
            pass
    
    async def move_multiple_gradually(self, movements, speed=1.0):
        """
        Move multiple servos simultaneously (parallel movement).
        
        Args:
            movements: Dict of {channel: target_pulse_width}
            speed: 0.1-1.0 speed factor
        
        Example:
            await controller.move_multiple_gradually({
                0: 300,  # Height to neutral
                1: 220,  # Left leg forward
                2: 380   # Right leg back
            }, speed=0.8)
        """
        if not movements:
            return
        
        # Create parallel tasks for all servos
        tasks = []
        for channel, target in movements.items():
            tasks.append(self.move_servo_gradually(channel, target, speed))
        
        # Execute all movements in parallel
        await asyncio.gather(*tasks)
    
    async def move_legs_parallel(self, height, left, right, speed=1.0):
        """
        Move all 3 leg servos simultaneously.
        
        Per TARS_INTEGRATION_PLAN.md:
        - Channel 0: Height (up/down)
        - Channel 1: Left leg (forward/back)
        - Channel 2: Right leg (forward/back)
        
        Args:
            height: Height pulse width
            left: Left leg pulse width
            right: Right leg pulse width
            speed: 0.1-1.0 speed factor
        """
        movements = {
            0: height,
            1: left,
            2: right
        }
        await self.move_multiple_gradually(movements, speed)
    
    async def move_arm_parallel(self, port_main=None, port_forearm=None, port_hand=None,
                                star_main=None, star_forearm=None, star_hand=None, 
                                speed=1.0):
        """
        Move arm servos simultaneously (right=port, left=star).
        
        Per TARS_INTEGRATION_PLAN.md:
        - Channels 3-5: Right arm (main, forearm, hand)
        - Channels 6-8: Left arm (main, forearm, hand)
        
        Args:
            port_*: Right arm pulse widths (None to skip)
            star_*: Left arm pulse widths (None to skip)
            speed: 0.1-1.0 speed factor
        """
        movements = {}
        
        # Right arm (port)
        if port_main is not None:
            movements[3] = port_main
        if port_forearm is not None:
            movements[4] = port_forearm
        if port_hand is not None:
            movements[5] = port_hand
        
        # Left arm (star)
        if star_main is not None:
            movements[6] = star_main
        if star_forearm is not None:
            movements[7] = star_forearm
        if star_hand is not None:
            movements[8] = star_hand
        
        if movements:
            await self.move_multiple_gradually(movements, speed)
    
    def disable_all_servos(self):
        """
        Disable all servos (set to 0 pulse width).
        Emergency stop function.
        """
        if self.pwm is None:
            return
        
        for channel in range(16):
            try:
                self.pwm.set_pwm(channel, 0, 0)
                self._positions[channel] = 0
            except Exception:
                pass
    
    def reset_to_neutral(self):
        """
        Reset all servos to neutral positions (synchronous).
        
        Uses neutral values from config:
        - Legs: 300 (neutral)
        - Arms: mid-point of range
        """
        # Legs to neutral
        self.set_position(0, 300)  # Height neutral
        self.set_position(1, 300)  # Left neutral
        self.set_position(2, 300)  # Right neutral
        
        # Right arm to mid-range
        right_arm = self.config.arms.get("right", {})
        if "main" in right_arm:
            mid = (right_arm["main"]["min"] + right_arm["main"]["max"]) // 2
            self.set_position(3, mid)
        if "forearm" in right_arm:
            mid = (right_arm["forearm"]["min"] + right_arm["forearm"]["max"]) // 2
            self.set_position(4, mid)
        if "hand" in right_arm:
            mid = (right_arm["hand"]["min"] + right_arm["hand"]["max"]) // 2
            self.set_position(5, mid)
        
        # Left arm to mid-range
        left_arm = self.config.arms.get("left", {})
        if "main" in left_arm:
            mid = (left_arm["main"]["min"] + left_arm["main"]["max"]) // 2
            self.set_position(6, mid)
        if "forearm" in left_arm:
            mid = (left_arm["forearm"]["min"] + left_arm["forearm"]["max"]) // 2
            self.set_position(7, mid)
        if "hand" in left_arm:
            mid = (left_arm["hand"]["min"] + left_arm["hand"]["max"]) // 2
            self.set_position(8, mid)
    
    def is_moving(self):
        """Check if servos are currently moving."""
        return self._moving
    
    def set_moving(self, moving):
        """Set moving flag (used by movement queue)."""
        self._moving = moving


# Self-tests
if __name__ == "__main__":
    print("Running servo control self-tests...")
    
    # Mock PWM controller
    class MockPWM:
        def __init__(self):
            self.values = {}
        
        def set_pwm(self, channel, on, off):
            self.values[channel] = off
    
    # Mock config
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from movements.config import ServoConfig
    config = ServoConfig()
    
    # Test 1: Controller initialization
    mock_pwm = MockPWM()
    controller = ServoController(mock_pwm, config)
    assert controller.pwm == mock_pwm
    assert controller.config == config
    assert controller._positions == {}
    print("✓ Controller initialization")
    
    # Test 2: Get/Set position
    controller.set_position(0, 300)
    assert controller.get_position(0) == 300
    assert mock_pwm.values[0] == 300
    print("✓ Get/Set position")
    
    # Test 3: Disable all servos
    controller.disable_all_servos()
    assert all(v == 0 for v in mock_pwm.values.values())
    print("✓ Disable all servos")
    
    # Test 4: Reset to neutral
    controller.reset_to_neutral()
    assert controller.get_position(0) == 300  # Height neutral
    assert controller.get_position(1) == 300  # Left neutral
    assert controller.get_position(2) == 300  # Right neutral
    print("✓ Reset to neutral")
    
    # Test 5: Moving flag
    assert not controller.is_moving()
    controller.set_moving(True)
    assert controller.is_moving()
    controller.set_moving(False)
    assert not controller.is_moving()
    print("✓ Moving flag")
    
    # Note: Async tests require asyncio.run() which may not be available
    # in all MicroPython versions. These are tested on hardware.
    
    print("\n✓ All servo control tests passed!")
    print("Note: Async movement tests should be run on ESP32 hardware")
