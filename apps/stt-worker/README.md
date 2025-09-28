# TARS STT Worker

Speech-to-text worker that streams microphone audio through Whisper, applies suppression heuristics, and publishes transcriptions over MQTT. Packaged as `tars-stt-worker` for deployment inside the TARS voice assistant stack.

## FFT telemetry

The worker can surface a down-sampled FFT feed for UI spectrum renders. By default it still publishes frames over MQTT (`stt/audio_fft`); set `FFT_PUBLISH=0` to disable that channel. For lightweight consumers, enable the built-in WebSocket fan-out by setting `FFT_WS_ENABLE=1` (and optionally adjust `FFT_WS_HOST`, `FFT_WS_PORT`, or `FFT_WS_PATH`). Clients can then connect to `ws://<host>:<port><path>` and receive JSON payloads shaped as `{"fft": [...], "ts": <epoch_seconds>}`.
