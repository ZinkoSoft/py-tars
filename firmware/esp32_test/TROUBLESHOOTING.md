# Troubleshooting Guide - TARS Servo Controller

Common issues and solutions for the ESP32 servo control system.

## Hardware Issues

### PCA9685 Not Detected

**Symptom**: Error message "PCA9685 not detected at address 0x40"

**Solutions**:

1. **Check power supply**
   - PCA9685 VCC should be connected to 3.3V (logic) or 5V
   - V+ should be connected to servo power supply (5-6V)
   - Verify power LED on PCA9685 is lit

2. **Verify I2C wiring**
   ```
   ESP32 GPIO 8 (SDA) → PCA9685 SDA
   ESP32 GPIO 9 (SCL) → PCA9685 SCL
   ESP32 GND → PCA9685 GND
   ```

3. **Check I2C address**
   - Default is 0x40
   - Run: `./diagnose.sh` to scan for devices
   - If different address found, update in `main.py`:
     ```python
     pca = PCA9685(i2c, address=0x41)  # Change to your address
     ```

4. **Test I2C bus**
   ```bash
   ./diagnose.sh
   ```
   Should show device at 0x40

5. **Check for shorts**
   - Inspect SDA/SCL lines for short circuits
   - Ensure no loose wires touching

### Servos Not Moving

**Symptom**: Servos don't respond to commands

**Solutions**:

1. **Check servo power**
   - Servos need 5-6V external power (NOT from ESP32)
   - Verify power supply can provide 2-5A depending on servo count
   - Check all ground connections are common

2. **Test individual servo**
   ```bash
   ./test_servos.sh
   ```

3. **Verify calibration**
   - Check `servo_config.py` SERVO_CALIBRATION values
   - Ensure min/max are within physical limits

4. **Check connections**
   - Servo signal wires to PCA9685 channels 0-8
   - Ensure servo connectors are fully seated

5. **Test from REPL**
   ```python
   from pca9685 import PCA9685
   import machine
   i2c = machine.I2C(0, scl=machine.Pin(9), sda=machine.Pin(8))
   pca = PCA9685(i2c)
   pca.set_pwm_freq(50)
   pca.set_pwm(0, 0, 300)  # Test channel 0
   ```

### Servo Jitters or Vibrates

**Symptom**: Servo shakes or vibrates at certain positions

**Solutions**:

1. **Insufficient power**
   - Upgrade to higher current power supply
   - Check voltage under load (should be 5-6V)

2. **Mechanical binding**
   - Check for obstructions
   - Ensure servo arm isn't hitting limits
   - Reduce range in `servo_config.py` if needed

3. **Electrical noise**
   - Add capacitors across servo power lines (1000µF)
   - Use shielded cables for long runs
   - Keep signal wires away from power wires

### Servo Moves to Wrong Position

**Symptom**: Servo goes to unexpected position

**Solutions**:

1. **Inverted calibration**
   - Left arm servos (6-8) have inverted min/max
   - Check SERVO_CALIBRATION in `servo_config.py`

2. **Wrong channel mapping**
   - Verify servo connected to correct PCA9685 channel
   - See README.md for channel mapping

3. **Calibration out of range**
   - Re-calibrate using `test_servos.sh`
   - Adjust min/max values in `servo_config.py`

## Network Issues

### WiFi Connection Failed

**Symptom**: "WiFi connection failed" after timeout

**Solutions**:

1. **Check network compatibility**
   - ESP32 only supports 2.4GHz WiFi (not 5GHz)
   - WPA2 security required
   - Hidden SSIDs not recommended

2. **Verify credentials**
   ```bash
   ./configure_wifi.sh
   ```
   Re-enter SSID and password carefully

3. **Check signal strength**
   - Move ESP32 closer to router
   - Avoid metal enclosures
   - Check for interference

4. **Router settings**
   - Enable DHCP
   - Check MAC address filtering
   - Verify client limit not reached

5. **Test connection manually**
   In REPL:
   ```python
   import network
   wlan = network.WLAN(network.STA_IF)
   wlan.active(True)
   wlan.connect('SSID', 'PASSWORD')
   ```

### Cannot Access Web Interface

**Symptom**: Browser shows "Can't reach this page"

**Solutions**:

1. **Check IP address**
   ```bash
   ./status.sh
   ```
   Verify IP address shown

2. **Firewall**
   - Check firewall on your computer
   - Allow incoming connections on port 80
   - Try from same network segment

3. **Verify web server running**
   In serial console, should see:
   ```
   Web server listening on port 80
   ✓ SYSTEM READY
   ```

4. **Restart system**
   ```bash
   mpremote connect /dev/ttyACM0 exec "import machine; machine.reset()"
   ```

### Web Interface Slow or Unresponsive

**Symptom**: Pages load slowly or commands timeout

**Solutions**:

1. **Network congestion**
   - Reduce WiFi network traffic
   - Move ESP32 closer to router

2. **Memory issues**
   - Check memory: `./status.sh`
   - Restart if memory low: `machine.reset()`

3. **Too many servos moving**
   - Reduce concurrent movements
   - Emergency stop and restart

## Software Issues

### Import Error

**Symptom**: "ImportError: no module named 'xxx'"

