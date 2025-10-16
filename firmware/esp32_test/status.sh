#!/bin/bash
#
# Fetch and display system status from TARS Servo Controller
# Shows WiFi, hardware, memory, and servo information
#

DEVICE="/dev/ttyACM0"

echo "=========================================="
echo "System Status - TARS Servo Controller"
echo "=========================================="
echo ""

# Check if device exists
if [ ! -e "$DEVICE" ]; then
    echo "ERROR: Device $DEVICE not found!"
    exit 1
fi

# Get WiFi status
echo "WiFi Status:"
echo "----------------------------------------"
mpremote connect "$DEVICE" exec "
import network
wlan = network.WLAN(network.STA_IF)
if wlan.isconnected():
    config = wlan.ifconfig()
    print(f'  Status: Connected')
    print(f'  IP Address: {config[0]}')
    print(f'  Network: {wlan.config(\"essid\")}')
    print(f'  Signal: {wlan.status(\"rssi\")} dBm')
    print(f'')
    print(f'  Web Interface: http://{config[0]}/')
else:
    print('  Status: Disconnected')
"
echo ""

# Get hardware status
echo "Hardware Status:"
echo "----------------------------------------"
mpremote connect "$DEVICE" exec "
import machine
try:
    i2c = machine.I2C(0, scl=machine.Pin(9), sda=machine.Pin(8), freq=100000)
    devices = i2c.scan()
    if 0x40 in devices:
        print('  PCA9685: Detected at 0x40')
        print('  PWM Frequency: 50Hz (servos)')
    else:
        print('  PCA9685: NOT FOUND')
    print(f'  CPU Frequency: {machine.freq() // 1000000} MHz')
except Exception as e:
    print(f'  Error: {e}')
"
echo ""

# Get memory status
echo "Memory Status:"
echo "----------------------------------------"
mpremote connect "$DEVICE" exec "
import gc
gc.collect()
free = gc.mem_free()
alloc = gc.mem_alloc()
total = free + alloc
used_pct = (alloc / total) * 100
print(f'  Free: {free // 1024} KB')
print(f'  Used: {alloc // 1024} KB ({used_pct:.1f}%)')
print(f'  Total: {total // 1024} KB')
"
echo ""

# Get servo controller status (if running)
echo "Servo Controller Status:"
echo "----------------------------------------"
mpremote connect "$DEVICE" exec "
try:
    # Try to import and check if controller exists
    import sys
    if 'servo_controller' in sys.modules:
        # Controller module is loaded
        print('  Status: Running')
    else:
        print('  Status: Not started')
        print('  Run: mpremote connect $DEVICE exec \"import main\"')
except:
    print('  Status: Unknown')
" 2>/dev/null || echo "  Status: Not started"

echo ""
echo "=========================================="
echo ""
echo "To start the servo controller:"
echo "  mpremote connect $DEVICE exec 'import main'"
echo ""
echo "To view live console:"
echo "  ./start_server.sh"
echo ""
echo "=========================================="
