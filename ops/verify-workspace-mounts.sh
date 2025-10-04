#!/bin/bash
# Verify Docker workspace mount fix for all services
# Run from ops/ directory: ./verify-workspace-mounts.sh

set -e

echo "==================================="
echo "Docker Workspace Mount Verification"
echo "==================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if containers are running
echo "Checking running containers..."
if ! docker ps | grep -q "tars-"; then
    echo -e "${RED}✗ No TARS containers running. Start them first: docker compose up -d${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Containers are running${NC}"
echo ""

# Test each service
test_service() {
    local container=$1
    local module=$2
    local expected_path=$3
    
    echo -n "Testing $container..."
    
    if ! docker ps | grep -q "$container"; then
        echo -e " ${YELLOW}⚠ Not running${NC}"
        return
    fi
    
    actual_path=$(docker exec "$container" python -c "import $module; print($module.__file__)" 2>/dev/null)
    
    if [[ "$actual_path" == *"$expected_path"* ]]; then
        echo -e " ${GREEN}✓ Using workspace${NC}"
        echo "  Path: $actual_path"
    elif [[ "$actual_path" == *"site-packages"* ]]; then
        echo -e " ${RED}✗ Using site-packages (OLD CODE!)${NC}"
        echo "  Path: $actual_path"
    else
        echo -e " ${YELLOW}⚠ Unknown path${NC}"
        echo "  Path: $actual_path"
    fi
}

# Test Python services
echo "Verifying import paths..."
echo "-----------------------------------"
test_service "tars-mcp-bridge" "mcp_bridge" "/workspace/apps/mcp-bridge"
test_service "tars-llm" "llm_worker" "/workspace/apps/llm-worker"
test_service "tars-tts" "tts_worker" "/workspace/apps/tts-worker"
test_service "tars-stt" "stt_worker" "/workspace/apps/stt-worker"
test_service "tars-wake-activation" "wake_activation" "/workspace/apps/wake-activation"
test_service "tars-router" "main" "/workspace/apps/router"

echo ""
echo "-----------------------------------"
echo "Checking for installed packages..."
echo "-----------------------------------"

check_no_package() {
    local container=$1
    local package_pattern=$2
    
    echo -n "Checking $container for $package_pattern..."
    
    if ! docker ps | grep -q "$container"; then
        echo -e " ${YELLOW}⚠ Not running${NC}"
        return
    fi
    
    if docker exec "$container" pip list 2>/dev/null | grep -qi "$package_pattern"; then
        echo -e " ${RED}✗ Package still installed!${NC}"
        docker exec "$container" pip list 2>/dev/null | grep -i "$package_pattern"
    else
        echo -e " ${GREEN}✓ No package installed${NC}"
    fi
}

check_no_package "tars-mcp-bridge" "tars-mcp-bridge"
check_no_package "tars-llm" "tars-llm-worker"
check_no_package "tars-tts" "tars-tts-worker"
check_no_package "tars-stt" "tars-stt-worker"
check_no_package "tars-wake-activation" "wake-activation"

echo ""
echo "-----------------------------------"
echo "Summary"
echo "-----------------------------------"
echo ""
echo "If all services show '✓ Using workspace', the fix is working!"
echo "If any show '✗ Using site-packages', rebuild that service:"
echo "  docker compose build SERVICE_NAME"
echo "  docker compose up -d SERVICE_NAME"
echo ""
echo "If packages are still installed, uninstall them:"
echo "  docker exec CONTAINER pip uninstall -y PACKAGE_NAME"
echo "  docker compose restart SERVICE_NAME"
echo ""
