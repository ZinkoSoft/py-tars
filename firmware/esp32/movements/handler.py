"""
Movement Command Handler - MQTT command processing and queue management

This module handles:
- Parsing movement/test MQTT messages
- Movement command queue (prevent overlapping)
- Emergency stop functionality
- Command validation

Per TARS_INTEGRATION_PLAN.md Phase 3.
"""

try:
    import ujson as json
except ImportError:
    import json

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio


class MovementCommandHandler:
    """
    MQTT command handler for movement sequences.
    
    Subscribes to movement/test topic and executes movement commands.
    Ensures only one movement executes at a time via queue.
    
    Command format:
    {
        "command": "step_forward",
        "speed": 0.8,
        "params": {...}  # Optional parameters for specific commands
    }
    
    Supported commands:
    - Basic: reset, step_forward, step_backward, turn_left, turn_right
    - Expressive: wave, laugh, swing_legs, pezz, now, balance, mic_drop, monster, pose, bow
    - Control: disable, stop (emergency)
    - Manual: move_legs, move_arm (with parameters)
    
    Args:
        movement_sequences: MovementSequences instance
        servo_controller: ServoController instance
        servo_config: ServoConfig instance
    """
    
    def __init__(self, movement_sequences, servo_controller, servo_config):
        self.sequences = movement_sequences
        self.controller = servo_controller
        self.config = servo_config
        self._queue = []  # Command queue
        self._executing = False  # Execution lock
        self._stopped = False  # Emergency stop flag
    
    def parse_command(self, payload):
        """
        Parse MQTT message payload into command dict.
        
        Args:
            payload: JSON string or bytes
        
        Returns:
            dict with keys: command, speed, params
            or None if invalid
        """
        try:
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')
            
            cmd = json.loads(payload)
            
            if not isinstance(cmd, dict):
                print("Invalid command: not a dict")
                return None
            
            if "command" not in cmd:
                print("Invalid command: missing 'command' field")
                return None
            
            # Set defaults
            cmd.setdefault("speed", 1.0)
            cmd.setdefault("params", {})
            
            return cmd
            
        except Exception as e:
            print(f"Error parsing command: {e}")
            return None
    
    def validate_command(self, command):
        """
        Validate that command is supported.
        
        Args:
            command: Command string
        
        Returns:
            bool: True if valid
        """
        valid_commands = [
            # Basic movements
            "reset", "step_forward", "step_backward", "turn_left", "turn_right",
            # Expressive movements
            "wave", "laugh", "swing_legs", "pezz", "pezz_dispenser",
            "now", "balance", "mic_drop", "monster", "pose", "bow",
            # Control
            "disable", "stop",
            # Manual
            "move_legs", "move_arm"
        ]
        
        return command in valid_commands
    
    async def execute_command(self, cmd):
        """
        Execute a movement command.
        
        Args:
            cmd: Command dict with command, speed, params
        
        Returns:
            bool: True if executed successfully
        """
        command = cmd["command"]
        speed = float(cmd.get("speed", 1.0))
        params = cmd.get("params", {})
        
        # Validate speed
        if speed < 0.1:
            speed = 0.1
        elif speed > 1.0:
            speed = 1.0
        
        print(f"Executing: {command} (speed={speed})")
        
        try:
            # Basic movements
            if command == "reset":
                await self.sequences.reset_position(speed)
            
            elif command == "step_forward":
                await self.sequences.step_forward(speed)
            
            elif command == "step_backward":
                await self.sequences.step_backward(speed)
            
            elif command == "turn_left":
                await self.sequences.turn_left(speed)
            
            elif command == "turn_right":
                await self.sequences.turn_right(speed)
            
            # Expressive movements
            elif command == "wave":
                await self.sequences.wave(speed)
            
            elif command == "laugh":
                await self.sequences.laugh(speed)
            
            elif command == "swing_legs":
                await self.sequences.swing_legs(speed)
            
            elif command in ("pezz", "pezz_dispenser"):
                await self.sequences.pezz_dispenser(speed)
            
            elif command == "now":
                await self.sequences.now(speed)
            
            elif command == "balance":
                await self.sequences.balance(speed)
            
            elif command == "mic_drop":
                await self.sequences.mic_drop(speed)
            
            elif command == "monster":
                await self.sequences.monster(speed)
            
            elif command == "pose":
                await self.sequences.pose(speed)
            
            elif command == "bow":
                await self.sequences.bow(speed)
            
            # Control commands
            elif command == "disable":
                self.controller.disable_all_servos()
            
            elif command == "stop":
                self.emergency_stop()
            
            # Manual commands (with parameters)
            elif command == "move_legs":
                await self._execute_move_legs(params, speed)
            
            elif command == "move_arm":
                await self._execute_move_arm(params, speed)
            
            else:
                print(f"Unknown command: {command}")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error executing {command}: {e}")
            return False
    
    async def _execute_move_legs(self, params, speed):
        """
        Execute manual move_legs command with percentage parameters.
        
        Params:
            height_percent: 1-100
            left_percent: 1-100
            right_percent: 1-100
        """
        height_pct = params.get("height_percent", 50)
        left_pct = params.get("left_percent", 50)
        right_pct = params.get("right_percent", 50)
        
        # Convert percentages to pulse widths
        height = self.config.percentage_to_pulse(
            height_pct,
            self.config.legs["height"]["up"],
            self.config.legs["height"]["down"]
        )
        
        left = self.config.percentage_to_pulse(
            left_pct,
            self.config.legs["left"]["forward"],
            self.config.legs["left"]["back"]
        )
        
        right = self.config.percentage_to_pulse(
            right_pct,
            self.config.legs["right"]["forward"],
            self.config.legs["right"]["back"]
        )
        
        await self.controller.move_legs_parallel(height, left, right, speed)
    
    async def _execute_move_arm(self, params, speed):
        """
        Execute manual move_arm command with percentage parameters.
        
        Params:
            port_main, port_forearm, port_hand: 1-100 (right arm)
            star_main, star_forearm, star_hand: 1-100 (left arm)
        """
        # Right arm (port)
        port_main = None
        port_forearm = None
        port_hand = None
        
        if "port_main" in params:
            port_main = self.config.percentage_to_pulse(
                params["port_main"],
                self.config.arms["right"]["main"]["min"],
                self.config.arms["right"]["main"]["max"]
            )
        
        if "port_forearm" in params:
            port_forearm = self.config.percentage_to_pulse(
                params["port_forearm"],
                self.config.arms["right"]["forearm"]["min"],
                self.config.arms["right"]["forearm"]["max"]
            )
        
        if "port_hand" in params:
            port_hand = self.config.percentage_to_pulse(
                params["port_hand"],
                self.config.arms["right"]["hand"]["min"],
                self.config.arms["right"]["hand"]["max"]
            )
        
        # Left arm (star)
        star_main = None
        star_forearm = None
        star_hand = None
        
        if "star_main" in params:
            star_main = self.config.percentage_to_pulse(
                params["star_main"],
                self.config.arms["left"]["main"]["min"],
                self.config.arms["left"]["main"]["max"]
            )
        
        if "star_forearm" in params:
            star_forearm = self.config.percentage_to_pulse(
                params["star_forearm"],
                self.config.arms["left"]["forearm"]["min"],
                self.config.arms["left"]["forearm"]["max"]
            )
        
        if "star_hand" in params:
            star_hand = self.config.percentage_to_pulse(
                params["star_hand"],
                self.config.arms["left"]["hand"]["min"],
                self.config.arms["left"]["hand"]["max"]
            )
        
        await self.controller.move_arm_parallel(
            port_main, port_forearm, port_hand,
            star_main, star_forearm, star_hand,
            speed
        )
    
    def queue_command(self, cmd):
        """
        Add command to queue.
        
        Args:
            cmd: Command dict
        """
        if self._stopped:
            print("Commands blocked: emergency stop active")
            return
        
        self._queue.append(cmd)
        print(f"Queued: {cmd['command']} (queue size: {len(self._queue)})")
    
    async def process_queue(self):
        """
        Process command queue (run continuously).
        
        Executes commands one at a time in FIFO order.
        Should be run as an asyncio task.
        """
        while True:
            # Wait if stopped
            if self._stopped:
                await asyncio.sleep_ms(500)
                continue
            
            # Wait if queue is empty
            if not self._queue:
                await asyncio.sleep_ms(100)
                continue
            
            # Wait if already executing
            if self._executing:
                await asyncio.sleep_ms(100)
                continue
            
            # Get next command
            cmd = self._queue.pop(0)
            
            # Execute
            self._executing = True
            self.controller.set_moving(True)
            
            try:
                await self.execute_command(cmd)
            except Exception as e:
                print(f"Queue execution error: {e}")
            finally:
                self._executing = False
                self.controller.set_moving(False)
            
            # Small delay between commands
            await asyncio.sleep_ms(200)
    
    def emergency_stop(self):
        """
        Emergency stop - clear queue, disable servos, set stop flag.
        """
        print("🛑 EMERGENCY STOP")
        self._stopped = True
        self._queue.clear()
        self.controller.disable_all_servos()
        self._executing = False
        self.controller.set_moving(False)
    
    def clear_stop(self):
        """Clear emergency stop flag (allow commands again)."""
        print("✓ Emergency stop cleared")
        self._stopped = False
    
    def is_stopped(self):
        """Check if emergency stop is active."""
        return self._stopped
    
    def is_executing(self):
        """Check if a command is currently executing."""
        return self._executing
    
    def queue_size(self):
        """Get current queue size."""
        return len(self._queue)
    
    def clear_queue(self):
        """Clear all queued commands (doesn't stop current execution)."""
        count = len(self._queue)
        self._queue.clear()
        print(f"Cleared {count} queued commands")


