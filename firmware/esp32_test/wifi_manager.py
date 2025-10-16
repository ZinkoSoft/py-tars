"""
WiFi Manager for ESP32 MicroPython
Handles WiFi connection with retry logic and error handling
"""

import network
import time
import uasyncio as asyncio


async def connect_wifi(ssid, password, timeout=10, max_attempts=5):
    """
    Connect to WiFi network with retry logic
    
    Args:
        ssid: WiFi network name
        password: WiFi password
        timeout: Connection timeout in seconds per attempt
        max_attempts: Maximum number of connection attempts
    
    Returns:
        tuple: (success: bool, ip_address: str or None, error_msg: str or None)
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    # If already connected, return current IP
    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        print(f"Already connected to WiFi: {ip}")
        return True, ip, None
    
    print(f"Connecting to WiFi SSID: {ssid}")
    
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"Attempt {attempt}/{max_attempts}...")
            
            # Start connection
            wlan.connect(ssid, password)
            
            # Wait for connection with timeout
            start_time = time.time()
            while not wlan.isconnected():
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"Connection timeout after {timeout}s")
                await asyncio.sleep(0.5)
            
            # Success
            ip = wlan.ifconfig()[0]
            print("="*50)
            print(f"✓ WiFi Connected Successfully!")
            print(f"✓ IP Address: {ip}")
            print(f"✓ Network: {ssid}")
            print("="*50)
            return True, ip, None
            
        except TimeoutError as e:
            print(f"✗ Attempt {attempt} timed out")
            if attempt < max_attempts:
                # Exponential backoff: 2, 4, 8, 16 seconds
                backoff = min(2 ** attempt, 16)
                print(f"  Retrying in {backoff} seconds...")
                await asyncio.sleep(backoff)
            else:
                error_msg = f"Failed to connect after {max_attempts} attempts"
                print(f"✗ {error_msg}")
                return False, None, error_msg
                
        except Exception as e:
            print(f"✗ Connection error: {e}")
            if attempt < max_attempts:
                backoff = min(2 ** attempt, 16)
                print(f"  Retrying in {backoff} seconds...")
                await asyncio.sleep(backoff)
            else:
                error_msg = f"Connection failed: {str(e)}"
                print(f"✗ {error_msg}")
                return False, None, error_msg
    
    # Should not reach here, but just in case
    return False, None, "Unknown error"


def get_wifi_status():
    """
    Get current WiFi connection status
    
    Returns:
        dict: WiFi status information
    """
    wlan = network.WLAN(network.STA_IF)
    
    if not wlan.active():
        return {
            "connected": False,
            "ip": None,
            "ssid": None,
            "rssi": None
        }
    
    if not wlan.isconnected():
        return {
            "connected": False,
            "ip": None,
            "ssid": None,
            "rssi": None
        }
    
    config = wlan.ifconfig()
    
    return {
        "connected": True,
        "ip": config[0],
        "netmask": config[1],
        "gateway": config[2],
        "dns": config[3],
        "ssid": wlan.config('essid'),
        "rssi": wlan.status('rssi')
    }
