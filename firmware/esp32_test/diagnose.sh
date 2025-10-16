#!/bin/bash
#
# Run comprehensive diagnostics on ESP32 for TARS Servo Controller
# Checks I2C, PCA9685, WiFi connection, and memory status
#

DEVICE="/dev/ttyACM0"

echo "=========================================="
echo "System Diagnostics - TARS Servo Controller"
echo "=========================================="
echo ""

# Check if mpremote is available
if ! command -v mpremote &> /dev/null; then
    echo "ERROR: mpremote not found!"
    echo "Install with: pip install mpremote"
    exit 1
fi

# Check if device exists
if [ ! -e "$DEVICE" ]; then
    echo "ERROR: Device $DEVICE not found!"
    echo "Available devices:"
    ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || echo "  No devices found"
    exit 1
fi

echo "Device: $DEVICE"
echo ""

# Step 1: I2C Scan
echo "Step 1: I2C Bus Scan"
echo "----------------------------------------"
if mpremote connect "$DEVICE" fs cp i2c_scanner.py : 2>/dev/null; then
    mpremote connect "$DEVICE" exec "import i2c_scanner"
    echo ""
else
    echo "✗ Failed to upload scanner"
fi

# Step 2: Check PCA9685
echo "Step 2: PCA9685 Detection"
echo "----------------------------------------"
mpremote connect "$DEVICE" exec "
import machine
try:
    i2c = machine.I2C(0, scl=machine.Pin(9), sda=machine.Pin(8), freq=100000)
    devices = i2c.scan()
    if 0x40 in devices:
        print('✓ PCA9685 detected at address 0x40')
    else:
        print('✗ PCA9685 NOT found at 0x40')
        print(f'  Devices found: {[hex(d) for d in devices]}')
except Exception as e:
    print(f'✗ I2C Error: {e}')
"
echo ""

# Step 3: WiFi Status
echo "Step 3: WiFi Connection Status"
echo "----------------------------------------"
mpremote connect "$DEVICE" exec "
import network
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
if wlan.isconnected():
    config = wlan.ifconfig()
    print(f'✓ WiFi Connected')
    print(f'  IP: {config[0]}')
    print(f'  SSID: {wlan.config(\"essid\")}')
    print(f'  RSSI: {wlan.status(\"rssi\")} dBm')
else:
    print('✗ WiFi Not Connected')
    print('  Run: ./configure_wifi.sh')
"
echo ""

# Step 4: Memory Status
echo "Step 4: Memory Status"
echo "----------------------------------------"
mpremote connect "$DEVICE" exec "
import gc
gc.collect()
free = gc.mem_free()
alloc = gc.mem_alloc()
total = free + alloc
print(f'Free Memory: {free} bytes ({free//1024} KB)')
print(f'Allocated: {alloc} bytes ({alloc//1024} KB)')
print(f'Total: {total} bytes ({total//1024} KB)')
if free < 150000:
    print('⚠ Warning: Low memory!')
else:
    print('✓ Memory OK')
"
echo ""

echo "=========================================="
echo "Diagnostics Complete"
echo "=========================================="
