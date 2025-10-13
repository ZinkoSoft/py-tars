"""
TARS Servo Tester - Web Interface Entry Point
MicroPython for ESP32 with PCA9685

Run this file to start the web server.
Access the UI from your browser at the displayed IP address.
"""

from web_interface import main

# Start the web interface automatically
# AP mode will activate if WiFi connection fails
main()
