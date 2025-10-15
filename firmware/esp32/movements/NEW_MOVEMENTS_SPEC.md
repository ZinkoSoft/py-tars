# New Movement Specifications

## Overview
This document specifies the 5 new movements to be added to TARS:
1. **big_shrug** - "I don't know" gesture
2. **thinking_pose** - Contemplative stance  
3. **excited_bounce** - Energetic celebration
4. **reach_forward** - Extending to grab
5. **wide_stance** - Stable/strong position

All movements respect single-axis joint constraints and use sequential choreography.

---

## Servo Configuration Reference

### Legs (Channels 0-2)
- **Channel 0 (height)**: up=220, neutral=300, down=350, range=[200-400]
- **Channel 1 (left leg)**: forward=220, neutral=300, back=380, range=[200-400]
- **Channel 2 (right leg)**: forward=380, neutral=300, back=220, range=[200-400]

### Arms (Channels 3-8)
- **Channel 3 (right main/shoulder)**: range=[135-440], neutral=287
- **Channel 4 (right forearm)**: range=[200-380], neutral=290
- **Channel 5 (right hand)**: range=[200-280], neutral=240
- **Channel 6 (left main/shoulder)**: range=[135-440], neutral=287
- **Channel 7 (left forearm)**: range=[200-380], neutral=290
- **Channel 8 (left hand)**: range=[280-380], neutral=330

---

## Movement 1: big_shrug

**Purpose**: Express "I don't know" or uncertainty  
**Duration**: ~3 seconds  
**Complexity**: Medium (uses all joint types)

### Sequence
1. **Setup** (0.5s)
   - Height: neutral (300)
   - Legs: neutral (300, 300)
   - Move to starting position

2. **Shrug Phase** (1.5s)
   - Right arm: main=440 (max sweep out), forearm=200 (min/down), hand=200 (open)
   - Left arm: main=135 (max sweep out), forearm=200 (min/down), hand=380 (open)
   - Both arms sweep outward simultaneously
   - Forearms angled down (shoulder shrug effect)

3. **Hold** (1.0s)
   - Maintain shrug position
   - Static pose for emphasis

4. **Return** (1.0s)
   - Reset to neutral via reset_position()

### Servo Positions
```python
# Phase 1: Setup
height=300, left=300, right=300

# Phase 2: Shrug
port_main=440, port_forearm=200, port_hand=200  # right arm out, down, open
star_main=135, star_forearm=200, star_hand=380  # left arm out, down, open

# Phase 3: Hold (same as phase 2)
# Phase 4: Reset (all neutral)
```

---

## Movement 2: thinking_pose

**Purpose**: Contemplative/considering stance  
**Duration**: ~4 seconds  
**Complexity**: Low (mostly static)

### Sequence
1. **Stance** (1.0s)
   - Height: up (220) - tall confident stance
   - Legs: left forward (220), right back (220) - slight lean

2. **Left Arm Position** (1.0s)
   - Left main: forward (135)
   - Left forearm: tilted up (200) - supporting "chin"
   - Left hand: closed (280)

3. **Right Arm Position** (1.0s)
   - Right main: back (440)
   - Right forearm: neutral (290)
   - Right hand: closed (200)

4. **Hold** (2.0s)
   - Static contemplative pose

5. **Return** (1.0s)
   - Reset to neutral

### Servo Positions
```python
# Phase 1: Stance
height=220, left=220, right=220

# Phase 2-3: Arms (move together)
star_main=135, star_forearm=200, star_hand=280  # left arm forward, up, closed
port_main=440, port_forearm=290, port_hand=200  # right arm back, neutral, closed

# Phase 4: Hold (same as phase 2-3)
# Phase 5: Reset (all neutral)
```

---

## Movement 3: excited_bounce

**Purpose**: High-energy celebration  
**Duration**: ~3 seconds  
**Complexity**: High (rapid cycling)

### Sequence
Loop 3 times (0.9s per cycle):
1. **Bounce Down** (0.3s)
   - Height: down (350) - squat
   - Arms: alternating positions
   - Cycle 1: right forward (135), left back (440)
   - Cycle 2: right back (440), left forward (135)
   - Cycle 3: right forward (135), left back (440)

2. **Bounce Up** (0.3s)
   - Height: up (220) - jump
   - Arms: continue alternating

3. **Mid Bounce** (0.3s)
   - Height: neutral (300)
   - Hands: open/close rapidly
   - Right hand: toggle between 200-280
   - Left hand: toggle between 280-380

4. **Return** (0.5s)
   - Reset to neutral after 3 cycles

