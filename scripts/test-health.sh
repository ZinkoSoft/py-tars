#!/bin/bash
# Test script to check health messages on MQTT broker

MQTT_HOST=${MQTT_HOST:-127.0.0.1}
MQTT_PORT=${MQTT_PORT:-1883}
MQTT_USER=${MQTT_USER:-tars}
MQTT_PASS=${MQTT_PASS:-pass}

echo "=================================================="
echo "Health Message Checker"
echo "=================================================="
echo "Checking retained health messages on broker..."
echo ""

# Subscribe to all health topics and show what's retained
timeout 3 mosquitto_sub \
    -h "$MQTT_HOST" \
    -p "$MQTT_PORT" \
    -u "$MQTT_USER" \
    -P "$MQTT_PASS" \
    -t 'system/health/#' \
    -v \
    -F '%t: %p' \
    2>/dev/null || echo "No retained messages found or connection failed"

echo ""
echo "=================================================="
echo "Live monitoring (press Ctrl+C to stop)..."
echo "=================================================="

# Subscribe and monitor live
mosquitto_sub \
    -h "$MQTT_HOST" \
    -p "$MQTT_PORT" \
    -u "$MQTT_USER" \
    -P "$MQTT_PASS" \
    -t 'system/health/#' \
    -v \
    -F '[%I:%M:%S] %t: %p'
