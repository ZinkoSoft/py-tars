# main.py - ESP32 Auto-start for TARS Movement Controller
# This file is automatically executed on boot by MicroPython

import time
import sys

print("=" * 50)
print("TARS Movement Controller - Boot Sequence")
print("=" * 50)

try:
    # Small delay to let system stabilize
    time.sleep(1)
    
    print("[BOOT] Starting tars_controller.py...")
    
    # Import and run the TARS controller
    import tars_controller
    
    print("[BOOT] tars_controller.py loaded successfully")
    
    # The tars_controller module should handle its own main loop
    # If it has a main() or run() function, call it here
    if hasattr(tars_controller, 'main'):
        tars_controller.main()
    elif hasattr(tars_controller, 'run'):
        tars_controller.run()
    else:
        print("[BOOT] tars_controller.py has no main() or run() function")
        print("[BOOT] Module loaded but not started")
        
except KeyboardInterrupt:
    print("\n[BOOT] Interrupted by user")
    sys.exit(0)
    
except Exception as e:
    print(f"[BOOT] ERROR: Failed to start tars_controller.py")
    print(f"[BOOT] Exception: {e}")
    import sys
    sys.print_exception(e)
    
    # Don't crash completely - allow REPL access for debugging
    print("[BOOT] Entering REPL mode for debugging...")

