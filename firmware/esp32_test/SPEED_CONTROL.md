# Global Speed Control

The TARS servo controller now supports global speed multipliers from **0.1x to 3.0x**, allowing you to speed up or slow down all movements proportionally.

## Quick Access: 1.5x Speed Boost

### Via Web Interface
1. Open the web interface at `http://<ESP32_IP>`
2. In the "Global Speed Control" section, click the **1.5x** button
3. All subsequent movements will be 50% faster

### Via HTTP API
```bash
curl -X POST http://<ESP32_IP>/control \
  -H "Content-Type: application/json" \
  -d '{"type":"speed","speed":1.5}'
```

### Via Python (from MicroPython REPL or script)
```python
servo_controller.global_speed = 1.5
```

## Speed Reference

| Speed | Effect | Use Case |
|-------|--------|----------|
| 0.1x | Very slow | Precise calibration, debugging |
| 0.5x | Slow | Smooth, gentle movements |
| **1.0x** | **Normal** | Default speed, balanced |
| **1.5x** | **Fast** | Quicker responses, energetic |
| 2.0x | Very fast | Rapid movements |
| 3.0x | Maximum | Fastest possible (may reduce smoothness) |

## Technical Details

### How It Works
The global speed multiplier affects the delay between PWM steps:
- `speed ≤ 1.0`: `delay = 0.02s × (1.1 - speed)`
- `speed > 1.0`: `delay = 0.02s / speed`

### Examples
- **1.0x**: 0.02s per step = 50 steps/second
- **1.5x**: 0.013s per step = 75 steps/second (50% faster)
- **2.0x**: 0.01s per step = 100 steps/second (2x faster)
- **3.0x**: 0.007s per step = 143 steps/second (3x faster)

### Per-Movement Speed Override
Individual movements can still specify their own speed, which is then multiplied by the global speed:
```python
# Move with speed 0.8, but global_speed=1.5 makes it effectively 1.2x
await servo_controller.move_servo_smooth(channel=0, target=300, speed=0.8)
# Effective speed = 0.8 × 1.5 = 1.2
```

## Web Interface Features

The web UI now includes:
- **Slider**: Fine control from 0.1x to 3.0x
- **Quick buttons**: One-click preset speeds (1.0x, 1.5x, 2.0x, 3.0x)
- **Real-time display**: Shows current speed multiplier

## Safety Notes

⚠️ **High speeds (>2.0x) may:**
- Reduce movement smoothness
- Increase mechanical stress
- Cause servo jitter if I2C communication can't keep up

✅ **Recommended range: 0.5x - 1.5x** for optimal balance of speed and smoothness.

## Persistence

Speed settings are **not** saved across reboots. To make 1.5x the default:

```python
# In main.py, after initializing servo_controller:
servo_controller.global_speed = 1.5
```
