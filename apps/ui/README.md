# TARS UI (Raspberry Pi 5" IPS Display)

A lightweight pygame-based UI that visualizes:
- Live microphone spectrum (FFT-based)
- Recent STT client output (final transcripts)
- Recent AI responses (TTS text)

This app subscribes to MQTT topics published by the existing stack and renders a simple dashboard suitable for a 5" touchscreen.

## Topics
- `stt/partial` (optional): shows transient text while speaking
- `stt/final`: displays last transcript
- `tts/status`: shows last AI response when `speaking_start` arrives

## FFT stream
The spectrum visual now pulls data from the STT worker's websocket hub (defaults to `ws://127.0.0.1:8765/fft`).

- Enable the hub by setting `FFT_WS_ENABLE=1` for the STT worker.
- Configure the UI via `[fft_ws]` in `ui.toml` or `UI_FFT_WS_URL` / `UI_FFT_WS_ENABLE` environment variables.
- Set `[fft_ws].enabled = false` (or `UI_FFT_WS_ENABLE=0`) to fall back to the legacy `stt/audio_fft` MQTT topic if needed.

## Run (host, recommended on Pi)
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

3) Configure broker:
	- Either set MQTT_URL env, e.g. export MQTT_URL="mqtt://user:pass@127.0.0.1:1883"
	- Or edit `ui.toml` to set `[mqtt].url`

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

Note: If running on a desktop with Wayland, ensure a running XWayland or set SDL_VIDEODRIVER=wayland.

## Run (container)
This app is also packaged as a container in `docker-compose.yml` (service: `ui`). Ensure the host X server is accessible:
	- xhost +local:
Then:
	- docker compose --profile ui up -d ui
