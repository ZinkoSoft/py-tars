#!/bin/bash
#
# Connect to ESP32 REPL
#

DEVICE="/dev/ttyACM0"

echo "=========================================="
echo "Connecting to ESP32 REPL"
echo "=========================================="
echo ""
echo "Device: $DEVICE"
echo ""
echo "Commands:"
echo "  import main          - Start web server"
echo "  machine.reset()      - Restart ESP32"
echo "  Ctrl+X               - Exit REPL"
echo ""
echo "Connecting..."
echo "=========================================="
echo ""

mpremote connect "$DEVICE"
