#!/bin/bash
# Test script for character/persona system

MQTT_HOST="${MQTT_HOST:-127.0.0.1}"
MQTT_PORT="${MQTT_PORT:-1883}"
MQTT_USER="${MQTT_USER:-tars}"
MQTT_PASS="${MQTT_PASS:-pass}"

echo "=== TARS Character System Test ==="
echo ""

# Subscribe to character current (retained message)
echo "1. Getting current character configuration (retained)..."
echo "   Topic: system/character/current"
mosquitto_sub \
  -h "$MQTT_HOST" \
  -p "$MQTT_PORT" \
  -u "$MQTT_USER" \
  -P "$MQTT_PASS" \
  -t "system/character/current" \
  -C 1 \
  -v | jq '.'

echo ""
echo "---"
echo ""

# Request entire character
echo "2. Requesting entire character snapshot..."
echo "   Topic: character/get"
echo "   Payload: {}"
mosquitto_pub \
  -h "$MQTT_HOST" \
  -p "$MQTT_PORT" \
  -u "$MQTT_USER" \
  -P "$MQTT_PASS" \
  -t "character/get" \
  -m '{}'

# Wait for response
sleep 0.5
mosquitto_sub \
  -h "$MQTT_HOST" \
  -p "$MQTT_PORT" \
  -u "$MQTT_USER" \
  -P "$MQTT_PASS" \
  -t "character/result" \
  -C 1 \
  -v | jq '.'

echo ""
echo "---"
echo ""

# Request traits section only
echo "3. Requesting traits section only..."
echo "   Topic: character/get"
echo "   Payload: {\"section\": \"traits\"}"
mosquitto_pub \
  -h "$MQTT_HOST" \
  -p "$MQTT_PORT" \
  -u "$MQTT_USER" \
  -P "$MQTT_PASS" \
  -t "character/get" \
  -m '{"section": "traits"}'

# Wait for response
sleep 0.5
mosquitto_sub \
  -h "$MQTT_HOST" \
  -p "$MQTT_PORT" \
  -u "$MQTT_USER" \
  -P "$MQTT_PASS" \
  -t "character/result" \
  -C 1 \
  -v | jq '.'

echo ""
echo "---"
echo ""

# Show personality traits extracted
echo "4. Extracting personality traits..."
mosquitto_sub \
  -h "$MQTT_HOST" \
  -p "$MQTT_PORT" \
  -u "$MQTT_USER" \
  -P "$MQTT_PASS" \
  -t "system/character/current" \
  -C 1 \
  -v | jq -r '.data.traits | to_entries[] | "\(.key) = \(.value)"'

echo ""
echo "=== Test Complete ==="
