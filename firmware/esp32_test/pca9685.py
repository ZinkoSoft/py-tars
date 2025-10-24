"""
PCA9685 PWM Driver for ESP32 MicroPython
- 16-channel, 12-bit PWM over I2C
- Servo-first ergonomics (50 Hz default), plus generic PWM helpers
- Proper PRE_SCALE sequence (SLEEP → write → wake → RESTART)
- MODE2 set to OUTDRV (totem-pole), OCH=0 (change on STOP)
"""

from machine import I2C
from time import sleep_ms, sleep_us

# Registers
MODE1      = 0x00
MODE2      = 0x01
SUBADR1    = 0x02
SUBADR2    = 0x03
SUBADR3    = 0x04
ALLCALLADR = 0x05
LED0_ON_L  = 0x06
LED0_ON_H  = 0x07
LED0_OFF_L = 0x08
LED0_OFF_H = 0x09
ALL_LED_ON_L  = 0xFA
ALL_LED_ON_H  = 0xFB
ALL_LED_OFF_L = 0xFC
ALL_LED_OFF_H = 0xFD
PRE_SCALE     = 0xFE

# MODE1 bits
RESTART = 0x80
EXTCLK  = 0x40
AI      = 0x20
SLEEP   = 0x10
ALLCALL = 0x01  # default on after POR per datasheet

# MODE2 bits
OUTDRV = 0x04  # totem pole (push-pull)
OCH    = 0x08  # 0=change on STOP (default), 1=change on ACK

# Special flags (bit 4 of *_H high byte)
FULL_ON_OFF_BIT = 0x10  # 1<<4

