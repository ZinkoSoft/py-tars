"""
MQTT Client Wrapper - MQTT connection management for ESP32

This module handles:
- MQTT connection with authentication
- Automatic reconnection with retry logic
- Topic subscription management
- State and health publishing
- Message callbacks
"""

# Imports with MicroPython/CPython compatibility
try:
    from umqtt.robust import MQTTClient as RobustMQTTClient  # type: ignore
except ImportError:
    RobustMQTTClient = None  # type: ignore

try:
    import ujson as json  # type: ignore
    import utime as time  # type: ignore
except ImportError:
    import json  # type: ignore
    import time  # type: ignore

try:
    from lib.utils import sleep_ms, ticks_ms
except ImportError:
    # Fallback for testing outside MicroPython
    import time as time_module
    sleep_ms = lambda ms: time_module.sleep(ms / 1000.0)
    ticks_ms = lambda: int(time_module.time() * 1000)


class MQTTClientWrapper:
    """
    MQTT client wrapper with reconnection and publishing helpers.
    
    Wraps umqtt.robust.MQTTClient with convenience methods for:
    - Connection with authentication
    - Subscription management
    - State and health publishing
    - Automatic reconnection
    
    Args:
        config: Configuration dict with 'mqtt' and 'topics' sections
        on_message_callback: Callback function(topic, payload) for received messages
        on_publish_callback: Optional callback when a message is published (for LED blink, etc.)
    """
    
    def __init__(self, config, on_message_callback=None, on_publish_callback=None, monitor=None):
        self.config = config
        self._on_message_callback = on_message_callback
        self._on_publish_callback = on_publish_callback
        self._monitor = monitor  # Optional MQTTMonitor instance
        self._client = None
        
    def connect(self):
        """
        Connect to MQTT broker using configuration.
        
        Creates a new MQTT client, connects to the broker, and subscribes
        to the frame topic. Publishes ready state and health on success.
        
        Raises:
            RuntimeError: If umqtt.robust is not available
            Exception: If connection fails
        """
        if RobustMQTTClient is None:
            raise RuntimeError("umqtt.robust is required")
            
        mqtt_cfg = self.config["mqtt"]
        client = RobustMQTTClient(
            client_id=mqtt_cfg.get("client_id", "tars-esp32"),
            server=mqtt_cfg.get("host"),
            port=mqtt_cfg.get("port", 1883),
            user=mqtt_cfg.get("username"),
            password=mqtt_cfg.get("password"),
            keepalive=mqtt_cfg.get("keepalive", 30),
        )
        
        # Set up message callback
        if self._on_message_callback:
            client.set_callback(self._on_message_callback)
            
        client.connect()
        client.subscribe(self.config["topics"]["frame"], qos=1)
        self._client = client
        
        try:
            print('MQTT connected to', mqtt_cfg.get('host'))
        except Exception:
            pass
        try:
            print('Subscribed to', self.config['topics']['frame'])
        except Exception:
            pass
            
        # Publish ready state
        try:
            self.publish_state("ready", {"event": "firmware_online"})
        except Exception:
            pass
        try:
            self.publish_health(True, "ready")
        except Exception:
            pass
    
    def reconnect(self, retry_interval_ms=10000):
        """
        Attempt to reconnect to MQTT broker with retries.
        
        Tries to reconnect every retry_interval_ms until successful.
        Resubscribes to topics and publishes health on success.
        
        Args:
            retry_interval_ms: Time to wait between reconnection attempts (default 10s)
        """
        if self._client is None:
            # No client to reconnect; create new connection
            self.connect()
            return
            
        while True:
            try:
                print('Attempting MQTT reconnection...')
                self._client.reconnect()
                self._client.subscribe(self.config["topics"]["frame"], qos=1)
                print('MQTT reconnected successfully')
                self.publish_health(True, "reconnected")
                break  # Exit retry loop on successful reconnection
            except Exception as reconn_exc:
                print('MQTT reconnection failed:', str(reconn_exc))
                print(f'Retrying in {retry_interval_ms/1000} seconds...')
                sleep_ms(retry_interval_ms)
    
    def wait_msg(self):
        """
        Wait for a message (blocking call with timeout).
        
        Delegates to umqtt client's wait_msg(). If connection is lost,
        automatically attempts reconnection.
        
        Raises:
            RuntimeError: If client not connected
        """
        if self._client is None:
            raise RuntimeError("MQTT client not connected")
        
        try:
            self._client.wait_msg()
        except Exception as exc:
            print('MQTT connection lost:', str(exc))
            self.publish_state("error", {"error": "mqtt_wait_failed", "detail": str(exc)})
            self.publish_health(False, "mqtt_wait_failed")
            # Reconnect will be handled by caller
            raise
    
    def check_msg(self):
        """
        Check for a message (non-blocking call with short wait).
        
        Actually uses wait_msg() internally but doesn't block forever.
        The umqtt library's check_msg() is unreliable on MicroPython.
        
        Raises:
            RuntimeError: If client not connected
        """
        if self._client is None:
            raise RuntimeError("MQTT client not connected")
        
        try:
            # Set a very short socket timeout for non-blocking behavior
            # This allows wait_msg() to return quickly if no data
            sock = self._client.sock
            if sock:
                sock.settimeout(0.001)  # 1ms timeout for near-instant return
            
            # Now wait_msg() will return quickly if no messages
            self._client.wait_msg()
            
        except OSError as e:
            # Timeout or no data is expected - not an error
            if e.args[0] not in (110, 11):  # ETIMEDOUT, EAGAIN
                print(f'MQTT error: {e}')
                self.publish_state("error", {"error": "mqtt_check_failed", "detail": str(e)})
                self.publish_health(False, "mqtt_check_failed")
                raise
        except Exception as exc:
            print(f'MQTT connection lost: {exc}')
            self.publish_state("error", {"error": "mqtt_check_failed", "detail": str(exc)})
            self.publish_health(False, "mqtt_check_failed")
            raise
    
    def publish_state(self, event, payload=None):
        """
        Publish state message to state topic.
        
        Publishes a JSON message with event, timestamp, and optional payload.
        Retains message if event is "ready".
        
        Args:
            event: Event name (e.g., "ready", "error")
            payload: Optional dict with additional data
        """
        if self._client is None:
            return
            
        body = {
            "event": event,
            "timestamp": time.time() if hasattr(time, 'time') else 0,
        }
        if payload:
            body.update(payload)
            
        state_topic = self.config["topics"]["state"]
        retain = event == "ready"
        
        try:
            self._client.publish(state_topic, json.dumps(body), qos=1, retain=retain)
            print('Published state ->', state_topic, 'event=', event)
            
            # Notify callback (for LED blink, etc.)
            if self._on_publish_callback:
                try:
                    self._on_publish_callback()
                except Exception:
                    pass
        except Exception:
            pass
    
    def publish_health(self, ok, event):
        """
        Publish health message to health topic (retained).
        
        Publishes a JSON message with ok status, event, and timestamp.
        Always retained for monitoring.
        
        Args:
            ok: Boolean health status
            event: Event name (e.g., "ready", "error", "frame_timeout")
        """
        if self._client is None:
            return
            
        topic = self.config["topics"].get("health")
        if not topic:
            return
            
        body = {
            "ok": bool(ok),
            "event": event,
            "timestamp": time.time() if hasattr(time, 'time') else 0,
        }
        
        try:
            self._client.publish(topic, json.dumps(body), qos=1, retain=True)
            print('Published health ->', topic, 'ok=', ok, 'event=', event)
            
            # Notify callback (for LED blink, etc.)
            if self._on_publish_callback:
                try:
                    self._on_publish_callback()
                except Exception:
                    pass
        except Exception:
            pass
    
    def publish(self, topic, message, qos=0, retain=False):
        """
        Publish a message to an arbitrary topic.
        
        Args:
            topic: MQTT topic string
            message: Message payload (string or bytes)
            qos: Quality of Service level (0, 1, or 2)
            retain: Whether to retain the message
        """
        if self._client is None:
            return
            
        try:
            # Log to monitor before publishing
            if self._monitor:
                self._monitor.log_outgoing(topic, message)
            
            self._client.publish(topic, message, qos=qos, retain=retain)
            print('Published ->', topic)
            
            # Notify callback
            if self._on_publish_callback:
                try:
                    self._on_publish_callback()
                except Exception:
                    pass
        except Exception as e:
            print('Publish failed:', str(e))
    
    def subscribe(self, topic, qos=0):
        """
        Subscribe to an additional topic.
        
        Args:
            topic: MQTT topic string (can include wildcards)
            qos: Quality of Service level (0, 1, or 2)
        """
        if self._client is None:
            return
            
        try:
            self._client.subscribe(topic, qos=qos)
            print('Subscribed to', topic)
        except Exception as e:
            print('Subscribe failed:', str(e))
    
    def is_connected(self):
        """Check if MQTT client is connected."""
        return self._client is not None
    
    def disconnect(self):
        """Disconnect from MQTT broker."""
        if self._client is None:
            return
            
        try:
            self._client.disconnect()
            print('MQTT disconnected')
        except Exception as e:
            print('Disconnect error:', str(e))
        finally:
            self._client = None


