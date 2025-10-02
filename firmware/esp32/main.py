# main.py - ESP32 Auto-start for TARS Movement Controller
# This file is automatically executed on boot by MicroPython

import sys

print("=" * 50)
print("TARS Movement Controller - Boot Sequence")
print("=" * 50)

try:
    # Import async support
    try:
        import uasyncio as asyncio
        import utime as time
    except ImportError:
        import asyncio
        import time
    
    # Small delay to let system stabilize
    time.sleep(1)
    
    print("[BOOT] Starting tars_controller.py...")
    
    # Import and run the TARS controller
    import tars_controller
    
    print("[BOOT] tars_controller.py loaded successfully")
    
    # Run the async main function with event loop
    if hasattr(tars_controller, 'main'):
        print("[BOOT] Starting async main loop...")
        
        # MicroPython doesn't have asyncio.run(), use get_event_loop()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(tars_controller.main())
        
    else:
        print("[BOOT] ERROR: tars_controller.py has no main() function")
        print("[BOOT] Module loaded but not started")
        
except KeyboardInterrupt:
    print("\n[BOOT] Interrupted by user")
    sys.exit(0)
    
except Exception as e:
    print(f"[BOOT] ERROR: Failed to start tars_controller.py")
    print(f"[BOOT] Exception: {e}")
    sys.print_exception(e)
    
    # Don't crash completely - allow REPL access for debugging
    print("[BOOT] Entering REPL mode for debugging...")

