# ESP32 Servo Tester for TARS - Web Interface

MicroPython servo control system for ESP32 with beautiful web-based UI. Control 9 servos using PCA9685 I2C servo driver from any device with a web browser.

## Features

- 🌐 **Web-Based Interface** - Control servos from any device (phone, tablet, PC)
- 🎨 **Modern UI** - Beautiful, responsive design with real-time updates
- 📱 **Mobile Friendly** - Works perfectly on smartphones
- 🔄 **Real-Time Control** - Instant servo position updates
- 🔧 **Individual Control** - Fine-tune each servo with sliders
- 🧪 **Testing Tools** - Test individual servos or all at once
- ⚡ **Fast & Responsive** - Optimized for ESP32's capabilities

## Hardware Requirements

- ESP32 development board (with WiFi)
- PCA9685 16-channel servo driver board
- 9 servos connected to channels 0-8
- Power supply for servos (5-6V, adequate amperage)
- WiFi network (or use built-in Access Point mode)

## Wiring

### I2C Connection (ESP32 to PCA9685):
- **SDA**: GPIO 21 (ESP32 I2C SDA)
- **SCL**: GPIO 20 (ESP32 I2C SCL)
- **VCC**: 3.3V (logic level)
- **GND**: GND

### Servo Channels:
- **Channel 0**: Main Legs (height control)
- **Channel 1**: Left Leg Rotation
- **Channel 2**: Right Leg Rotation
- **Channel 3**: Right Leg Main Arm
- **Channel 4**: Right Leg Forearm
- **Channel 5**: Right Leg Hand
- **Channel 6**: Left Leg Main Arm
- **Channel 7**: Left Leg Forearm
- **Channel 8**: Left Leg Hand

## Installation

### 1. Flash MicroPython to ESP32:
```bash
esptool.py --port /dev/ttyUSB0 erase_flash
esptool.py --port /dev/ttyUSB0 write_flash -z 0x1000 esp32-*.bin
```

### 2. Configure WiFi:
Edit `wifi_config.py` with your WiFi credentials:
```python
WIFI_SSID = "YourWiFiName"
WIFI_PASSWORD = "YourPassword"
```

### 3. Upload Files:

**Easy way (using provided scripts):**
```bash
# Make scripts executable
chmod +x *.sh

# Upload all files
./upload.sh

# Configure WiFi credentials
./configure_wifi.sh

# Start the web server
./start_server.sh
```

**Manual way (using mpremote):**
```bash
DEVICE="/dev/ttyACM0"

mpremote connect "$DEVICE" fs cp pca9685.py :
mpremote connect "$DEVICE" fs cp servo_config.py :
mpremote connect "$DEVICE" fs cp servo_controller.py :
mpremote connect "$DEVICE" fs cp wifi_config.py :
mpremote connect "$DEVICE" fs cp web_interface.py :
mpremote connect "$DEVICE" fs cp boot.py :
mpremote connect "$DEVICE" fs cp main.py :
```

## Usage

### Quick Start (Automated):
```bash
# 1. Upload all files
./upload.sh

# 2. Configure WiFi
./configure_wifi.sh

# 3. Start web server
./start_server.sh
```

### Start the Web Server:

**Option 1: Using script**
```bash
./start_server.sh
```

**Option 2: Manual via mpremote**
```bash
mpremote connect /dev/ttyACM0 exec "import main"
```

**Option 3: Auto-start on boot**
- Just power on the ESP32
- Wait 10-15 seconds for startup
- Look for the IP address on serial console

### Connect to Web Interface:

1. **WiFi Mode** (default):
   - ESP32 connects to your WiFi network
   - Serial console shows: `URL: http://192.168.x.x`
   - Open that URL in any web browser

2. **Access Point Mode** (fallback):
   - If WiFi fails, ESP32 creates its own network
   - Network name: `TARS-Servo`
   - Password: `tars1234`
   - Connect to this network
   - Open browser to: `http://192.168.4.1`

### Web Interface Controls:

