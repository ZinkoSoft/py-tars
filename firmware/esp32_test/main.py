"""
TARS Servo Controller - Main Entry Point
MicroPython for ESP32 with PCA9685

Initializes hardware, connects to WiFi, and starts web server
"""

import uasyncio as asyncio
import machine
import gc
import sys

# Import our modules
try:
    from wifi_manager import connect_wifi
    from pca9685 import PCA9685
    from servo_controller import ServoController
    from web_server import start_server
except ImportError as e:
    print(f"✗ Import error: {e}")
    print("Please ensure all required modules are uploaded to the ESP32")
    sys.exit(1)

# Import WiFi credentials
try:
    from wifi_config import WIFI_SSID, WIFI_PASSWORD
except ImportError:
    print("✗ wifi_config.py not found!")
    print("Please create wifi_config.py with WIFI_SSID and WIFI_PASSWORD")
    sys.exit(1)


async def main():
    """Main initialization and startup sequence"""
    
    print("\n" + "="*50)
    print("TARS Servo Controller Starting...")
    print("="*50 + "\n")
    
    # Step 1: Connect to WiFi
    print("Step 1: Connecting to WiFi...")
    success, ip, error = await connect_wifi(WIFI_SSID, WIFI_PASSWORD)
    
    if not success:
        print(f"✗ WiFi connection failed: {error}")
        print("System cannot continue without WiFi")
        return
    
    # Step 2: Initialize I2C bus
    print("\nStep 2: Initializing I2C bus...")
    try:
        # Custom GPIO: SDA=8, SCL=9
        i2c = machine.I2C(0, scl=machine.Pin(9), sda=machine.Pin(8), freq=100000)
        devices = i2c.scan()
        print(f"I2C devices found: {[hex(d) for d in devices]}")
    except Exception as e:
        print(f"✗ I2C initialization failed: {e}")
        return
    
    # Step 3: Initialize PCA9685
    print("\nStep 3: Initializing PCA9685...")
    try:
        pca = PCA9685(i2c, address=0x40)
        pca.set_pwm_freq(50)  # 50Hz for servos
    except OSError as e:
        print(f"✗ PCA9685 not detected: {e}")
        print("Please check:")
        print("  - PCA9685 is powered")
        print("  - I2C wiring (SDA=GPIO8, SCL=GPIO9)")
        print("  - I2C address is 0x40")
        return
    except Exception as e:
        print(f"✗ PCA9685 initialization failed: {e}")
        return
    
    # Step 4: Initialize Servo Controller
    print("\nStep 4: Initializing Servo Controller...")
    try:
        servo_controller = ServoController(pca)
        servo_controller.initialize_servos()
    except Exception as e:
        print(f"✗ Servo controller initialization failed: {e}")
        return
    
    # Step 5: Start web server
    print("\nStep 5: Starting web server...")
    try:
        # Create task for web server
        server_task = asyncio.create_task(start_server(servo_controller))
        
        print("\n" + "="*50)
        print("✓ SYSTEM READY")
        print(f"✓ Web Interface: http://{ip}/")
        print(f"✓ All 9 servos initialized")
        print("="*50 + "\n")
        
        # Keep running
        await server_task
        
    except Exception as e:
        print(f"✗ Web server failed: {e}")
        import sys
        sys.print_exception(e)
        return


# Run main function
try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("\n\nShutdown requested by user")
except Exception as e:
    print(f"\n\nFatal error: {e}")
    import sys
    sys.print_exception(e)
finally:
    # Cleanup
    gc.collect()
    print("System halted")
