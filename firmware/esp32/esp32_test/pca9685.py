"""
PCA9685 PWM Servo Driver for MicroPython
Adapted for ESP32 from Adafruit CircuitPython library
"""

from machine import I2C, Pin
import time

# Registers
PCA9685_ADDRESS = 0x40
MODE1 = 0x00
MODE2 = 0x01
SUBADR1 = 0x02
SUBADR2 = 0x03
SUBADR3 = 0x04
PRESCALE = 0xFE
LED0_ON_L = 0x06
LED0_ON_H = 0x07
LED0_OFF_L = 0x08
LED0_OFF_H = 0x09
ALL_LED_ON_L = 0xFA
ALL_LED_ON_H = 0xFB
ALL_LED_OFF_L = 0xFC
ALL_LED_OFF_H = 0xFD

# Bits
RESTART = 0x80
SLEEP = 0x10
ALLCALL = 0x01
INVRT = 0x10
OUTDRV = 0x04


class PCA9685:
    """PCA9685 PWM LED/Servo controller for MicroPython on ESP32"""
    
    def __init__(self, i2c=None, address=PCA9685_ADDRESS, sda_pin=8, scl_pin=9):
        """
        Initialize PCA9685
        
        Args:
            i2c: Pre-configured I2C object (optional)
            address: I2C address of PCA9685 (default 0x40)
            sda_pin: GPIO pin for SDA (default 8 for YD-ESP32-S3)
            scl_pin: GPIO pin for SCL (default 9 for YD-ESP32-S3)
        """
        if i2c is None:
            # 100kHz confirmed working by I2C scanner
            self.i2c = I2C(0, sda=Pin(sda_pin), scl=Pin(scl_pin), freq=100000)
        else:
            self.i2c = i2c
            
        self.address = address
        
        # Scan for device
        devices = self.i2c.scan()
        if self.address not in devices:
            raise OSError(f"PCA9685 not found at address 0x{self.address:02X}")
        
        print(f"PCA9685 found at address 0x{self.address:02X}")
        
        # Reset device
        self._write_register(MODE1, 0x00)
        time.sleep_ms(5)
    
    def _write_register(self, register, value):
        """Write a byte to a register"""
        self.i2c.writeto_mem(self.address, register, bytes([value]))
    
    def _read_register(self, register):
        """Read a byte from a register"""
        return self.i2c.readfrom_mem(self.address, register, 1)[0]
    
    def set_pwm_freq(self, freq_hz):
        """
        Set the PWM frequency
        
        Args:
            freq_hz: Frequency in Hz (typically 50Hz for servos)
        """
        prescaleval = 25000000.0    # 25MHz
        prescaleval /= 4096.0       # 12-bit
        prescaleval /= float(freq_hz)
        prescaleval -= 1.0
        
        prescale = int(prescaleval + 0.5)
        
        oldmode = self._read_register(MODE1)
        newmode = (oldmode & 0x7F) | SLEEP  # sleep
        self._write_register(MODE1, newmode)  # go to sleep
        self._write_register(PRESCALE, prescale)
        self._write_register(MODE1, oldmode)
        time.sleep_ms(5)
        self._write_register(MODE1, oldmode | RESTART)
        
        print(f"PWM frequency set to {freq_hz}Hz")
    
    def set_pwm(self, channel, on, off):
        """
        Set PWM values for a channel
        
        Args:
            channel: Channel number (0-15)
            on: 12-bit value for when to turn on (0-4095)
            off: 12-bit value for when to turn off (0-4095)
        """
        if channel < 0 or channel > 15:
            raise ValueError("Channel must be 0-15")
        
        self.i2c.writeto_mem(self.address, LED0_ON_L + 4 * channel, 
                            bytes([on & 0xFF]))
        self.i2c.writeto_mem(self.address, LED0_ON_H + 4 * channel, 
                            bytes([on >> 8]))
        self.i2c.writeto_mem(self.address, LED0_OFF_L + 4 * channel, 
                            bytes([off & 0xFF]))
        self.i2c.writeto_mem(self.address, LED0_OFF_H + 4 * channel, 
                            bytes([off >> 8]))
    
    def set_all_pwm(self, on, off):
        """
        Set PWM for all channels at once
        
        Args:
            on: 12-bit value for when to turn on (0-4095)
            off: 12-bit value for when to turn off (0-4095)
        """
        self.i2c.writeto_mem(self.address, ALL_LED_ON_L, bytes([on & 0xFF]))
        self.i2c.writeto_mem(self.address, ALL_LED_ON_H, bytes([on >> 8]))
        self.i2c.writeto_mem(self.address, ALL_LED_OFF_L, bytes([off & 0xFF]))
        self.i2c.writeto_mem(self.address, ALL_LED_OFF_H, bytes([off >> 8]))
    
    def set_servo_pulse(self, channel, pulse_us):
        """
        Set servo position using pulse width in microseconds
        
        Args:
            channel: Servo channel (0-15)
            pulse_us: Pulse width in microseconds (typically 500-2500)
        """
        # Calculate pulse length for 50Hz (20ms period)
        pulse_length = 1000000    # 1,000,000 us per second
        pulse_length //= 50       # 50 Hz
        pulse_length //= 4096     # 12 bits of resolution
        
        pulse = int((pulse_us * 4096) / 20000)
        self.set_pwm(channel, 0, pulse)
    
    def disable_all_servos(self):
        """Disable all servos (set PWM to 0)"""
        self.set_all_pwm(0, 0)
        print("All servos disabled")
