# TARS AI Movement System Changes Analysis

**Analysis Date**: October 23, 2025  
**Source Files Analyzed**:
- `firmware/esp32_test/tars-community-movement-original/module_btcontroller_v2.py`
- `firmware/esp32_test/tars-community-movement-original/module_servoctl_v2.py`

**Target Implementation**:
- `firmware/esp32_test/servo_controller.py`
- `firmware/esp32_test/movement_presets.py`

---

## Summary of Key Changes

### 1. Enhanced PCA9685 Initialization (CRITICAL - P1)

**What Changed**:
- Added dedicated `initialize_pca9685()` function with proper error handling
- Implements retry logic with MAX_RETRIES=3 and 50ms delays
- Specific detection of errno 121 (Remote I/O error) vs other I2C errors
- Returns boolean success/failure instead of raising exceptions
- Initializes all 16 channels to 0 duty cycle explicitly

**Original Code** (module_servoctl_v2.py):
```python
def initialize_pca9685():
    global pca
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        pca = PCA9685(i2c, address=0x40)
        pca.frequency = 50
        queue_message("LOAD: PCA9685 initialized successfully")
        return True
    except OSError as e:
        if e.errno == 121:
            queue_message(f"ERROR: I2C Remote I/O error - Check connections and power!")
        else:
            queue_message(f"ERROR: I2C error {e.errno}: {e}")
        return False
    except Exception as e:
        queue_message(f"ERROR: Failed to initialize PCA9685: {e}")
        return False
```

**Impact**: Significantly improves reliability on startup and during operation with loose connections or electrical noise.

---

### 2. PWM to Duty Cycle Conversion (CRITICAL - P1)

**What Changed**:
- Added explicit `pwm_to_duty_cycle()` conversion function
- Formula: `int((pwm_value / 4095.0) * 65535)`
- Converts 12-bit PCA9685 values to 16-bit MicroPython duty cycle

**Original Code** (module_servoctl_v2.py):
```python
def pwm_to_duty_cycle(pwm_value):
    return int((pwm_value / 4095.0) * 65535)
```

**Current ESP32 Code** (pca9685.py):
```python
# Direct PWM setting - no conversion
def set_pwm(self, channel, on, off):
    self._write_word(0x06 + 4 * channel, on)
    self._write_word(0x08 + 4 * channel, off)
```

**Impact**: ESP32 currently uses raw 12-bit PWM values directly. Need to determine if conversion is needed based on how pca9685.py driver works.

---

### 3. Enhanced set_servo_pwm() with Retry Logic (CRITICAL - P1)

**What Changed**:
- Wraps PWM operations with retry logic (MAX_RETRIES=3)
- Uses i2c_lock for thread-safe access
- Returns boolean success/failure
- Detects and handles errno 121 specifically
- 50ms delay between retry attempts

**Original Code** (module_servoctl_v2.py):
```python
def set_servo_pwm(channel, pwm_value):
    if pca is None:
        return False
    
    duty_cycle = pwm_to_duty_cycle(pwm_value)

    for attempt in range(MAX_RETRIES):
        try:
            with i2c_lock:
                pca.channels[channel].duty_cycle = duty_cycle
            return True
        except OSError as e:
            if e.errno == 121:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(0.05)  # 50ms delay
                    continue
                else:
                    queue_message(f"I2C error on channel {channel} after {MAX_RETRIES} attempts")
            return False
        except Exception as e:
            queue_message(f"Error setting PWM on channel {channel}: {e}")
            return False
    
    return False
```

**Impact**: Makes servo control resilient to transient I2C errors.

---

### 4. Thread-Safe Position Tracking (HIGH - P2)

**What Changed**:
- Added `servo_positions = {}` global dictionary
- Tracks current PWM value for each servo channel
- Used by `move_servo_gradually_thread()` to calculate gradual movement steps
- Protected by i2c_lock for thread-safe access

**Original Code** (module_servoctl_v2.py):
```python
i2c_lock = Lock()
servo_positions = {}

def move_servo_gradually_thread(channel, target_value, speed_factor):
    if target_value is None:
        return
    
    with i2c_lock:
        current_value = servo_positions.get(channel, None)
    
    if current_value is None or current_value == target_value:
        if set_servo_pwm(channel, target_value):
            with i2c_lock:
                servo_positions[channel] = target_value
        return
    
    step = 1 if target_value > current_value else -1
    for value in range(current_value, target_value + step, step):
        set_servo_pwm(channel, value)
        time.sleep(0.02 * (1.0 - speed_factor))
    
    with i2c_lock:
        servo_positions[channel] = target_value
```

**Current ESP32 Code**: Has position tracking in `ServoController.positions` but uses it differently - stores positions for all servos, not dynamically updated during gradual movement.

**Impact**: Enables smoother gradual movements with proper step calculation.

---

### 5. MOVING Flag for step_forward() (MEDIUM - P2)

