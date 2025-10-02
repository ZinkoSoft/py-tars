"""
LED status indicator module for ESP32 TARS firmware.

Supports multiple LED types:
- NeoPixel (WS2812) RGB LEDs (preferred)
- Individual RGB PWM channels
- Single-channel PWM LED (legacy)
- Digital GPIO LED (basic on/off)

Status Colors:
- Cyan (0.0, 1.0, 1.0): System booting
- Red breathing: No WiFi / Setup portal mode
- Yellow blinking (1.0, 1.0, 0.0): MQTT error
- Green (0.0, 1.0, 0.0): Fully operational

Example:
    from machine import Pin
    from lib.led_status import LEDStatus
    
    # NeoPixel LED on GPIO 48
    led = LEDStatus(status_led=48)
    led.set_color(0.0, 1.0, 0.0)  # Green = operational
    
    # Breathing red effect for portal mode
    while in_portal_mode:
        led.update_breathing()
        sleep_ms(50)
"""

try:
    from machine import Pin  # type: ignore
    import machine  # type: ignore
except ImportError:  # pragma: no cover
    Pin = None  # type: ignore
    machine = None  # type: ignore

try:
    import math
except Exception:  # pragma: no cover
    math = None

try:
    from lib.utils import ticks_ms, ticks_diff
except ImportError:
    # Fallback for standalone execution
    from utils import ticks_ms, ticks_diff  # type: ignore


# Status color constants
COLOR_CYAN = (0.0, 1.0, 1.0)      # System booting
COLOR_RED = (1.0, 0.0, 0.0)       # Error / No WiFi
COLOR_YELLOW = (1.0, 1.0, 0.0)    # MQTT error
COLOR_GREEN = (0.0, 1.0, 0.0)     # Operational
COLOR_OFF = (0.0, 0.0, 0.0)       # Off


