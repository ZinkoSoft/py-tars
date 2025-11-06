#!/bin/bash
# Convenience script to start TARS with X11 UI support
# Usage: ./start-ui.sh [compose-file]

set -e

COMPOSE_FILE="${1:-ops/compose.non-stt-wake.yml}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "========================================"
echo "Starting TARS Stack with UI"
echo "========================================"
echo ""

# Step 1: Setup X11 access
echo "Step 1: Setting up X11 access..."
bash ops/setup-x11-docker.sh
echo ""

# Step 2: Export XAUTHORITY for docker compose
export XAUTHORITY=/tmp/.docker-xauth/Xauthority
echo "Step 2: Starting Docker Compose..."
echo "  Compose file: $COMPOSE_FILE"
echo "  XAUTHORITY: $XAUTHORITY"
echo ""

# Step 3: Start docker compose
docker compose -f "$COMPOSE_FILE" up "$@"
