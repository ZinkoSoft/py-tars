# V2 Configuration Verification

**Status**: ✅ **VERIFIED AND CORRECTED**  
**Date**: 2025-01-XX  
**Config Source**: `firmware/esp32_test/tars-community-movement-original/config.ini`  
**Movement Version**: `MOVEMENT_VERSION = V2`

---

## Configuration Corrections Made

### Issue Identified
Initial planning documents (`data-model.md`, `contracts/servo-commands.md`) contained **incorrect calibration values** that did not match the V2 configuration in `config.ini`. Some values were placeholders or V1 values.

### Hardware Inventory

### I2C Configuration

**Custom GPIO Pin Assignment**:
- **SDA (Data)**: GPIO 8 (not default GPIO 21)
- **SCL (Clock)**: GPIO 9 (not default GPIO 22)
- **I2C Speed**: 100kHz (standard mode)
- **I2C Bus**: Bus 0 on ESP32

**MicroPython Initialization**:
```python
import machine
i2c = machine.I2C(0, scl=machine.Pin(9), sda=machine.Pin(8))
```

**Note**: Using GPIO 8/9 instead of the typical GPIO 21/22 to avoid conflicts with other peripherals or due to hardware design constraints.

---

### Complete Servo Configuration

| Channel | Function | Servo Type | Torque | Notes |
|---------|----------|------------|--------|-------|
| 0 | Main Legs Lift | **LDX-227** | High | Raises/lowers both legs vertically |
| 1 | Left Leg Rotation (Starboard) | **LDX-227** | High | Wide ±108° rotation range |
| 2 | Right Leg Rotation (Port) | **LDX-227** | High | Wide ±108° rotation range |
| 3 | Right Shoulder | **MG996R** | High (11kg·cm @ 4.8V) | Heavy-duty shoulder joint |
| 4 | Right Elbow | **MG90S** | Medium (2.2kg·cm @ 4.8V) | Lightweight forearm control |
| 5 | Right Hand | **MG90S** | Medium | Wrist/hand with reduced range (280 max) |
| 6 | Left Shoulder | **MG996R** | High (11kg·cm @ 4.8V) | Heavy-duty shoulder joint |
| 7 | Left Elbow | **MG90S** | Medium (2.2kg·cm @ 4.8V) | Lightweight forearm control |
| 8 | Left Hand | **MG90S** | Medium | Wrist/hand with inverted range |

**Servo Type Summary**:
- **3x LDX-227** (Channels 0-2): High-torque legs with wide rotation range
- **2x MG996R** (Channels 3, 6): High-torque shoulders (11kg·cm torque)
- **4x MG90S** (Channels 4-5, 7-8): Lightweight arms/hands (2.2kg·cm torque, faster response)

**Design Rationale**:
- LDX-227 on legs provides ±108° rotation vs MG996R's ±80° (35% more range)
- MG996R on shoulders handles heavy arm weight and provides strong lifting
- MG90S on forearms/hands reduces overall arm weight and improves speed/precision

---

## V2 Values Applied

#### Leg Servos (Channels 0-2)

| Channel | Servo Name | Config Variable | V2 Value | Notes |
|---------|-----------|-----------------|----------|-------|
| 0 | Main Legs Lift | upHeight | 220 | Min (raised position) - **LDX-227** |
| 0 | Main Legs Lift | neutralHeight | 300 | Neutral |
| 0 | Main Legs Lift | downHeight | 350 | Max (lowered position) |
| 1 | Left Leg (Starboard) | forwardStarboard | 192 | Min (forward) - **LDX-227** |
| 1 | Left Leg (Starboard) | neutralStarboard | 300 | Neutral |
| 1 | Left Leg (Starboard) | backStarboard | 408 | Max (back) - **LDX-227** |
| 2 | Right Leg (Port) | backPort | 192 | Min (back) - **LDX-227** |
| 2 | Right Leg (Port) | neutralPort | 300 | Neutral |
| 2 | Right Leg (Port) | forwardPort | 408 | Max (forward) - **LDX-227** |

**V2 Changes**: 
- **Channels 0-2 use LDX-227 servos** with ±108 range from neutral (300): Min=192, Max=408
- V1 used MG996R with ±50 from neutral (350)
- If using MG996R servos instead, use ±80 range: Min=220, Max=380

---

#### Right Arm Servos (Channels 3-5)

| Channel | Servo Name | Servo Type | Config Variable | V2 Value | Notes |
|---------|-----------|------------|-----------------|----------|-------|
| 3 | Right Shoulder | **MG996R** | portMainMin | 135 | Min |
| 3 | Right Shoulder | **MG996R** | portMainMax | 440 | Max |
| 4 | Right Elbow | **MG90S** | portForarmMin | 200 | Min |
| 4 | Right Elbow | **MG90S** | portForarmMax | 380 | Max |
| 5 | Right Hand | **MG90S** | portHandMin | 200 | Min |
| 5 | Right Hand | **MG90S** | portHandMax | **280** | Max (not 380!) |

