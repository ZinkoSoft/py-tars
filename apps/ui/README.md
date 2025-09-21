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

## Run
This app is packaged as a container in `docker-compose.yml` (service: `ui`). Ensure the Pi has pygame dependencies and the container can access the display.
