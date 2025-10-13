#!/bin/bash
#
# Run I2C scanner on ESP32 to diagnose connection issues
#

DEVICE="/dev/ttyACM0"

echo "=========================================="
echo "I2C Diagnostics - TARS Servo Controller"
echo "=========================================="
echo ""
echo "This will scan for I2C devices on your ESP32"
echo ""
echo "Uploading scanner..."

# Upload the scanner script
if mpremote connect "$DEVICE" fs cp i2c_scanner.py : 2>/dev/null; then
    echo "✓ Scanner uploaded"
    echo ""
    echo "Running scan..."
    echo "=========================================="
    mpremote connect "$DEVICE" exec "import i2c_scanner"
    echo "=========================================="
else
    echo "✗ Failed to upload scanner"
    echo "Make sure ESP32 is connected to $DEVICE"
fi