**What Changed**:
- Added global `MOVING = False` flag
- `step_forward()` checks and sets flag to prevent concurrent execution
- Flag is reset after movement completes

**Original Code** (module_servoctl_v2.py):
```python
MOVING = False

def step_forward():
    global MOVING
    if not MOVING:
        MOVING = True
        # ... movement sequence ...
        MOVING = False
```

**Impact**: Prevents movement corruption from rapid repeated commands.

---

### 6. Updated step_forward() Movement Sequence (LOW - P3)

**What Changed**:
- Modified movement percentages and timing for smoother gait

**Original Sequence** (module_servoctl_v2.py):
```python
move_legs(50, 50, 50, 0.4)
time.sleep(0.2)
move_legs(22, 50, 50, 0.6)  # Lower height (22% vs 28%)
time.sleep(0.2)
move_legs(40, 17, 17, 0.65)  # Different height/rotation combo
time.sleep(0.2)
move_legs(85, 50, 50, 0.8)  # Higher lift (85% vs 55%)
time.sleep(0.2)
move_legs(50, 50, 50, 1)
time.sleep(0.5)  # Longer final pause
disable_all_servos()
```

**Impact**: Visual improvement in walking gait smoothness and stability.

---

## Implementation Priority

### Phase 1 (Critical - P1)
1. ✅ Add `initialize_pca9685()` with error handling and retry logic
2. ✅ Investigate and implement `pwm_to_duty_cycle()` if needed for ESP32
3. ✅ Add retry logic to servo PWM operations
4. ✅ Implement proper error detection (errno 121 handling)

### Phase 2 (High - P2)
5. ✅ Add `servo_positions` dictionary with thread-safe access (adapt to asyncio.Lock)
6. ✅ Update `move_servo_smooth()` to use position tracking for gradual movements
7. ✅ Add MOVING flag to prevent concurrent step_forward() execution

### Phase 3 (Low - P3)
8. ✅ Update step_forward() movement sequence with new percentages/timing

---

## MicroPython Adaptation Notes

### Threading → Asyncio
- **Original**: `from threading import Thread, Lock`
- **ESP32**: `import uasyncio as asyncio` with `asyncio.Lock()`
- **Change**: Replace `threading.Lock()` with `asyncio.Lock()` and use `async with` instead of `with`
- **Change**: Replace `time.sleep()` with `await asyncio.sleep()`

### Error Handling
- **Original**: `except OSError as e: if e.errno == 121:`
- **ESP32**: MicroPython may expose errors differently - need to test if `e.errno` is available
- **Fallback**: Use `str(e)` or `e.args` if errno attribute not available

### I2C Access Pattern
- **Original**: `pca.channels[channel].duty_cycle = duty_cycle`
- **ESP32**: `pca.set_pwm(channel, 0, pwm_value)` - different API
- **Impact**: Need to verify if duty cycle conversion is required or if ESP32 driver handles it

---

## Testing Strategy

### Unit Tests
- Test `pwm_to_duty_cycle()` conversion accuracy (0, 2047, 4095 → 0, 32767, 65535)
- Test retry logic with simulated I2C failures
- Test MOVING flag prevents concurrent step_forward() calls
- Test servo_positions dictionary updates correctly during movements

### Integration Tests
- Test full initialization sequence with PCA9685 connected/disconnected
- Test concurrent move_legs() + move_arm() without position corruption
- Test step_forward() with rapid repeated calls (should ignore overlaps)
- Test servo position tracking across 100 consecutive movements

### Hardware Tests
- Test with loose I2C wiring to verify retry recovery
- Test with servo load (actual movement) to verify position accuracy
- Measure step_forward() execution time to ensure MOVING flag clears properly
- Visual inspection of updated step_forward() gait smoothness

---

## Files to Modify

1. **servo_controller.py** (primary changes)
   - Add MOVING flag
   - Add servo_positions dictionary
   - Update move_servo_smooth() to track positions
   - Add retry logic to PWM operations
   - Add errno 121 detection

2. **pca9685.py** (verify/update)
   - Check if pwm_to_duty_cycle conversion needed
   - Add error handling to set_pwm()
   - Consider adding retry logic at driver level

3. **movement_presets.py** (minor changes)
   - Update PRESET_STEP_FORWARD sequence values

4. **main.py** (minor changes)
   - Update initialization to use new error handling
   - Add global MOVING flag initialization

---

## Risk Assessment

### High Risk
- **PWM conversion mismatch**: If ESP32 pca9685.py expects different value range, servos could move incorrectly
  - **Mitigation**: Test with single servo movement before full sequences

### Medium Risk
- **Asyncio.Lock performance**: If lock contention is high, could slow down movements
  - **Mitigation**: Profile movement timing before/after changes

### Low Risk
- **MOVING flag edge cases**: If flag doesn't reset on error, could lock out step_forward() permanently
  - **Mitigation**: Add emergency stop function to reset all flags
