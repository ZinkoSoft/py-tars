"""
Movement Sequences - TARS-AI movement library

This module implements 20 movement sequences (15 original + 5 new expressive):

Basic Movements:
- reset_position() - Return to neutral stance
- step_forward() - Walk forward one step
- step_backward() - Walk backward one step
- turn_left() - Rotate left
- turn_right() - Rotate right

Expressive Movements (Original):
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

New Expressive Movements (Phase 2 Expansion):
- big_shrug() - "I don't know" gesture with arms out
- thinking_pose() - Contemplative stance with arm supporting chin
- excited_bounce() - High-energy celebration with rapid bouncing
- reach_forward() - Extending arms to grab/receive
- wide_stance() - Stable defensive position with wide base

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
    
    # ========================================================================
    # NEW EXPRESSIVE MOVEMENTS (Phase 2 Expansion)
    # ========================================================================
    
    async def big_shrug(self, speed=0.7):
        """
        "I don't know" gesture - arms out, forearms down.
        
        Sequence:
        1. Setup neutral stance
        2. Sweep both arms outward with forearms angled down
        3. Hold shrug position
        4. Return to neutral
        
        Duration: ~3 seconds
        """
        print("Big shrug...")
        
        # Phase 1: Ensure neutral starting position
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["neutral"],
            left=self.config.legs["left"]["neutral"],
            right=self.config.legs["right"]["neutral"],
            speed=speed
        )
        await asyncio.sleep_ms(200)
        
        # Phase 2: Shrug - arms sweep out, forearms down, hands open
        await self.controller.move_arm_parallel(
            port_main=self.config.arms["right"]["main"]["max"],  # 440 - right arm out
            port_forearm=self.config.arms["right"]["forearm"]["min"],  # 200 - forearm down
            port_hand=self.config.arms["right"]["hand"]["min"],  # 200 - hand open
            star_main=self.config.arms["left"]["main"]["min"],  # 135 - left arm out
            star_forearm=self.config.arms["left"]["forearm"]["min"],  # 200 - forearm down
            star_hand=self.config.arms["left"]["hand"]["max"],  # 380 - hand open
            speed=speed
        )
        
        # Phase 3: Hold shrug for emphasis
        await asyncio.sleep_ms(1000)
        
        # Phase 4: Return to neutral
        await self.reset_position(speed)
        
        print("✓ Big shrug complete")
    
    async def thinking_pose(self, speed=0.6):
        """
        Contemplative stance - one arm supporting chin, tall stance.
        
        Sequence:
        1. Stand tall with slight lean
        2. Left arm forward/up (supporting chin)
        3. Right arm back
        4. Hold contemplative pose
        5. Return to neutral
        
        Duration: ~4 seconds
        """
        print("Thinking pose...")
        
        # Phase 1: Tall stance with slight lean
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["up"],  # 220 - tall
            left=self.config.legs["left"]["forward"],  # 220 - left forward
            right=self.config.legs["right"]["back"],  # 220 - right back (creates lean)
            speed=speed
        )
        await asyncio.sleep_ms(500)
        
        # Phase 2-3: Position arms
        await self.controller.move_arm_parallel(
            star_main=self.config.arms["left"]["main"]["min"],  # 135 - left arm forward
            star_forearm=self.config.arms["left"]["forearm"]["min"],  # 200 - forearm up
            star_hand=self.config.arms["left"]["hand"]["min"],  # 280 - hand closed
            port_main=self.config.arms["right"]["main"]["max"],  # 440 - right arm back
            port_forearm=self.config.arms["right"]["forearm"]["neutral"],  # 290 - neutral
            port_hand=self.config.arms["right"]["hand"]["min"],  # 200 - hand closed
            speed=speed
        )
        
        # Phase 4: Hold contemplative pose
        await asyncio.sleep_ms(2000)
        
        # Phase 5: Return to neutral
        await self.reset_position(speed)
        
        print("✓ Thinking pose complete")
    
    async def excited_bounce(self, speed=1.0):
        """
        High-energy celebration - rapid bouncing with arm swings.
        
        Sequence:
        - 3 rapid cycles of squat/jump with alternating arm positions
        - Hands open/close rapidly for energy effect
        
        Duration: ~3 seconds
        """
        print("Excited bounce...")
        
        # 3 bounce cycles
        for i in range(3):
            # Determine arm positions (alternate each cycle)
            if i % 2 == 0:
                # Right forward, left back
                port_main = self.config.arms["right"]["main"]["min"]  # 135
                star_main = self.config.arms["left"]["main"]["max"]  # 440
            else:
                # Right back, left forward
                port_main = self.config.arms["right"]["main"]["max"]  # 440
                star_main = self.config.arms["left"]["main"]["min"]  # 135
            
            # Bounce down - squat
            await self.controller.move_legs_parallel(
                height=self.config.legs["height"]["down"],  # 350 - squat
                left=self.config.legs["left"]["neutral"],
                right=self.config.legs["right"]["neutral"],
                speed=speed
            )
            await self.controller.move_arm_parallel(
                port_main=port_main,
                star_main=star_main,
                speed=speed
            )
            await asyncio.sleep_ms(200)
            
            # Bounce up - jump
            await self.controller.move_legs_parallel(
                height=self.config.legs["height"]["up"],  # 220 - jump
                left=self.config.legs["left"]["neutral"],
                right=self.config.legs["right"]["neutral"],
                speed=speed
            )
            # Rapid hand open/close
            await self.controller.move_arm_parallel(
                port_hand=self.config.arms["right"]["hand"]["max"],  # 280 - open
                star_hand=self.config.arms["left"]["hand"]["max"],  # 380 - open
                speed=speed
            )
            await asyncio.sleep_ms(150)
            
            # Mid bounce
            await self.controller.move_legs_parallel(
                height=self.config.legs["height"]["neutral"],  # 300
                left=self.config.legs["left"]["neutral"],
                right=self.config.legs["right"]["neutral"],
                speed=speed
            )
            await self.controller.move_arm_parallel(
                port_hand=self.config.arms["right"]["hand"]["min"],  # 200 - close
                star_hand=self.config.arms["left"]["hand"]["min"],  # 280 - close
                speed=speed
            )
            await asyncio.sleep_ms(150)
        
        # Return to neutral
        await self.reset_position(speed)
        
        print("✓ Excited bounce complete")
    
    async def reach_forward(self, speed=0.7):
        """
        Extend arms forward to grab/receive - functional reaching motion.
        
        Sequence:
        1. Start from neutral
        2. Extend both arms forward with forearms down (reach)
        3. Hold with hands open
        4. Close hands (grab)
        5. Return to neutral
        
        Duration: ~4 seconds
        """
        print("Reaching forward...")
        
        # Phase 1: Prepare (ensure neutral)
        await self.reset_position(speed)
        await asyncio.sleep_ms(300)
        
        # Phase 2: Extend arms forward
        await self.controller.move_arm_parallel(
            port_main=self.config.arms["right"]["main"]["min"],  # 135 - forward
            port_forearm=self.config.arms["right"]["forearm"]["max"],  # 380 - extend down
            port_hand=self.config.arms["right"]["hand"]["min"],  # 200 - open
            star_main=self.config.arms["left"]["main"]["min"],  # 135 - forward
            star_forearm=self.config.arms["left"]["forearm"]["max"],  # 380 - extend down
            star_hand=self.config.arms["left"]["hand"]["max"],  # 380 - open
            speed=speed
        )
        
        # Phase 3: Hold reach position
        await asyncio.sleep_ms(1000)
        
        # Phase 4: Grab - close hands rapidly
        await self.controller.move_arm_parallel(
            port_hand=self.config.arms["right"]["hand"]["max"],  # 280 - close
            star_hand=self.config.arms["left"]["hand"]["min"],  # 280 - close
            speed=1.0  # Fast grab
        )
        await asyncio.sleep_ms(500)
        
        # Phase 5: Return to neutral (with hands closed)
        await self.reset_position(speed)
        
        print("✓ Reach forward complete")
    
    async def wide_stance(self, speed=0.6):
        """
        Stable/strong defensive position - low wide base, arms out.
        
        Sequence:
        1. Lower body into wide leg stance
        2. Spread arms out to sides
        3. Hold strong pose
        4. Return to neutral
        
        Duration: ~4 seconds
        """
        print("Wide stance...")
        
        # Phase 1: Lower body with wide leg base
        await self.controller.move_legs_parallel(
            height=self.config.legs["height"]["down"],  # 350 - low stable
            left=self.config.legs["left"]["forward"],  # 220 - max forward
            right=self.config.legs["right"]["back"],  # 220 - max back
            speed=speed
        )
        await asyncio.sleep_ms(800)
        
        # Phase 2: Arms out to sides, level, fists closed
        await self.controller.move_arm_parallel(
            port_main=self.config.arms["right"]["main"]["max"],  # 440 - right out
            port_forearm=self.config.arms["right"]["forearm"]["neutral"],  # 290 - level
            port_hand=self.config.arms["right"]["hand"]["max"],  # 280 - closed
            star_main=self.config.arms["left"]["main"]["min"],  # 135 - left out
            star_forearm=self.config.arms["left"]["forearm"]["neutral"],  # 290 - level
            star_hand=self.config.arms["left"]["hand"]["min"],  # 280 - closed
            speed=speed
        )
        
        # Phase 3: Hold strong pose
        await asyncio.sleep_ms(2500)
        
        # Phase 4: Return to neutral
        await self.reset_position(speed)
        
        print("✓ Wide stance complete")


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
    
    # Test that all 20 methods exist (15 original + 5 new)
    methods = [
        'reset_position', 'step_forward', 'step_backward', 'turn_left', 'turn_right',
        'wave', 'laugh', 'swing_legs', 'pezz_dispenser', 'now',
        'balance', 'mic_drop', 'monster', 'pose', 'bow',
        'big_shrug', 'thinking_pose', 'excited_bounce', 'reach_forward', 'wide_stance'
    ]
    
    for method in methods:
        assert hasattr(sequences, method), f"Missing method: {method}"
        assert callable(getattr(sequences, method)), f"Not callable: {method}"
    print(f"✓ All {len(methods)} movement methods exist")
    
    print("\n✓ All movement sequences tests passed!")
    print(f"Total: {len(methods)} movement sequences ready")
    print("Note: Full async sequence tests should be run on ESP32 hardware")
