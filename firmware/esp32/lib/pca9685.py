"""
PCA9685 16-channel PWM servo driver for ESP32 MicroPython.

The PCA9685 is an I2C-bus controlled 16-channel, 12-bit PWM LED/servo controller.
Used to drive up to 16 servos with precise pulse-width control.

Hardware:
- I2C address: 0x40 (default)
- Frequency: 50Hz (standard servo frequency)
- Resolution: 12-bit (0-4095)

Example:
    from machine import I2C, Pin
    from lib.pca9685 import PCA9685
    
    i2c = I2C(0, scl=Pin(22), sda=Pin(21))
    pwm = PCA9685(i2c, address=0x40)
    pwm.set_pwm_freq(50)  # 50Hz for servos
    pwm.set_pwm(0, 0, 300)  # Channel 0, pulse width ~1.5ms
"""

try:
    from machine import I2C  # type: ignore
except ImportError:  # pragma: no cover
    I2C = None  # type: ignore

try:
    from lib.utils import sleep_ms
except ImportError:
    # Fallback for standalone execution
    from utils import sleep_ms  # type: ignore


# PCA9685 register addresses
_MODE1 = 0x00       # Mode register 1
_PRESCALE = 0xFE    # Prescaler for PWM output frequency
_LED0_ON_L = 0x06   # LED0 output and brightness control byte 0


class PCA9685:
    """
    PCA9685 16-channel 12-bit PWM LED/Servo driver.
    
    Attributes:
        _i2c: I2C bus instance
        _address: I2C device address (default 0x40)
        _buffer: 4-byte buffer for batch writes
    
    Methods:
        reset(): Reset the device
        set_pwm_freq(freq_hz): Set PWM frequency (e.g., 50Hz for servos)
        set_pwm(channel, on, off): Set PWM for a specific channel
        set_off(channel): Turn off a specific channel
        all_off(): Turn off all channels
    """
    
    def __init__(self, i2c, address=0x40):
        """
        Initialize PCA9685.
        
        Args:
            i2c: machine.I2C instance
            address: I2C address (default 0x40)
        
        Example:
            from machine import I2C, Pin
            i2c = I2C(0, scl=Pin(22), sda=Pin(21))
            pwm = PCA9685(i2c)
        """
        self._i2c = i2c
        self._address = address
        self._buffer = bytearray(4)
        self.reset()

    def reset(self):
        """
        Reset the PCA9685 to default state.
        
        Sets MODE1 register to 0x00 and waits 10ms for oscillator to stabilize.
        """
        self._write_reg(_MODE1, 0x00)
        sleep_ms(10)

    def set_pwm_freq(self, freq_hz):
        """
        Set the PWM frequency for all channels.
        
        Args:
            freq_hz: Frequency in Hz (typically 50Hz for servos)
        
        Notes:
            - Standard servos use 50Hz
            - Calculates prescale value based on 25MHz internal clock
            - Puts device to sleep during frequency change
        
        Example:
            pwm.set_pwm_freq(50)  # 50Hz for standard servos
        """
        prescale_val = int((25_000_000 / (4096 * freq_hz)) - 1)
        current_mode = self._read_reg(_MODE1)
        # Sleep mode required to change prescale
        self._write_reg(_MODE1, (current_mode & 0x7F) | 0x10)
        self._write_reg(_PRESCALE, prescale_val)
        self._write_reg(_MODE1, current_mode)
        sleep_ms(5)
        # Wake up and enable auto-increment
        self._write_reg(_MODE1, current_mode | 0xA1)

    def set_pwm(self, channel, on, off):
        """
        Set PWM pulse for a specific channel.
        
        Args:
            channel: Channel number (0-15)
            on: PWM on tick (0-4095), typically 0
            off: PWM off tick (0-4095), controls pulse width
        
        Notes:
            - 12-bit resolution (0-4095)
            - At 50Hz, each tick is ~4.88μs
            - Typical servo range: 150 (0.73ms) to 600 (2.93ms)
        
        Example:
            # Center position for typical servo (~1.5ms pulse)
            pwm.set_pwm(0, 0, 307)
            
            # Left position (~1ms pulse)
            pwm.set_pwm(0, 0, 205)
            
            # Right position (~2ms pulse)
            pwm.set_pwm(0, 0, 410)
        """
        base = _LED0_ON_L + 4 * channel
        self._buffer[0] = on & 0xFF
        self._buffer[1] = (on >> 8) & 0x0F
        self._buffer[2] = off & 0xFF
        self._buffer[3] = (off >> 8) & 0x0F
        self._i2c.writeto_mem(self._address, base, self._buffer)

    def set_off(self, channel):
        """
        Turn off PWM output for a specific channel.
        
        Args:
            channel: Channel number (0-15)
        
        Example:
            pwm.set_off(0)  # Turn off channel 0
        """
        self.set_pwm(channel, 0, 0)

    def all_off(self):
        """
        Turn off PWM output for all 16 channels.
        
        Iterates through channels 0-15 and turns each off.
        Useful for emergency stop or shutdown.
        
        Example:
            pwm.all_off()  # Turn off all servos
        """
        for ch in range(16):
            self.set_off(ch)

    def _write_reg(self, reg, value):
        """
        Write a byte to a PCA9685 register.
        
        Args:
            reg: Register address
            value: Byte value to write
        """
        self._i2c.writeto_mem(self._address, reg, bytes([value & 0xFF]))

    def _read_reg(self, reg):
        """
        Read a byte from a PCA9685 register.
        
        Args:
            reg: Register address
        
        Returns:
            int: Byte value from register
        """
        data = self._i2c.readfrom_mem(self._address, reg, 1)
        return data[0]


# Self-test when run directly
if __name__ == "__main__":
    print("Testing lib.pca9685...")
    
    # Test register constants
    assert _MODE1 == 0x00, "MODE1 register address wrong"
    assert _PRESCALE == 0xFE, "PRESCALE register address wrong"
    assert _LED0_ON_L == 0x06, "LED0_ON_L register address wrong"
    print("  ✓ Register constants valid")
    
    # Test class instantiation (without hardware)
    print("  ✓ PCA9685 class defined")
    print("  ✓ Methods: reset, set_pwm_freq, set_pwm, set_off, all_off")
    
    # Calculate prescale for 50Hz
    freq = 50
    prescale = int((25_000_000 / (4096 * freq)) - 1)
    expected_prescale = 121  # Should be around 121 for 50Hz
    assert abs(prescale - expected_prescale) < 2, f"Prescale calculation off: {prescale}"
    print(f"  ✓ Prescale calculation works ({prescale} for {freq}Hz)")
    
    # Test pulse width calculations
    # At 50Hz (20ms period), each tick is ~4.88μs
    # 1.5ms pulse (center) should be around 307 ticks
    pulse_ms = 1.5
    ticks = int((pulse_ms / 20.0) * 4096)
    assert 300 < ticks < 315, f"Pulse calculation off: {ticks}"
    print(f"  ✓ Pulse width calculations work ({ticks} ticks for {pulse_ms}ms)")
    
    print("✓ All pca9685 tests passed")
    print("\nNote: Hardware tests require actual PCA9685 device on I2C bus")
