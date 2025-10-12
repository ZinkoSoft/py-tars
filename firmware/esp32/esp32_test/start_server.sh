#!/bin/bash
#
# Start the TARS web server on ESP32
#

DEVICE="/dev/ttyACM0"

echo "=========================================="
echo "Starting TARS Web Server"
echo "=========================================="
echo ""
echo "Device: $DEVICE"
echo ""
echo "Connecting to ESP32 and starting web server..."
echo "Watch for IP address below:"
echo ""
echo "------------------------------------------"

mpremote connect "$DEVICE" exec "import main"

echo "------------------------------------------"
echo ""
echo "To reconnect to REPL:"
echo "  mpremote connect $DEVICE"
echo ""
echo "To restart:"
echo "  mpremote connect $DEVICE exec 'import machine; machine.reset()'"
echo "=========================================="
