# Quickstart: Testing TARS AI Movement Updates

**Feature**: Adopt TARS AI Movement System Updates  
**Date**: 2025-10-23  
**Audience**: Developers testing on ESP32 hardware

---

## Prerequisites

### Hardware Setup

1. **ESP32-S3** with MicroPython v1.20+ installed
2. **PCA9685** servo controller connected via I2C:
   - SDA → GPIO 8
   - SCL → GPIO 9
   - VCC → 3.3V
   - GND → GND
   - I2C address: 0x40 (default)
3. **9 servos** connected to PCA9685 channels 0-8:
   - Channels 0-2: Leg servos (LDX-227)
   - Channels 3-5: Right arm servos (MG996R shoulder, MG90S elbow/hand)
   - Channels 6-8: Left arm servos (MG996R shoulder, MG90S elbow/hand)
4. **Servo power supply**: 5-6V, sufficient current (≥2A recommended)
5. **WiFi network** for web interface access

### Software Setup

1. **Upload files to ESP32**:
   ```bash
   cd firmware/esp32_test
   
   # Upload Python files (use ampy, rshell, or Thonny)
   ampy --port /dev/ttyUSB0 put main.py
   ampy --port /dev/ttyUSB0 put pca9685.py
   ampy --port /dev/ttyUSB0 put servo_controller.py
   ampy --port /dev/ttyUSB0 put servo_config.py
   ampy --port /dev/ttyUSB0 put movement_presets.py
   ampy --port /dev/ttyUSB0 put web_server.py
   ampy --port /dev/ttyUSB0 put wifi_manager.py
   ampy --port /dev/ttyUSB0 put wifi_config.py  # Update with your WiFi credentials
   ```

2. **Verify WiFi credentials** in `wifi_config.py`:
   ```python
   WIFI_SSID = "YourNetworkName"
   WIFI_PASSWORD = "YourPassword"
   ```

---

## Quick Test: Verify I2C Retry Logic

### Test 1: Normal Operation (Success Path)

**Goal**: Verify servo controller initializes and moves without errors

**Steps**:
1. Power on ESP32
2. Connect to serial console: `screen /dev/ttyUSB0 115200`
3. Observe initialization output:
   ```
   TARS Servo Controller Starting...
   Step 1: Connecting to WiFi...
   ✓ Connected: 192.168.1.XXX
   Step 2: Initializing I2C bus...
   I2C devices found: ['0x40']
   Step 3: Initializing PCA9685...
   Step 4: Initializing Servo Controller...
   Initializing servos to safe positions...
     Channel 0 (Main Legs Lift): 300 -> 300 (neutral) [normal]
     Channel 1 (Left Leg Rotation): 300 -> 300 (neutral) [normal]
     ...
   Servo initialization complete
   ✓ SYSTEM READY
   ✓ Web Interface: http://192.168.1.XXX/
   ```

**Expected**: All channels initialize successfully, no retry messages

**Pass Criteria**: ✅ No "I2C retry" messages, ✅ All servos move to safe positions

---

### Test 2: I2C Error Recovery (Retry Path)

**Goal**: Verify retry logic activates on I2C errors

**Steps**:
1. **Induce I2C error** (choose one method):
   - **Method A**: Wiggle I2C wires while system is initializing
   - **Method B**: Add temporary delay in `pca9685.py` to simulate timeout
   - **Method C**: Briefly disconnect PCA9685 power during operation

2. Observe retry messages in serial console:
   ```
   I2C retry 1/3 on ch0
   I2C retry 2/3 on ch0
   ✓ Channel 0 (Main Legs Lift): 300 -> 300 (neutral) [normal]
   ```

3. Verify system continues operating after retries succeed

**Expected**: Up to 3 retry attempts with 50ms delays, then success

**Pass Criteria**: 
- ✅ Retry messages appear during I2C errors
- ✅ System recovers automatically
- ✅ No more than 3 retries per operation

---

### Test 3: Retry Exhaustion (Failure Path)

**Goal**: Verify system handles unrecoverable I2C failures gracefully

**Steps**:
1. **Disconnect PCA9685** completely (remove power or I2C wires)
2. Power on ESP32
3. Observe initialization failure:
   ```
   Step 3: Initializing PCA9685...
   ✗ PCA9685 not detected: [Errno 19] ENODEV
   Please check:
     - PCA9685 is powered
     - I2C wiring (SDA=GPIO8, SCL=GPIO9)
     - I2C address is 0x40
   ```

**Expected**: Clear error message, system halts gracefully

**Pass Criteria**: 
- ✅ Error message indicates I2C failure
- ✅ No infinite retry loop
- ✅ System halts without crash

---

## Feature Test: Updated step_forward Movement

### Test 4: New Movement Sequence

**Goal**: Verify step_forward uses updated TARS AI sequence

**Steps**:
1. Access web interface: `http://192.168.1.XXX/`
2. Click "Step Forward" button
3. **Visually observe** movement sequence:
   - **Step 1**: Legs remain neutral (0.2s pause)
   - **Step 2**: Legs lower to 22% (was 28%) → should be noticeably lower
   - **Step 3**: Legs at 40% height, rotated 17% → new combined motion
   - **Step 4**: Legs lift to 85% (was 55%) → should be noticeably higher
   - **Step 5**: Return to neutral (0.5s pause, was 0.2s)
