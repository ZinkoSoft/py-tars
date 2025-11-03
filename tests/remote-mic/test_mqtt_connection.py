"""
Test suite for remote MQTT connectivity.

Validates that remote services can connect to main TARS MQTT broker
and publish/subscribe to appropriate topics.

Note: These tests require a running MQTT broker. Set MQTT_TEST_HOST
environment variable to run integration tests, otherwise tests are skipped.
"""

import os
import pytest
import socket
import time
from pathlib import Path

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False


# Skip all tests if paho-mqtt not installed
pytestmark = pytest.mark.skipif(
    not MQTT_AVAILABLE,
    reason="paho-mqtt not installed"
)


@pytest.fixture
def mqtt_host():
    """MQTT broker host from environment or skip test."""
    host = os.getenv("MQTT_TEST_HOST")
    if not host:
        pytest.skip("MQTT_TEST_HOST not set - skipping integration tests")
    return host


@pytest.fixture
def mqtt_port():
    """MQTT broker port from environment or default."""
    return int(os.getenv("MQTT_TEST_PORT", "1883"))


def test_mqtt_broker_reachable(mqtt_host, mqtt_port):
    """Verify MQTT broker is reachable via TCP."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    
    try:
        result = sock.connect_ex((mqtt_host, mqtt_port))
        assert result == 0, f"Cannot connect to MQTT broker at {mqtt_host}:{mqtt_port}"
    finally:
        sock.close()


def test_mqtt_connection_basic(mqtt_host, mqtt_port):
    """Test basic MQTT connection with anonymous auth."""
    client = mqtt.Client()
    connected = False
    
    def on_connect(client, userdata, flags, rc):
        nonlocal connected
        connected = True
    
    client.on_connect = on_connect
    
    try:
        client.connect(mqtt_host, mqtt_port, 10)
        client.loop_start()
        
        # Wait for connection (up to 5 seconds)
        for _ in range(50):
            if connected:
                break
            time.sleep(0.1)
        
        assert connected, f"Failed to connect to MQTT broker at {mqtt_host}:{mqtt_port}"
    finally:
        client.loop_stop()
        client.disconnect()


def test_mqtt_publish_wake_event(mqtt_host, mqtt_port):
    """Test publishing to wake/event topic."""
    client = mqtt.Client()
    published = False
    
    def on_publish(client, userdata, mid):
        nonlocal published
        published = True
    
    client.on_publish = on_publish
    
    try:
        client.connect(mqtt_host, mqtt_port, 10)
        client.loop_start()
        
        # Wait for connection
        time.sleep(1)
        
        # Publish test message
        test_message = '{"message_id": "test-123", "detected": true, "score": 0.85, "wake_word": "hey_tars", "timestamp": 1234567890.0}'
        result = client.publish("wake/event", test_message, qos=1)
        
        # Wait for publish confirmation (up to 2 seconds)
        for _ in range(20):
            if published:
                break
            time.sleep(0.1)
        
        assert published, "Failed to publish to wake/event topic"
    finally:
        client.loop_stop()
        client.disconnect()


def test_mqtt_publish_stt_final(mqtt_host, mqtt_port):
    """Test publishing to stt/final topic."""
    client = mqtt.Client()
    published = False
    
    def on_publish(client, userdata, mid):
        nonlocal published
        published = True
    
    client.on_publish = on_publish
    
    try:
        client.connect(mqtt_host, mqtt_port, 10)
        client.loop_start()
        
        # Wait for connection
        time.sleep(1)
        
        # Publish test message
        test_message = '{"message_id": "test-456", "text": "test transcription", "lang": "en", "confidence": 0.95, "ts": 1234567890.0, "is_final": true}'
        result = client.publish("stt/final", test_message, qos=1)
        
        # Wait for publish confirmation (up to 2 seconds)
        for _ in range(20):
            if published:
                break
            time.sleep(0.1)
        
        assert published, "Failed to publish to stt/final topic"
    finally:
        client.loop_stop()
        client.disconnect()


def test_mqtt_subscribe_wake_mic(mqtt_host, mqtt_port):
    """Test subscribing to wake/mic topic."""
    client = mqtt.Client()
    subscribed = False
    
    def on_subscribe(client, userdata, mid, granted_qos):
        nonlocal subscribed
        subscribed = True
    
    client.on_subscribe = on_subscribe
    
    try:
        client.connect(mqtt_host, mqtt_port, 10)
        client.loop_start()
        
        # Wait for connection
        time.sleep(1)
        
        # Subscribe to topic
        result = client.subscribe("wake/mic", qos=1)
        
        # Wait for subscription confirmation (up to 2 seconds)
        for _ in range(20):
            if subscribed:
                break
            time.sleep(0.1)
        
        assert subscribed, "Failed to subscribe to wake/mic topic"
    finally:
        client.loop_stop()
        client.disconnect()


def test_mqtt_subscribe_tts_status(mqtt_host, mqtt_port):
    """Test subscribing to tts/status topic."""
    client = mqtt.Client()
    subscribed = False
    
    def on_subscribe(client, userdata, mid, granted_qos):
        nonlocal subscribed
        subscribed = True
    
    client.on_subscribe = on_subscribe
    
    try:
        client.connect(mqtt_host, mqtt_port, 10)
        client.loop_start()
        
        # Wait for connection
        time.sleep(1)
        
        # Subscribe to topic
        result = client.subscribe("tts/status", qos=1)
        
        # Wait for subscription confirmation (up to 2 seconds)
        for _ in range(20):
            if subscribed:
                break
            time.sleep(0.1)
        
        assert subscribed, "Failed to subscribe to tts/status topic"
    finally:
        client.loop_stop()
        client.disconnect()


def test_mqtt_reconnection(mqtt_host, mqtt_port):
    """Test MQTT reconnection behavior after disconnect."""
    client = mqtt.Client()
    connection_count = 0
    
    def on_connect(client, userdata, flags, rc):
        nonlocal connection_count
        connection_count += 1
    
    client.on_connect = on_connect
    
    try:
        # Initial connection
        client.connect(mqtt_host, mqtt_port, 10)
        client.loop_start()
        time.sleep(1)
        
        assert connection_count == 1, "Initial connection failed"
        
        # Disconnect
        client.disconnect()
        time.sleep(1)
        
        # Reconnect
        client.reconnect()
        time.sleep(1)
        
        assert connection_count == 2, "Reconnection failed"
    finally:
        client.loop_stop()
        try:
            client.disconnect()
        except:
            pass


def test_mqtt_qos1_delivery(mqtt_host, mqtt_port):
    """Test QoS 1 message delivery (at least once)."""
    publisher = mqtt.Client()
    subscriber = mqtt.Client()
    
    received_messages = []
    subscribed = False
    
    def on_subscribe(client, userdata, mid, granted_qos):
        nonlocal subscribed
        subscribed = True
    
    def on_message(client, userdata, msg):
        received_messages.append(msg.payload.decode())
    
    subscriber.on_subscribe = on_subscribe
    subscriber.on_message = on_message
    
    try:
        # Connect subscriber
        subscriber.connect(mqtt_host, mqtt_port, 10)
        subscriber.loop_start()
        time.sleep(0.5)
        
        # Subscribe to test topic
        subscriber.subscribe("test/qos1", qos=1)
        
        # Wait for subscription
        for _ in range(20):
            if subscribed:
                break
            time.sleep(0.1)
        
        assert subscribed, "Failed to subscribe"
        
        # Connect publisher
        publisher.connect(mqtt_host, mqtt_port, 10)
        publisher.loop_start()
        time.sleep(0.5)
        
        # Publish test message
        test_message = "test-qos1-delivery"
        publisher.publish("test/qos1", test_message, qos=1)
        
        # Wait for message (up to 2 seconds)
        for _ in range(20):
            if received_messages:
                break
            time.sleep(0.1)
        
        assert len(received_messages) > 0, "Message not received"
        assert received_messages[0] == test_message, "Message content mismatch"
    finally:
        publisher.loop_stop()
        subscriber.loop_stop()
        publisher.disconnect()
        subscriber.disconnect()


def test_mqtt_health_topic_publish(mqtt_host, mqtt_port):
    """Test publishing to system/health/* topics."""
    client = mqtt.Client()
    published = False
    
    def on_publish(client, userdata, mid):
        nonlocal published
        published = True
    
    client.on_publish = on_publish
    
    try:
        client.connect(mqtt_host, mqtt_port, 10)
        client.loop_start()
        time.sleep(1)
        
        # Publish health message
        health_message = '{"ok": true, "event": "ready"}'
        result = client.publish("system/health/stt", health_message, qos=1, retain=True)
        
        # Wait for publish confirmation
        for _ in range(20):
            if published:
                break
            time.sleep(0.1)
        
        assert published, "Failed to publish to system/health/stt topic"
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    # Run tests with MQTT_TEST_HOST set
    # Example: MQTT_TEST_HOST=192.168.1.100 pytest tests/remote-mic/test_mqtt_connection.py -v
    pytest.main([__file__, "-v"])
