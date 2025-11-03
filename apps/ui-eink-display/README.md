# UI E-Ink Display Service

Visual communication interface for the TARS remote microphone system using a Waveshare 2.13" V4 e-ink display.

## Overview

This service provides real-time visual feedback on the e-ink display showing:
- System operational status (standby, listening, processing, error)
- User speech transcripts as right-aligned message bubbles
- TARS responses as left-aligned message bubbles
- Intelligent screen space management with timeout to standby

## Hardware Requirements

- **Device**: Radxa Zero 3W or compatible SBC with 40-pin GPIO header
- **Display**: Waveshare 2.13" V4 e-ink display (250x122 pixels, monochrome)
- **Connection**: SPI interface via GPIO pins
- **Network**: Connection to main TARS system MQTT broker

## Dependencies

### System Dependencies
- Python 3.11+
- SPI enabled in kernel (`/dev/spidev0.0` accessible)
- GPIO permissions (root or gpio group membership)
- DejaVu Sans fonts (standard Linux package)

### Python Dependencies
- `asyncio-mqtt` - MQTT client for async messaging
- `Pillow` - Image generation and rendering
- `waveshare-epd` - E-ink display driver library
- `pydantic` - Contract validation (from tars-core)

### External Dependencies
- Main TARS system MQTT broker (must be accessible over network)
- STT worker publishing to `stt/final`
- LLM worker publishing to `llm/response`
- Wake activation publishing to `wake/event`

## Installation

### 1. Install Waveshare Library

```bash
# Clone Waveshare e-Paper repository
cd /data/git
git clone https://github.com/waveshare/e-Paper

# Add to PYTHONPATH
export PYTHONPATH=/data/git/e-Paper/RaspberryPi_JetsonNano/python/lib:$PYTHONPATH
```

### 2. Install Service

```bash
cd /data/git/py-tars/apps/ui-eink-display
pip install -e .
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your MQTT_URL and other settings
```

## Usage

### Docker Deployment (Recommended)

```bash
cd /data/git/py-tars
docker compose -f ops/compose.remote-mic.yml up ui-eink-display
```

### Local Development

```bash
# Set environment variables
export MQTT_URL=mqtt://tars:pass@192.168.1.100:1883
export DISPLAY_TIMEOUT_SEC=45
export LOG_LEVEL=DEBUG
export PYTHONPATH=/data/git/e-Paper/RaspberryPi_JetsonNano/python/lib:$PYTHONPATH

# Run with mock display (no hardware required)
export MOCK_DISPLAY=1
python -m ui_eink_display

# Run with real display
python -m ui_eink_display
```

## Display States

### Standby Mode
Sci-fi inspired screen showing "TARS REMOTE INTERFACE" and "AWAITING SIGNAL". System is operational and waiting for wake word.

### Listening Mode
Shows "● LISTENING ●" indicator. Wake word detected, system is capturing audio.

### Processing Mode
Displays user's transcribed message in right-aligned bubble with "transmitting..." indicator.

### Conversation Mode
Shows both user message (right) and TARS response (left) as message bubbles. If both don't fit, prioritizes TARS response only.

### Error Mode
Displays "⚠ ERROR ⚠" with error description. Shown when MQTT connection fails or display hardware errors occur.

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=ui_eink_display --cov-report=html

# Run specific test types
pytest tests/unit/
pytest tests/integration/
pytest tests/contract/

# Run with mock display
MOCK_DISPLAY=1 pytest
```

## Configuration

See `.env.example` for all available configuration options.

### Required Variables
- `MQTT_URL` - MQTT connection URL with credentials (e.g., `mqtt://tars:pass@192.168.1.100:1883`)

### Optional Variables
- `LOG_LEVEL` - Logging verbosity (default: INFO)
- `DISPLAY_TIMEOUT_SEC` - Seconds before returning to standby (default: 45)
- `MOCK_DISPLAY` - Set to 1 for testing without hardware (default: 0)
- `PYTHONPATH` - Path to waveshare-epd library
- `FONT_PATH` - Path to font files (default: /usr/share/fonts/truetype/dejavu)

## Architecture

- **config.py** - Environment configuration parsing
- **display_state.py** - State machine (STANDBY, LISTENING, PROCESSING, CONVERSATION, ERROR)
- **display_manager.py** - E-ink hardware control and rendering
- **message_formatter.py** - Text layout and wrapping logic
- **mqtt_handler.py** - MQTT subscriptions and message routing
- **__main__.py** - Service entry point

## Troubleshooting

### Display Not Initializing
- Check SPI is enabled: `ls /dev/spidev*`
- Verify GPIO permissions: `groups` (should include `gpio` or `spi`)
- Check display connections (refer to Waveshare wiring guide)

### MQTT Connection Fails
- Verify MQTT broker is reachable: `ping <broker-host>`
- Check broker is running on main TARS system
- Verify firewall allows port 1883
- Verify MQTT_URL credentials are correct

### Text Not Readable
- Check font files exist: `ls /usr/share/fonts/truetype/dejavu/`
- Verify display orientation (should be landscape)
- Test with shorter messages

## Development

### Adding New Display States
1. Add enum value to `DisplayMode` in `display_state.py`
2. Implement `render_<state>()` method in `display_manager.py`
3. Add state transition logic in `DisplayState.transition_to()`
4. Write tests in `tests/unit/test_display_state.py`

### Testing Without Hardware
Set `MOCK_DISPLAY=1` to use simulated display that logs updates instead of controlling hardware.

## License

Part of the py-tars project.