- **Sliders**: Adjust servo positions (150-600 pulse width)
- **Set Button**: Apply the slider value to servo
- **Test Button**: Run full range test on individual servo
- **Neutral Position**: Move all servos to safe default positions
- **Test All Servos**: Sequential test of all 9 servos
- **Refresh Positions**: Update sliders with current servo positions
- **Disable All**: Turn off all servo PWM signals

## Configuration

### WiFi Settings (`wifi_config.py`):
```python
WIFI_SSID = "YourNetwork"        # Your WiFi name
WIFI_PASSWORD = "YourPassword"   # Your WiFi password
WEB_PORT = 80                    # Web server port
AP_SSID = "TARS-Servo"          # Access Point name
AP_PASSWORD = "tars1234"         # Access Point password
```

### Servo Calibration (`servo_config.py`):
```python
SERVO_RANGES = {
    0: {'min': 200, 'max': 500, 'default': 300},  # Adjust per servo
    # ... etc
}
```

**Calibration Process:**
1. Access web interface
2. Use sliders to find safe min/max values
3. Test each servo's full range
4. Update `servo_config.py` with actual values
5. Re-upload the file

## Troubleshooting

### Can't connect to WiFi:
- Check `wifi_config.py` credentials
- Verify WiFi network is 2.4GHz (ESP32 doesn't support 5GHz)
- Try Access Point mode as fallback

### Servos not responding:
- Check I2C connections (SDA/SCL)
- Verify PCA9685 power (separate 5V for servos)
- Check servo power supply amperage
- Look for errors in serial console

### Web page won't load:
- Verify IP address from serial console
- Try `http://192.168.4.1` if in AP mode
- Clear browser cache
- Check firewall settings

### ESP32 crashes/reboots:
- Insufficient power supply
- Servo power feedback (use separate supplies)
- Memory issue (reduce servo movements)

## API Endpoints

The web interface uses JSON API:

- `POST /servo` - Set servo position
  ```json
  {"channel": 0, "pulse": 300}
  ```

- `POST /test` - Test single servo
  ```json
  {"channel": 0}
  ```

- `POST /testall` - Test all servos
- `POST /preset` - Load preset position
  ```json
  {"name": "neutral"}
  ```

- `POST /positions` - Get current positions
- `POST /disable` - Disable all servos

## Safety Notes

1. **Always connect servo power supply before testing**
2. **Start with neutral position to verify safe defaults**
3. **Test individual servos before running complex movements**
4. **Keep emergency power disconnect accessible**
5. **Ensure servos have proper current rating power supply**
6. **Monitor servo temperatures during extended testing**
7. **Use web interface's "Disable All" button in emergencies**

## Advanced Usage

### Auto-start on boot:
The system automatically starts when powered on. To disable:
- Comment out auto-start in `boot.py`

### Custom Presets:
Add custom positions in `servo_config.py`:
```python
PRESET_POSITIONS = {
    'neutral': {...},
    'custom': {
        0: 350,
        1: 400,
        # ... etc
    }
}
```

### Integration:
Use the API endpoints to control servos from other systems:
```python
import urequests
urequests.post('http://192.168.x.x/servo', 
               json={'channel': 0, 'pulse': 300})
```

## Helper Scripts

- **`upload.sh`** - Upload all Python files to ESP32
- **`configure_wifi.sh`** - Configure WiFi credentials interactively
- **`start_server.sh`** - Start the web server on ESP32
- **`connect.sh`** - Connect to ESP32 REPL
- **`list_files.sh`** - List files on ESP32
- **`clean.sh`** - Remove all files from ESP32

Make executable: `chmod +x *.sh`

## Files Overview

- **`pca9685.py`** - Low-level PCA9685 I2C driver
- **`servo_config.py`** - Servo ranges and presets
- **`servo_controller.py`** - High-level servo control logic
- **`wifi_config.py`** - Network configuration
- **`web_interface.py`** - HTTP server and web UI
- **`boot.py`** - ESP32 boot configuration
- **`main.py`** - Entry point (starts web server)

## Credits

Based on TARS-AI community modules. Converted to MicroPython web interface for ESP32 by GitHub Copilot.
