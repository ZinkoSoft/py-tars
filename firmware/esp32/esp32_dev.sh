#!/bin/bash
# ESP32 Development Workflow Script
# Manages flashing, connecting, and REPL access for TARS firmware

set -e  # Exit on error

DEVICE="/dev/ttyACM0"
FIRMWARE_DIR="/home/james/git/py-tars/firmware/esp32"

cd "$FIRMWARE_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}TARS ESP32 Development Workflow${NC}"
echo -e "${GREEN}======================================${NC}"

show_menu() {
    echo ""
    echo "Select an option:"
    echo "  1) Flash all files to ESP32 (upload everything)"
    echo "  2) Quick update (tars_controller.py only)"
    echo "  3) Connect to REPL (program running in background)"
    echo "  4) Stop and enter REPL (interactive mode)"
    echo "  5) Soft reset (restart program)"
    echo "  6) Flash + restart (full deployment)"
    echo "  7) Exit"
    echo ""
    read -p "Choice: " choice
    
    case $choice in
        1) flash_all ;;
        2) quick_update ;;
        3) connect_repl ;;
        4) stop_and_repl ;;
        5) soft_reset ;;
        6) flash_and_restart ;;
        7) exit 0 ;;
        *) echo -e "${RED}Invalid choice${NC}"; show_menu ;;
    esac
}

flash_all() {
    echo -e "${YELLOW}Flashing all files to ESP32...${NC}"
    
    # Core files
    mpremote connect "$DEVICE" fs cp main.py :main.py
    mpremote connect "$DEVICE" fs cp tars_controller.py :tars_controller.py
    mpremote connect "$DEVICE" fs cp movement_config.json :movement_config.json
    
    # Lib directory
    echo "Uploading lib/..."
    mpremote connect "$DEVICE" fs mkdir :lib 2>/dev/null || true
    for file in lib/*.py; do
        [ -f "$file" ] && mpremote connect "$DEVICE" fs cp "$file" ":$file"
    done
    
    # Movements directory
    echo "Uploading movements/..."
    mpremote connect "$DEVICE" fs mkdir :movements 2>/dev/null || true
    for file in movements/*.py; do
        [ -f "$file" ] && mpremote connect "$DEVICE" fs cp "$file" ":$file"
    done
    
    echo -e "${GREEN}✓ All files uploaded${NC}"
    show_menu
}

quick_update() {
    echo -e "${YELLOW}Quick update: tars_controller.py${NC}"
    mpremote connect "$DEVICE" fs cp tars_controller.py :tars_controller.py
    echo -e "${GREEN}✓ tars_controller.py updated${NC}"
    echo -e "${YELLOW}Press CTRL+D on the REPL to soft reset${NC}"
    show_menu
}

connect_repl() {
    echo -e "${GREEN}Connecting to REPL (program running)...${NC}"
    echo -e "${YELLOW}Press CTRL+C to stop program and get REPL${NC}"
    echo -e "${YELLOW}Press CTRL+D for soft reset${NC}"
    echo -e "${YELLOW}Press CTRL+X to exit${NC}"
    echo ""
    mpremote connect "$DEVICE"
}

stop_and_repl() {
    echo -e "${GREEN}Connecting and stopping program...${NC}"
    echo -e "${YELLOW}The program will be interrupted${NC}"
    echo -e "${YELLOW}Press CTRL+D to restart, CTRL+X to exit${NC}"
    echo ""
    # Send CTRL+C to stop the program
    mpremote connect "$DEVICE" exec "raise KeyboardInterrupt()" || mpremote connect "$DEVICE"
}

soft_reset() {
    echo -e "${YELLOW}Performing soft reset...${NC}"
    mpremote connect "$DEVICE" reset
    echo -e "${GREEN}✓ ESP32 reset complete${NC}"
    show_menu
}

flash_and_restart() {
    echo -e "${YELLOW}Full deployment: flashing all files and restarting...${NC}"
    flash_all
    soft_reset
    echo -e "${GREEN}✓ Deployment complete!${NC}"
    echo ""
    read -p "Connect to REPL to view logs? (y/n): " connect
    if [ "$connect" = "y" ]; then
        connect_repl
    else
        show_menu
    fi
}

# Start
show_menu