class LEDStatus:
    """
    Unified LED status indicator supporting multiple LED types.
    
    Attributes:
        _np: NeoPixel object (if using WS2812 RGB LED)
        _led_pwm: PWM object (if using single PWM LED)
        _led: Pin object (if using digital LED)
        _led_rgb_pwms: Dict of RGB PWM objects
        _led_rgb_pins: Dict of RGB Pin objects
        _last_mode: Tuple tracking last LED state (for debug logging)
        _last_led_print: Timestamp of last debug print
        _breathe_level: Current breathing effect level (0.0-1.0)
        _breathe_last_update: Timestamp of last breathing update
    """
    
    def __init__(self, status_led=None):
        """
        Initialize LED status indicator.
        
        Args:
            status_led: LED configuration (int pin, dict of RGB pins, or None)
                - int: Single pin for NeoPixel or PWM LED
                - dict: {"r": pin, "g": pin, "b": pin} for RGB PWM
                - None: No LED (no-op)
        
        Example:
            # NeoPixel on GPIO 48
            led = LEDStatus(48)
            
            # RGB PWM LEDs
            led = LEDStatus({"r": 25, "g": 26, "b": 27})
            
            # No LED
            led = LEDStatus(None)
        """
        self._np = None
        self._led_pwm = None
        self._led = None
        self._led_rgb_pwms = {}
        self._led_rgb_pins = {}
        self._last_mode = None
        self._last_led_print = ticks_ms()
        self._breathe_level = 0.0
        self._breathe_last_update = ticks_ms()
        
        if status_led is None or Pin is None or machine is None:
            return
        
        # Try to import NeoPixel
        try:
            from neopixel import NeoPixel  # type: ignore
        except Exception:
            NeoPixel = None  # type: ignore
        
        PWM = getattr(machine, "PWM", None)
        
        # RGB mapping (dict config)
        if isinstance(status_led, dict):
            # Allow keys: r, g, b or red, green, blue
            key_map = {"r": None, "g": None, "b": None}
            for k in ("r", "g", "b", "red", "green", "blue"):
                if k in status_led:
                    short = k[0]
                    key_map[short] = status_led[k]
            
            for col, pin_num in key_map.items():
                if pin_num is None:
                    continue
                try:
                    if PWM is not None:
                        p = PWM(Pin(pin_num))
                        try:
                            p.freq(1000)
                        except Exception:
                            pass
                        try:
                            p.duty_u16(0)
                        except Exception:
                            try:
                                p.duty(0)
                            except Exception:
                                pass
                        self._led_rgb_pwms[col] = p
                    else:
                        self._led_rgb_pins[col] = Pin(pin_num, Pin.OUT)
                except Exception:
                    try:
                        self._led_rgb_pins[col] = Pin(pin_num, Pin.OUT)
                    except Exception:
                        pass
        
        # Single pin (NeoPixel or PWM)
        else:
            # Prefer NeoPixel if available
            if NeoPixel is not None:
                try:
                    self._np = NeoPixel(Pin(status_led), 1)
                except Exception:
                    pass
            
            # Fallback to PWM
            if self._np is None and PWM is not None:
                try:
                    p = PWM(Pin(status_led))
                    try:
                        p.freq(1000)
                    except Exception:
                        pass
                    try:
                        p.duty_u16(0)
                    except Exception:
                        try:
                            p.duty(0)
                        except Exception:
                            pass
                    self._led_pwm = p
                except Exception:
                    pass
            
            # Last resort: digital pin
            if self._np is None and self._led_pwm is None:
                try:
                    self._led = Pin(status_led, Pin.OUT)
                    self._led.value(0)
                except Exception:
                    pass
    
    def set_power(self, level):
        """
        Set single-channel LED brightness (0.0-1.0).
        
        Args:
            level: Brightness level (0.0 = off, 1.0 = full)
        
        Notes:
            - Used for single-pin PWM or digital LEDs
            - Digital LEDs use threshold (>0.5 = on)
        
        Example:
            led.set_power(0.5)  # 50% brightness
        """
        try:
            level = max(0.0, min(1.0, level))
            
            # PWM LED
            if self._led_pwm is not None:
                try:
                    self._led_pwm.duty_u16(int(level * 65535))
                    self._debug_print("power", level)
                    return
                except Exception:
                    pass
                try:
                    self._led_pwm.duty(int(level * 1023))
                    self._debug_print("power", level)
                    return
                except Exception:
                    pass
            
            # Digital LED
            if self._led is not None:
                try:
                    self._led.value(1 if level > 0.5 else 0)
                    self._debug_print("digital", 1 if level > 0.5 else 0)
                except Exception:
                    pass
        except Exception:
            pass
    
    def set_color(self, r, g, b):
        """
        Set LED color (0.0-1.0 for each channel).
        
        Args:
            r: Red channel (0.0-1.0)
            g: Green channel (0.0-1.0)
            b: Blue channel (0.0-1.0)
        
        Notes:
            - Works with NeoPixel, RGB PWM, or single-channel LEDs
            - Single-channel LEDs use brightness = max(g, (r+g)/2)
        
        Example:
            led.set_color(0.0, 1.0, 0.0)  # Green
            led.set_color(1.0, 1.0, 0.0)  # Yellow
            led.set_color(0.0, 1.0, 1.0)  # Cyan
        """
        try:
            # Normalize
            r = max(0.0, min(1.0, r))
            g = max(0.0, min(1.0, g))
            b = max(0.0, min(1.0, b))
            
            # RGB PWM channels
            if any(self._led_rgb_pwms.values()):
                for col, val in (("r", r), ("g", g), ("b", b)):
                    p = self._led_rgb_pwms.get(col)
                    if p is not None:
                        try:
                            p.duty_u16(int(val * 65535))
                            continue
                        except Exception:
                            pass
                        try:
                            p.duty(int(val * 1023))
                            continue
                        except Exception:
                            pass
                    # Pin-level fallback
                    pin = self._led_rgb_pins.get(col)
                    if pin is not None:
                        try:
                            pin.value(1 if val > 0.5 else 0)
                        except Exception:
                            pass
                return
            
            # NeoPixel
            if self._np is not None:
                try:
                    rgb_tuple = (int(r * 255), int(g * 255), int(b * 255))
                    self._np[0] = rgb_tuple
                    self._np.write()
                    self._debug_print("rgb", rgb_tuple)
                    return
                except Exception:
                    pass
            
            # Single-channel fallback
            # Map color to brightness: green steady -> use g; yellow ~ average of r+g
            brightness = max(g, (r + g) / 2.0)
            self.set_power(brightness)
        except Exception:
            pass
    
    def update_breathing(self, now=None):
        """
        Update red breathing effect (for WiFi portal mode).
        
        Args:
            now: Current timestamp (from ticks_ms()), or None for auto
        
        Notes:
            - 3-second breathing cycle
            - Smooth sinusoidal fade with gamma correction
            - Call repeatedly in loop for animation
        
        Example:
            while in_portal_mode:
                led.update_breathing()
                sleep_ms(50)
        """
        try:
            if now is None:
                now = ticks_ms()
            
            # 3-second breathing cycle
            period = 3000
            t = (now % period) / float(period)
            
            # Sinusoidal breathing pattern
            if math is not None:
                target = 0.5 * (1 - math.cos(2 * math.pi * t))
            else:
                # Triangle wave fallback
                target = 1 - abs(2 * t - 1)
            target = max(0.0, min(1.0, target))
            
            # Smooth transition
            dt_ms = ticks_diff(now, self._breathe_last_update)
            if dt_ms <= 0 or dt_ms > 5000:
                self._breathe_level = target
            else:
                smoothing = min(1.0, dt_ms / 400.0)
                self._breathe_level += (target - self._breathe_level) * smoothing
            self._breathe_last_update = now
            
            # Gamma correction for perceptual linearity
            level = max(0.0, min(1.0, self._breathe_level))
            try:
                gamma = 2.2
                if math is not None and hasattr(math, "pow"):
                    level_gamma = math.pow(level, gamma)
                else:
                    level_gamma = level ** gamma
            except Exception:
                level_gamma = level
            
            # Set red color with breathing level
            if self._np is not None or self._led_rgb_pwms or self._led_rgb_pins:
                self.set_color(level_gamma, 0.0, 0.0)
            else:
                self.set_power(level_gamma)
        except Exception:
            pass
    
    def _debug_print(self, mode_type, value):
        """Internal: Print LED changes to console (rate-limited)."""
        try:
            now = ticks_ms()
            if self._last_mode != (mode_type, value) and ticks_diff(now, self._last_led_print) > 2000:
                try:
                    print(f'LED {mode_type} set to {value}')
                except Exception:
                    pass
                self._last_led_print = now
                self._last_mode = (mode_type, value)
        except Exception:
            pass


