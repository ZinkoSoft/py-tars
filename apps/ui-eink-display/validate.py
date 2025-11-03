#!/usr/bin/env python3
"""
Quick validation script for ui-eink-display service.

Tests that all modules can be imported and basic functionality works.
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

print("🔍 Validating ui-eink-display service...")

try:
    # Test imports
    print("  ✓ Importing config...")
    from ui_eink_display.config import DisplayConfig
    
    print("  ✓ Importing display_state...")
    from ui_eink_display.display_state import DisplayMode, DisplayState, MessageBubble
    
    print("  ✓ Importing display_manager...")
    from ui_eink_display.display_manager import DisplayManager, MockDisplay
    
    print("  ✓ Importing message_formatter...")
    from ui_eink_display.message_formatter import MessageFormatter, LayoutConstraints
    
    print("  ✓ Importing mqtt_handler...")
    from ui_eink_display.mqtt_handler import MQTTHandler
    
    print("  ✓ Importing __main__...")
    import ui_eink_display.__main__
    
    # Test basic functionality
    print("\n🧪 Testing basic functionality...")
    
    print("  ✓ Creating DisplayState...")
    state = DisplayState()
    assert state.mode == DisplayMode.STANDBY
    
    print("  ✓ Testing state transitions...")
    state.transition_to(DisplayMode.LISTENING)
    assert state.mode == DisplayMode.LISTENING
    
    print("  ✓ Testing message creation...")
    bubble = MessageBubble(text="Test message", is_user=True)
    assert bubble.text == "Test message"
    assert bubble.is_user is True
    
    print("  ✓ Testing message formatter...")
    formatter = MessageFormatter()
    lines = formatter.wrap_text("This is a test message", max_chars=10)
    assert len(lines) > 1
    
    print("  ✓ Testing layout constraints...")
    constraints = LayoutConstraints()
    assert constraints.display_width == 250
    assert constraints.display_height == 122
    
    print("  ✓ Testing mock display...")
    mock = MockDisplay()
    assert mock.width == 250
    assert mock.height == 122
    
    print("\n✅ All validation checks passed!")
    print("\n📦 Service is ready for deployment")
    sys.exit(0)
    
except ImportError as e:
    print(f"\n❌ Import error: {e}")
    sys.exit(1)
except AssertionError as e:
    print(f"\n❌ Assertion failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
