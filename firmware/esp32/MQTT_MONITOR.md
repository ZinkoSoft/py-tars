# TARS MQTT Monitor

A real-time web interface for monitoring MQTT message traffic on the ESP32.

## Overview

The MQTT Monitor provides a live view of all MQTT messages flowing through the ESP32:
- 📥 **Incoming Messages**: Messages received from MQTT topics (commands, frames)
- 📤 **Outgoing Messages**: Messages published by the ESP32 (status, health)
- 🔄 **Auto-Refresh**: Page automatically updates every 5 seconds
- 📊 **Statistics**: Message counts, connection status, uptime

## Access

After the ESP32 connects to WiFi and MQTT, the monitor is available at:

```
http://<esp32-ip-address>:8080/
```

**Example**: `http://192.168.1.100:8080/`

### Finding Your ESP32 IP Address

Check the ESP32 serial console during boot:
```
✓ WiFi connected: 192.168.1.100
✓ MQTT Monitor: http://192.168.1.100:8080/
```

Or check your router's DHCP client list for device named `tars-esp32`.

## Features

### Connection Status
- **Green pulsing dot** = MQTT connected
- **Red dot** = MQTT disconnected
- **Uptime display** shows how long MQTT has been connected

### Message History
- Shows last 20 incoming and 20 outgoing messages
- Displays:
  - **Timestamp** (HH:MM:SS format)
  - **Topic** (e.g., `movement/test`, `movement/status`)
  - **Payload** (first 500 characters)
  - **Size** (in bytes)

### Message Types

**Incoming (Blue Border)**:
- `movement/test` - Movement commands
- `movement/frame` - Servo frame data
- `movement/stop` - Emergency stop commands

**Outgoing (Orange Border)**:
- `movement/status` - Command execution status
- `movement/state` - State changes
- `system/health/movement-esp32` - Health checks

### Statistics
- Total incoming messages received
- Total outgoing messages published
- Combined message count

## Usage

### Debugging Movement Commands

1. Open the MQTT monitor in your browser: `http://<esp32-ip>:8080/`
2. Send a test command via MQTT:
   ```bash
   mosquitto_pub -h <broker-ip> -u tars -P pass \
     -t movement/test \
     -m '{"command":"wave","speed":0.5}'
   ```
3. Watch the monitor to see:
   - Incoming message on `movement/test` topic
   - Outgoing status on `movement/status` topic

### Troubleshooting

**Problem**: Commands sent but no response
- **Check**: Monitor shows incoming message but no outgoing status
- **Likely cause**: Command validation failed or execution error
- **Action**: Check payload format, consult ESP32 serial console

**Problem**: No messages appearing
- **Check**: Connection status (should be green pulsing)
- **Action**: Verify MQTT broker is running and ESP32 is connected

**Problem**: Monitor page won't load
- **Check**: Port 8080 is accessible
- **Action**: Check firewall, verify ESP32 WiFi connection

### Controls

- **Refresh Button**: Manually reload the page
- **Clear Button**: Clear all message history (statistics reset to 0)
- **Auto-Refresh**: Page automatically reloads every 5 seconds

## Configuration

Edit `movement_config.json` to customize the monitor:

```json
{
  "mqtt_monitor": {
    "port": 8080,
    "max_messages": 50
  }
}
```

**Options**:
- `port`: HTTP port for monitor interface (default: 8080)
- `max_messages`: Maximum messages to keep in history (default: 50)

## API Endpoint

The monitor also provides a JSON API for programmatic access:

```
GET http://<esp32-ip>:8080/api/messages
```

**Response**:
```json
{
  "connected": true,
  "uptime": 3600,
  "incoming": [
    {
      "time": 1696953600,
      "topic": "movement/test",
      "payload": "{\"command\":\"wave\"}",
      "size": 21
    }
  ],
  "outgoing": [
    {
      "time": 1696953601,
      "topic": "movement/status",
      "payload": "{\"status\":\"executing\"}",
      "size": 25
    }
  ]
}
```

## Technical Details

### Implementation
- Built using MicroPython `socket` module
- Non-blocking HTTP server (doesn't block main event loop)
- Lightweight HTML/CSS (no external dependencies)
- Runs in parallel with MQTT communication

### Performance
- **Memory**: ~20KB for 50 messages
- **CPU**: Minimal impact (<1% in main loop)
- **Network**: Only when browser requests page

### Architecture
- `lib/mqtt_monitor.py`: Monitor implementation
- `tars_controller.py`: Integration with MQTT wrapper
- `lib/mqtt_client.py`: Automatic message logging

## Example Session

```
1. ESP32 boots and connects to WiFi
   ✓ MQTT Monitor: http://192.168.1.100:8080/

2. Open browser to http://192.168.1.100:8080/
   → See "Connected" status with green pulsing dot

3. Send test command:
   mosquitto_pub -t movement/test -m '{"command":"wave","speed":0.5}'

4. Monitor shows:
   📥 Incoming: movement/test → {"command":"wave","speed":0.5}
   📤 Outgoing: movement/status → {"status":"executing","command":"wave"}
   📤 Outgoing: movement/status → {"status":"completed","command":"wave"}

5. Click "Clear" to reset history
   → All messages cleared, statistics reset
```

## Comparison to WiFi Setup Page

| Feature | WiFi Setup Page | MQTT Monitor |
|---------|----------------|--------------|
| **Purpose** | Configure WiFi | Debug MQTT traffic |
| **When** | Initial setup | Runtime monitoring |
| **Port** | 80 | 8080 |
| **Auto-refresh** | No | Yes (5s) |
| **Styling** | Dark orange | Dark blue/orange |
| **Access** | Setup AP or after WiFi | After WiFi connected |

Both pages use similar styling and architecture for consistency.

## See Also

- [ESP32 README](README.md) - Full ESP32 firmware documentation
- [Movement Commands](README.md#mqtt-commands) - Available MQTT commands
- [WiFi Setup](README.md#wifi-setup) - Initial WiFi configuration

