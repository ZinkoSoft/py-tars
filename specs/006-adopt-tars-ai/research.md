# Phase 0: Research & Technical Decisions

**Feature**: Adopt TARS AI Movement System Updates  
**Date**: 2025-10-23  
**Status**: Complete

## Research Tasks

### 1. PWM Duty Cycle Conversion Analysis

**Question**: Does the ESP32 PCA9685 driver require the same PWM-to-duty-cycle conversion as the Raspberry Pi implementation?

**Investigation**:

Analyzed the two different PCA9685 APIs:

**Raspberry Pi (CircuitPython) API**:
```python
# Uses 16-bit duty cycle (0-65535)
pca.channels[channel].duty_cycle = duty_cycle
```

**ESP32 MicroPython API** (current `pca9685.py`):
```python
# Uses 12-bit PWM values (0-4095) directly
def set_pwm(self, channel, on, off):
    self._write_word(0x06 + 4 * channel, on)
    self._write_word(0x08 + 4 * channel, off)
```

**Decision**: **NO CONVERSION NEEDED**

**Rationale**:
- ESP32 driver already uses 12-bit PWM values (0-4095) matching PCA9685 hardware
- CircuitPython driver abstracts this to 16-bit duty cycle for consistency with other PWM interfaces
- `servo_config.py` calibration values are already in 12-bit range (e.g., 192-408, 220-360)
- Conversion formula `(pwm_value / 4095.0) * 65535` is CircuitPython-specific

**Action**: Do NOT implement `pwm_to_duty_cycle()` function. Continue using `set_pwm(channel, 0, pulse_width)` directly.

---

### 2. Threading to Asyncio Adaptation

**Question**: How to adapt Python `threading.Lock` to MicroPython `asyncio.Lock` for I2C thread safety?

**Investigation**:

**Original Pattern (Raspberry Pi)**:
```python
from threading import Lock
i2c_lock = Lock()

def set_servo_pwm(channel, pwm_value):
    for attempt in range(MAX_RETRIES):
        try:
            with i2c_lock:
                pca.channels[channel].duty_cycle = duty_cycle
            return True
        except OSError as e:
            # retry logic
```

**MicroPython Equivalent**:
```python
import uasyncio as asyncio
i2c_lock = asyncio.Lock()

async def set_servo_pwm(channel, pwm_value):
    for attempt in range(MAX_RETRIES):
        try:
            async with i2c_lock:
                pca.set_pwm(channel, 0, pwm_value)
            return True
        except OSError as e:
            # retry logic
```

**Decision**: Use `asyncio.Lock()` with `async with` syntax

**Rationale**:
- MicroPython's `asyncio.Lock()` provides same mutual exclusion semantics
- Requires making I2C functions async (already done in `ServoController`)
- Maintains async-first architecture (no thread blocking)
- Compatible with existing `move_servo_smooth()` async implementation

**Alternatives Considered**:
- **Global lock variable with manual acquire/release**: Rejected - error-prone, no RAII cleanup
- **Machine.disable_irq()**: Rejected - too coarse, blocks all interrupts including WiFi
- **No locking**: Rejected - concurrent I2C access causes corruption

**Action**: Add `self.i2c_lock = asyncio.Lock()` to ServoController, use in all PCA9685 operations.

---

### 3. Errno 121 Error Handling in MicroPython

**Question**: Does MicroPython OSError expose `.errno` attribute like CPython?

**Investigation**:

**CPython Pattern**:
```python
except OSError as e:
    if e.errno == 121:  # EREMOTEIO
        # specific handling
```

**MicroPython Reality**:
MicroPython OSError may not always have `.errno` attribute. Error codes are platform-dependent.

**Decision**: Use defensive error checking with fallback

**Rationale**:
- Check if `.errno` exists before accessing: `hasattr(e, 'errno')`
- Fall back to string matching if needed: `"Remote I/O" in str(e)`
- Log full exception for debugging

**Pattern to Use**:
```python
except OSError as e:
    if hasattr(e, 'errno') and e.errno == 121:
        # Remote I/O error - retry
    elif "Remote I/O" in str(e):
        # Fallback string detection
    else:
        # Other OSError
```

**Action**: Implement defensive errno checking with string fallback.

---

### 4. Servo Position Tracking Strategy

**Question**: How to integrate `servo_positions` dictionary into existing ServoController architecture?

**Investigation**:

**Current ESP32 Architecture**:
- `ServoController.positions` already exists (list of 9 positions)
- Updated in `move_servo_smooth()` at completion
- No mid-movement tracking

**TARS AI Pattern**:
- `servo_positions` dict tracks last commanded position
- Updated after each gradual step
- Used to calculate step direction

**Decision**: Enhance existing `self.positions` tracking