**Critical Notes**: 
- Channel 3 uses **MG996R** (high torque) for shoulder joint
- Channels 4-5 use **MG90S** (lightweight) for forearm/hand
- Channel 5 (right hand) max is **280**, not 380 like other arm servos. This prevents over-extension of the hand mechanism.

---

#### Left Arm Servos (Channels 6-8)

| Channel | Servo Name | Servo Type | Config Variable | V2 Value | Notes |
|---------|-----------|------------|-----------------|----------|-------|
| 6 | Left Shoulder | **MG996R** | starMainMin | **440** | Min (inverted from right) |
| 6 | Left Shoulder | **MG996R** | starMainMax | **135** | Max (inverted from right) |
| 7 | Left Elbow | **MG90S** | starForarmMin | **380** | Min (inverted from right) |
| 7 | Left Elbow | **MG90S** | starForarmMax | **200** | Max (inverted from right) |
| 8 | Left Hand | **MG90S** | starHandMin | **380** | Min (inverted from right) |
| 8 | Left Hand | **MG90S** | starHandMax | **280** | Max (inverted from right) |

**Critical Notes**: 
- Channel 6 uses **MG996R** (high torque) for shoulder joint
- Channels 7-8 use **MG90S** (lightweight) for forearm/hand
- Left arm servos have **inverted min/max values** compared to right arm. This is due to mirrored mechanical mounting. In config.ini, `starMainMin=440` and `starMainMax=135` (opposite of portMain).

---

## Neutral Position Calculations

**Original Issue**: Some neutral positions were set to 200 (arbitrary), which could cause servo strain at startup.

**Correction**: Neutral positions now calculated as **midpoint between min and max** to ensure servos start in mechanically safe positions:

| Channel | Min | Max | Neutral (Midpoint) | Servo Type |
|---------|-----|-----|--------------------|------------|
| 0 | 220 | 350 | 300 (from config) | **LDX-227** |
| 1 | 192 | 408 | 300 (from config) | **LDX-227** |
| 2 | 192 | 408 | 300 (from config) | **LDX-227** |
| 3 | 135 | 440 | **287** (calculated) | **MG996R** |
| 4 | 200 | 380 | **290** (calculated) | **MG90S** |
| 5 | 200 | 280 | **240** (calculated) | **MG90S** |
| 6 | 135 | 440 | **287** (calculated) | **MG996R** |
| 7 | 200 | 380 | **290** (calculated) | **MG90S** |
| 8 | 280 | 380 | **330** (calculated) | **MG90S** |

**Rationale**: Using midpoint neutral positions prevents servos from being under strain when initialized, extending servo lifespan.

---

## Files Updated

1. **`specs/002-esp32-micropython-servo/data-model.md`**
   - `SERVO_CALIBRATION` dict updated with all V2 values
   - Added critical notes about inverted left arm values
   - Documented channel 5 hand max=280 exception
   - Added V2 configuration header comments

2. **`specs/002-esp32-micropython-servo/contracts/servo-commands.md`**
   - Servo channel mapping table updated with V2 min/max/neutral
   - Added V2 configuration notes section
   - Documented leg rotation ±80 range
   - Clarified channel 0 inverted semantics (min=up, max=down)

---

## Implementation Checklist

When implementing `servo_controller.py`, ensure:

- [ ] `SERVO_CALIBRATION` dict matches V2 values exactly (copy from `data-model.md`)
- [ ] Channel 5 max is **280** (not 380)
- [ ] Channel 8 range is **280-380** (inverted from channel 5's 200-280)
- [ ] Left arm channels 6-8 have **inverted** min/max from right arm channels 3-5
- [ ] Neutral positions use calculated midpoints (not arbitrary 200)
- [ ] Validation checks enforce min/max limits per channel
- [ ] Emergency stop resets all servos to their **neutral** positions (not arbitrary values)

---

## Safety Warnings

⚠️ **CRITICAL**: The following values **must not be exceeded** to prevent mechanical damage:

1. **Channel 0 (Main Legs - LDX-227)**: Do not set below 220 (upHeight) or above 350 (downHeight)
2. **Channels 1-2 (Leg Rotation - LDX-227)**: Do not exceed ±108 range (192-408). **Wider range than MG996R's ±80!**
3. **Channel 5 (Right Hand)**: Max is **280**, not 380 - exceeding causes hand mechanism binding
4. **All Servos**: Never send PWM values outside calibrated min/max ranges

⚠️ **Testing Protocol**:
1. Always test new servos at **neutral position first**
2. Slowly increase/decrease to min/max while monitoring for resistance
3. If servo makes noise or vibrates at a position, **immediately stop and reduce range**
4. Fine-tune calibration values in `servo_controller.py` if needed

---

## Verification Signature

- [x] V2 values confirmed from `config.ini` (MOVEMENT_VERSION = V2)
- [x] All 9 servo channels have correct min/max/neutral values
- [x] Inverted left arm values documented and verified
- [x] Channel 5 hand max=280 exception noted
- [x] Neutral positions calculated as midpoints
- [x] Planning documents (`data-model.md`, `contracts/servo-commands.md`) updated
- [x] Safety warnings documented

**Ready for implementation**: All configuration values are now V2-compliant and safe for ESP32 firmware development.
