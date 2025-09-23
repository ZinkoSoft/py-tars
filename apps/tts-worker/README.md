# TTS Worker

Uses Piper by default for local TTS. Subscribes to `tts/say` and plays audio via PulseAudio/ALSA.

## External providers

You can switch to ElevenLabs by setting the following environment variables for the `tts` service:

- TTS_PROVIDER=elevenlabs
- ELEVEN_API_KEY=... (required)
- ELEVEN_VOICE_ID=... (required)
- ELEVEN_API_BASE (optional, default https://api.elevenlabs.io/v1)
- ELEVEN_MODEL_ID (optional, default eleven_multilingual_v2)
- ELEVEN_OPTIMIZE_STREAMING (optional 0-3)

When using ElevenLabs, the worker will stream audio to the system player for low latency; if streaming fails, it will fall back to synthesizing a WAV then playing it.