4. Measure timing with stopwatch: Total ~1.3 seconds (0.2+0.2+0.2+0.2+0.5)

**Expected**: Smoother, more stable gait with higher lift and lower crouch

**Pass Criteria**:
- ✅ Lower crouch is visible (22% vs 28%)
- ✅ Higher lift is visible (85% vs 55%)
- ✅ Longer final pause (0.5s vs 0.2s)
- ✅ No wobbling or loss of balance

---

## Performance Test: Concurrent Movements

### Test 5: Position Tracking Accuracy

**Goal**: Verify servo position tracking works during concurrent leg+arm movements

**Steps**:
1. Access web interface
2. Execute "Wave Right" preset (moves right arm while legs are stable)
3. Observe serial console for position updates
4. **No errors expected** - concurrent movements should complete smoothly

**Expected**: All servos move smoothly without position corruption

**Pass Criteria**:
- ✅ No position tracking errors
- ✅ Smooth, coordinated movement
- ✅ All servos return to expected positions

---

### Test 6: Lock Contention Check

**Goal**: Verify I2C lock doesn't cause movement delays

**Steps**:
1. Measure step_forward timing before changes (baseline)
2. Apply updates with I2C lock
3. Measure step_forward timing after changes
4. Compare timings

**Expected**: Timing difference <5% (lock overhead minimal)

**Measurement**:
```python
import time
start = time.ticks_ms()
# Execute step_forward
duration = time.ticks_diff(time.ticks_ms(), start)
print(f"Duration: {duration}ms")
```

**Pass Criteria**:
- ✅ Duration increase <5% compared to baseline
- ✅ No visible stuttering or delays

---

## Regression Test: Existing Functionality

### Test 7: All Presets Execute

**Goal**: Verify changes don't break existing movement presets

**Steps**:
1. Execute each preset via web interface:
   - Step Forward ✓
   - Step Backward ✓
   - Turn Left ✓
   - Turn Right ✓
   - Wave Right ✓
   - (Add others as applicable)
2. Verify each completes without errors

**Pass Criteria**: ✅ All presets execute successfully

---

### Test 8: Emergency Stop

**Goal**: Verify emergency stop still works with async locks

**Steps**:
1. Start a long preset (e.g., Monster)
2. Trigger emergency stop (web interface or hardware button)
3. Verify:
   - Movement stops within 100ms
   - All servos disabled (floating state)
   - No lock deadlocks

**Pass Criteria**:
- ✅ Immediate stop (<100ms response)
- ✅ Servos disabled
- ✅ System remains responsive

---

## Debugging Tips

### Serial Console Messages

**Normal operation**:
```
Initializing servos to safe positions...
  Channel 0 (Main Legs Lift): 300 -> 300 (neutral) [normal]
Servo initialization complete
Executing preset: PRESET_STEP_FORWARD
  Step 1/5: Start from neutral
  Step 2/5: Lower legs
  ...
Preset PRESET_STEP_FORWARD complete - disabling servos
```

**I2C retry**:
```
I2C retry 1/3 on ch0
I2C retry 2/3 on ch0
✓ Channel 0 initialized
```

**I2C failure**:
```
I2C error on ch0: [Errno 121] Remote I/O error
✗ Channel 0 failed: initialization error
```

### Common Issues

| Symptom | Likely Cause | Solution |
|---------|--------------|----------|
| "I2C retry" messages frequently | Loose wiring, noisy power | Check connections, add capacitor to PCA9685 VCC |
| Servos jitter during movement | Position tracking incorrect | Verify SERVO_CALIBRATION min/max values |
| step_forward looks same as before | PRESET_STEP_FORWARD not updated | Re-upload movement_presets.py |
| Lock deadlock (system freezes) | Lock acquisition order wrong | Verify channel lock → i2c lock order |
| Movement slower than expected | Global speed too low | Check `servo_controller.global_speed = 1.0` |

### Enabling Debug Logging

Add to `servo_controller.py` for verbose logging:
```python
DEBUG = True

if DEBUG:
    print(f"[DEBUG] Channel {channel}: {current} -> {target}, step={step}")
```

---

## Success Criteria Summary

**Phase 1 (P1 - Critical)**:
- ✅ I2C retry logic activates on errors
- ✅ System recovers from transient I2C failures
- ✅ No PWM conversion errors (servos move correctly)

**Phase 2 (P2 - High)**:
- ✅ Position tracking maintains accuracy
- ✅ Concurrent movements execute without corruption
- ✅ Lock overhead <5% performance impact

**Phase 3 (P3 - Polish)**:
- ✅ step_forward gait improved (visually smoother)
- ✅ Lower crouch and higher lift visible
- ✅ Longer pause at neutral position

**All Phases**:
- ✅ No regressions in existing presets
- ✅ Emergency stop works correctly
- ✅ Web interface remains functional

---

## Next Steps After Testing

1. **Document findings** in test report
2. **Adjust calibration** if servos move to wrong positions
3. **Fine-tune timing** in movement presets if needed
4. **Merge changes** to main branch after validation
5. **Update README** with new movement capabilities

---

## Contact & Support

- **Issues**: File bug reports with serial console logs
- **Hardware Problems**: Check PCA9685 datasheet for I2C specs
- **Software Questions**: Refer to MicroPython asyncio docs

**Last Updated**: 2025-10-23
