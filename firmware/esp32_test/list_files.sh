#!/bin/bash
#
# List files on ESP32
#

DEVICE="/dev/ttyACM0"

echo "=========================================="
echo "ESP32 File System"
echo "=========================================="
echo ""

mpremote connect "$DEVICE" fs ls

echo ""
echo "=========================================="
