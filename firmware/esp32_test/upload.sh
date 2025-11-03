#!/bin/bash
#
# Upload TARS Servo Controller files to ESP32 using mpremote
#

DEVICE="/dev/ttyACM0"

echo "=========================================="
echo "TARS Servo Controller - ESP32 Upload"
echo "=========================================="
echo ""
echo "Device: $DEVICE"
echo ""

# Check if mpremote is installed
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

echo "Performing soft reset to stop any running programs..."
mpremote connect "$DEVICE" soft-reset 2>/dev/null
sleep 1

echo "Uploading files..."
echo ""

# Array of files to upload
FILES=(
    "boot.py"
    "pca9685.py"
    "servo_config.py"
    "servo_controller.py"
    "wifi_config.py"
    "wifi_manager.py"
    "web_server.py"
    "movement_presets.py"
    "main.py"
)

# Upload each file
FAILED=0
for FILE in "${FILES[@]}"; do
    if [ -f "$FILE" ]; then
        echo -n "  [$FILE] ... "
        if mpremote connect "$DEVICE" fs cp "$FILE" : 2>/dev/null; then
            echo "✓ OK"
        else
            echo "✗ FAILED"
            FAILED=$((FAILED + 1))
        fi
    else
        echo "  [$FILE] ... ✗ NOT FOUND"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "=========================================="

if [ $FAILED -eq 0 ]; then
    echo "✓ All files uploaded successfully!"
    echo ""
    echo "Next steps:"
    echo "  1. Edit wifi_config.py with your WiFi credentials"
    echo "  2. Run: ./configure_wifi.sh"
    echo "  3. Restart ESP32 or run: mpremote connect $DEVICE exec 'import main'"
    echo ""
    echo "Or start now:"
    echo "  mpremote connect $DEVICE exec 'import main'"
else
    echo "✗ $FAILED file(s) failed to upload"
    echo ""
    echo "Troubleshooting:"
    echo "  - Check USB connection"
    echo "  - Try: mpremote connect $DEVICE"
    echo "  - Check device permissions: sudo chmod 666 $DEVICE"
    exit 1
fi

echo "=========================================="
