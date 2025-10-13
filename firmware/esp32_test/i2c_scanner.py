"""
I2C Scanner for ESP32
Scans all I2C addresses to find connected devices
"""

from machine import I2C, Pin
import time

print("\n" + "="*50)
print("I2C Scanner - TARS Servo Controller")
print("="*50)
print()

# Pin combinations to test - prioritized for YD-ESP32-S3 board
pin_combinations = [
    (8, 9),    # YD-ESP32-S3 labeled SDA/SCL pins (GPIO8=SDA, GPIO9=SCL)
    (21, 20),  # User's current wiring: GPIO21=SDA, GPIO20=SCL
    (20, 21),  # Reversed: GPIO20=SDA, GPIO21=SCL
    (21, 22),  # Classic ESP32 default I2C pins
    (43, 44),  # TX0/RX0 UART pins (CLK_OUT1/CLK_OUT2)
    (1, 2),    # Touch1/Touch2 pins (also labeled ADC1_0/ADC1_1)
    (4, 5),    # Touch4/Touch5 pins
    (10, 11),  # GPIO10/GPIO11 pins
    (18, 19),  # GPIO18/GPIO19 pins
    (16, 17),  # GPIO16/GPIO17 pins
]

# Try multiple frequencies - some devices are sensitive to clock speed
frequencies = [100000, 400000, 50000]  # Standard, Fast, Slow

devices = []
working_config = None

print("Scanning for I2C devices with multiple pin/frequency combinations...")
print("This will take about 30 seconds...")
print()

for sda, scl in pin_combinations:
    print(f"Testing SDA=GPIO{sda}, SCL=GPIO{scl}...")
    
    for freq in frequencies:
        try:
            i2c = I2C(0, sda=Pin(sda), scl=Pin(scl), freq=freq)
            found = i2c.scan()
            
            if found:
                print(f"  ✓ SUCCESS at {freq//1000}kHz!")
                print(f"    SDA: GPIO {sda}, SCL: GPIO {scl}")
                print(f"    Found {len(found)} device(s)")
                devices = found
                working_config = (sda, scl, freq)
                break
        except Exception as e:
            pass  # Silent fail, keep trying
    
    if devices:
        break
    else:
        print(f"  ✗ No devices found")

print()

try:
    if devices and working_config:
        print(f"\n✓ Found {len(devices)} device(s):")
        print()
        for addr in devices:
            print(f"  • Address: 0x{addr:02X} (decimal {addr})")
            
            # Identify common devices
            if addr == 0x40:
                print("    → PCA9685 Servo Driver (default address)")
            elif addr == 0x70:
                print("    → PCA9685 Servo Driver (alternate address)")
            elif addr == 0x68:
                print("    → MPU6050/DS3231 or similar")
            elif addr == 0x76 or addr == 0x77:
                print("    → BMP280/BME280 sensor")
            elif addr in range(0x50, 0x58):
                print("    → EEPROM")
        
        
        sda, scl, freq = working_config
        print()
        print("="*50)
        print("CONFIGURATION REQUIRED:")
        print("="*50)
        print()
        print("Update servo_config.py with these values:")
        print(f"  I2C_SDA_PIN = {sda}")
        print(f"  I2C_SCL_PIN = {scl}")
        print()
        print("Update pca9685.py line ~25:")
        print(f"  freq={freq}")
        print()
        
        # Check if PCA9685 was found
        if 0x40 in devices:
            print("✓ PCA9685 found at expected address 0x40")
            print("  After updating config, your servo controller should work!")
        elif 0x70 in devices:
            print("⚠ PCA9685 found at address 0x70")
            print("  Also update servo_config.py:")
            print("  PCA9685_ADDRESS = 0x70")
        else:
            print("✗ PCA9685 not found at 0x40 or 0x70")
            print("  Please check:")
            print("  1. Wiring connections (SDA, SCL, GND, VCC)")
            print("  2. PCA9685 power supply")
            print("  3. Pull-up resistors (usually built-in)")
    else:
        print()
        print("✗ No I2C devices found on ANY pin combination!")
        print()
        print("="*50)
        print("HARDWARE TROUBLESHOOTING:")
        print("="*50)
        print()
        print("1. Check PCA9685 power:")
        print("   - Is there a power LED lit?")
        print("   - VCC connected to 3.3V")
        print("   - GND connected to ground")
        print("   - Servo power (V+) connected to 5-6V")
        print()
        print("2. Check wiring:")
        print("   - Wires firmly connected (no loose connections)")
        print("   - No shorts between pins")
        print("   - Try different jumper wires")
        print()
        print("3. Test with multimeter:")
        print("   - Check 3.3V at PCA9685 VCC pin")
        print("   - Check continuity on SDA/SCL lines")
        print()
        print("4. PCA9685 board:")
        print("   - Is the board working? (try another device)")
        print("   - Check for damaged components")
    
    print()
    print("="*50)
    
except Exception as e:
    print(f"\n✗ Error during scan: {e}")
    print("="*50)
