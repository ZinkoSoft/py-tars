# Research: ESP32 MicroPython Servo Control System

**Feature**: 002-esp32-micropython-servo  
**Date**: 2025-10-15  
**Status**: Phase 0 Complete

## Research Questions & Decisions

### 1. PCA9685 I2C Driver for MicroPython

**Question**: Which PCA9685 driver library is compatible with MicroPython on ESP32-S3?

**Decision**: Implement minimal custom driver based on Adafruit CircuitPython PCA9685 library

**Rationale**:
- MicroPython doesn't have a built-in PCA9685 library in stdlib
- Adafruit CircuitPython PCA9685 is well-documented and proven
- CircuitPython and MicroPython share similar `machine.I2C` interface
- Full library has unnecessary features (LED control); minimal driver is ~150 lines
- Only need: I2C init, set PWM frequency (50Hz), set PWM per channel (0-4095 range)

**Alternatives Considered**:
- **micropython-pca9685** (GitHub): Exists but not actively maintained, lacks error handling
- **Port Adafruit CircuitPython library directly**: Too heavy, includes LED patterns, requires `adafruit_bus_device`
- **Register-level implementation from datasheet**: Most control, but reinventing wheel

**Implementation Notes**:
```python
# Minimal PCA9685 class structure
class PCA9685:
    def __init__(self, i2c, address=0x40):
        # Initialize I2C, verify device responds
        # Set MODE1 register for auto-increment
        pass
    
    def set_pwm_freq(self, freq_hz):
        # Calculate prescale value: prescale = round(25MHz / (4096 * freq)) - 1
        # For 50Hz servos: prescale = 121
        # Write to PRE_SCALE register
        pass
    
    def set_pwm(self, channel, on, off):
        # Write 16-bit on/off values to LED<channel>_ON_L/H and LED<channel>_OFF_L/H
        # Servo control uses on=0, off=pulse_width (0-4095, constrained to 0-600)
        pass
```

