#!/usr/bin/env bash
# Validation script: Run make check for all standardized apps
# Usage: ./scripts/validate-all-apps.sh

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🔍 Validating all apps in the repository..."
echo "Repository root: $REPO_ROOT"
echo

# List of all apps that should be standardized
APPS=(
    "wake-activation"
    "camera-service"
    "ui"
    "ui-web"
    "movement-service"
    "mcp-bridge"
    "mcp-server"
    "memory-worker"
    "tts-worker"
    "llm-worker"
    "stt-worker"
    "router"
)

PASSED=0
FAILED=0
SKIPPED=0

for APP in "${APPS[@]}"; do
    APP_PATH="$REPO_ROOT/apps/$APP"
    
    # Check if app directory exists
    if [ ! -d "$APP_PATH" ]; then
        echo "⚠️  $APP: Directory not found (SKIPPED)"
        ((SKIPPED++))
        continue
    fi
    
    # Check if Makefile exists
    if [ ! -f "$APP_PATH/Makefile" ]; then
        echo "⚠️  $APP: No Makefile found (SKIPPED)"
        ((SKIPPED++))
        continue
    fi
    
    echo "📦 Testing $APP..."
    
    # Run make check
    if (cd "$APP_PATH" && make check > /dev/null 2>&1); then
        echo "✅ $APP: PASSED"
        ((PASSED++))
    else
        echo "❌ $APP: FAILED"
        echo "   Run: cd apps/$APP && make check"
        ((FAILED++))
    fi
    
    echo
done

echo "================================================"
echo "Validation Summary:"
echo "  ✅ Passed:  $PASSED"
echo "  ❌ Failed:  $FAILED"
echo "  ⚠️  Skipped: $SKIPPED"
echo "================================================"

if [ $FAILED -gt 0 ]; then
    echo
    echo "❌ Validation FAILED. Please fix the failing apps."
    exit 1
fi

echo
echo "✅ All apps validated successfully!"
exit 0