class PCA9685:
    """PCA9685 driver with servo helpers."""

    def __init__(self, i2c: I2C, address=0x40, osc_freq=25_000_000):
        self.i2c = i2c
        self.address = address
        self.osc_freq = osc_freq  # 25 MHz typical
        self.freq_hz = None

        # Confirm device present
        if address not in self.i2c.scan():
            raise OSError("PCA9685 not detected at 0x%02X" % address)

        # Set MODE2 (totem-pole), keep OCH=0 (change on STOP)
        self._write8(MODE2, OUTDRV)  # 0x04

        # Enable Auto-Increment in MODE1; leave ALLCALL as default (1)
        mode1 = self._read8(MODE1)
        mode1 = (mode1 | AI) & ~SLEEP  # ensure AI on, not sleeping
        self._write8(MODE1, mode1)
        sleep_ms(1)

    # ---------- Low-level I2C ----------
    def _write8(self, reg, val):
        self.i2c.writeto_mem(self.address, reg, bytes([val & 0xFF]))

    def _read8(self, reg):
        return self.i2c.readfrom_mem(self.address, reg, 1)[0]

    def _write4(self, reg_base, b0, b1, b2, b3):
        # Single I2C burst for ON_L/H, OFF_L/H
        self.i2c.writeto_mem(self.address, reg_base, bytes([b0, b1, b2, b3]))

    # ---------- Core features ----------
    def set_pwm_freq(self, freq_hz: int):
        """Set global PWM frequency (Hz). Servos typically use 50 Hz."""
        # clamp to legal range (~24..1526 Hz per datasheet)
        if freq_hz < 24: freq_hz = 24
        if freq_hz > 1526: freq_hz = 1526

        # Compute prescale per datasheet: round(osc/(4096*freq)) - 1
        prescale_f = self.osc_freq / (4096 * freq_hz)
        prescale = int(round(prescale_f) - 1)

        oldmode = self._read8(MODE1)
        sleepmode = (oldmode | SLEEP) & 0xFF
        self._write8(MODE1, sleepmode)          # go to sleep to allow PRE_SCALE write
        self._write8(PRE_SCALE, prescale)       # write prescale
        self._write8(MODE1, oldmode & ~SLEEP)   # wake
        sleep_us(500)                           # datasheet: 500 us max for oscillator to stabilize
        self._write8(MODE1, oldmode | RESTART)  # restart PWM channels

        self.freq_hz = freq_hz

    def set_pwm(self, channel: int, on: int, off: int):
        """Raw 12-bit PWM window. on/off in [0..4095]."""
        if not 0 <= channel <= 15:
            raise ValueError("Channel 0-15")
        if not (0 <= on <= 4095 and 0 <= off <= 4095):
            raise ValueError("on/off must be 0..4095")

        base = LED0_ON_L + 4 * channel
        self._write4(base, on & 0xFF, (on >> 8) & 0x0F, off & 0xFF, (off >> 8) & 0x0F)

    def set_duty_cycle(self, channel: int, duty_0_1: float, phase_ticks: int = 0):
        """
        Set duty cycle as 0.0..1.0 with optional phase offset.
        
        Args:
            channel: PWM channel (0-15)
            duty_0_1: Duty cycle (0.0=off, 1.0=full on)
            phase_ticks: Phase offset in ticks (0-4095). If on+ticks >= 4096,
                        off wraps around, creating inverted duty behavior.
        """
        duty_0_1 = 0.0 if duty_0_1 < 0 else (1.0 if duty_0_1 > 1 else duty_0_1)
        ticks = int(duty_0_1 * 4096)
        if ticks <= 0:
            self.channel_full_off(channel)
            return
        if ticks >= 4096:
            self.channel_full_on(channel)
            return
        on = phase_ticks % 4096
        off = (on + ticks) % 4096
        self.set_pwm(channel, on, off)

    # ---------- Full ON/OFF helpers (bit 4 in *_H) ----------
    def channel_full_on(self, channel: int):
        """Set channel to full ON (100% duty), ignoring PWM counter."""
        base = LED0_ON_L + 4 * channel
        # ON_H bit 4 = 1, OFF counts don't care
        self._write4(base, 0x00, FULL_ON_OFF_BIT, 0x00, 0x00)

    def channel_full_off(self, channel: int):
        """Set channel to full OFF (0% duty), ignoring PWM counter."""
        base = LED0_ON_L + 4 * channel
        # OFF_H bit 4 = 1
        self._write4(base, 0x00, 0x00, 0x00, FULL_ON_OFF_BIT)

    def all_full_off(self):
        """Turn off all channels simultaneously."""
        self._write8(ALL_LED_OFF_H, FULL_ON_OFF_BIT)

    # ---------- Servo helpers ----------
    def pulse_us_to_ticks(self, pulse_us: float) -> int:
        if self.freq_hz is None:
            raise RuntimeError("Call set_pwm_freq() first")
        # ticks = pulse_us * freq * 4096 / 1e6
        t = int(round(pulse_us * self.freq_hz * 4096 / 1_000_000))
        if t < 0: t = 0
        if t > 4095: t = 4095
        return t

    def set_pwm_us(self, channel: int, pulse_us: float, phase_ticks: int = 0):
        """
        Set PWM pulse width in microseconds.
        
        Requires set_pwm_freq() to be called first.
        """
        ticks = self.pulse_us_to_ticks(pulse_us)
        on = phase_ticks % 4096
        off = (on + ticks) % 4096
        self.set_pwm(channel, on, off)

    def set_servo_angle(self, channel: int, angle_deg: float,
                        min_us=500, max_us=2500, phase_ticks: int = 0):
        """Map 0..180° to pulse width. Tune min_us/max_us per servo."""
        if angle_deg < 0: angle_deg = 0
        if angle_deg > 180: angle_deg = 180
        pulse = min_us + (max_us - min_us) * (angle_deg / 180.0)
        self.set_pwm_us(channel, pulse, phase_ticks)

    # ---------- Power / reset ----------
    def sleep(self):
        """Put PCA9685 into low-power sleep mode (stops PWM oscillator)."""
        self._write8(MODE1, self._read8(MODE1) | SLEEP)

    def wake(self):
        """Wake PCA9685 from sleep mode (restarts PWM oscillator)."""
        self._write8(MODE1, self._read8(MODE1) & ~SLEEP)
        sleep_us(500)  # wait for oscillator to stabilize

    def software_reset(self):
        """
        I2C general call software reset (SWRST).
        
        Resets all PCA9685 devices on the bus. May not work on all
        I2C implementations.
        """
        try:
            # General Call address 0x00 with 0x06 triggers Software Reset
            self.i2c.writeto(0x00, b'\x06')
        except OSError:
            pass  # some I2C implementations don't support general call