**Reference**: [PCA9685 Datasheet](https://www.nxp.com/docs/en/data-sheet/PCA9685.pdf), [Adafruit CircuitPython PCA9685](https://github.com/adafruit/Adafruit_CircuitPython_PCA9685)

---

### 2. Async HTTP Server Implementation

**Question**: What's the best approach for async HTTP server in MicroPython on ESP32-S3?

**Decision**: Implement minimal async HTTP server using `uasyncio` + raw sockets

**Rationale**:
- MicroPython stdlib includes `socket` and `uasyncio` but no HTTP framework
- `micropython-async` library (Peter Hinch) provides good patterns but adds dependency
- For 5-10 routes (control, status, emergency, presets), custom implementation is simpler
- Memory-efficient: no routing framework overhead, no middleware stack
- Full control over response streaming for real-time status updates

**Alternatives Considered**:
- **Microdot** (Miguel Grinberg): Flask-like micro-framework, well-maintained but ~500 lines overhead
- **micropython-async web server**: Excellent resource but overkill for simple control interface
- **Blocking socket server**: Would block servo movements, violates async requirement

**Implementation Pattern**:
```python
import uasyncio as asyncio
import socket
import json

async def handle_client(reader, writer):
    """Handle single HTTP request"""
    request_line = await reader.readline()
    method, path, _ = request_line.decode().split()
    
    # Parse headers (minimal - just Content-Length if POST)
    headers = {}
    while True:
        line = await reader.readline()
        if line == b'\r\n':
            break
        k, v = line.decode().strip().split(':', 1)
        headers[k] = v.strip()
    
    # Read body if POST
    body = None
    if method == 'POST' and 'Content-Length' in headers:
        length = int(headers['Content-Length'])
        body = await reader.readexactly(length)
    
    # Route dispatch
    if path == '/':
        response = get_html_interface()
    elif path == '/control':
        response = await handle_control(json.loads(body))
    elif path == '/emergency':
        response = await handle_emergency_stop()
    # ... more routes
    
    writer.write(b'HTTP/1.1 200 OK\r\n')
    writer.write(b'Content-Type: application/json\r\n')
    writer.write(f'Content-Length: {len(response)}\r\n\r\n'.encode())
    writer.write(response.encode())
    await writer.drain()
    writer.close()
    await writer.wait_closed()

async def start_server():
    server = await asyncio.start_server(handle_client, '0.0.0.0', 80)
    print(f'Web server running on http://{wifi.ifconfig()[0]}')
    await server.wait_closed()
```

**Reference**: [MicroPython uasyncio docs](https://docs.micropython.org/en/latest/library/uasyncio.html), [Peter Hinch async tutorials](https://github.com/peterhinch/micropython-async)

---

### 3. Async Servo Movement Coordination

**Question**: How to replace multiprocessing-based parallel servo movements with asyncio?

**Decision**: Use `asyncio.create_task()` for each servo movement, with semaphore per channel to prevent conflicts

**Rationale**:
- Original code uses `multiprocessing.Process` to move servos in parallel (one process per servo)
- MicroPython has no multiprocessing; asyncio provides cooperative multitasking
- Servo movements are I/O-bound (20ms delays between incremental steps) - perfect for async
- Semaphore per servo channel prevents multiple tasks from controlling same servo
- `asyncio.gather()` can wait for coordinated movements to complete

**Alternatives Considered**:
- **Sequential servo movements**: Simple but slow; multi-step choreography would be jerky
- **Threading**: MicroPython threading is limited; async is preferred model
- **Global movement queue**: More complex; semaphore-per-channel is simpler

**Implementation Pattern**:
```python
import uasyncio as asyncio

class ServoController:
    def __init__(self, pca9685):
        self.pca = pca9685
        self.positions = [300] * 16  # Track current positions (default neutral)
        self.locks = [asyncio.Lock() for _ in range(16)]  # One lock per channel
        self.emergency_stop = False
    
    async def move_servo_smooth(self, channel, target, speed=1.0):
        """Move servo gradually from current to target position"""
        async with self.locks[channel]:  # Only one movement per servo at a time
            current = self.positions[channel]
            step = 1 if target > current else -1
            
            for pos in range(current, target + step, step):
                if self.emergency_stop:
                    raise asyncio.CancelledError("Emergency stop activated")
                
                self.pca.set_pwm(channel, 0, pos)
                self.positions[channel] = pos
                await asyncio.sleep(0.02 * (1.0 - speed))  # Slower = longer delay
    
    async def move_multiple(self, targets, speed=1.0):
        """Move multiple servos simultaneously"""
        tasks = []
        for channel, target in targets.items():
            if target is not None:
                task = asyncio.create_task(
                    self.move_servo_smooth(channel, target, speed)
                )
                tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def emergency_stop_all(self):
        """Disable all servos immediately"""
        self.emergency_stop = True
        await asyncio.sleep(0.1)  # Let tasks cancel
        for ch in range(16):
            self.pca.set_pwm(ch, 0, 0)  # PWM=0 = floating/disabled
        self.emergency_stop = False
```

**Reference**: [uasyncio tutorial](https://github.com/peterhinch/micropython-async/blob/master/v3/docs/TUTORIAL.md)

---

### 4. WiFi Connection Management

**Question**: How to handle WiFi connection and display IP address for web access?

**Decision**: Use `network.WLAN` with retry logic; display IP on serial console and web status page

**Rationale**:
- MicroPython `network` module provides `WLAN` class for ESP32 WiFi
- `configure_wifi.sh` writes credentials to `wifi_config.py` (constants: SSID, PASSWORD)
- Retry connection with exponential backoff (5 attempts max)
- Display IP address on serial console so user can navigate to web interface
- No fallback AP mode initially (adds complexity; can add later if needed)

**Alternatives Considered**:
- **AP mode fallback**: If connection fails, start access point for configuration - adds complexity, not needed with configure_wifi.sh
- **mDNS/Bonjour**: Advertise as `tars.local` - nice-to-have but not critical, adds dependency
- **Blocking connection wait**: Simple but delays boot; async with timeout is better

**Implementation Pattern**:
```python
import network
import uasyncio as asyncio
import time

async def connect_wifi(ssid, password, timeout=10):
    """Connect to WiFi with timeout"""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if wlan.isconnected():
        print(f'Already connected: {wlan.ifconfig()[0]}')
        return wlan
    
    print(f'Connecting to {ssid}...')
    wlan.connect(ssid, password)
    
    start = time.time()
    while not wlan.isconnected():
        if time.time() - start > timeout:
            print(f'WiFi connection timeout after {timeout}s')
            return None
        await asyncio.sleep(0.5)
    
    ip = wlan.ifconfig()[0]
    print(f'Connected! IP: {ip}')
    print(f'Web interface: http://{ip}')
    return wlan
```

**Reference**: [MicroPython network module](https://docs.micropython.org/en/latest/library/network.html)

---

### 5. Web Interface Design

**Question**: Should web interface be separate HTML/CSS/JS files or embedded in Python?

**Decision**: Embed single-page HTML/CSS/JS as string constant in `web_server.py`

**Rationale**:
- Simplifies deployment: upload.sh only needs to copy .py files
- Reduces filesystem reads: HTML served from RAM
- Total size <10KB for HTML+CSS+JS: minimal memory impact
- Single-page app pattern: no asset loading, all controls on one page
- JavaScript fetch API for AJAX control requests

**Alternatives Considered**:
- **Separate .html file**: Requires filesystem read on each request, more files to manage
- **Template engine**: Overkill for static interface; adds memory overhead
- **Progressive web app**: Service workers not supported in MicroPython HTTP server

**Implementation Pattern**:
```python
HTML_INTERFACE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial; margin: 20px; }
        .emergency { 
            position: fixed; 
            top: 20px; 
            right: 20px; 
            background: red; 
            color: white;
            padding: 20px;
            border-radius: 50%;
            font-size: 24px;
            cursor: pointer;
            z-index: 1000;
        }
        .servo-control { margin: 20px 0; }
        /* ... more styles ... */
    </style>
</head>
<body>
    <div class="emergency" onclick="emergencyStop()">STOP</div>
    <h1>TARS Servo Controller</h1>
    <!-- Servo sliders, preset buttons, status display -->
    <script>
        async function emergencyStop() {
            await fetch('/emergency', {method: 'POST'});
            alert('Emergency stop activated!');
        }
        // ... more JS ...
    </script>
</body>
</html>
"""

def get_html_interface():
    return HTML_INTERFACE
```

---

### 6. Servo Calibration Storage

**Question**: How to store servo calibration values (min/max pulse widths per channel)?

**Decision**: Hard-code calibration values as module-level constants in `servo_controller.py`, with comments referencing original config.ini

**Rationale**:
- Original `config.ini` has 18 config values (min/max for each servo + offsets)
- MicroPython has no built-in INI parser; would need custom parser or JSON
- Calibration values rarely change once set
- Hard-coding as constants is simplest, no runtime parsing overhead
- Comments link back to original config.ini for reference

**Alternatives Considered**:
- **JSON config file**: Requires `json.load()` on boot, adds complexity for rarely-changed values
- **Interactive calibration mode**: Nice-to-have but not in MVP scope
- **EEPROM storage**: ESP32 has NVRAM but MicroPython access is limited

**Implementation Pattern**:
```python
# servo_controller.py
# Calibration values from tars-community-movement-original/config.ini

# Center Lift Servo (channel 0)
UP_HEIGHT = 400        # config.ini: upHeight
NEUTRAL_HEIGHT = 300   # config.ini: neutralHeight  
DOWN_HEIGHT = 200      # config.ini: downHeight

# Port Drive Servo (channel 1)
FORWARD_PORT = 400     # config.ini: forwardPort + perfectPortoffset
NEUTRAL_PORT = 300     # config.ini: neutralPort + perfectPortoffset
BACK_PORT = 200        # config.ini: backPort + perfectPortoffset

# Starboard Drive Servo (channel 2)
FORWARD_STARBOARD = 400  # config.ini: forwardStarboard + perfectStaroffset
NEUTRAL_STARBOARD = 300  # config.ini: neutralStarboard + perfectStaroffset
BACK_STARBOARD = 200     # config.ini: backStarboard + perfectStaroffset

# Arms (channels 3-8): Min/Max ranges
PORT_ARM_MAIN_MIN = 135
PORT_ARM_MAIN_MAX = 440
# ... etc for all 6 arm servos

SERVO_LABELS = [
    "Main Legs Lift",
    "Left Leg Rotation", 
    "Right Leg Rotation",
    "Right Leg Main Arm",
    "Right Leg Forearm",
    "Right Leg Hand",
    "Left Leg Main Arm",
    "Left Leg Forearm",
    "Left Leg Hand"
]
```

---

## Best Practices Summary

### MicroPython on ESP32-S3

1. **Memory Management**:
   - Call `gc.collect()` periodically in long-running loops
   - Pre-allocate buffers for repeated operations
   - Use `const()` for compile-time constants to save RAM
   - Monitor free memory with `gc.mem_free()`

2. **Async Patterns**:
   - Use `asyncio.create_task()` for fire-and-forget operations
   - Use `asyncio.gather()` for coordinated parallel operations
   - Always handle `CancelledError` for clean shutdown
   - Use `asyncio.Lock()` to prevent race conditions on shared resources

3. **I2C Communication**:
   - Initialize I2C with explicit pin numbers: `machine.I2C(0, scl=Pin(9), sda=Pin(8))`
   - Use `i2c.scan()` to verify device presence before operations
   - Add retries for transient I2C errors (bus contention)
   - Keep I2C frequency at 100kHz (standard) unless fast mode needed

4. **Web Server**:
   - Keep responses small (<4KB) to fit in socket buffers
   - Use chunked transfer encoding for large responses
   - Set socket timeout to prevent hung connections
   - Limit concurrent connections (2-3 max on ESP32)

5. **Error Handling**:
   - Wrap hardware operations in try/except with specific exceptions
   - Log errors to serial console (no file logging on embedded)
   - Provide user-friendly error messages on web interface
   - Implement watchdog timer for automatic recovery from hangs

### Security Considerations

1. **WiFi Security**: WPA2 credentials stored in plaintext in `wifi_config.py` - acceptable for local dev network
2. **HTTP not HTTPS**: No TLS on MicroPython HTTP server - acceptable for trusted local network
3. **No authentication**: Web interface has no login - acceptable for single-user robot
4. **Rate limiting**: Not implemented - consider adding if misuse observed

**Note**: This is a local network embedded device, not internet-facing. Security is appropriate for the threat model.

---

## Technology Stack Summary

| Component | Technology | Justification |
|-----------|-----------|---------------|
| Language | MicroPython v1.20+ | Specified in requirements; runs on ESP32-S3 |
| Platform | ESP32-S3 (240MHz, 512KB RAM, 4MB flash) | Specified in requirements |
| I2C Driver | Custom minimal PCA9685 driver | No stdlib driver; custom is simplest |
| Async Runtime | uasyncio (MicroPython stdlib) | Required for parallel servo movements |
| Web Server | Custom async HTTP server | No framework needed for 5-10 routes |
| WiFi | network.WLAN (MicroPython stdlib) | Standard ESP32 WiFi interface |
| Config | Python constants + wifi_config.py | No env vars in MicroPython; simplest approach |
| Storage | None (stateless) | No persistence needed beyond configuration |
| Testing | Manual via web interface | MicroPython test automation not practical |

---

## Phase 0 Complete

All research questions resolved. Ready to proceed to Phase 1 (Design & Contracts).