**Solutions**:

1. **Upload missing file**
   ```bash
   ./upload.sh
   ```

2. **Check file exists**
   ```bash
   ./list_files.sh
   ```

3. **Re-upload specific file**
   ```bash
   mpremote connect /dev/ttyACM0 fs cp <filename.py> :
   ```

### Memory Error

**Symptom**: "MemoryError: memory allocation failed"

**Solutions**:

1. **Check free memory**
   ```bash
   ./status.sh
   ```

2. **Restart ESP32**
   ```python
   import machine
   machine.reset()
   ```

3. **Reduce memory usage**
   - Avoid running multiple presets simultaneously
   - Reduce number of concurrent servo movements
   - Clear variables in REPL: `import gc; gc.collect()`

4. **Monitor memory over time**
   - If gradually decreasing, may indicate memory leak
   - Report issue with details

### Emergency Stop Not Working

**Symptom**: Emergency stop button doesn't stop servos

**Solutions**:

1. **Check web server connection**
   - Verify web interface is loaded
   - Check browser console for errors

2. **Network timeout**
   - Emergency stop should respond in <100ms
   - If network is slow, may take longer

3. **Physical power switch**
   - As last resort, cut servo power supply
   - Do NOT cut ESP32 power while servos moving

### Preset Sequence Fails

**Symptom**: Preset stops mid-sequence with error

**Solutions**:

1. **Check error message**
   - View serial console: `./start_server.sh`
   - Look for validation errors

2. **Mechanical limits**
   - Preset may exceed servo physical limits
   - Check for binding during movement

3. **Memory exhausted**
   - Long presets may run out of memory
   - Restart and try shorter preset

4. **Emergency stop triggered**
   - Check if emergency stop was activated
   - Resume and retry

## Upload Issues

### Upload Failed

**Symptom**: "✗ FAILED" when uploading files

**Solutions**:

1. **Check device connection**
   ```bash
   ls -l /dev/ttyACM* /dev/ttyUSB*
   ```

2. **Device permissions**
   ```bash
   sudo chmod 666 /dev/ttyACM0
   ```
   Or add user to dialout group:
   ```bash
   sudo usermod -a -G dialout $USER
   # Logout and login again
   ```

3. **Device busy**
   - Close other programs using serial port
   - Kill hanging mpremote: `pkill -f mpremote`

4. **Wrong device**
   - Try `/dev/ttyUSB0` instead of `/dev/ttyACM0`
   - Edit scripts to use correct device

5. **Flash full**
   - Check flash usage: `./list_files.sh`
   - Remove unused files: `./clean.sh`

### mpremote Not Found

**Symptom**: "command not found: mpremote"

**Solutions**:

1. **Install mpremote**
   ```bash
   pip install mpremote
   ```

2. **Add to PATH**
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   ```

3. **Use full path**
   ```bash
   python -m mpremote connect /dev/ttyACM0
   ```

## Performance Issues

### Slow Servo Movement

**Symptom**: Servos move slower than expected

**Solutions**:

1. **Check speed setting**
   - Global speed should be 1.0 for fastest
   - Per-command speed overrides global

2. **Power supply voltage**
   - Low voltage = slow servos
   - Verify 5-6V under load

3. **Mechanical friction**
   - Check for binding
   - Lubricate if needed

### Web Server Unresponsive During Movement

**Symptom**: Can't access web interface while servos moving

**Solutions**:

1. **Expected for complex presets**
   - Some long presets may block briefly
   - Wait for preset to complete

2. **Memory issues**
   - Check memory: `./status.sh`
   - Restart if low

3. **Network issues**
   - Check WiFi signal strength
   - Reduce network traffic

## Diagnostic Commands

### Quick Health Check
```bash
./status.sh
```

### Full Diagnostics
```bash
./diagnose.sh
```

### Test All Servos
```bash
./test_servos.sh
```

### View Live Console
```bash
./start_server.sh
```

### Check I2C Devices
```bash
mpremote connect /dev/ttyACM0 exec "
import machine
i2c = machine.I2C(0, scl=machine.Pin(9), sda=machine.Pin(8))
print(i2c.scan())
"
```

### Check Memory
```bash
mpremote connect /dev/ttyACM0 exec "
import gc
gc.collect()
print(f'Free: {gc.mem_free()} bytes')
"
```

### Reset ESP32
```bash
mpremote connect /dev/ttyACM0 exec "
import machine
machine.reset()
"
```

## Getting Help

If you can't resolve the issue:

1. Run full diagnostics: `./diagnose.sh`
2. Check serial console: `./start_server.sh`
3. Note any error messages
4. Check hardware connections
5. Review README.md for correct setup
6. Create issue with:
   - Error messages
   - Diagnostic output
   - Hardware configuration
   - Steps to reproduce

## Safety Reminders

⚠️ **Always**:
- Use external power for servos (not ESP32)
- Test movements at slow speed first
- Keep emergency stop accessible
- Monitor for overheating
- Respect mechanical limits

⚠️ **Never**:
- Power servos from ESP32
- Exceed calibrated ranges
- Force servos past mechanical limits
- Run servos without proper power supply
- Ignore unusual sounds or vibrations
