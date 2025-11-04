#!/bin/bash
# Setup X11 access for Docker containers
# This script should be run before starting docker compose

set -e

DISPLAY="${DISPLAY:-:0}"

echo "Setting up X11 access for Docker containers..."

# Disable X11 access control completely (simplest solution for local development)
# This allows any process on the local machine to connect to the X server
DISPLAY="$DISPLAY" xhost + 2>/dev/null || {
    echo "⚠ Warning: Could not run 'xhost +'. Make sure DISPLAY is set and X is running."
    exit 1
}

echo "✓ X11 access control disabled for display: $DISPLAY"
echo "✓ Docker containers can now access the display"
echo ""
echo "Note: This disables X11 access control for security. For production, use:"
echo "  - xhost +local:docker (Docker only)"
echo "  - Proper Xauthority file sharing"
echo ""
echo "You can now start docker compose:"
echo "  cd ops && docker compose -f compose.non-stt-wake.yml up"
