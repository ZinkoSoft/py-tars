#!/usr/bin/env python3
"""
Generate servo_config.ini from current servo positions

Usage:
    python3 generate_config.py > servo_config.ini
    
Or interactively:
    python3 generate_config.py --interactive
"""

import sys

# Default configuration template
DEFAULT_CONFIG = {
    0: {"min": 220, "max": 360, "neutral": 300, "label": "Main Legs Lift", "reverse": False},
    1: {"min": 192, "max": 408, "neutral": 300, "label": "Left Leg Rotation", "reverse": False},
    2: {"min": 192, "max": 408, "neutral": 300, "label": "Right Leg Rotation", "reverse": True},
    3: {"min": 135, "max": 440, "neutral": 135, "label": "Right Shoulder", "reverse": True},
    4: {"min": 200, "max": 380, "neutral": 200, "label": "Right Elbow", "reverse": True},
    5: {"min": 200, "max": 280, "neutral": 200, "label": "Right Hand", "reverse": True},
    6: {"min": 135, "max": 440, "neutral": 135, "label": "Left Shoulder", "reverse": False},
    7: {"min": 200, "max": 380, "neutral": 200, "label": "Left Elbow", "reverse": False},
    8: {"min": 280, "max": 380, "neutral": 280, "label": "Left Hand", "reverse": False},
}


def generate_config(config_dict):
    """Generate INI file content from config dictionary"""
    lines = [
        "# TARS Servo Configuration",
        "# Edit values and reload to apply changes - no firmware re-upload needed!",
        "#",
        "# How to apply changes:",
        "#   1. Edit this file",
        "#   2. Upload: ./upload_config.sh",
        "#   3. Reload: curl -X POST http://<ESP32_IP>/config/reload",
        "#      OR reboot ESP32",
        "#",
        "# Pulse Width Guide (12-bit PWM at 50Hz):",
        "#   - 1.0ms = 204 (typical servo minimum)",
        "#   - 1.5ms = 307 (typical center)",
        "#   - 2.0ms = 409 (typical servo maximum)",
        "#   Formula: pwm_value = pulse_us * 0.2048",
        "",
    ]
    
    for channel in range(9):
        if channel in config_dict:
            servo = config_dict[channel]
            lines.extend([
                f"[servo_{channel}]",
                f"min = {servo['min']}",
                f"max = {servo['max']}",
                f"neutral = {servo['neutral']}",
                f"label = {servo['label']}",
                f"reverse = {servo['reverse']}",
                "",
            ])
    
    return "\n".join(lines)


def interactive_mode():
    """Interactive configuration builder"""
    print("=== TARS Servo Configuration Generator ===")
    print()
    print("Enter values for each servo, or press Enter to use defaults")
    print()
    
    config = {}
    
    for channel in range(9):
        default = DEFAULT_CONFIG[channel]
        print(f"\n--- Servo {channel}: {default['label']} ---")
        
        # Min
        while True:
            val = input(f"Min [{default['min']}]: ").strip()
            if not val:
                min_val = default['min']
                break
            try:
                min_val = int(val)
                if 0 <= min_val <= 4095:
                    break
                print("Error: Must be 0-4095")
            except ValueError:
                print("Error: Must be an integer")
        
        # Max
        while True:
            val = input(f"Max [{default['max']}]: ").strip()
            if not val:
                max_val = default['max']
                break
            try:
                max_val = int(val)
                if 0 <= max_val <= 4095:
                    break
                print("Error: Must be 0-4095")
            except ValueError:
                print("Error: Must be an integer")
        
        # Neutral
        while True:
            val = input(f"Neutral [{default['neutral']}]: ").strip()
            if not val:
                neutral_val = default['neutral']
                break
            try:
                neutral_val = int(val)
                if min_val <= neutral_val <= max_val:
                    break
                print(f"Error: Must be between {min_val} and {max_val}")
            except ValueError:
                print("Error: Must be an integer")
        
        # Label
        label = input(f"Label [{default['label']}]: ").strip()
        if not label:
            label = default['label']
        
        # Reverse
        rev_str = input(f"Reverse [{default['reverse']}] (y/n): ").strip().lower()
        if rev_str == 'y' or rev_str == 'yes' or rev_str == 'true':
            reverse = True
        elif rev_str == 'n' or rev_str == 'no' or rev_str == 'false':
            reverse = False
        else:
            reverse = default['reverse']
        
        config[channel] = {
            "min": min_val,
            "max": max_val,
            "neutral": neutral_val,
            "label": label,
            "reverse": reverse,
        }
    
    print("\n=== Configuration Complete ===")
    print()
    return config


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ('--interactive', '-i'):
        config = interactive_mode()
        
        # Confirm before output
        print("Generate config? (y/n): ", end='')
        if input().strip().lower() not in ('y', 'yes'):
            print("Cancelled.")
            sys.exit(0)
        
        print("\n" + "="*50)
        print(generate_config(config))
    else:
        # Non-interactive: just output defaults
        print(generate_config(DEFAULT_CONFIG))


if __name__ == '__main__':
    main()
