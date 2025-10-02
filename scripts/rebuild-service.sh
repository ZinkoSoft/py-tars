#!/usr/bin/env bash
# scripts/rebuild-service.sh
# Quick rebuild and restart a service with BuildKit optimizations
#
# Usage:
#   ./scripts/rebuild-service.sh ui
#   ./scripts/rebuild-service.sh llm
#   ./scripts/rebuild-service.sh stt

set -e

SERVICE="${1:-}"

if [[ -z "$SERVICE" ]]; then
    echo "Usage: $0 <service-name>"
    echo "Example: $0 ui"
    exit 1
fi

cd "$(dirname "$0")/../ops" || exit 1

echo "🔨 Building $SERVICE with BuildKit..."
DOCKER_BUILDKIT=1 docker compose build "$SERVICE"

echo "🔄 Restarting $SERVICE..."
docker compose restart "$SERVICE"

echo "✅ $SERVICE rebuilt and restarted!"
echo ""
echo "📋 View logs with: docker compose logs -f $SERVICE"
