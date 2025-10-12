"""
boot.py - Runs on ESP32 boot
Basic setup and configuration
"""

import gc
import esp
import machine

# Disable ESP32 debug output
esp.osdebug(None)

# Enable garbage collection
gc.enable()

# Optional: Set frequency (240MHz is max for ESP32)
machine.freq(240000000)

print("\n" + "="*50)
print("ESP32 Booting - TARS Servo Controller")
print(f"CPU Freq: {machine.freq()/1000000:.0f}MHz")
print(f"Free Memory: {gc.mem_free()} bytes")
print("="*50 + "\n")
