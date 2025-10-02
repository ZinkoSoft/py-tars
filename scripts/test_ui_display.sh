#!/bin/bash
# Test script for UI text display functionality
# Usage: ./test_ui_display.sh

MQTT_HOST="${MQTT_HOST:-localhost}"
MQTT_PORT="${MQTT_PORT:-1883}"
MQTT_USER="${MQTT_USER:-tars}"
MQTT_PASS="${MQTT_PASS:-pass}"

echo "=== TARS UI Text Display Test ==="
echo "Testing STT → LLM → TTS flow with fade animations"
echo ""

# Helper function
pub() {
    mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" \
        -u "$MQTT_USER" -P "$MQTT_PASS" \
        -t "$1" -m "$2"
}

echo "1. Sending STT final (should appear top right)..."
pub "stt/final" '{"text":"what is the weather today","is_final":true,"confidence":0.95}'
sleep 1

echo "2. Sending LLM response (should appear left side below STT)..."
pub "llm/response" '{"id":"test1","reply":"The weather today is sunny with a high of 72 degrees Fahrenheit and clear skies. Perfect day for a walk!","provider":"openai","model":"gpt-4"}'
sleep 1

echo "3. Sending TTS start (both texts should stay visible)..."
pub "tts/status" '{"event":"speaking_start","text":"The weather today is sunny with a high of 72 degrees...","timestamp":1727890123.456}'
sleep 3

echo "4. Sending TTS end (LLM text should start fading)..."
pub "tts/status" '{"event":"speaking_end","timestamp":1727890126.789}'
echo ""
echo "✓ Test sequence complete!"
echo ""
echo "Expected behavior:"
echo "  - STT text 'You: what is...' appeared top right"
echo "  - STT text faded out after 3 seconds"
echo "  - LLM text 'The weather...' appeared left side"
echo "  - LLM text stayed visible during TTS"
echo "  - LLM text fades out 4 seconds after TTS ends"
echo ""
echo "=== Quick Test Commands ==="
echo ""
echo "# Test STT only:"
echo "mosquitto_pub -h $MQTT_HOST -p $MQTT_PORT -u $MQTT_USER -P $MQTT_PASS -t 'stt/final' -m '{\"text\":\"hello world\"}'"
echo ""
echo "# Test LLM only:"
echo "mosquitto_pub -h $MQTT_HOST -p $MQTT_PORT -u $MQTT_USER -P $MQTT_PASS -t 'llm/response' -m '{\"id\":\"test\",\"reply\":\"Hello! How can I help you?\"}'"
echo ""
echo "# Test TTS start:"
echo "mosquitto_pub -h $MQTT_HOST -p $MQTT_PORT -u $MQTT_USER -P $MQTT_PASS -t 'tts/status' -m '{\"event\":\"speaking_start\",\"text\":\"test\"}'"
echo ""
echo "# Test TTS end:"
echo "mosquitto_pub -h $MQTT_HOST -p $MQTT_PORT -u $MQTT_USER -P $MQTT_PASS -t 'tts/status' -m '{\"event\":\"speaking_end\"}'"
