#!/bin/bash
# Setup X11 access for Docker containers
# This script should be run before starting docker compose

set -e

DISPLAY="${DISPLAY:-:0}"

echo "Setting up X11 access for Docker containers..."

# Step 1: Allow local Docker connections
echo "Step 1: Allowing X11 access from localhost..."
DISPLAY="$DISPLAY" xhost +local:docker 2>/dev/null || {
    echo "⚠ Warning: 'xhost +local:docker' failed, trying 'xhost +'..."
    DISPLAY="$DISPLAY" xhost + 2>/dev/null || {
        echo "⚠ Warning: Could not run 'xhost'. Make sure DISPLAY is set and X is running."
        exit 1
    }
}

# Step 2: Generate a new Xauthority file that's world-readable (for Docker)
echo "Step 2: Creating Docker-accessible Xauthority file..."
XAUTH_DIR="/tmp/.docker-xauth"
mkdir -p "$XAUTH_DIR"
XAUTH="$XAUTH_DIR/Xauthority"

# Remove old auth file if it exists
rm -f "$XAUTH"

# Generate new auth cookie
xauth nlist "$DISPLAY" | sed -e 's/^..../ffff/' | xauth -f "$XAUTH" nmerge -

# Make it readable by all (Docker containers)
chmod 644 "$XAUTH"

echo "✓ X11 access control configured for display: $DISPLAY"
echo "✓ Docker Xauthority file created at: $XAUTH"
echo "✓ Docker containers can now access the display"
echo ""
echo "Environment variables set:"
echo "  DISPLAY=$DISPLAY"
echo "  XAUTHORITY=$XAUTH"
echo ""
echo "You can now start docker compose:"
echo "  XAUTHORITY=$XAUTH docker compose -f ops/compose.non-stt-wake.yml up"
