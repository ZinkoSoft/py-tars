# TARS UI

A lightweight pygame-based UI for TARS that visualizes:
- Live microphone spectrum (FFT-based)
- Recent STT client output (final transcripts)
- Recent AI responses (TTS text)

This app subscribes to MQTT topics published by the existing TARS stack and renders a simple dashboard suitable for various displays.

## Topics
- `stt/partial` (optional): shows transient text while speaking
- `stt/final`: displays last transcript
- `tts/status`: shows last AI response when `speaking_start` arrives

## FFT Stream
The spectrum visual pulls data from the STT worker's websocket hub (defaults to `ws://127.0.0.1:8765/fft`).

- Enable the hub by setting `FFT_WS_ENABLE=1` for the STT worker.
- Configure the UI via `[fft_ws]` in `ui.toml` or `UI_FFT_WS_URL` / `UI_FFT_WS_ENABLE` environment variables.
- Set `[fft_ws].enabled = false` (or `UI_FFT_WS_ENABLE=0`) to fall back to the legacy `stt/audio_fft` MQTT topic if needed.

## Layout Configuration

The UI uses a JSON-based layout system to position components like the spectrum bars and idle screen. Layouts are defined in `layout.json` and support different orientations (landscape/portrait) and rotations (0°, 90°, 180°, 270°).

### Components
- `spectrum`: FFT-based audio spectrum bars.
- `tars_idle`: Sci-fi idle screen with matrix rain and geometric shapes (renders as background).

### Coordinate System
- **x, y, width, height**: Normalized coordinates (0.0 to 1.0) representing fractions of the screen dimensions.
  - `x`: Horizontal position as a fraction of screen width (0.0 = left edge, 1.0 = right edge).
  - `y`: Vertical position as a fraction of screen height (0.0 = top edge, 1.0 = bottom edge).
  - `width`: Component width as a fraction of screen width.
  - `height`: Component height as a fraction of screen height.
- These normalized values are converted to pixel coordinates at runtime, accounting for screen resolution and rotation.
- Rotation transforms the coordinates: e.g., 90° rotation swaps width/height and adjusts positioning.

### Example Layout
```json
{
  "landscape": [
    {
      "name": "tars_idle",
      "x": 0.0,
      "y": 0.0,
      "width": 1.0,
      "height": 1.0,
      "expandable": false
    },
    {
      "name": "spectrum",
      "x": 0.0,
      "y": 0.0,
      "width": 1.0,
      "height": 1.0,
      "expandable": false
    }
  ],
  "portrait": [
    {
      "name": "tars_idle",
      "x": 0.0,
      "y": 0.0,
      "width": 1.0,
      "height": 1.0,
      "expandable": false
    },
    {
      "name": "spectrum",
      "x": 0.0,
      "y": 0.0,
      "width": 1.0,
      "height": 1.0,
      "expandable": false
    }
  ]
}
```

- `landscape`: Layout for horizontal orientations (0°/180° rotation).
- `portrait`: Layout for vertical orientations (90°/270° rotation).
- `name`: Component identifier (e.g., "spectrum" for FFT bars, "tars_idle" for idle screen).
- `expandable`: Reserved for future use (currently ignored).

If no matching orientation is found, the UI falls back to a default full-width spectrum layout.

## Run (Host, Recommended)
Install system packages, create a venv, install Python deps, and run directly.

1) System packages (Debian/Ubuntu/Raspberry Pi OS):
   - sudo apt-get update
   - sudo apt-get install -y python3-venv python3-dev libsdl2-2.0-0 libsdl2-ttf-2.0-0 libx11-6 libxext6 libxrender1 libxrandr2 libxcursor1 libxi6 fonts-dejavu-core

2) Python venv + deps:
   - cd apps/ui
   - python3 -m venv .venv
   - source .venv/bin/activate
   - pip install --upgrade pip
   - pip install -r requirements.txt

3) Configure broker and layout:
   - Set MQTT_URL env, e.g. `export MQTT_URL="mqtt://user:pass@127.0.0.1:1883"`
   - Edit `ui.toml` for UI settings (screen size, layout file, rotation, etc.)
   - Customize `layout.json` for component positioning

4) Run:
   - python -u main.py

Optional: systemd user service to auto-start on login/boot:

~/.config/systemd/user/tars-ui.service

[Unit]
Description=TARS UI
After=default.target

[Service]
Type=simple
Environment=MQTT_URL=mqtt://user:pass@127.0.0.1:1883
WorkingDirectory=%h/git/py-tars/apps/ui
ExecStart=%h/git/py-tars/apps/ui/.venv/bin/python -u main.py
Restart=on-failure

[Install]
WantedBy=default.target

Then enable and start:
   - systemctl --user daemon-reload
   - systemctl --user enable --now tars-ui

Note: If running on a desktop with Wayland, ensure a running XWayland or set `SDL_VIDEODRIVER=wayland`.

## Run (Container)
This app is also packaged as a container in `docker-compose.yml` (service: `ui`). Ensure the host X server is accessible:
   - xhost +local:
Then:
   - docker compose --profile ui up -d ui
