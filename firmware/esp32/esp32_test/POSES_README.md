# TARS Servo Controller - Movement Poses

## Overview
All movement sequences from the original Python `app-servotester.py` have been ported to MicroPython and integrated into the web interface.

## Available Poses

### Movement Controls
- **Reset** - Return to neutral position
- **Forward** - Step forward
- **Backward** - Step backward  
- **Turn Right** - Rotate right
- **Turn Left** - Rotate left

### Gestures
- **Greet / Wave** - Wave hello with right arm (3 waves)
- **Now!** - Pointing gesture with emphasis
- **Bow** - Take a respectful bow
- **Strike Pose** - Strike a dramatic pose

### Actions
- **Laugh** - Bouncing motion simulating laughter (5 bounces)
- **Swing Legs** - Dynamic leg swinging motion (3 swings)
- **Balance** - Balance on one leg with compensating motions
- **PEZZ Dispenser** - Dispenser pose (holds for 3 seconds)

### Special Moves
- **Mic Drop** - Dramatic mic drop gesture
- **Defensive** - Monster/defensive posture with claw motions

## Servo Mapping

### Legs (Channels 0-2)
- **Channel 0**: Main Legs (Height) - raises/lowers the robot
- **Channel 1**: Left Leg Rotation
- **Channel 2**: Right Leg Rotation

### Arms (Channels 3-8)
- **Channel 3**: Right Arm Main
- **Channel 4**: Right Arm Forearm
- **Channel 5**: Right Arm Hand
- **Channel 6**: Left Arm Main  
- **Channel 7**: Left Arm Forearm
- **Channel 8**: Left Arm Hand

## Technical Details

### Percentage System
All poses use a percentage system (1-100) for servo positioning:
- **1%** = Minimum position (servo's min pulse width)
- **50%** = Center/neutral position
- **100%** = Maximum position (servo's max pulse width)
- **0** = No movement (skip this servo)

### Speed Control
Each movement can specify a `speed_factor` (0.1-1.0):
- **0.1** = Very slow
- **0.5** = Medium speed
- **1.0** = Fast

### Web API Endpoints
```
POST /pose/reset       - Reset to neutral
POST /pose/forward     - Step forward
POST /pose/backward    - Step backward
POST /pose/turn_right  - Turn right
POST /pose/turn_left   - Turn left
POST /pose/greet       - Wave hello
POST /pose/laugh       - Laughing bounce
POST /pose/swing_legs  - Swing legs
POST /pose/pezz        - PEZZ dispenser
POST /pose/now         - "Now!" pointing
POST /pose/balance     - Balance on one leg
POST /pose/mic_drop    - Mic drop
POST /pose/defensive   - Defensive posture
POST /pose/pose        - Strike pose
POST /pose/bow         - Bow
```

## Files Modified

1. **servo_controller.py** - Added 15 new movement methods
2. **web_interface.py** - Added pose routes and HTML buttons  
3. **i2c_scanner.py** - Enhanced scanner for ESP32-S3 pin detection

## Hardware Requirements

- ESP32-S3 (YD-ESP32-S3 or similar)
- PCA9685 16-Channel PWM Servo Driver
- 9 Servos connected to channels 0-8
- I2C connection on GPIO 8 (SDA) and GPIO 9 (SCL)

## Usage

1. Connect to TARS-Servo WiFi network (or your configured WiFi)
2. Browse to http://192.168.4.1 (or your ESP32's IP)
3. Click any pose button to execute the movement
4. Use individual servo sliders for fine control

## Notes

- All poses automatically disable servos when complete to prevent overheating
- Some poses have built-in delays (e.g., PEZZ holds for 3 seconds, bow holds for 3 seconds)
- Poses execute sequentially and cannot be interrupted
- The web UI shows status messages during pose execution