### Servo Positions
```python
# Cycle pattern (repeat 3x, alternating arms):
# Down phase
height=350
port_main=135, star_main=440  # Cycle 1 (right forward, left back)
port_main=440, star_main=135  # Cycle 2 (right back, left forward)

# Up phase
height=220
# Arms continue from down phase

# Mid phase  
height=300
port_hand=200→280→200  # rapid open/close
star_hand=280→380→280

# Final: Reset (all neutral)
```

---

## Movement 4: reach_forward

**Purpose**: Extending arms to grab/receive something  
**Duration**: ~4 seconds  
**Complexity**: Medium (sequential arm movement)

### Sequence
1. **Prepare** (1.0s)
   - Height: neutral (300)
   - Legs: neutral
   - Arms: neutral starting position

2. **Extend Arms** (1.5s)
   - Both arms: main=135 (forward sweep)
   - Forearms: extend down (380) for reach
   - Hands: open (200, 380)

3. **Reach Hold** (1.0s)
   - Static extended position
   - Hands remain open

4. **Grab** (0.5s)
   - Hands: close rapidly
   - Right hand: 200→280 (close)
   - Left hand: 380→280 (close)

5. **Return** (1.0s)
   - Reset to neutral with hands closed

### Servo Positions
```python
# Phase 1: Prepare (neutral)
height=300, left=300, right=300
port_main=287, port_forearm=290, port_hand=240
star_main=287, star_forearm=290, star_hand=330

# Phase 2: Extend
port_main=135, port_forearm=380, port_hand=200  # right arm forward, extend, open
star_main=135, star_forearm=380, star_hand=380  # left arm forward, extend, open

# Phase 3: Hold (same as phase 2)

# Phase 4: Grab
port_hand=280  # right hand close
star_hand=280  # left hand close

# Phase 5: Reset (all neutral, hands closed)
```

---

## Movement 5: wide_stance

**Purpose**: Stable/strong/defensive position  
**Duration**: ~4 seconds  
**Complexity**: Low (static pose)

### Sequence
1. **Lower Body** (1.5s)
   - Height: down (350) - low stable stance
   - Left leg: max forward (220)
   - Right leg: max back (220)
   - Wide leg base for stability

2. **Arms Out** (1.0s)
   - Right arm: out (440)
   - Left arm: out (135)
   - Forearms: level (290)
   - Hands: closed fists (280, 280)

3. **Hold** (2.5s)
   - Static strong pose
   - Emphasize stability

4. **Return** (1.0s)
   - Reset to neutral

### Servo Positions
```python
# Phase 1: Lower body
height=350, left=220, right=220  # low, wide stance

# Phase 2: Arms
port_main=440, port_forearm=290, port_hand=280  # right arm out, level, closed
star_main=135, star_forearm=290, star_hand=280  # left arm out, level, closed

# Phase 3: Hold (same as phase 1-2)

# Phase 4: Reset (all neutral)
```

---

## Implementation Notes

### Speed Parameters
- **big_shrug**: speed=0.7 (medium smooth)
- **thinking_pose**: speed=0.6 (slow deliberate)
- **excited_bounce**: speed=1.0 (fast energetic)
- **reach_forward**: speed=0.7 (medium controlled)
- **wide_stance**: speed=0.6 (slow powerful)

### Timing Patterns
All movements follow existing patterns from sequences.py:
- Use `asyncio.sleep_ms()` for delays (200-500ms between phases)
- Use `await self.controller.move_legs_parallel()` for leg movements
- Use `await self.controller.move_arm_parallel()` for arm movements
- Always end with `await self.reset_position(speed)` or explicit return to neutral

### Safety Considerations
- All positions use values within configured min/max ranges
- Movements respect single-axis joint constraints
- No simultaneous compound rotations that could bind linkages
- Speeds kept moderate (0.6-1.0) to avoid servo strain

---

## Testing Checklist

Per movement:
- [ ] Verify all servo positions within safe ranges
- [ ] Test on hardware with `movement/test` MQTT command
- [ ] Verify no binding or mechanical interference
- [ ] Confirm timing feels natural (not too fast/slow)
- [ ] Test speed parameter variations (0.1-1.0)
- [ ] Verify reset_position() completes cleanly

Per integration:
- [ ] MCP tool created with proper @app.tool() decorator
- [ ] MQTT message structure matches existing patterns
- [ ] Unit test added to test_tools.py
- [ ] LLM can invoke via "tars-movement" command
- [ ] End-to-end test via llm/request topic