# Self-tests
if __name__ == "__main__":
    print("Running movement command handler self-tests...")
    
    # Mock components
    class MockPWM:
        def set_pwm(self, channel, on, off):
            pass
    
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from movements.config import ServoConfig
    from movements.control import ServoController
    from movements.sequences import MovementSequences
    
    config = ServoConfig()
    controller = ServoController(MockPWM(), config)
    sequences = MovementSequences(controller, config)
    handler = MovementCommandHandler(sequences, controller, config)
    
    # Test 1: Initialization
    assert handler.sequences == sequences
    assert handler.controller == controller
    assert handler.config == config
    assert handler._queue == []
    assert not handler._executing
    assert not handler._stopped
    print("✓ Handler initialization")
    
    # Test 2: Parse valid command
    cmd = handler.parse_command('{"command": "wave", "speed": 0.8}')
    assert cmd is not None
    assert cmd["command"] == "wave"
    assert cmd["speed"] == 0.8
    print("✓ Parse valid command")
    
    # Test 3: Parse command with defaults
    cmd = handler.parse_command('{"command": "reset"}')
    assert cmd["speed"] == 1.0
    assert cmd["params"] == {}
    print("✓ Parse command with defaults")
    
    # Test 4: Parse invalid command
    cmd = handler.parse_command('invalid json')
    assert cmd is None
    print("✓ Parse invalid command")
    
    # Test 5: Validate commands
    assert handler.validate_command("wave")
    assert handler.validate_command("step_forward")
    assert handler.validate_command("reset")
    assert not handler.validate_command("invalid_command")
    print("✓ Validate commands")
    
    # Test 6: Queue commands
    handler.queue_command({"command": "wave", "speed": 0.8})
    handler.queue_command({"command": "reset", "speed": 1.0})
    assert handler.queue_size() == 2
    print("✓ Queue commands")
    
    # Test 7: Clear queue
    handler.clear_queue()
    assert handler.queue_size() == 0
    print("✓ Clear queue")
    
    # Test 8: Emergency stop
    handler.queue_command({"command": "wave", "speed": 0.8})
    handler.emergency_stop()
    assert handler.is_stopped()
    assert handler.queue_size() == 0
    print("✓ Emergency stop")
    
    # Test 9: Clear stop
    handler.clear_stop()
    assert not handler.is_stopped()
    print("✓ Clear stop")
    
    # Test 10: Queue blocked when stopped
    handler.emergency_stop()
    handler.queue_command({"command": "wave", "speed": 0.8})
    assert handler.queue_size() == 0  # Should not be queued
    handler.clear_stop()
    print("✓ Queue blocked when stopped")
    
    print("\n✓ All movement command handler tests passed!")
    print("Note: Async queue processing should be tested on ESP32 hardware")
