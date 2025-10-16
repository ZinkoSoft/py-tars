"""
PCA9685 PWM Driver for ESP32 MicroPython
16-channel 12-bit PWM driver via I2C
Used for servo control with 50Hz frequency
"""

import time


# PCA9685 Register Definitions
MODE1 = 0x00
MODE2 = 0x01
PRESCALE = 0xFE
LED0_ON_L = 0x06
LED0_ON_H = 0x07
LED0_OFF_L = 0x08
LED0_OFF_H = 0x09


class PCA9685:
    """PCA9685 PWM driver class for servo control"""
    
    def __init__(self, i2c, address=0x40):
        """
        Initialize PCA9685 controller
        
        Args:
            i2c: I2C bus instance (machine.I2C)
            address: I2C address of PCA9685 (default 0x40)
        
        Raises:
            OSError: If PCA9685 not detected at specified address
        """
        self.i2c = i2c
        self.address = address
        
        # Verify device is present
        try:
            devices = self.i2c.scan()
            if self.address not in devices:
                raise OSError(f"PCA9685 not detected at address 0x{self.address:02X}")
        except Exception as e:
            raise OSError(f"PCA9685 not detected at address 0x{self.address:02X}") from e
        
        # Reset device
        self._write_reg(MODE1, 0x00)
        time.sleep_ms(5)
        
        print(f"PCA9685 initialized at address 0x{self.address:02X}")
    
    def set_pwm_freq(self, freq_hz):
        """
        Set PWM frequency for all channels
        
        Args:
            freq_hz: Frequency in Hz (typically 50Hz for servos)
        """
        # Calculate prescale value
        # prescale = round(25MHz / (4096 * freq)) - 1
        prescale_val = int(25000000.0 / (4096.0 * freq_hz) - 0.5)
        
        # Read old mode
        old_mode = self._read_reg(MODE1)
        
        # Sleep mode to change prescale
        new_mode = (old_mode & 0x7F) | 0x10  # Set sleep bit
        self._write_reg(MODE1, new_mode)
        
        # Set prescale
        self._write_reg(PRESCALE, prescale_val)
        
        # Restore old mode
        self._write_reg(MODE1, old_mode)
        time.sleep_ms(5)
        
        # Auto-increment mode
        self._write_reg(MODE1, old_mode | 0xA0)
        
        print(f"PCA9685 frequency set to {freq_hz}Hz (prescale={prescale_val})")
    
    def set_pwm(self, channel, on, off):
        """
        Set PWM values for a specific channel
        
        Args:
            channel: Channel number (0-15)
            on: 12-bit value (0-4095) when signal turns on
            off: 12-bit value (0-4095) when signal turns off
        """
        if not 0 <= channel <= 15:
            raise ValueError(f"Channel must be 0-15, got {channel}")
        if not 0 <= on <= 4095:
            raise ValueError(f"On value must be 0-4095, got {on}")
        if not 0 <= off <= 4095:
            raise ValueError(f"Off value must be 0-4095, got {off}")
        
        # Calculate register address for this channel
        reg_base = LED0_ON_L + (4 * channel)
        
        # Write 4 bytes: ON_L, ON_H, OFF_L, OFF_H
        try:
            self._write_reg(reg_base, on & 0xFF)
            self._write_reg(reg_base + 1, (on >> 8) & 0xFF)
            self._write_reg(reg_base + 2, off & 0xFF)
            self._write_reg(reg_base + 3, (off >> 8) & 0xFF)
        except OSError as e:
            # Retry once on I2C error
            time.sleep_ms(100)
            try:
                self._write_reg(reg_base, on & 0xFF)
                self._write_reg(reg_base + 1, (on >> 8) & 0xFF)
                self._write_reg(reg_base + 2, off & 0xFF)
                self._write_reg(reg_base + 3, (off >> 8) & 0xFF)
            except OSError:
                raise OSError(f"I2C communication error on channel {channel}") from e
    
    def _write_reg(self, reg, value):
        """Write a byte to a register"""
        self.i2c.writeto_mem(self.address, reg, bytes([value]))
    
    def _read_reg(self, reg):
        """Read a byte from a register"""
        return self.i2c.readfrom_mem(self.address, reg, 1)[0]
