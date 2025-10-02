"""
TARS Controller - Autonomous Movement System

ESP32 firmware for TARS with complete modular architecture:

WiFi/MQTT Infrastructure:
- WiFiManager: Connection with auto-reconnect
- MQTTClient: Broker connection with QoS support

Movement System:
- ServoConfig: TARS-AI compatible servo definitions with percentage-based API
- ServoController: Asyncio-based parallel servo control
- MovementSequences: 15 pre-programmed movement sequences
- MovementCommandHandler: MQTT command queue with emergency stop

Features:
- Autonomous movement execution (no host dependency)
- User-friendly percentage-based API (1-100 scale)
- 15 movement sequences (5 basic + 10 expressive)
- Emergency stop with queue clearing
- LED status indicators (WiFi, MQTT, activity)
- Graceful error handling and recovery

Ready for ESP32 hardware deployment.
"""

# Standard library
try:
    import ujson as json
    import utime as time
    import uasyncio as asyncio
except ImportError:
    import json
    import time
    import asyncio

try:
    from machine import I2C, Pin
except ImportError:
    I2C = None
    Pin = None

try:
    import network
except ImportError:
    network = None

# Phase 1-2 modules (existing)
from lib.utils import sleep_ms, ticks_ms, ticks_diff
from lib.config import load_config, save_config, DEFAULT_CONFIG
from lib.pca9685 import PCA9685
from lib.led_status import LEDStatus

# Phase 3 modules (NEW - just created!)
from lib.wifi_manager import WiFiManager, SetupHTTPServer
from lib.mqtt_client import MQTTClientWrapper

# Phase 4-5 modules (Movement sequences - TARS Integration)
from movements import (
    ServoConfig,
    ServoController,
    MovementSequences,
    MovementCommandHandler
)


