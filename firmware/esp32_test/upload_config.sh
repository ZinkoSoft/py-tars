#!/bin/bash
#
# Upload just the servo_config.ini file to ESP32
#

DEVICE="${1:-/dev/ttyACM0}"
CONFIG_FILE="${2:-servo_config.ini}"
VENV_PATH="../../.venv/bin/activate"

echo "=========================================="
echo "TARS - Upload Servo Configuration"
echo "=========================================="
echo ""
echo "Device: $DEVICE"
echo "Config: $CONFIG_FILE"
echo ""

# Activate venv if it exists
if [ -f "$VENV_PATH" ]; then
    source "$VENV_PATH"
fi

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

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file $CONFIG_FILE not found!"
    echo ""
    echo "To download current config from ESP32:"
    echo "  mpremote connect $DEVICE fs cp :servo_config.ini $CONFIG_FILE"
    exit 1
fi

echo "Performing soft reset..."
mpremote connect "$DEVICE" soft-reset 2>/dev/null
sleep 1

echo "Uploading $CONFIG_FILE..."
if mpremote connect "$DEVICE" fs cp "$CONFIG_FILE" : 2>/dev/null; then
    echo "✓ Upload successful!"
    echo ""
    echo "To apply changes:"
    echo ""
    echo "Option 1: Reload via HTTP (no reboot needed)"
    echo "  curl -X POST http://<ESP32_IP>/config/reload"
    echo ""
    echo "Option 2: Reload via REPL"
    echo "  mpremote connect $DEVICE exec 'from servo_config import reload_config; reload_config()'"
    echo ""
    echo "Option 3: Reboot ESP32"
    echo "  mpremote connect $DEVICE exec 'import machine; machine.reset()'"
    echo ""
else
    echo "✗ Upload failed!"
    echo ""
    echo "Troubleshooting:"
    echo "  - Check USB connection"
    echo "  - Try: mpremote connect $DEVICE"
    echo "  - Check device permissions: sudo chmod 666 $DEVICE"
    exit 1
fi

echo "=========================================="