# Self-tests (run when module is executed directly)
if __name__ == "__main__":
    print("Running mqtt_client self-tests...")
    
    # Test 1: MQTTClientWrapper instantiation
    config = {
        "mqtt": {
            "host": "localhost",
            "port": 1883,
            "username": "test",
            "password": "test",
            "client_id": "test-client",
            "keepalive": 30,
        },
        "topics": {
            "frame": "movement/frame",
            "state": "system/state",
            "health": "system/health",
        }
    }
    
    # Mock callback
    messages_received = []
    def mock_callback(topic, payload):
        messages_received.append((topic, payload))
    
    publish_count = [0]
    def mock_publish_callback():
        publish_count[0] += 1
    
    wrapper = MQTTClientWrapper(config, mock_callback, mock_publish_callback)
    assert wrapper.config == config
    assert wrapper._on_message_callback == mock_callback
    assert wrapper._on_publish_callback == mock_publish_callback
    assert wrapper._client is None
    print("✓ MQTTClientWrapper instantiation")
    
    # Test 2: is_connected
    assert not wrapper.is_connected()
    print("✓ is_connected (not connected)")
    
    # Test 3: State publishing (no-op without connection)
    wrapper.publish_state("test", {"data": "value"})
    assert not wrapper.is_connected()
    print("✓ publish_state (no-op without connection)")
    
    # Test 4: Health publishing (no-op without connection)
    wrapper.publish_health(True, "test_event")
    assert not wrapper.is_connected()
    print("✓ publish_health (no-op without connection)")
    
    # Test 5: wait_msg raises when not connected
    try:
        wrapper.wait_msg()
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "not connected" in str(e).lower()
    print("✓ wait_msg raises when not connected")
    
    # Test 6: Disconnect (no-op without connection)
    wrapper.disconnect()
    assert not wrapper.is_connected()
    print("✓ disconnect (no-op without connection)")
    
    # Note: Actual MQTT connection tests require a running broker
    # and are better done as integration tests on the ESP32
    
    print("\n✓ All mqtt_client tests passed!")
    print("Note: Integration tests with real MQTT broker should be run on ESP32")