class TARSController:
    """
    Clean architecture controller for TARS ESP32 firmware.
    
    Responsibilities:
    - Initialize hardware (PWM, LED)
    - Manage WiFi connection (delegates to WiFiManager)
    - Manage MQTT connection (delegates to MQTTClientWrapper)
    - Route MQTT messages to appropriate handlers
    - Execute movement sequences (delegates to MovementSequences)
    - Monitor health and timeouts
    
    NOT responsible for:
    - WiFi portal implementation (in WiFiManager)
    - MQTT reconnection logic (in MQTTClientWrapper)
    - HTTP server details (in SetupHTTPServer)
    - Movement sequence details (in movements.sequences)
    - Servo control details (in movements.control)
    """
    
    def __init__(self, config):
        self.config = config
        self._config_path = config.get("config_path", DEFAULT_CONFIG["config_path"])
        
        # Hardware components
        self._pwm = None
        self._led_status = None
        self._station = None
        
        # Network components (Phase 3)
        self._mqtt_wrapper = None
        self._http_server = None
        
        # Movement components (Phase 4-5)
        self.servo_config = None
        self.servo_controller = None
        self.sequences = None
        self.movement_handler = None
        
        # Legacy movement state (for frame-based control)
        self._positions = {}  # Current servo positions
        self._last_frame_at = ticks_ms()
        
        # Health monitoring
        self._last_health_publish_at = ticks_ms()
        self._health_publish_interval_ms = 300000  # 5 minutes
        self._last_frame_timeout_logged = False
        
        # Flags
        self._pending_reset_at = None
        self._running = True
        
    def setup(self):
        """Initialize all hardware and network components."""
        print("=" * 50)
        print("TARS Controller - Phase 3 Architecture Demo")
        print("=" * 50)
        
        # 1. Setup LED status indicator
        self._setup_led()
        
        # 2. Setup PWM controller (PCA9685)
        self._setup_pwm()
        
        # 2.5. Setup movement components (Phase 4-5)
        self._setup_movements()
        
        # 3. Connect to WiFi (Phase 3: uses WiFiManager)
        self._connect_wifi()
        
        # 4. Connect to MQTT (Phase 3: uses MQTTClientWrapper)
        self._connect_mqtt()
        
        # 5. Start HTTP server for ongoing portal access
        self._start_http_server()
        
        print("=" * 50)
        print("✓ TARS Controller initialized successfully")
        print("=" * 50)
    
    def _setup_led(self):
        """Initialize LED status indicator."""
        led_cfg = self.config.get("status_led")
        if led_cfg is None:
            print("No LED configured")
            return
        
        try:
            self._led_status = LEDStatus(led_cfg)
            self._led_status.set_color(255, 255, 0)  # Yellow during init
            print("✓ LED status initialized")
        except Exception as e:
            print(f"✗ LED initialization failed: {e}")
    
    def _setup_pwm(self):
        """Initialize PCA9685 PWM controller."""
        if I2C is None:
            print("I2C not available (running on host?)")
            return
        
        try:
            i2c_cfg = self.config.get("i2c", {})
            i2c = I2C(
                i2c_cfg.get("id", 0),
                scl=Pin(i2c_cfg.get("scl", 22)),
                sda=Pin(i2c_cfg.get("sda", 21)),
                freq=i2c_cfg.get("freq", 400000),
            )
            
            self._pwm = PCA9685(i2c, address=i2c_cfg.get("pca9685_addr", 0x40))
            self._pwm.freq(i2c_cfg.get("pwm_freq", 50))
            
            print("✓ PCA9685 PWM controller initialized")
        except Exception as e:
            print(f"✗ PWM initialization failed: {e}")
    
    def _setup_movements(self):
        """Initialize movement components (Phase 4-5)."""
        print("\n--- Movement Setup (Phase 4-5: TARS Integration) ---")
        
        try:
            # Create servo configuration
            self.servo_config = ServoConfig()
            print("✓ Servo configuration loaded")
            
            # Create servo controller
            self.servo_controller = ServoController(self._pwm, self.servo_config)
            print("✓ Servo controller initialized")
            
            # Create movement sequences
            self.sequences = MovementSequences(self.servo_controller, self.servo_config)
            print("✓ Movement sequences loaded (15 sequences)")
            
            # Create command handler (without mqtt_client initially - will be set after MQTT connects)
            self.movement_handler = MovementCommandHandler(
                self.sequences,
                self.servo_controller,
                self.servo_config,
                mqtt_client=None,  # Will be set in _update_movement_handler_mqtt()
                status_topic="movement/status"
            )
            print("✓ Movement command handler initialized")
            
        except Exception as e:
            print(f"✗ Movement setup failed: {e}")
    
    def _update_movement_handler_mqtt(self):
        """Update movement handler with MQTT client after connection."""
        if self.movement_handler and self._mqtt_wrapper:
            # Pass the wrapper, not the underlying client
            self.movement_handler.mqtt_client = self._mqtt_wrapper
            print("✓ Movement handler connected to MQTT for status publishing")
    
    def _connect_wifi(self):
        """
        Connect to WiFi using WiFiManager (Phase 3).
        
        WiFiManager handles:
        - Connection attempts with retries
        - LED breathing effect during connection
        - Fallback to setup portal if connection fails
        - SSID scanning for portal
        """
        print("\n--- WiFi Connection (Phase 3: WiFiManager) ---")
        
        if WiFiManager is None:
            print("✗ WiFiManager not available")
            return
        
        def led_callback(color):
            """Callback for WiFiManager to update LED during connection."""
            if self._led_status:
                self._led_status.set_color(*color)
        
        # Delegate WiFi connection to WiFiManager
        WiFiManager.connect(
            self.config,
            self._led_status,
            led_callback
        )
        
        # Get station reference for IP display
        if network is not None:
            self._station = network.WLAN(network.STA_IF)
            if self._station.isconnected():
                print(f"✓ WiFi connected: {self._station.ifconfig()[0]}")
        
        if self._led_status:
            self._led_status.set_color(0, 255, 255)  # Cyan = WiFi connected
    
    def _connect_mqtt(self):
        """
        Connect to MQTT broker using MQTTClientWrapper (Phase 3).
        
        MQTTClientWrapper handles:
        - Connection with authentication
        - Subscription to frame topic
        - Publishing ready state and health
        - Message callbacks
        - Reconnection logic
        """
        print("\n--- MQTT Connection (Phase 3: MQTTClientWrapper) ---")
        
        if MQTTClientWrapper is None:
            print("✗ MQTTClientWrapper not available")
            return
        
        def on_message(topic, payload):
            """Route incoming MQTT messages to appropriate handlers."""
            self._handle_mqtt_message(topic, payload)
        
        def on_publish():
            """Blink LED when publishing (visual feedback)."""
            if self._led_status:
                try:
                    self._led_status.set_color(0, 0, 255)  # Blue flash
                    sleep_ms(300)
                    self._led_status.set_color(0, 255, 255)  # Back to cyan
                except Exception:
                    pass
        
        # Create MQTT wrapper with callbacks
        self._mqtt_wrapper = MQTTClientWrapper(
            self.config,
            on_message,
            on_publish
        )
        
        # Connect to broker
        try:
            self._mqtt_wrapper.connect()
            print("✓ MQTT connected and subscribed to movement/frame")
            
            # Subscribe to additional movement topics
            self._mqtt_wrapper.subscribe("movement/test", qos=1)
            self._mqtt_wrapper.subscribe("movement/stop", qos=1)
            print("✓ Subscribed to movement/test and movement/stop")
            
            # Update movement handler with MQTT client for status publishing
            self._update_movement_handler_mqtt()
        except Exception as e:
            print(f"✗ MQTT connection failed: {e}")
    
    def _start_http_server(self):
        """
        Start HTTP server for ongoing portal access (Phase 3).
        
        Uses SetupHTTPServer from WiFiManager module to provide
        web interface after WiFi is connected.
        """
        print("\n--- HTTP Server (Phase 3: SetupHTTPServer) ---")
        
        if SetupHTTPServer is None:
            print("✗ SetupHTTPServer not available")
            return
        
        try:
            # Note: SetupHTTPServer constructor signature may differ
            # This is a placeholder - adjust based on actual implementation
            self._http_server = SetupHTTPServer()
            print("✓ HTTP server started")
        except Exception as e:
            print(f"✗ HTTP server failed: {e}")
    
    def _handle_mqtt_message(self, topic, payload):
        """
        Route MQTT messages to appropriate handlers.
        
        Topics:
        - movement/frame: Servo frame data (existing functionality)
        - movement/test: Test movement sequences (future: TARS integration)
        - movement/stop: Emergency stop (future)
        """
        try:
            topic_str = topic.decode('utf-8') if isinstance(topic, bytes) else topic
            payload_str = payload.decode('utf-8') if isinstance(payload, bytes) else payload
            
            print(f"MQTT received: {topic_str}")
            
            if "frame" in topic_str:
                self._handle_frame_message(payload_str)
            elif "test" in topic_str:
                self._handle_test_message(payload_str)
            elif "stop" in topic_str:
                self._handle_stop_message()
            else:
                print(f"Unknown topic: {topic_str}")
                
        except Exception as e:
            print(f"Error handling MQTT message: {e}")
    
    def _handle_frame_message(self, payload):
        """
        Handle movement/frame messages (existing functionality).
        
        Frame format:
        {
            "ch0": 300, "ch1": 250, ...,
            "timestamp": 1234567890
        }
        """
        # Parse frame
        try:
            frame = json.loads(payload)
        except Exception as e:
            print(f"Invalid frame JSON: {e}")
            return
        
        # Apply frame to servos
        self._apply_frame(frame)
        
        # Update last frame timestamp
        self._last_frame_at = ticks_ms()
        
        # Publish state
        if self._mqtt_wrapper:
            self._mqtt_wrapper.publish_state("frame_applied", {
                "channels": len([k for k in frame.keys() if k.startswith("ch")])
            })
    
    def _handle_test_message(self, payload):
        """
        Handle movement/test messages (TARS integration - Phase 4-5).
        
        Command format (per TARS_INTEGRATION_PLAN.md):
        {
            "command": "step_forward",
            "speed": 0.8
        }
        
        Supported commands:
        - Movement: step_forward, step_backward, turn_left, turn_right
        - Expressions: wave, laugh, swing_legs, pezz, now, balance, etc.
        - Control: reset, disable
        - Manual: move_legs, move_arm (with parameters)
        """
        if self.movement_handler is None:
            print("Movement handler not available")
            return
        
        try:
            # Parse and validate command (uses lib/validation.py for strong typing)
            cmd = self.movement_handler.parse_and_validate_command(payload)
            if cmd is None:
                print("Invalid command format or validation failed")
                if self._mqtt_wrapper:
                    self._mqtt_wrapper.publish_state("command_error", {
                        "error": "invalid_format_or_validation_failed"
                    })
                return
            
            # Queue command for execution
            self.movement_handler.queue_command(cmd)
            
            # Acknowledge
            if self._mqtt_wrapper:
                self._mqtt_wrapper.publish_state("command_queued", {
                    "command": cmd["command"],
                    "speed": cmd.get("speed", 1.0),
                    "queue_size": self.movement_handler.queue_size()
                })
            
        except Exception as e:
            print(f"Error handling test command: {e}")
            if self._mqtt_wrapper:
                self._mqtt_wrapper.publish_state("command_error", {
                    "error": str(e)
                })
    
    def _handle_stop_message(self):
        """Emergency stop - disable all servos immediately (Phase 4-5)."""
        print("🛑 EMERGENCY STOP")
        
        # Trigger movement handler emergency stop
        if self.movement_handler:
            self.movement_handler.emergency_stop()
        else:
            # Fallback: disable servos directly
            if self.servo_controller:
                self.servo_controller.disable_all_servos()
        
        # Update LED to red
        if self._led_status:
            self._led_status.set_color(255, 0, 0)
        
        # Publish stopped state
        if self._mqtt_wrapper:
            self._mqtt_wrapper.publish_state("stopped", {
                "reason": "emergency_stop_command"
            })
    
    def _apply_frame(self, frame):
        """
        Apply servo frame to PWM controller.
        
        Frame keys: ch0, ch1, ch2, ... ch15 (PCA9685 has 16 channels)
        Values: PWM pulse width (typically 150-600 for servos)
        """
        if self._pwm is None:
            print("  (PWM not available, skipping frame application)")
            return
        
        applied_count = 0
        for key, value in frame.items():
            if not key.startswith("ch"):
                continue
            
            try:
                channel = int(key[2:])
                if 0 <= channel <= 15:
                    self._pwm.set_pwm(channel, 0, int(value))
                    self._positions[channel] = int(value)
                    applied_count += 1
            except Exception as e:
                print(f"  Error setting {key}: {e}")
        
        print(f"  Applied {applied_count} servo positions")
    
    def _check_frame_timeout(self):
        """
        Check if frame timeout has occurred.
        
        If no frames received within timeout period, log warning once
        and optionally disable servos. Only publishes health every 5 minutes.
        """
        frame_timeout_ms = self.config.get("frame_timeout_ms", 5000)
        elapsed = ticks_diff(ticks_ms(), self._last_frame_at)
        
        if elapsed > frame_timeout_ms:
            # Only log once when timeout first occurs
            if not self._last_frame_timeout_logged:
                print(f"⚠ Frame timeout ({elapsed}ms) - will not log again until frames resume")
                self._last_frame_timeout_logged = True
            
            # Optional: disable servos on timeout
            # self._disable_all_servos()
        else:
            # Reset logging flag when frames resume
            if self._last_frame_timeout_logged:
                print("✓ Frame reception resumed")
                self._last_frame_timeout_logged = False
    
    def _publish_periodic_health(self):
        """
        Publish health status periodically (every 5 minutes).
        """
        now = ticks_ms()
        elapsed = ticks_diff(now, self._last_health_publish_at)
        
        if elapsed >= self._health_publish_interval_ms:
            if self._mqtt_wrapper:
                # Check if frames are timing out
                frame_timeout_ms = self.config.get("frame_timeout_ms", 5000)
                frames_ok = ticks_diff(now, self._last_frame_at) <= frame_timeout_ms
                
                if frames_ok:
                    self._mqtt_wrapper.publish_health(True, "periodic_health_check")
                else:
                    self._mqtt_wrapper.publish_health(False, "frame_timeout")
            
            self._last_health_publish_at = now
    
    async def loop(self):
        """
        Main event loop (async for movement support).
        
        Responsibilities:
        - Wait for MQTT messages
        - Poll HTTP server  
        - Process movement queue (Phase 4-5)
        - Check frame timeout
        - Handle reconnection
        """
        print("\n--- Starting main loop ---\n")
        
        # Start movement queue processor (Phase 4-5)
        if self.movement_handler:
            queue_task = asyncio.create_task(self.movement_handler.process_queue())
            print("✓ Movement queue processor started")
        
        while self._running:
            try:
                # Check for MQTT messages (non-blocking)
                # Call check_msg() multiple times to process all pending messages
                if self._mqtt_wrapper:
                    try:
                        for _ in range(10):  # Process up to 10 messages per loop iteration
                            self._mqtt_wrapper.check_msg()
                    except Exception as mqtt_exc:
                        print(f"MQTT error: {mqtt_exc}")
                        # Reconnect handled by wrapper
                        try:
                            self._mqtt_wrapper.reconnect()
                        except Exception as reconnect_exc:
                            print(f"Reconnect failed: {reconnect_exc}")
                
                # Poll HTTP server (non-blocking)
                if self._http_server:
                    try:
                        self._http_server.poll()
                    except Exception as http_exc:
                        print(f"HTTP error: {http_exc}")
                
                # Check frame timeout (logs once, no health spam)
                self._check_frame_timeout()
                
                # Publish periodic health (every 5 minutes)
                self._publish_periodic_health()
                
                # Small async delay to prevent tight loop and allow other tasks to run
                await asyncio.sleep_ms(50)  # 50ms delay for better responsiveness
                
            except KeyboardInterrupt:
                print("\nKeyboard interrupt - shutting down")
                self._running = False
                break
            except Exception as e:
                print(f"Loop error: {e}")
                sleep_ms(1000)
    
    def shutdown(self):
        """Clean shutdown of all components."""
        print("\n--- Shutting down ---")
        
        # Disable servos
        self._disable_all_servos()
        
        # Disconnect MQTT
        if self._mqtt_wrapper:
            self._mqtt_wrapper.publish_state("shutdown", {})
            self._mqtt_wrapper.disconnect()
        
        # Close HTTP server
        if self._http_server:
            try:
                self._http_server.close()
            except Exception:
                pass
        
        # Turn off LED
        if self._led_status:
            self._led_status.set_color(0, 0, 0)
        
        print("✓ Shutdown complete")
    
    # ========================================================================
    # MOVEMENT METHODS (Phase 4-5: TARS Integration COMPLETE)
    # ========================================================================
    # Delegate to movements module (all async methods)
    
    def _disable_all_servos(self):
        """
        Disable all servos (set to 0 pulse width).
        Delegates to ServoController (Phase 4-5).
        """
        if self.servo_controller:
            self.servo_controller.disable_all_servos()
        elif self._pwm:
            # Fallback for legacy frame-based control
            for channel in range(16):
                try:
                    self._pwm.set_pwm(channel, 0, 0)
                except Exception:
                    pass
    
    async def reset_position(self, speed=1.0):
        """
        Return all servos to neutral position.
        Per TARS_INTEGRATION_PLAN.md: Reset to neutral stance
        """
        if self.sequences:
            await self.sequences.reset_position(speed)
    
    async def step_forward(self, speed=0.8):
        """
        Walk forward one step.
        Per TARS_INTEGRATION_PLAN.md: Basic movement sequence
        """
        if self.sequences:
            await self.sequences.step_forward(speed)
    
    async def step_backward(self, speed=0.8):
        """
        Walk backward one step.
        Per TARS_INTEGRATION_PLAN.md: Basic movement sequence
        """
        if self.sequences:
            await self.sequences.step_backward(speed)
    
    async def turn_left(self, speed=0.8):
        """
        Rotate left.
        Per TARS_INTEGRATION_PLAN.md: Basic movement sequence
        """
        if self.sequences:
            await self.sequences.turn_left(speed)
    
    async def turn_right(self, speed=0.8):
        """
        Rotate right.
        Per TARS_INTEGRATION_PLAN.md: Basic movement sequence
        """
        if self.sequences:
            await self.sequences.turn_right(speed)
    
    async def wave(self, speed=0.7):
        """
        Wave with right arm.
        Per TARS_INTEGRATION_PLAN.md: Expressive movement (right_hi)
        """
        if self.sequences:
            await self.sequences.wave(speed)
    
    async def laugh(self, speed=0.9):
        """
        Bouncing motion (laugh).
        Per TARS_INTEGRATION_PLAN.md: Expressive movement
        """
        if self.sequences:
            await self.sequences.laugh(speed)
    
    async def swing_legs(self, speed=0.6):
        """
        Pendulum leg motion.
        Per TARS_INTEGRATION_PLAN.md: Expressive movement
        """
        if self.sequences:
            await self.sequences.swing_legs(speed)
    
    # Note: Additional expressive movements available via movement_handler:
    # - pezz_dispenser, now, balance, mic_drop, monster, pose, bow
    # Access via MQTT commands or self.sequences directly


async def main():
    """Main entry point (async for movement support)."""
    # Load configuration
    config_path = "movement_config.json"
    try:
        config = load_config(config_path)
        print(f"✓ Loaded config from {config_path}")
    except Exception as e:
        print(f"⚠ Failed to load config: {e}")
        print("Using default configuration")
        config = DEFAULT_CONFIG.copy()
        config["config_path"] = config_path
    
    # Create and setup controller
    controller = TARSController(config)
    
    try:
        controller.setup()
        await controller.loop()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"\nFatal error: {e}")
    finally:
        controller.shutdown()


if __name__ == "__main__":
    # Run async main function
    try:
        print("[Tars Controller] Starting async run")
        asyncio.run(main())
    except AttributeError:
        # MicroPython doesn't have asyncio.run(), use get_event_loop()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
