#!/bin/bash
# Test script for camera streaming integration

echo "Testing TARS Camera Streaming Integration"
echo "=========================================="

# Check if services are running
echo "1. Checking if camera service is running..."
if docker ps | grep -q tars-camera; then
    echo "✓ Camera service is running"
else
    echo "✗ Camera service is not running"
    echo "Start with: docker compose -f ops/compose.yml up camera -d"
    exit 1
fi

# Check if ui-web is running
echo "2. Checking if ui-web service is running..."
if docker ps | grep -q tars-ui-web; then
    echo "✓ UI-Web service is running"
else
    echo "✗ UI-Web service is not running"
    echo "Start with: docker compose -f ops/compose.yml up ui-web -d"
    exit 1
fi

# Check MQTT connectivity
echo "3. Checking MQTT connectivity..."
if docker ps | grep -q tars-mqtt; then
    echo "✓ MQTT broker is running"
else
    echo "✗ MQTT broker is not running"
    echo "Start with: docker compose -f ops/compose.yml up mqtt -d"
    exit 1
fi

echo "4. Testing camera HTTP streaming..."
if curl -s --max-time 5 http://localhost:8080/snapshot > /dev/null; then
    echo "✓ Camera HTTP endpoint responding"
else
    echo "✗ Camera HTTP endpoint not responding"
    echo "Check: curl http://localhost:8080/stream"
    exit 1
fi

# Test MQTT monitoring frames
echo "5. Testing camera MQTT monitoring frames..."
if timeout 5 mosquitto_sub -h 127.0.0.1 -p 1883 -u tars -P change_me -t 'camera/frame' -C 1 > /dev/null 2>&1; then
    echo "✓ Camera MQTT monitoring frames received"
else
    echo "⚠ Camera MQTT monitoring frames not received (may be normal if rate is low)"
fi

echo ""
echo "Manual Testing Steps:"
echo "1. Open browser to http://localhost:5010"
echo "2. Click the 'Camera' button in the toolbar"
echo "3. Camera drawer should open and display MJPEG stream from http://localhost:8080/stream"
echo "4. Check browser developer tools for any errors"
echo "5. Monitor MQTT traffic in the 'MQTT Stream' drawer (should see occasional camera/frame messages)"
echo "6. Test direct stream access: curl http://localhost:8080/stream | head -c 1000"

echo ""
echo "Performance Validation:"
echo "- MJPEG stream should be smooth at target CAMERA_FPS (${CAMERA_FPS:-10} fps)"
echo "- MQTT traffic should be low (only occasional monitoring frames every ${CAMERA_MQTT_RATE:-2} seconds)"
echo "- HTTP streaming should use ~200-500KB/sec depending on resolution/quality"
echo "- UI should remain responsive while streaming"

echo ""
echo "Troubleshooting:"
echo "- Check camera service logs: docker logs tars-camera"
echo "- Check ui-web logs: docker logs tars-ui-web"
echo "- Verify camera device access: ls /dev/video*"
echo "- Test HTTP endpoints: curl http://localhost:8080/snapshot"
echo "- Test MQTT monitoring: mosquitto_sub -h 127.0.0.1 -p 1883 -u tars -P change_me -t 'camera/frame' -C 1"
echo "- Check camera service health: mosquitto_sub -h 127.0.0.1 -p 1883 -u tars -P change_me -t 'system/health/camera' -v"