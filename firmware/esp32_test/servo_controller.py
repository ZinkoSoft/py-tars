"""
Servo Controller for ESP32 MicroPython
Manages servo movements with async control, speed adjustment, and safety features
"""

import uasyncio as asyncio
import gc
from servo_config import (
    SERVO_CALIBRATION, 
    validate_channel, 
    validate_pulse_width, 
    validate_speed,
    apply_reverse_if_needed
)


class ServoController:
    """
    Async servo controller for coordinated multi-servo movements
    """
    
    def __init__(self, pca9685):
        """
        Initialize servo controller
        
        Args:
            pca9685: PCA9685 instance for PWM control
        """
        self.pca9685 = pca9685
        
        # Current positions for all 9 servos (initialized to neutral)
        self.positions = [SERVO_CALIBRATION[i]["neutral"] for i in range(9)]
        
        # Locks for thread-safe servo access (one per channel)
        self.locks = [asyncio.Lock() for _ in range(9)]
        
        # Emergency stop flag
        self.emergency_stop = False
        
        # Global speed multiplier (0.1 to 1.0)
        self.global_speed = 1.0
        
        # Active sequence name (None if no sequence running)
        self.active_sequence = None
        
        print("ServoController initialized")
    
    def initialize_servos(self):
        """
        Initialize all servos to safe starting positions
        - Legs (0-2): neutral (center) positions
        - Arms (3-8): minimum (closed/retracted) positions
        Synchronous function called during startup
        """
        print("Initializing servos to safe positions...")
        
        for channel in range(9):
            # Arms (channels 3-8) start at minimum (closed), legs (0-2) at neutral
            if channel >= 3:
                target = SERVO_CALIBRATION[channel]["min"]
                pos_desc = "min (closed)"
            else:
                target = SERVO_CALIBRATION[channel]["neutral"]
                pos_desc = "neutral"
            
            try:
                self.pca9685.set_pwm(channel, 0, target)
                self.positions[channel] = target
                print(f"  Channel {channel} ({SERVO_CALIBRATION[channel]['label']}): {target} ({pos_desc})")
            except Exception as e:
                print(f"  ✗ Channel {channel} failed: {e}")
        
        print("Servo initialization complete")
    
    async def move_servo_smooth(self, channel, target, speed=None):
        """
        Move a single servo smoothly from current position to target
        
        Args:
            channel: Servo channel (0-8)
            target: Target pulse width (will be reversed if channel has reverse flag)
            speed: Movement speed (0.1-1.0), uses global_speed if None
        
        Raises:
            ValueError: If channel or target is invalid
            asyncio.CancelledError: If emergency stop is triggered
        """
        # Validate inputs
        validate_channel(channel)
        validate_pulse_width(channel, target)
        
        # Apply reverse transformation if needed for this channel
        actual_target = apply_reverse_if_needed(channel, target)
        
        # Calculate effective speed: use provided speed, default to 1.0, then multiply by global_speed
        if speed is None:
            speed = 1.0
        else:
            validate_speed(speed)
        
        # Apply global speed multiplier
        effective_speed = speed * self.global_speed
        # Ensure result is still within valid range
        effective_speed = max(0.1, min(1.0, effective_speed))
        
        # Acquire lock for this channel
        async with self.locks[channel]:
            current = self.positions[channel]
            
            # Calculate step direction
            if current == actual_target:
                return  # Already at target
            
            step = 1 if actual_target > current else -1
            
            # Movement loop
            position = current
            while position != actual_target:
                # Check emergency stop
                if self.emergency_stop:
                    raise asyncio.CancelledError("Emergency stop activated")
                
                # Move one step
                position += step
                
                # Set PWM
                try:
                    self.pca9685.set_pwm(channel, 0, position)
                    self.positions[channel] = position
                except Exception as e:
                    print(f"Error moving servo {channel}: {e}")
                    raise
                
                # Delay based on effective speed (0.02s base, adjusted by speed)
                # speed=1.0: 0.02s per step (fast)
                # speed=0.1: 0.18s per step (slow)
                delay = 0.02 * (1.1 - effective_speed)
                await asyncio.sleep(delay)
    
    async def move_multiple(self, targets, speed=None):
        """
        Move multiple servos simultaneously
        
        Args:
            targets: Dictionary of {channel: target_pulse_width}
            speed: Movement speed (0.1-1.0), uses global_speed if None
        
        Raises:
            ValueError: If any channel or target is invalid
        """
        # Create tasks for all servo movements
        tasks = []
        for channel, target in targets.items():
            task = asyncio.create_task(
                self.move_servo_smooth(channel, target, speed)
            )
            tasks.append(task)
        
        # Wait for all movements to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check for errors
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Movement error in task {i}: {result}")
    
    async def emergency_stop_all(self):
        """
        Emergency stop - immediately disable all servos
        Response time: <100ms
        """
        print("🚨 EMERGENCY STOP ACTIVATED")
        
        # Set flag to cancel ongoing movements
        self.emergency_stop = True
        
        # Wait for tasks to detect flag and cancel
        await asyncio.sleep(0.1)
        
        # Disable all servos (set PWM to 0 = floating state)
        print("Disabling all servos...")
        for channel in range(9):
            try:
                self.pca9685.set_pwm(channel, 0, 0)
                print(f"  Channel {channel} disabled")
            except Exception as e:
                print(f"  ✗ Channel {channel} disable failed: {e}")
        
        # Reset emergency stop flag
        self.emergency_stop = False
        
        print("Emergency stop complete - all servos in floating state")
    
    async def execute_preset(self, preset_name, presets):
        """
        Execute a preset movement sequence
        
        Args:
            preset_name: Name of preset to execute
            presets: Dictionary of all available presets
        
        Raises:
            ValueError: If preset not found
            RuntimeError: If another sequence is already running
        """
        # Check if sequence already running
        if self.active_sequence is not None:
            raise RuntimeError(f"Sequence already running: {self.active_sequence}")
        
        # Get preset
        if preset_name not in presets:
            raise ValueError(f"Unknown preset: {preset_name}")
        
        preset = presets[preset_name]
        
        try:
            self.active_sequence = preset_name
            print(f"Executing preset: {preset_name}")
            
            # Execute each step
            for i, step in enumerate(preset["steps"]):
                # Check emergency stop
                if self.emergency_stop:
                    print(f"Preset {preset_name} cancelled by emergency stop")
                    raise asyncio.CancelledError("Emergency stop during preset")
                
                print(f"  Step {i+1}/{len(preset['steps'])}: {step.get('description', 'Moving')}")
                
                # Move servos
                await self.move_multiple(step["targets"], step.get("speed", self.global_speed))
                
                # Delay after step
                delay = step.get("delay_after", 0.5)
                await asyncio.sleep(delay)
            
            # Disable servos after sequence
            print(f"Preset {preset_name} complete - disabling servos")
            self.disable_all_servos()
            
        finally:
            self.active_sequence = None
            gc.collect()
    
    def disable_all_servos(self):
        """
        Disable all servos (set to floating state)
        Removes holding torque to save power and reduce heat
        """
        for channel in range(9):
            try:
                self.pca9685.set_pwm(channel, 0, 0)
            except Exception as e:
                print(f"Error disabling channel {channel}: {e}")
    
    def get_status(self):
        """
        Get current servo controller status
        
        Returns:
            dict: Status information
        """
        return {
            "positions": self.positions.copy(),
            "emergency_stop": self.emergency_stop,
            "global_speed": self.global_speed,
            "active_sequence": self.active_sequence,
            "servos": [
                {
                    "channel": i,
                    "label": SERVO_CALIBRATION[i]["label"],
                    "position": self.positions[i],
                    "min": SERVO_CALIBRATION[i]["min"],
                    "max": SERVO_CALIBRATION[i]["max"],
                    "neutral": SERVO_CALIBRATION[i]["neutral"]
                }
                for i in range(9)
            ]
        }
