#!/usr/bin/env bash
# ESP32 Movement Controller Setup Script
# Generates movement_config.json with MQTT credentials from .env and host IP detection
# Flashes ESP32-S3 with MicroPython and uploads firmware

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
CONFIG_FILE="$SCRIPT_DIR/movement_config.json"
MAIN_FILE="$SCRIPT_DIR/main.py"
ESP32_CHIP="esp32s3"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

error() {
    echo -e "${RED}[ERROR]${NC} $*"
    exit 1
}

# Check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# ============================================
# Step 1: Check for required tools
# ============================================
echo ""
info "Checking for required tools..."

# Add ~/.local/bin to PATH if not already there (needed for pipx installs)
if [[ -d "$HOME/.local/bin" ]] && [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    export PATH="$HOME/.local/bin:$PATH"
    info "Added ~/.local/bin to PATH"
fi

if ! command_exists esptool && ! command_exists esptool.py; then
    error "esptool not found. Install with: pip install esptool or pipx install esptool"
fi
if command_exists esptool; then
    success "✓ esptool found"
elif command_exists esptool.py; then
    success "✓ esptool.py found (deprecated, consider upgrading)"
    # Use esptool.py if esptool is not available
    ESPTOOL_BIN="esptool.py"
else
    ESPTOOL_BIN="esptool"
fi

if ! command_exists mpremote; then
    error "mpremote not found. Install with: pip install mpremote"
fi
success "✓ mpremote found"

# Check for download tools (curl or wget)
if ! command_exists curl && ! command_exists wget; then
    warn "Neither curl nor wget found. Firmware auto-download will not be available."
    info "Install curl or wget to enable automatic firmware downloads."
else
    if command_exists curl; then
        success "✓ curl found (for downloads)"
    else
        success "✓ wget found (for downloads)"
    fi
fi

# ============================================
# Step 2: Detect ESP32 device
# ============================================
echo ""
info "Scanning for connected ESP32 devices..."

# Check dialout group on Linux (needed for serial port access)
if [[ "$(uname)" == "Linux" ]]; then
    if ! groups | grep -q dialout; then
        warn "Your user is not in the 'dialout' group"
        warn "You may not have permission to access serial ports"
        echo ""
        echo "To fix this, run:"
        echo -e "  ${BLUE}sudo usermod -a -G dialout \$USER${NC}"
        echo "  Then log out and log back in for changes to take effect"
        echo ""
        read -p "Continue anyway? [y/N]: " CONTINUE_NO_DIALOUT
        if [[ ! "$CONTINUE_NO_DIALOUT" =~ ^[Yy]$ ]]; then
            error "Please add your user to dialout group and try again"
        fi
        echo ""
    fi
fi

# Try different patterns for serial devices
# Linux: /dev/ttyUSB*, /dev/ttyACM*
# macOS: /dev/tty.*, /dev/cu.usbmodem*, /dev/cu.usbserial*
SERIAL_DEVICES=()
for pattern in /dev/ttyUSB* /dev/ttyACM* /dev/tty.usbmodem* /dev/tty.usbserial* /dev/cu.usbmodem* /dev/cu.usbserial*; do
    if ls $pattern 2>/dev/null | grep -q .; then
        while IFS= read -r device; do
            SERIAL_DEVICES+=("$device")
        done < <(ls $pattern 2>/dev/null)
    fi
done

if [[ ${#SERIAL_DEVICES[@]} -eq 0 ]]; then
    echo ""
    error "No serial devices found. Please check:"
    echo ""
    echo "1. ESP32 is connected via USB"
    echo "2. USB cable supports data (not just power)"
    echo "3. ESP32 drivers are installed (CP210x or CH340)"
    echo "4. On Linux, user is in 'dialout' group"
    echo ""
    echo "Expected device paths:"
    echo "  Linux:  /dev/ttyUSB0 or /dev/ttyACM0"
    echo "  macOS:  /dev/tty.usbserial-* or /dev/cu.usbmodem*"
    echo ""
    exit 1
fi

success "Found ${#SERIAL_DEVICES[@]} serial device(s):"
for i in "${!SERIAL_DEVICES[@]}"; do
    echo "  [$i] ${SERIAL_DEVICES[$i]}"
done

# Show USB device info if lsusb is available
if command_exists lsusb; then
    echo ""
    info "USB devices (ESP32 chips often show as CP210x, CH340, or FTDI):"
    lsusb | grep -iE "CP210|CH340|FTDI|Silicon|QinHeng|Espressif" || echo "  (No common ESP32 USB chips detected)"
fi

# Select device
if [[ ${#SERIAL_DEVICES[@]} -eq 1 ]]; then
    ESP_PORT="${SERIAL_DEVICES[0]}"
    info "Auto-selecting: $ESP_PORT"
else
    echo ""
    read -p "Select device number [0]: " DEVICE_NUM
    DEVICE_NUM="${DEVICE_NUM:-0}"
    ESP_PORT="${SERIAL_DEVICES[$DEVICE_NUM]}"
    if [[ -z "$ESP_PORT" ]]; then
        error "Invalid device selection"
    fi
    info "Selected: $ESP_PORT"
fi

# Check if we have permission to access the device
echo ""
if [[ ! -r "$ESP_PORT" ]] || [[ ! -w "$ESP_PORT" ]]; then
    warn "No permission to access $ESP_PORT"
    ls -l "$ESP_PORT"
    echo ""
    
    # Check if in dialout group
    if groups | grep -q dialout; then
        warn "You are in 'dialout' group but permissions not active yet"
        warn "You need to log out and log back in for group changes to take effect"
        echo ""
        info "Options:"
        echo "  1. Log out and log back in, then run this script again (recommended)"
        echo "  2. Use 'sudo' for this session (temporary fix)"
        echo ""
        read -p "Use sudo for flashing? [y/N]: " USE_SUDO
        if [[ "$USE_SUDO" =~ ^[Yy]$ ]]; then
            ESPTOOL_CMD="sudo ${ESPTOOL_BIN:-esptool}"
            MPREMOTE_CMD="sudo mpremote"
            success "Will use sudo for device access"
        else
            error "Cannot proceed without device access. Please log out and log back in."
        fi
    else
        error "User not in 'dialout' group. Run: sudo usermod -a -G dialout \$USER"
    fi
else
    ESPTOOL_CMD="${ESPTOOL_BIN:-esptool}"
    MPREMOTE_CMD="mpremote"
    success "✓ Have permission to access $ESP_PORT"
fi

# ============================================
# Step 3: Read MQTT configuration from .env
# ============================================
echo ""
if [[ ! -f "$ENV_FILE" ]]; then
    error ".env file not found at $ENV_FILE"
fi

info "Reading MQTT configuration from .env..."

# Parse .env file (skip comments and empty lines)
parse_env() {
    local key="$1"
    grep "^${key}=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' | tr -d "'" | head -n1
}

MQTT_USER=$(parse_env "MQTT_USER")
MQTT_PASS=$(parse_env "MQTT_PASS")
MQTT_PORT=$(parse_env "MQTT_PORT")

# Validate required values
if [[ -z "$MQTT_USER" ]]; then
    error "MQTT_USER not found in .env"
fi

if [[ -z "$MQTT_PASS" ]]; then
    error "MQTT_PASS not found in .env"
fi

if [[ -z "$MQTT_PORT" ]]; then
    warn "MQTT_PORT not found in .env, using default: 1883"
    MQTT_PORT=1883
fi

success "✓ MQTT User: $MQTT_USER"
success "✓ MQTT Port: $MQTT_PORT"

# Detect host IP address
# Priority: 1) User-provided arg, 2) Auto-detect from default route, 3) Fallback
if [[ -n "$1" ]]; then
    HOST_IP="$1"
    info "Using provided IP address: $HOST_IP"
else
    info "Auto-detecting host IP address..."
    
    # Try to get IP from default route (works on most Linux systems)
    if command -v ip &> /dev/null; then
        HOST_IP=$(ip route get 1.1.1.1 2>/dev/null | grep -oP 'src \K\S+' || true)
    fi
    
    # Fallback: try hostname -I (may return multiple IPs)
    if [[ -z "$HOST_IP" ]] && command -v hostname &> /dev/null; then
        HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
    fi
    
    # Last resort: check common network interfaces
    if [[ -z "$HOST_IP" ]]; then
        for iface in eth0 wlan0 en0; do
            if command -v ifconfig &> /dev/null; then
                HOST_IP=$(ifconfig "$iface" 2>/dev/null | grep -oP 'inet \K[\d.]+' | head -n1 || true)
                [[ -n "$HOST_IP" ]] && break
            fi
        done
    fi
    
    if [[ -z "$HOST_IP" ]]; then
        warn "Could not auto-detect IP address"
        read -p "Enter your host IP address (e.g., 192.168.1.100): " HOST_IP
        if [[ -z "$HOST_IP" ]]; then
            error "No IP address provided"
        fi
    else
        info "Detected host IP: $HOST_IP"
    fi
fi

# ============================================
# Step 4: WiFi Configuration
# ============================================
echo ""
info "ESP32 Wi-Fi Configuration"
echo ""
echo "Choose an option:"
echo "  [1] Scan for available WiFi networks"
echo "  [2] Manually enter WiFi SSID"
echo "  [3] Skip WiFi setup (configure via ESP32 setup portal later)"
echo ""
read -p "Select option [1]: " WIFI_OPTION
WIFI_OPTION="${WIFI_OPTION:-1}"

WIFI_SSID=""
WIFI_PASSWORD=""

if [[ "$WIFI_OPTION" == "1" ]]; then
    # Scan for WiFi networks
    info "Scanning for WiFi networks..."
    echo ""
    
    WIFI_NETWORKS=()
    
    # Try nmcli (NetworkManager) first
    if command_exists nmcli; then
        while IFS= read -r line; do
            # Parse SSID from nmcli output (format: SSID:SIGNAL:SECURITY)
            ssid=$(echo "$line" | cut -d':' -f1 | xargs)
            [[ -n "$ssid" ]] && WIFI_NETWORKS+=("$ssid")
        done < <(nmcli -t -f SSID,SIGNAL,SECURITY dev wifi list 2>/dev/null | sort -t':' -k2 -rn | head -n 20)
    # Fallback to iw scan (requires root on some systems)
    elif command_exists iw; then
        # Get wireless interface
        WIFI_IFACE=$(iw dev 2>/dev/null | awk '$1=="Interface"{print $2; exit}')
        if [[ -n "$WIFI_IFACE" ]]; then
            warn "Scanning requires sudo privileges..."
            while IFS= read -r line; do
                WIFI_NETWORKS+=("$line")
            done < <(sudo iw dev "$WIFI_IFACE" scan 2>/dev/null | grep "SSID:" | sed 's/.*SSID: //' | grep -v "^$" | sort -u)
        fi
    fi
    
    if [[ ${#WIFI_NETWORKS[@]} -eq 0 ]]; then
        warn "No WiFi networks found or scanning not available"
        read -p "Enter WiFi SSID manually: " WIFI_SSID
    else
        # Remove duplicates while preserving spaces in SSIDs
        temp_array=()
        while IFS= read -r line; do
            temp_array+=("$line")
        done < <(printf '%s\n' "${WIFI_NETWORKS[@]}" | sort -u)
        WIFI_NETWORKS=("${temp_array[@]}")
        
        info "Found ${#WIFI_NETWORKS[@]} network(s):"
        for i in "${!WIFI_NETWORKS[@]}"; do
            # Display with 1-based numbering for better UX
            echo "  [$((i+1))] ${WIFI_NETWORKS[$i]}"
        done
        
        echo ""
        read -p "Select network number (or press Enter to enter manually): " WIFI_NUM
        
        if [[ -n "$WIFI_NUM" ]] && [[ "$WIFI_NUM" =~ ^[0-9]+$ ]] && [[ "$WIFI_NUM" -ge 1 ]] && [[ "$WIFI_NUM" -le "${#WIFI_NETWORKS[@]}" ]]; then
            # Convert 1-based user input to 0-based array index
            WIFI_SSID="${WIFI_NETWORKS[$((WIFI_NUM-1))]}"
            success "Selected: $WIFI_SSID"
        else
            read -p "Enter WiFi SSID manually: " WIFI_SSID
        fi
    fi
    
    if [[ -n "$WIFI_SSID" ]]; then
        read -sp "Enter WiFi Password for '$WIFI_SSID' (leave blank for open network): " WIFI_PASSWORD
        echo ""
    fi
    
elif [[ "$WIFI_OPTION" == "2" ]]; then
    # Manual entry
    read -p "Enter WiFi SSID: " WIFI_SSID
    if [[ -n "$WIFI_SSID" ]]; then
        read -sp "Enter WiFi Password (leave blank for open network): " WIFI_PASSWORD
        echo ""
    fi
    
elif [[ "$WIFI_OPTION" == "3" ]]; then
    # Skip WiFi setup
    info "Skipping WiFi configuration"
    info "The ESP32 will start a 'TARS-Setup' WiFi portal"
    info "Connect to it and configure WiFi at http://192.168.4.1/"
    WIFI_SSID=""
    WIFI_PASSWORD=""
else
    error "Invalid option selected"
fi

# Optional: Customize client ID
echo ""
read -p "Enter MQTT Client ID [tars-esp32]: " MQTT_CLIENT_ID
MQTT_CLIENT_ID="${MQTT_CLIENT_ID:-tars-esp32}"

# ============================================
# Step 5: Generate configuration files
# ============================================
echo ""
info "Generating configuration files..."

# Generate movement_config.json
# Handle empty WiFi credentials (will trigger ESP32 setup portal)
if [[ -z "$WIFI_SSID" ]]; then
    cat > "$CONFIG_FILE" << EOF
{
  "wifi": {
    "ssid": "",
    "password": ""
  },
  "mqtt": {
    "host": "$HOST_IP",
    "port": $MQTT_PORT,
    "username": "$MQTT_USER",
    "password": "$MQTT_PASS",
    "client_id": "$MQTT_CLIENT_ID",
    "keepalive": 30
  },
  "pca9685": {
    "address": 64,
    "frequency": 50,
    "scl": 20,
    "sda": 21
  },
  "topics": {
    "frame": "movement/frame",
    "state": "movement/state",
    "health": "system/health/movement-esp32",
    "test": "movement/test",
    "stop": "movement/stop",
    "status": "movement/status"
  },
  "frame_timeout_ms": 2500,
  "status_led": 48,
  "setup_portal": {
    "ssid": "TARS-Setup",
    "password": null,
    "port": 80,
    "timeout_s": 300
  },
  "servo_channel_count": 12,
  "default_center_pulse": 305,
  "servo_centers": {
    "0": 302,
    "1": 310
  },
  "servos": {
    "legs": {
      "height": {
        "channel": 0,
        "up": 220,
        "neutral": 300,
        "down": 350,
        "min": 200,
        "max": 400
      },
      "left": {
        "channel": 1,
        "forward": 220,
        "neutral": 300,
        "back": 380,
        "offset": 0,
        "min": 200,
        "max": 400
      },
      "right": {
        "channel": 2,
        "forward": 380,
        "neutral": 300,
        "back": 220,
        "offset": 0,
        "min": 200,
        "max": 400
      }
    },
    "arms": {
      "right": {
        "main": {
          "channel": 3,
          "min": 135,
          "max": 440,
          "neutral": 287
        },
        "forearm": {
          "channel": 4,
          "min": 200,
          "max": 380,
          "neutral": 290
        },
        "hand": {
          "channel": 5,
          "min": 200,
          "max": 280,
          "neutral": 240
        }
      },
      "left": {
        "main": {
          "channel": 6,
          "min": 135,
          "max": 440,
          "neutral": 287
        },
        "forearm": {
          "channel": 7,
          "min": 200,
          "max": 380,
          "neutral": 290
        },
        "hand": {
          "channel": 8,
          "min": 280,
          "max": 380,
          "neutral": 330
        }
      }
    }
  }
}
EOF
    warn "WiFi credentials not set - ESP32 will start in setup mode"
else
    cat > "$CONFIG_FILE" << EOF
{
  "wifi": {
    "ssid": "$WIFI_SSID",
    "password": "$WIFI_PASSWORD"
  },
  "mqtt": {
    "host": "$HOST_IP",
    "port": $MQTT_PORT,
    "username": "$MQTT_USER",
    "password": "$MQTT_PASS",
    "client_id": "$MQTT_CLIENT_ID",
    "keepalive": 30
  },
  "pca9685": {
    "address": 64,
    "frequency": 50,
    "scl": 20,
    "sda": 21
  },
  "topics": {
    "frame": "movement/frame",
    "state": "movement/state",
    "health": "system/health/movement-esp32",
    "test": "movement/test",
    "stop": "movement/stop",
    "status": "movement/status"
  },
  "frame_timeout_ms": 2500,
  "status_led": 48,
  "setup_portal": {
    "ssid": "TARS-Setup",
    "password": null,
    "port": 80,
    "timeout_s": 300
  },
  "servo_channel_count": 12,
  "default_center_pulse": 305,
  "servo_centers": {
    "0": 302,
    "1": 310
  },
  "servos": {
    "legs": {
      "height": {
        "channel": 0,
        "up": 220,
        "neutral": 300,
        "down": 350,
        "min": 200,
        "max": 400
      },
      "left": {
        "channel": 1,
        "forward": 220,
        "neutral": 300,
        "back": 380,
        "offset": 0,
        "min": 200,
        "max": 400
      },
      "right": {
        "channel": 2,
        "forward": 380,
        "neutral": 300,
        "back": 220,
        "offset": 0,
        "min": 200,
        "max": 400
      }
    },
    "arms": {
      "right": {
        "main": {
          "channel": 3,
          "min": 135,
          "max": 440,
          "neutral": 287
        },
        "forearm": {
          "channel": 4,
          "min": 200,
          "max": 380,
          "neutral": 290
        },
        "hand": {
          "channel": 5,
          "min": 200,
          "max": 280,
          "neutral": 240
        }
      },
      "left": {
        "main": {
          "channel": 6,
          "min": 135,
          "max": 440,
          "neutral": 287
        },
        "forearm": {
          "channel": 7,
          "min": 200,
          "max": 380,
          "neutral": 290
        },
        "hand": {
          "channel": 8,
          "min": 280,
          "max": 380,
          "neutral": 330
        }
      }
    }
  }
}
EOF
fi

success "✓ Created: $CONFIG_FILE"

# Generate main.py that auto-starts tars_controller.py
cat > "$MAIN_FILE" << 'EOF'
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

EOF

success "✓ Created: $MAIN_FILE"

# ============================================
# Step 6: Display summary
# ============================================
echo ""
echo "======================================"
echo "  ESP32 Configuration Summary"
echo "======================================"
if [[ -z "$WIFI_SSID" ]]; then
    echo "Wi-Fi SSID:       (not configured - will use setup portal)"
else
    echo "Wi-Fi SSID:       $WIFI_SSID"
fi
echo "MQTT Host:        $HOST_IP:$MQTT_PORT"
echo "MQTT User:        $MQTT_USER"
echo "MQTT Client ID:   $MQTT_CLIENT_ID"
echo "ESP32 Port:       $ESP_PORT"
echo "ESP32 Chip:       $ESP32_CHIP"
echo "Config File:      $CONFIG_FILE"
echo "Main File:        $MAIN_FILE"
echo "======================================"
echo ""

if [[ -z "$WIFI_SSID" ]]; then
    info "WiFi Setup Portal Instructions:"
    echo "  1. After flashing, the ESP32 will create a WiFi network: 'TARS-Setup'"
    echo "  2. Connect to 'TARS-Setup' from your phone/laptop"
    echo "  3. Open a browser and go to: http://192.168.4.1/"
    echo "  4. Enter your WiFi credentials in the web portal"
    echo "  5. The ESP32 will reboot and connect to your network"
    echo ""
fi

# ============================================
# Step 7: Flash MicroPython firmware
# ============================================
info "Do you want to flash the ESP32 now?"
echo "This will:"
echo "  1. Erase the ESP32 flash memory"
echo "  2. Install MicroPython firmware (if provided)"
echo "  3. Upload servoctl.py, main.py, and movement_config.json"
echo ""
read -p "Continue with flashing? [y/N]: " DO_FLASH

if [[ ! "$DO_FLASH" =~ ^[Yy]$ ]]; then
    warn "Skipping flash. Configuration files are ready at:"
    echo "  - $CONFIG_FILE"
    echo "  - $MAIN_FILE"
    echo ""
    info "To flash manually, run:"
    echo -e "  ${BLUE}esptool --chip $ESP32_CHIP --port $ESP_PORT erase_flash${NC}"
    echo -e "  ${BLUE}esptool --chip $ESP32_CHIP --port $ESP_PORT --baud 460800 write_flash -z 0x0 <firmware.bin>${NC}"
    echo -e "  ${BLUE}mpremote connect $ESP_PORT fs cp servoctl.py :${NC}"
    echo -e "  ${BLUE}mpremote connect $ESP_PORT fs cp main.py :${NC}"
    echo -e "  ${BLUE}mpremote connect $ESP_PORT fs cp movement_config.json :${NC}"
    exit 0
fi

# Check for MicroPython firmware
FIRMWARE_BIN=""
FIRMWARE_URL="https://micropython.org/resources/firmware/ESP32_GENERIC_S3-20250911-v1.26.1.bin"
FIRMWARE_NAME="ESP32_GENERIC_S3-20250911-v1.26.1.bin"
FIRMWARE_CACHE="/tmp/$FIRMWARE_NAME"

echo ""
info "Looking for MicroPython firmware..."

# Check local directory first
for pattern in "$SCRIPT_DIR"/*.bin "$SCRIPT_DIR"/../*.bin; do
    if [[ -f "$pattern" ]] && [[ "$pattern" == *"ESP32"* || "$pattern" == *"esp32"* ]]; then
        FIRMWARE_BIN="$pattern"
        success "Found local firmware: $FIRMWARE_BIN"
        break
    fi
done

# Check cache directory
if [[ -z "$FIRMWARE_BIN" ]] && [[ -f "$FIRMWARE_CACHE" ]]; then
    FIRMWARE_BIN="$FIRMWARE_CACHE"
    success "Found cached firmware: $FIRMWARE_BIN"
fi

# Download if not found
if [[ -z "$FIRMWARE_BIN" ]]; then
    warn "No MicroPython firmware found locally"
    echo ""
    read -p "Download MicroPython firmware from micropython.org? [Y/n]: " DOWNLOAD_FW
    DOWNLOAD_FW="${DOWNLOAD_FW:-Y}"
    
    if [[ "$DOWNLOAD_FW" =~ ^[Yy]$ ]]; then
        info "Downloading MicroPython firmware..."
        info "URL: $FIRMWARE_URL"
        info "Destination: $FIRMWARE_CACHE"
        
        # Try curl first, then wget
        if command_exists curl; then
            if curl -L -o "$FIRMWARE_CACHE" "$FIRMWARE_URL"; then
                FIRMWARE_BIN="$FIRMWARE_CACHE"
                success "✓ Firmware downloaded successfully"
            else
                error "Failed to download firmware with curl"
            fi
        elif command_exists wget; then
            if wget -O "$FIRMWARE_CACHE" "$FIRMWARE_URL"; then
                FIRMWARE_BIN="$FIRMWARE_CACHE"
                success "✓ Firmware downloaded successfully"
            else
                error "Failed to download firmware with wget"
            fi
        else
            error "Neither curl nor wget found. Install one to download firmware automatically."
        fi
    else
        info "Skipping firmware download"
        read -p "Enter path to MicroPython .bin file (or leave blank to skip): " FIRMWARE_BIN
    fi
fi

# Erase flash
echo ""
info "Step 1: Erasing ESP32 flash memory..."

# Try to erase flash with manual bootloader mode instructions on failure
if ! $ESPTOOL_CMD --chip "$ESP32_CHIP" --port "$ESP_PORT" erase_flash; then
    echo ""
    warn "Failed to connect to ESP32 automatically"
    echo ""
    warn "The ESP32 needs to be manually put into bootloader mode"
    echo ""
    echo "Please follow these steps:"
    echo "  1. HOLD the BOOT button (or IO0 button)"
    echo "  2. While holding BOOT, press and release the RESET button (or EN button)"
    echo "  3. Keep holding BOOT for 2 more seconds"
    echo "  4. Release the BOOT button"
    echo ""
    info "The ESP32 should now be in bootloader mode (flashing LED)"
    echo ""
    read -p "Press Enter once you've completed these steps..."
    
    echo ""
    info "Retrying flash erase..."
    if $ESPTOOL_CMD --chip "$ESP32_CHIP" --port "$ESP_PORT" erase_flash; then
        success "✓ Flash erased successfully"
    else
        error "Failed to erase flash even after manual bootloader mode. Please check connections."
    fi
else
    success "✓ Flash erased successfully"
fi

sleep 2

# Flash firmware if provided
if [[ -n "$FIRMWARE_BIN" ]] && [[ -f "$FIRMWARE_BIN" ]]; then
    echo ""
    info "Step 2: Flashing MicroPython firmware: $FIRMWARE_BIN"
    
    # Try to flash with manual bootloader mode instructions on failure
    if ! $ESPTOOL_CMD --chip "$ESP32_CHIP" --port "$ESP_PORT" --baud 460800 write_flash -z 0x0 "$FIRMWARE_BIN"; then
        echo ""
        warn "Failed to flash firmware"
        echo ""
        warn "Please put the ESP32 into bootloader mode again:"
        echo "  1. HOLD the BOOT button"
        echo "  2. Press and release RESET"
        echo "  3. Keep holding BOOT for 2 seconds"
        echo "  4. Release BOOT"
        echo ""
        read -p "Press Enter to retry..."
        
        if ! $ESPTOOL_CMD --chip "$ESP32_CHIP" --port "$ESP_PORT" --baud 460800 write_flash -z 0x0 "$FIRMWARE_BIN"; then
            error "Failed to flash MicroPython firmware even after manual bootloader mode"
        fi
    fi
    
    if [[ $? -eq 0 ]]; then
        success "✓ MicroPython firmware flashed successfully"
        echo ""
        warn "⚠️  IMPORTANT: The ESP32 needs to be reconnected after flashing"
        echo ""
        echo "Please follow these steps:"
        echo "  1. UNPLUG the ESP32 USB cable"
        echo "  2. Wait 2-3 seconds"
        echo "  3. PLUG the ESP32 USB cable back in"
        echo "  4. Wait 2-3 seconds for it to boot"
        echo ""
        read -p "Press Enter after you've unplugged and reconnected the ESP32..."
        
        echo ""
        info "Waiting for ESP32 to be ready..."
        sleep 3
        
        # Try to verify MicroPython is responding
        info "Verifying MicroPython is running..."
        if $MPREMOTE_CMD connect "$ESP_PORT" exec "print('OK')" &>/dev/null; then
            success "✓ MicroPython is responding"
        else
            warn "ESP32 not responding yet, waiting longer..."
            sleep 5
            if $MPREMOTE_CMD connect "$ESP_PORT" exec "print('OK')" &>/dev/null; then
                success "✓ MicroPython is responding"
            else
                error "ESP32 not responding. Please check the connection and try reconnecting again."
            fi
        fi
    else
        error "Failed to flash MicroPython firmware"
    fi
else
    warn "Skipping MicroPython firmware flash (no .bin file provided)"
    info "Make sure MicroPython is already installed on your ESP32"
fi

# ============================================
# Step 8: Upload files to ESP32
# ============================================
echo ""
info "Step 3: Uploading files to ESP32..."
echo ""

# Function to upload a single file with retry
upload_file() {
    local file="$1"
    local dest="${2:-:}"
    local name=$(basename "$file")
    local retries=3
    
    if [[ ! -f "$file" ]]; then
        warn "File not found: $file (skipping)"
        return 0
    fi
    
    for i in $(seq 1 $retries); do
        info "Uploading $name (attempt $i/$retries)..."
        if $MPREMOTE_CMD connect "$ESP_PORT" fs cp "$file" "$dest" 2>&1; then
            success "✓ $name uploaded"
            return 0
        else
            if [[ $i -lt $retries ]]; then
                warn "Upload failed, retrying in 3 seconds..."
                sleep 3
            fi
        fi
    done
    
    error "Failed to upload $name after $retries attempts"
    return 1
}

# Function to upload a directory recursively with retry
upload_directory() {
    local dir="$1"
    local dest="${2:-:$(basename "$dir")}"
    local name=$(basename "$dir")
    local retries=3
    
    if [[ ! -d "$dir" ]]; then
        warn "Directory not found: $dir (skipping)"
        return 0
    fi
    
    for i in $(seq 1 $retries); do
        info "Uploading directory $name/ (attempt $i/$retries)..."
        if $MPREMOTE_CMD connect "$ESP_PORT" fs cp -r "$dir/" "$dest/" 2>&1; then
            success "✓ Directory $name/ uploaded"
            return 0
        else
            if [[ $i -lt $retries ]]; then
                warn "Upload failed, retrying in 3 seconds..."
                sleep 3
            fi
        fi
    done
    
    error "Failed to upload directory $name/ after $retries attempts"
    return 1
}

# Upload modular library (required for tars_controller)
if [[ -d "$SCRIPT_DIR/lib" ]]; then
    upload_directory "$SCRIPT_DIR/lib" ":lib"
    sleep 1
else
    error "lib/ directory not found - tars_controller.py requires it"
fi

# Upload movement sequences (required for tars_controller)
if [[ -d "$SCRIPT_DIR/movements" ]]; then
    upload_directory "$SCRIPT_DIR/movements" ":movements"
    sleep 1
else
    error "movements/ directory not found - tars_controller.py requires it"
fi

# Upload main controller file
upload_file "$SCRIPT_DIR/tars_controller.py"
sleep 1

# Upload boot script
upload_file "$MAIN_FILE"
sleep 1

# Upload configuration
upload_file "$CONFIG_FILE"

# ============================================
# Step 9: Reboot ESP32
# ============================================
echo ""
info "Rebooting ESP32 to start the application..."
if $MPREMOTE_CMD connect "$ESP_PORT" soft-reset &>/dev/null; then
    success "✓ ESP32 rebooted successfully"
else
    warn "Could not soft reset ESP32. You may need to press the RESET button manually."
fi

echo ""
info "Checking if application is running..."
info "Monitoring serial output for 5 seconds..."
echo ""

# Capture serial output for 5 seconds
SERIAL_OUTPUT=$(timeout 5 $MPREMOTE_CMD connect "$ESP_PORT" 2>&1 || true)

# Check if we see actual application output
if echo "$SERIAL_OUTPUT" | grep -qE "WiFi connected|MQTT connected|Starting loop"; then
    success "✓ Application is running!"
    echo ""
    echo "Serial output:"
    echo "$SERIAL_OUTPUT" | tail -n 15
    echo ""
elif echo "$SERIAL_OUTPUT" | grep -q "Connected to MicroPython"; then
    warn "ESP32 is connected but application hasn't started yet"
    echo ""
    echo "This usually means the ESP32 needs a power cycle."
    echo ""
    info "Please follow these steps:"
    echo "  1. UNPLUG the ESP32 USB cable"
    echo "  2. Wait 2-3 seconds"
    echo "  3. PLUG the ESP32 USB cable back in"
    echo ""
    read -p "Press Enter after reconnecting..."
    
    echo ""
    info "Checking again..."
    sleep 3
    SERIAL_OUTPUT=$(timeout 5 $MPREMOTE_CMD connect "$ESP_PORT" 2>&1 || true)
    
    if echo "$SERIAL_OUTPUT" | grep -qE "WiFi connected|MQTT connected|Starting loop"; then
        success "✓ Application is now running!"
        echo ""
        echo "Serial output:"
        echo "$SERIAL_OUTPUT" | tail -n 15
        echo ""
    else
        warn "Still not seeing application output. Check serial monitor manually."
    fi
else
    warn "Could not connect to ESP32 serial port"
    info "You can monitor manually with: mpremote connect $ESP_PORT"
fi

# ============================================
# Step 10: Complete!
# ============================================
echo ""
echo "======================================"
success "ESP32 Setup Complete!"
echo "======================================"
echo ""
info "Your ESP32 is now configured and running!"
echo ""
echo "To monitor the ESP32 serial output:"
echo -e "  ${BLUE}mpremote connect $ESP_PORT${NC}"
echo ""
echo "Or use screen:"
echo -e "  ${BLUE}screen $ESP_PORT 115200${NC}"
echo "  (Press Ctrl-A then K to exit screen)"
echo ""
info "The ESP32 will automatically start tars_controller.py on boot."
echo ""
info "Movement sequences available:"
echo "  • Basic: reset_position, step_forward, step_backward, turn_left, turn_right"
echo "  • Expressive: wave, laugh, swing_legs, pezz_dispenser, now, balance, mic_drop, monster, pose, bow"
echo ""
info "Test a movement with:"
echo -e "  ${BLUE}mosquitto_pub -h $HOST_IP -t movement/test -m '{\"command\":\"wave\",\"speed\":0.8}'${NC}"
echo ""

# Show firmware cache info if downloaded
if [[ -n "$FIRMWARE_BIN" ]] && [[ "$FIRMWARE_BIN" == "/tmp/"* ]]; then
    info "Note: MicroPython firmware cached at: $FIRMWARE_BIN"
    info "The firmware will be reused for future setups until system reboot."
    echo ""
fi
