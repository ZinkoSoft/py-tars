"""
Movement Sequences - TARS-AI movement library

This module implements all 14 movement sequences from TARS-AI:

Basic Movements:
- reset_position() - Return to neutral stance
- step_forward() - Walk forward one step
- step_backward() - Walk backward one step
- turn_left() - Rotate left
- turn_right() - Rotate right

Expressive Movements:
- wave() - Wave with right arm (right_hi in TARS-AI)
- laugh() - Bouncing motion
- swing_legs() - Pendulum leg motion
- pezz_dispenser() - Dispense candy motion (10s hold)
- now() - Pointing gesture
- balance() - Balancing animation
- mic_drop() - Dramatic mic drop
- monster() - Defensive/threatening pose
- pose() - Strike a pose
- bow() - Bow forward

Per TARS_INTEGRATION_PLAN.md Phase 2.
"""

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

try:
    from lib.utils import sleep_ms
except ImportError:
    import time
    sleep_ms = lambda ms: time.sleep(ms / 1000.0)


class MovementSequences:
    """
    High-level movement sequences for TARS.
    
    All sequences are async and use ServoController for parallel servo movement.
    Based on TARS-AI community project movement patterns.
    
    Args:
        servo_controller: ServoController instance
        servo_config: ServoConfig instance
    """
    
    def __init__(self, servo_controller, servo_config):
        self.controller = servo_controller
        self.config = servo_config
    
    # ========================================================================
    # BASIC MOVEMENTS
    # ========================================================================
    
    async def reset_position(self, speed=1.0):
        """
        Return all servos to neutral position.
        
        Neutral positions:
        - Height: 300 (neutral)
        - Left leg: 300 (neutral)
        - Right leg: 300 (neutral)
        - Arms: mid-range of min/max
        """
        print("Resetting to neutral position...")
        
        # Legs to neutral
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["neutral"],
            left=self.config.legs["left"]["neutral"],
            right=self.config.legs["right"]["neutral"],
            speed=speed
        )
        
        # Arms to neutral (mid-range)
        right_main = (self.config.arms["right"]["main"]["min"] + 
                     self.config.arms["right"]["main"]["max"]) // 2
        right_forearm = (self.config.arms["right"]["forearm"]["min"] + 
                        self.config.arms["right"]["forearm"]["max"]) // 2
        right_hand = (self.config.arms["right"]["hand"]["min"] + 
                     self.config.arms["right"]["hand"]["max"]) // 2
        
        left_main = (self.config.arms["left"]["main"]["min"] + 
                    self.config.arms["left"]["main"]["max"]) // 2
        left_forearm = (self.config.arms["left"]["forearm"]["min"] + 
                       self.config.arms["left"]["forearm"]["max"]) // 2
        left_hand = (self.config.arms["left"]["hand"]["min"] + 
                    self.config.arms["left"]["hand"]["max"]) // 2
        
        await self.controller.move_arm_parallel(
            port_main=right_main,
            port_forearm=right_forearm,
            port_hand=right_hand,
            star_main=left_main,
            star_forearm=left_forearm,
            star_hand=left_hand,
            speed=speed
        )
        
        print("✓ Reset complete")
    
    async def step_forward(self, speed=0.8):
        """
        Walk forward one step.
        
        Sequence:
        1. Lift height
        2. Left leg forward, right leg back
        3. Lower height
        4. Return to neutral
        """
        print("Stepping forward...")
        
        # Phase 1: Lift
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["up"],
            left=self.config.legs["left"]["neutral"],
            right=self.config.legs["right"]["neutral"],
            speed=speed
        )
        await asyncio.sleep_ms(200)
        
        # Phase 2: Step
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["up"],
            left=self.config.legs["left"]["forward"],
            right=self.config.legs["right"]["back"],
            speed=speed
        )
        await asyncio.sleep_ms(200)
        
        # Phase 3: Lower
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["down"],
            left=self.config.legs["left"]["forward"],
            right=self.config.legs["right"]["back"],
            speed=speed
        )
        await asyncio.sleep_ms(200)
        
        # Phase 4: Return to neutral
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["neutral"],
            left=self.config.legs["left"]["neutral"],
            right=self.config.legs["right"]["neutral"],
            speed=speed
        )
        
        print("✓ Step forward complete")
    
    async def step_backward(self, speed=0.8):
        """
        Walk backward one step (reverse of forward).
        
        Sequence:
        1. Lift height
        2. Left leg back, right leg forward
        3. Lower height
        4. Return to neutral
        """
        print("Stepping backward...")
        
        # Phase 1: Lift
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["up"],
            left=self.config.legs["left"]["neutral"],
            right=self.config.legs["right"]["neutral"],
            speed=speed
        )
        await asyncio.sleep_ms(200)
        
        # Phase 2: Step back
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["up"],
            left=self.config.legs["left"]["back"],
            right=self.config.legs["right"]["forward"],
            speed=speed
        )
        await asyncio.sleep_ms(200)
        
        # Phase 3: Lower
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["down"],
            left=self.config.legs["left"]["back"],
            right=self.config.legs["right"]["forward"],
            speed=speed
        )
        await asyncio.sleep_ms(200)
        
        # Phase 4: Return to neutral
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["neutral"],
            left=self.config.legs["left"]["neutral"],
            right=self.config.legs["right"]["neutral"],
            speed=speed
        )
        
        print("✓ Step backward complete")
    
    async def turn_left(self, speed=0.8):
        """
        Rotate left.
        
        Sequence:
        1. Lift height
        2. Both legs rotate left direction
        3. Lower height
        4. Return to neutral
        """
        print("Turning left...")
        
        # Phase 1: Lift
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["up"],
            left=self.config.legs["left"]["neutral"],
            right=self.config.legs["right"]["neutral"],
            speed=speed
        )
        await asyncio.sleep_ms(200)
        
        # Phase 2: Rotate
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["up"],
            left=self.config.legs["left"]["back"],
            right=self.config.legs["right"]["back"],
            speed=speed
        )
        await asyncio.sleep_ms(300)
        
        # Phase 3: Lower
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["down"],
            left=self.config.legs["left"]["back"],
            right=self.config.legs["right"]["back"],
            speed=speed
        )
        await asyncio.sleep_ms(200)
        
        # Phase 4: Return to neutral
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["neutral"],
            left=self.config.legs["left"]["neutral"],
            right=self.config.legs["right"]["neutral"],
            speed=speed
        )
        
        print("✓ Turn left complete")
    
    async def turn_right(self, speed=0.8):
        """
        Rotate right (opposite of turn_left).
        """
        print("Turning right...")
        
        # Phase 1: Lift
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["up"],
            left=self.config.legs["left"]["neutral"],
            right=self.config.legs["right"]["neutral"],
            speed=speed
        )
        await asyncio.sleep_ms(200)
        
        # Phase 2: Rotate
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["up"],
            left=self.config.legs["left"]["forward"],
            right=self.config.legs["right"]["forward"],
            speed=speed
        )
        await asyncio.sleep_ms(300)
        
        # Phase 3: Lower
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["down"],
            left=self.config.legs["left"]["forward"],
            right=self.config.legs["right"]["forward"],
            speed=speed
        )
        await asyncio.sleep_ms(200)
        
        # Phase 4: Return to neutral
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["neutral"],
            left=self.config.legs["left"]["neutral"],
            right=self.config.legs["right"]["neutral"],
            speed=speed
        )
        
        print("✓ Turn right complete")
    
    # ========================================================================
    # EXPRESSIVE MOVEMENTS
    # ========================================================================
    
    async def wave(self, speed=0.7):
        """
        Wave with right arm (TARS-AI: right_hi).
        
        Sequence:
        1. Raise right arm up
        2. Wave hand back and forth 3 times
        3. Lower arm back down
        """
        print("Waving...")
        
        # Raise arm
        await self.controller.move_arm_parallel(
            port_main=self.config.arms["right"]["main"]["max"],
            port_forearm=self.config.arms["right"]["forearm"]["min"],
            speed=speed
        )
        await asyncio.sleep_ms(500)
        
        # Wave 3 times
        for _ in range(3):
            await self.controller.move_arm_parallel(
                port_hand=self.config.arms["right"]["hand"]["max"],
                speed=speed * 1.5
            )
            await asyncio.sleep_ms(200)
            await self.controller.move_arm_parallel(
                port_hand=self.config.arms["right"]["hand"]["min"],
                speed=speed * 1.5
            )
            await asyncio.sleep_ms(200)
        
        # Lower arm
        right_main = (self.config.arms["right"]["main"]["min"] + 
                     self.config.arms["right"]["main"]["max"]) // 2
        right_forearm = (self.config.arms["right"]["forearm"]["min"] + 
                        self.config.arms["right"]["forearm"]["max"]) // 2
        right_hand = (self.config.arms["right"]["hand"]["min"] + 
                     self.config.arms["right"]["hand"]["max"]) // 2
        
        await self.controller.move_arm_parallel(
            port_main=right_main,
            port_forearm=right_forearm,
            port_hand=right_hand,
            speed=speed
        )
        
        print("✓ Wave complete")
    
    async def laugh(self, speed=0.9):
        """
        Bouncing motion (laugh).
        
        Sequence:
        - Quick up/down height movements (5 bounces)
        """
        print("Laughing...")
        
        for _ in range(5):
            await self.controller.move_servo_gradually(
                0, self.config.legs["height"]["up"], speed
            )
            await asyncio.sleep_ms(150)
            await self.controller.move_servo_gradually(
                0, self.config.legs["height"]["down"], speed
            )
            await asyncio.sleep_ms(150)
        
        # Return to neutral
        await self.controller.move_servo_gradually(
            0, self.config.legs["height"]["neutral"], speed
        )
        
        print("✓ Laugh complete")
    
    async def swing_legs(self, speed=0.6):
        """
        Pendulum leg motion (swing back and forth).
        
        Sequence:
        - Both legs swing together left, then right, 3 times
        """
        print("Swinging legs...")
        
        for _ in range(3):
            # Swing left
            await self.controller.move_legs_parallel(
                height=self.config.legs["height"]["neutral"],
                left=self.config.legs["left"]["forward"],
                right=self.config.legs["right"]["forward"],
                speed=speed
            )
            await asyncio.sleep_ms(500)
            
            # Swing right
            await self.controller.move_legs_parallel(
                height=self.config.legs["height"]["neutral"],
                left=self.config.legs["left"]["back"],
                right=self.config.legs["right"]["back"],
                speed=speed
            )
            await asyncio.sleep_ms(500)
        
        # Return to neutral
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["neutral"],
            left=self.config.legs["left"]["neutral"],
            right=self.config.legs["right"]["neutral"],
            speed=speed
        )
        
        print("✓ Swing legs complete")
    
    async def pezz_dispenser(self, speed=0.5):
        """
        Dispense candy motion - head tilts back, hold 10 seconds.
        
        Sequence:
        1. Tilt back (height up, legs forward)
        2. Hold for 10 seconds
        3. Return to neutral
        """
        print("Pezz dispenser (10 second hold)...")
        
        # Tilt back
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["up"],
            left=self.config.legs["left"]["forward"],
            right=self.config.legs["right"]["forward"],
            speed=speed
        )
        
        # Hold for 10 seconds
        await asyncio.sleep_ms(10000)
        
        # Return to neutral
        await self.reset_position(speed)
        
        print("✓ Pezz dispenser complete")
    
    async def now(self, speed=0.7):
        """
        Pointing gesture - extend right arm forward.
        
        Sequence:
        1. Extend right arm forward
        2. Hold for 2 seconds
        3. Return to neutral
        """
        print("Pointing (now)...")
        
        # Extend arm
        await self.controller.move_arm_parallel(
            port_main=self.config.arms["right"]["main"]["min"],
            port_forearm=self.config.arms["right"]["forearm"]["max"],
            port_hand=self.config.arms["right"]["hand"]["min"],
            speed=speed
        )
        
        # Hold
        await asyncio.sleep_ms(2000)
        
        # Return to neutral
        await self.reset_position(speed)
        
        print("✓ Now (pointing) complete")
    
    async def balance(self, speed=0.6):
        """
        Balancing animation - shift weight side to side.
        
        Sequence:
        - Alternate left leg forward/right leg back (3 times each side)
        """
        print("Balancing...")
        
        for _ in range(3):
            # Lean left
            await self.controller.move_legs_parallel(
                height=self.config.legs["height"]["neutral"],
                left=self.config.legs["left"]["forward"],
                right=self.config.legs["right"]["neutral"],
                speed=speed
            )
            await asyncio.sleep_ms(800)
            
            # Lean right
            await self.controller.move_legs_parallel(
                height=self.config.legs["height"]["neutral"],
                left=self.config.legs["left"]["neutral"],
                right=self.config.legs["right"]["back"],
                speed=speed
            )
            await asyncio.sleep_ms(800)
        
        # Return to neutral
        await self.reset_position(speed)
        
        print("✓ Balance complete")
    
    async def mic_drop(self, speed=0.8):
        """
        Dramatic mic drop - drop right hand quickly.
        
        Sequence:
        1. Raise right arm
        2. Quick drop of hand
        3. Hold for 2 seconds
        4. Return to neutral
        """
        print("Mic drop...")
        
        # Raise arm
        await self.controller.move_arm_parallel(
            port_main=self.config.arms["right"]["main"]["max"],
            port_forearm=self.config.arms["right"]["forearm"]["min"],
            port_hand=self.config.arms["right"]["hand"]["min"],
            speed=speed
        )
        await asyncio.sleep_ms(500)
        
        # Drop hand
        await self.controller.move_arm_parallel(
            port_hand=self.config.arms["right"]["hand"]["max"],
            speed=1.0  # Fast drop
        )
        
        # Hold dramatic pose
        await asyncio.sleep_ms(2000)
        
        # Return to neutral
        await self.reset_position(speed)
        
        print("✓ Mic drop complete")
    
    async def monster(self, speed=0.7):
        """
        Defensive/threatening pose - arms up, spread wide.
        
        Sequence:
        1. Raise both arms up and spread
        2. Crouch slightly
        3. Hold for 3 seconds
        4. Return to neutral
        """
        print("Monster pose...")
        
        # Raise and spread arms
        await self.controller.move_arm_parallel(
            port_main=self.config.arms["right"]["main"]["max"],
            port_forearm=self.config.arms["right"]["forearm"]["max"],
            port_hand=self.config.arms["right"]["hand"]["max"],
            star_main=self.config.arms["left"]["main"]["min"],
            star_forearm=self.config.arms["left"]["forearm"]["min"],
            star_hand=self.config.arms["left"]["hand"]["min"],
            speed=speed
        )
        
        # Crouch
        await self.controller.move_servo_gradually(
            0, self.config.legs["height"]["down"], speed
        )
        
        # Hold
        await asyncio.sleep_ms(3000)
        
        # Return to neutral
        await self.reset_position(speed)
        
        print("✓ Monster pose complete")
    
    async def pose(self, speed=0.6):
        """
        Strike a pose - confident stance with one arm up.
        
        Sequence:
        1. Right arm up, left arm down
        2. Slight lean
        3. Hold for 3 seconds
        4. Return to neutral
        """
        print("Striking a pose...")
        
        # Arms
        await self.controller.move_arm_parallel(
            port_main=self.config.arms["right"]["main"]["max"],
            port_forearm=self.config.arms["right"]["forearm"]["min"],
            port_hand=self.config.arms["right"]["hand"]["min"],
            star_main=self.config.arms["left"]["main"]["max"],
            star_forearm=self.config.arms["left"]["forearm"]["max"],
            star_hand=self.config.arms["left"]["hand"]["max"],
            speed=speed
        )
        
        # Lean
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["neutral"],
            left=self.config.legs["left"]["forward"],
            right=self.config.legs["right"]["neutral"],
            speed=speed
        )
        
        # Hold
        await asyncio.sleep_ms(3000)
        
        # Return to neutral
        await self.reset_position(speed)
        
        print("✓ Pose complete")
    
    async def bow(self, speed=0.5):
        """
        Bow forward - polite bow gesture.
        
        Sequence:
        1. Tilt forward (height down, legs back)
        2. Hold for 2 seconds
        3. Return to neutral
        """
        print("Bowing...")
        
        # Bow forward
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["down"],
            left=self.config.legs["left"]["back"],
            right=self.config.legs["right"]["back"],
            speed=speed
        )
        
        # Hold
        await asyncio.sleep_ms(2000)
        
        # Return to neutral
        await self.reset_position(speed)
        
        print("✓ Bow complete")


# Self-tests
if __name__ == "__main__":
    print("Running movement sequences self-tests...")
    
    # Mock components
    class MockPWM:
        def set_pwm(self, channel, on, off):
            pass
    
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from movements.config import ServoConfig
    from movements.control import ServoController
    
    config = ServoConfig()
    controller = ServoController(MockPWM(), config)
    sequences = MovementSequences(controller, config)
    
    # Test initialization
    assert sequences.controller == controller
    assert sequences.config == config
    print("✓ MovementSequences initialization")
    
    # Test that all 14 methods exist
    methods = [
        'reset_position', 'step_forward', 'step_backward', 'turn_left', 'turn_right',
        'wave', 'laugh', 'swing_legs', 'pezz_dispenser', 'now',
        'balance', 'mic_drop', 'monster', 'pose', 'bow'
    ]
    
    for method in methods:
        assert hasattr(sequences, method), f"Missing method: {method}"
        assert callable(getattr(sequences, method)), f"Not callable: {method}"
    print(f"✓ All {len(methods)} movement methods exist")
    
    print("\n✓ All movement sequences tests passed!")
    print(f"Total: {len(methods)} movement sequences ready")
    print("Note: Full async sequence tests should be run on ESP32 hardware")
