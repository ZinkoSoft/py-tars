#!/bin/bash
#
# Test all servos by moving them to min, neutral, and max positions
# Automated test sequence for verifying servo calibration
#

DEVICE="/dev/ttyACM0"

echo "=========================================="
echo "Servo Test Sequence - TARS Controller"
echo "=========================================="
echo ""
echo "This will test all 9 servos by moving them to:"
echo "  1. Neutral position"
echo "  2. Minimum position"
echo "  3. Maximum position"
echo "  4. Back to neutral"
echo ""
echo "Device: $DEVICE"
echo ""
read -p "Press Enter to start test sequence..."

# Run test sequence
mpremote connect "$DEVICE" exec "
import machine
import time
from pca9685 import PCA9685
from servo_config import SERVO_CALIBRATION

print('\\nInitializing I2C and PCA9685...')
i2c = machine.I2C(0, scl=machine.Pin(9), sda=machine.Pin(8), freq=100000)
pca = PCA9685(i2c, address=0x40)
pca.set_pwm_freq(50)

print('\\nStarting servo test sequence...')
print('=' * 50)

for channel in range(9):
    cal = SERVO_CALIBRATION[channel]
    label = cal['label']
    min_pulse = cal['min']
    max_pulse = cal['max']
    neutral = cal['neutral']
    
    print(f'\\nChannel {channel}: {label}')
    print(f'  Range: {min_pulse} - {max_pulse}, Neutral: {neutral}')
    
    # Move to neutral
    print(f'  → Moving to neutral ({neutral})...')
    pca.set_pwm(channel, 0, neutral)
    time.sleep(2)
    
    # Move to min
    print(f'  → Moving to min ({min_pulse})...')
    for pos in range(neutral, min_pulse, -5 if min_pulse < neutral else 5):
        pca.set_pwm(channel, 0, pos)
        time.sleep(0.02)
    pca.set_pwm(channel, 0, min_pulse)
    time.sleep(1)
    
    # Move to max
    print(f'  → Moving to max ({max_pulse})...')
    for pos in range(min_pulse, max_pulse, 5 if max_pulse > min_pulse else -5):
        pca.set_pwm(channel, 0, pos)
        time.sleep(0.02)
    pca.set_pwm(channel, 0, max_pulse)
    time.sleep(1)
    
    # Return to neutral
    print(f'  → Returning to neutral ({neutral})...')
    step = 5 if neutral > max_pulse else -5
    for pos in range(max_pulse, neutral, step):
        pca.set_pwm(channel, 0, pos)
        time.sleep(0.02)
    pca.set_pwm(channel, 0, neutral)
    time.sleep(1)
    
    print(f'  ✓ Channel {channel} test complete')

print('\\n' + '=' * 50)
print('All servos tested successfully!')
print('\\nDisabling all servos...')

# Disable all servos
for ch in range(9):
    pca.set_pwm(ch, 0, 0)

print('Test sequence complete.')
"

echo ""
echo "=========================================="
echo "Test Complete"
echo "=========================================="
