#!/bin/bash
#
# Remove all files from ESP32
#

DEVICE="/dev/ttyACM0"

echo "=========================================="
echo "TARS ESP32 Clean"
echo "=========================================="
echo ""
echo "⚠️  WARNING: This will remove all files from ESP32!"
echo ""
read -p "Are you sure? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "Removing files..."
echo ""

FILES=(
    "pca9685.py"
    "servo_config.py"
    "servo_controller.py"
    "wifi_config.py"
    "web_interface.py"
    "boot.py"
    "main.py"
)

for FILE in "${FILES[@]}"; do
    echo -n "  Removing $FILE ... "
    if mpremote connect "$DEVICE" fs rm ":$FILE" 2>/dev/null; then
        echo "✓"
    else
        echo "✗ (not found or error)"
    fi
done

echo ""
echo "✓ Clean complete!"
echo "=========================================="
