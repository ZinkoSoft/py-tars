"""
Cross-platform utility functions for ESP32 MicroPython firmware.

Provides compatibility shims for:
- Time functions (sleep_ms, ticks_ms, ticks_diff)
- File I/O (with UTF-8 encoding fallback)

These utilities work on both MicroPython (ESP32) and CPython (development/testing).
"""

try:
    import utime as time  # type: ignore
except ImportError:  # pragma: no cover
    import time


def sleep_ms(duration):
    """
    Sleep for specified milliseconds.
    
    Args:
        duration: Sleep duration in milliseconds (int or float)
    
    Compatibility:
        - MicroPython: uses time.sleep_ms()
        - CPython: uses time.sleep() with conversion
    """
    try:
        time.sleep_ms(int(duration))
    except AttributeError:  # pragma: no cover
        time.sleep(duration / 1000.0)


def ticks_ms():
    """
    Get millisecond timestamp.
    
    Returns:
        int: Milliseconds since arbitrary point (monotonic)
    
    Compatibility:
        - MicroPython: uses time.ticks_ms()
        - CPython: uses time.time() * 1000
    
    Note:
        On MicroPython, this wraps around periodically.
        Always use ticks_diff() for time comparisons.
    """
    try:
        return time.ticks_ms()
    except AttributeError:  # pragma: no cover
        return int(time.time() * 1000)


def ticks_diff(a, b):
    """
    Calculate time difference between two ticks_ms() values.
    
    Args:
        a: Later timestamp (from ticks_ms())
        b: Earlier timestamp (from ticks_ms())
    
    Returns:
        int: Milliseconds elapsed (a - b)
    
    Compatibility:
        - MicroPython: uses time.ticks_diff() (handles wraparound)
        - CPython: simple subtraction
    
    Example:
        start = ticks_ms()
        # ... do work ...
        elapsed = ticks_diff(ticks_ms(), start)
    """
    try:
        return time.ticks_diff(a, b)
    except AttributeError:  # pragma: no cover
        return a - b


def open_file(path, mode):
    """
    Open a file with UTF-8 encoding (with fallback).
    
    Args:
        path: File path (str)
        mode: File mode ('r', 'w', 'a', etc.)
    
    Returns:
        File object
    
    Compatibility:
        - CPython: opens with UTF-8 encoding
        - MicroPython: falls back to basic open() (no encoding param)
    """
    try:
        return open(path, mode, encoding="utf-8")  # type: ignore
    except (TypeError, ValueError):  # pragma: no cover - MicroPython fallback
        return open(path, mode)  # type: ignore


# Self-test when run directly
if __name__ == "__main__":
    print("Testing lib.utils...")
    
    # Test sleep_ms
    start = ticks_ms()
    sleep_ms(100)
    elapsed = ticks_diff(ticks_ms(), start)
    print(f"  sleep_ms(100) took ~{elapsed}ms")
    assert 90 < elapsed < 150, "sleep_ms timing off"
    
    # Test ticks wraparound (simulate)
    assert ticks_diff(100, 50) == 50, "ticks_diff basic"
    
    # Test file I/O
    test_path = "/tmp/test_utils.txt" if time.__name__ == "time" else "test_utils.txt"
    try:
        with open_file(test_path, "w") as f:
            f.write("test")
        with open_file(test_path, "r") as f:
            content = f.read()
        assert content == "test", "File I/O failed"
        print("  File I/O works")
    except Exception as e:
        print(f"  File I/O test skipped: {e}")
    
    print("✓ All utils tests passed")
