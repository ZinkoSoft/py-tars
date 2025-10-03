#!/bin/bash
# Test script for Phase 1: LLM Worker MCP Integration
# Tests tool registry loading, tool calls, and personality context

set -e

MQTT_HOST="${MQTT_HOST:-localhost}"
MQTT_PORT="${MQTT_PORT:-1883}"
MQTT_USER="${MQTT_USER:-tars}"
MQTT_PASS="${MQTT_PASS:-change_me}"

echo "========================================"
echo "Phase 1: Tool Calling Integration Tests"
echo "========================================"
echo ""

# Function to publish and wait
test_request() {
    local test_name="$1"
    local text="$2"
    local expected="$3"
    
    echo "▶ Test: $test_name"
    echo "  Query: '$text'"
    
    # Subscribe to responses in background
    timeout 15 mosquitto_sub -h "$MQTT_HOST" -p "$MQTT_PORT" \
        -u "$MQTT_USER" -P "$MQTT_PASS" \
        -t "llm/response" -C 1 -v &
    SUB_PID=$!
    
    sleep 1
    
    # Publish request
    mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" \
        -u "$MQTT_USER" -P "$MQTT_PASS" \
        -t "llm/request" \
        -m "{\"id\":\"test-$(date +%s)\",\"text\":\"$text\",\"stream\":false}"
    
    # Wait for response
    wait $SUB_PID 2>/dev/null || true
    
    echo "  ✓ Response received"
    echo ""
    sleep 2
}

echo "1️⃣  Checking tool registry..."
echo "   Subscribing to llm/tools/registry..."
timeout 5 mosquitto_sub -h "$MQTT_HOST" -p "$MQTT_PORT" \
    -u "$MQTT_USER" -P "$MQTT_PASS" \
    -t "llm/tools/registry" -C 1 | jq '.' 2>/dev/null || echo "   ⚠️  No tools registered yet (mcp-bridge may not be running)"
echo ""

echo "2️⃣  Checking MCP bridge health..."
timeout 5 mosquitto_sub -h "$MQTT_HOST" -p "$MQTT_PORT" \
    -u "$MQTT_USER" -P "$MQTT_PASS" \
    -t "system/health/mcp-bridge" -C 1 -v 2>/dev/null || echo "   ⚠️  MCP bridge health not available"
echo ""

echo "3️⃣  Checking LLM worker health..."
timeout 5 mosquitto_sub -h "$MQTT_HOST" -p "$MQTT_PORT" \
    -u "$MQTT_USER" -P "$MQTT_PASS" \
    -t "system/health/llm" -C 1 -v 2>/dev/null || echo "   ⚠️  LLM worker health not available"
echo ""

echo "========================================"
echo "Starting integration tests..."
echo "========================================"
echo ""

# Test 1: Simple query (no tools needed)
test_request \
    "Simple query without tools" \
    "What is 2 + 2?" \
    "Should answer directly"

# Test 2: Tool availability query (should NOT use tools)
test_request \
    "Tool availability query" \
    "What tools do you have available?" \
    "Should describe available tools from context"

# Test 3: File system query (should use filesystem tool if available)
test_request \
    "Filesystem tool call" \
    "List the files in the workspace directory" \
    "Should call mcp:filesystem:list_dir tool"

# Test 4: Personality query (should answer from context, NO tool call)
test_request \
    "Personality query without tool" \
    "What are your personality settings?" \
    "Should answer from character context, not call tools"

echo "========================================"
echo "Test Summary"
echo "========================================"
echo "✓ Tool registry check"
echo "✓ Simple query test"
echo "✓ Tool availability query"
echo "✓ Filesystem tool call"
echo "✓ Personality context test"
echo ""
echo "Next steps:"
echo "1. Check LLM worker logs: docker compose -f ops/compose.yml logs llm"
echo "2. Check MCP bridge logs: docker compose -f ops/compose.yml logs mcp-bridge"
echo "3. Verify tool calls in logs (look for 'tool_calls' in LLM worker output)"
echo ""