**Rationale**:
- ESP32 already has position tracking infrastructure
- List vs dict doesn't matter (9 servos, contiguous channels 0-8)
- Current tracking happens at completion; add mid-movement updates
- Avoid duplicate state (don't add second positions dict)

**Pattern**:
```python
async def move_servo_smooth(self, channel, target, speed=None):
    async with self.locks[channel]:
        current = self.positions[channel]
        
        if current == actual_target:
            return
        
        step = 1 if actual_target > current else -1
        position = current
        
        while position != actual_target:
            position += step
            self.pca9685.set_pwm(channel, 0, position)
            self.positions[channel] = position  # Update each step
            await asyncio.sleep(delay)
```

**Action**: Update `self.positions[channel]` during gradual movement loop, not just at end.

---

### 5. MOVING Flag Implementation

**Question**: Where to place MOVING flag - global or class attribute? How to handle async context?

**Investigation**:

**TARS AI Pattern** (global):
```python
MOVING = False

def step_forward():
    global MOVING
    if not MOVING:
        MOVING = True
        # movement
        MOVING = False
```

**ESP32 Options**:
1. **Class attribute**: `self.is_moving` in ServoController
2. **Global variable**: `MOVING` at module level
3. **Per-preset tracking**: `self.active_sequence` (already exists)

**Decision**: Use existing `self.active_sequence` attribute

**Rationale**:
- `ServoController.active_sequence` already tracks if preset is running
- Checking `if self.active_sequence is not None` prevents concurrent execution
- Already implemented and working
- No need for separate MOVING flag

**Pattern**:
```python
async def execute_preset(self, preset_name, presets):
    if self.active_sequence is not None:
        raise RuntimeError(f"Sequence already running: {self.active_sequence}")
    
    try:
        self.active_sequence = preset_name
        # execute steps
    finally:
        self.active_sequence = None
```

**Action**: Add check to movement presets that call `execute_preset()`. For direct movement calls (not presets), document that they are not protected by MOVING flag.

---

### 6. Step Forward Sequence Update

**Question**: How to update step_forward movement preset with new percentage values?

**Investigation**:

**Current Sequence** (movement_presets.py):
```python
"PRESET_STEP_FORWARD": {
    "steps": [
        # Original timing/percentages
    ]
}
```

**TARS AI Sequence**:
```python
move_legs(50, 50, 50, 0.4)  # time.sleep(0.2)
move_legs(22, 50, 50, 0.6)  # time.sleep(0.2)
move_legs(40, 17, 17, 0.65) # time.sleep(0.2)
move_legs(85, 50, 50, 0.8)  # time.sleep(0.2)
move_legs(50, 50, 50, 1)    # time.sleep(0.5)
```

**Decision**: Update PRESET_STEP_FORWARD with new values

**Rationale**:
- Direct 1:1 mapping from TARS AI to preset format
- `move_legs(height%, left%, right%, speed)` maps to preset targets + speed
- Delays map to `wait` field in preset steps

**Action**: Update movement_presets.py PRESET_STEP_FORWARD with new percentages and timing.

---

## Best Practices Summary

### Async I2C Operations

**Pattern**: All PCA9685 operations must be async-safe
```python
async def _set_pwm_with_retry(self, channel, pulse):
    async with self.i2c_lock:
        for attempt in range(MAX_RETRIES):
            try:
                self.pca9685.set_pwm(channel, 0, pulse)
                return True
            except OSError as e:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(0.05)  # 50ms retry delay
                else:
                    print(f"I2C error on channel {channel}: {e}")
                    return False
```

### Position Tracking During Movement

**Pattern**: Update positions incrementally
```python
for position in range(current, target, step):
    self.pca9685.set_pwm(channel, 0, position)
    self.positions[channel] = position  # Track each step
    await asyncio.sleep(delay)
```

### Error Handling

**Pattern**: Defensive errno checking
```python
except OSError as e:
    is_remote_io = (hasattr(e, 'errno') and e.errno == 121) or "Remote I/O" in str(e)
    if is_remote_io and attempt < MAX_RETRIES - 1:
        await asyncio.sleep(0.05)
        continue
```

---

## Technology Choices

| Component | Choice | Rationale |
|-----------|--------|-----------|
| PWM API | Direct 12-bit values | ESP32 driver already uses hardware format |
| Locking | asyncio.Lock | MicroPython async-compatible, matches architecture |
| Position Tracking | Enhanced self.positions | Leverage existing infrastructure |
| Movement Protection | self.active_sequence | Already implemented, no new flag needed |
| Error Detection | Defensive errno + string | Handle MicroPython platform variations |
| Retry Delay | 50ms (asyncio.sleep) | Match TARS AI timing, async-compatible |

---

## Implementation Risks & Mitigations

### Risk 1: I2C Lock Contention

**Risk**: Concurrent leg + arm movements could cause lock contention, slowing movements

**Mitigation**:
- Profile movement timing before/after changes
- Lock is per-controller, not per-channel (9 channels share 1 lock)
- Operations are fast (<5ms per PWM write)
- Acceptable tradeoff for data integrity

### Risk 2: Position Tracking Memory

**Risk**: Updating positions every step increases memory writes

**Mitigation**:
- Only 9 integers (36 bytes)
- Updates already happen in existing code
- No new memory allocation

### Risk 3: Async Performance

**Risk**: Converting sync I2C to async adds overhead

**Mitigation**:
- I2C operations already wrapped in async functions
- Lock acquisition is fast (no contention in practice)
- Retry delays only occur on actual errors

---

## References

- TARS AI Community Code: `firmware/esp32_test/tars-community-movement-original/`
- ESP32 PCA9685 Driver: `firmware/esp32_test/pca9685.py`
- MicroPython asyncio docs: https://docs.micropython.org/en/latest/library/asyncio.html
- PCA9685 Datasheet: 12-bit PWM, I2C interface specification