# Self-test when run directly
if __name__ == "__main__":
    print("Testing lib.led_status...")
    
    # Test color constants
    assert COLOR_CYAN == (0.0, 1.0, 1.0), "CYAN color wrong"
    assert COLOR_RED == (1.0, 0.0, 0.0), "RED color wrong"
    assert COLOR_YELLOW == (1.0, 1.0, 0.0), "YELLOW color wrong"
    assert COLOR_GREEN == (0.0, 1.0, 0.0), "GREEN color wrong"
    print("  ✓ Color constants valid")
    
    # Test class instantiation (without hardware)
    led = LEDStatus(None)  # No LED
    print("  ✓ LEDStatus instantiates with None")
    
    # Test methods exist
    assert hasattr(led, 'set_color'), "Missing set_color method"
    assert hasattr(led, 'set_power'), "Missing set_power method"
    assert hasattr(led, 'update_breathing'), "Missing update_breathing method"
    print("  ✓ Methods: set_color, set_power, update_breathing")
    
    # Test no-op calls (no hardware)
    led.set_color(1.0, 0.0, 0.0)  # Should not crash
    led.set_power(0.5)  # Should not crash
    led.update_breathing()  # Should not crash
    print("  ✓ No-op calls work without hardware")
    
    # Test breathing calculations
    import time
    start = int(time.time() * 1000)
    led._breathe_last_update = start
    led.update_breathing(start + 750)  # 1/4 through 3s cycle
    assert 0.0 <= led._breathe_level <= 1.0, f"Breathing level out of range: {led._breathe_level}"
    print(f"  ✓ Breathing calculations work (level: {led._breathe_level:.2f})")
    
    print("✓ All led_status tests passed")
    print("\nNote: Hardware tests require actual LED connected to GPIO")
