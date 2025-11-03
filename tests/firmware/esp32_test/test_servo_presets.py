"""
Contract tests for movement preset validation - ESP32 TARS Movement Updates

Validates movement preset structure against contracts/movement-presets.md
"""

import pytest


def test_preset_step_forward_structure():
    """
    Verify PRESET_STEP_FORWARD follows the contract structure
    Based on contracts/movement-presets.md
    """
    try:
        import sys
        sys.path.insert(0, '/home/james/git/py-tars/firmware/esp32_test')
        from movement_presets import PRESETS
        from servo_config import SERVO_CALIBRATION
        
        # Get the preset
        preset_name = "step_forward"
        assert preset_name in PRESETS, f"Preset '{preset_name}' should exist"
        
        preset = PRESETS[preset_name]
        
        # Verify structure
        assert "steps" in preset, "Preset should have 'steps' list"
        assert isinstance(preset["steps"], list), "steps should be a list"
        assert len(preset["steps"]) == 5, "step_forward should have 5 steps"
        
        # Verify each step structure
        for i, step in enumerate(preset["steps"]):
            assert "targets" in step, f"Step {i+1} should have 'targets'"
            assert "speed" in step, f"Step {i+1} should have 'speed'"
            assert "delay_after" in step, f"Step {i+1} should have 'delay_after'"
            
            # Verify types
            assert isinstance(step["targets"], dict), f"Step {i+1} targets should be dict"
            assert isinstance(step["speed"], (int, float)), f"Step {i+1} speed should be numeric"
            assert isinstance(step["delay_after"], (int, float)), f"Step {i+1} delay_after should be numeric"
    
    except ImportError:
        pytest.skip("movement_presets not in path - run from firmware directory")


def test_preset_step_forward_values():
    """
    Verify step_forward has the correct updated values from spec
    """
    try:
        import sys
        sys.path.insert(0, '/home/james/git/py-tars/firmware/esp32_test')
        from movement_presets import PRESETS
        
        preset = PRESETS["step_forward"]
        steps = preset["steps"]
        
        # Expected speeds from spec
        expected_speeds = [0.4, 0.6, 0.65, 0.8, 1.0]
        actual_speeds = [step["speed"] for step in steps]
        assert actual_speeds == expected_speeds, f"Speeds should be {expected_speeds}, got {actual_speeds}"
        
        # Expected delays from spec (all 0.2 except last is 0.5)
        expected_delays = [0.2, 0.2, 0.2, 0.2, 0.5]
        actual_delays = [step["delay_after"] for step in steps]
        assert actual_delays == expected_delays, f"Delays should be {expected_delays}, got {actual_delays}"
        
    except ImportError:
        pytest.skip("movement_presets not in path - run from firmware directory")


def test_all_target_pulse_widths_in_calibration_range():
    """
    Verify all target pulse widths are within SERVO_CALIBRATION min/max
    """
    try:
        import sys
        sys.path.insert(0, '/home/james/git/py-tars/firmware/esp32_test')
        from movement_presets import PRESETS
        from servo_config import SERVO_CALIBRATION
        
        preset = PRESETS["step_forward"]
        
        for i, step in enumerate(preset["steps"]):
            for channel, pulse_width in step["targets"].items():
                min_val = SERVO_CALIBRATION[channel]["min"]
                max_val = SERVO_CALIBRATION[channel]["max"]
                
                # Handle reverse servos - check the actual range
                actual_min = min(min_val, max_val)
                actual_max = max(min_val, max_val)
                
                assert actual_min <= pulse_width <= actual_max, \
                    f"Step {i+1}, channel {channel}: pulse {pulse_width} out of range [{actual_min}, {actual_max}]"
    
    except ImportError:
        pytest.skip("servo_config not in path - run from firmware directory")


def test_all_speeds_in_valid_range():
    """
    Verify all speed values are in range 0.1-1.0
    """
    try:
        import sys
        sys.path.insert(0, '/home/james/git/py-tars/firmware/esp32_test')
        from movement_presets import PRESETS
        
        preset = PRESETS["step_forward"]
        
        for i, step in enumerate(preset["steps"]):
            speed = step["speed"]
            assert 0.1 <= speed <= 1.0, \
                f"Step {i+1}: speed {speed} out of range [0.1, 1.0]"
    
    except ImportError:
        pytest.skip("movement_presets not in path - run from firmware directory")


def test_all_wait_times_non_negative():
    """
    Verify all wait (delay_after) values are >= 0
    """
    try:
        import sys
        sys.path.insert(0, '/home/james/git/py-tars/firmware/esp32_test')
        from movement_presets import PRESETS
        
        preset = PRESETS["step_forward"]
        
        for i, step in enumerate(preset["steps"]):
            delay = step["delay_after"]
            assert delay >= 0, \
                f"Step {i+1}: delay_after {delay} should be >= 0"
    
    except ImportError:
        pytest.skip("movement_presets not in path - run from firmware directory")


def test_all_channels_in_valid_range():
    """
    Verify all channel numbers are in range 0-8
    """
    try:
        import sys
        sys.path.insert(0, '/home/james/git/py-tars/firmware/esp32_test')
        from movement_presets import PRESETS
        
        preset = PRESETS["step_forward"]
        
        for i, step in enumerate(preset["steps"]):
            for channel in step["targets"].keys():
                assert 0 <= channel <= 8, \
                    f"Step {i+1}: channel {channel} out of range [0, 8]"
    
    except ImportError:
        pytest.skip("movement_presets not in path - run from firmware directory")


def test_preset_has_descriptions():
    """
    Verify step_forward steps have descriptions (optional but recommended)
    """
    try:
        import sys
        sys.path.insert(0, '/home/james/git/py-tars/firmware/esp32_test')
        from movement_presets import PRESETS
        
        preset = PRESETS["step_forward"]
        
        # Check if at least some steps have descriptions
        steps_with_descriptions = sum(1 for step in preset["steps"] if "description" in step)
        assert steps_with_descriptions > 0, "At least some steps should have descriptions"
    
    except ImportError:
        pytest.skip("movement_presets not in path - run from firmware directory")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
