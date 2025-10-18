# TARS STT Worker

Speech-to-text worker that streams microphone audio through Whisper, applies suppression heuristics, and publishes transcriptions over MQTT. Packaged as `tars-stt-worker` for deployment inside the TARS voice assistant stack.

## Installation

```bash
pip install -e .
```

For development:
```bash
pip install -e ".[dev]"
```

## Usage

Run the STT worker:
```bash
tars-stt-worker
```

Or with Python module syntax:
```bash
python -m stt_worker
```

## Configuration

### Unified Configuration Management (Recommended)

As of spec 005, STT worker integrates with the centralized **ConfigLibrary** for runtime configuration management:

- **Initial load**: Configuration is loaded from the config database at startup
- **Runtime updates**: Changes made via the Config Manager UI are applied live via MQTT (no restart required)
- **Fallback**: If database is unavailable, falls back to Last-Known-Good (LKG) cache, then environment variables

**Key fields** (defined in `tars.config.models.STTWorkerConfig`):
- `whisper_model` - Whisper model size (e.g., "base.en", "small", "medium")
- `stt_backend` - Backend type: "whisper" or "ws"
- `ws_url` - WebSocket backend URL (when backend=ws)
- `streaming_partials` - Enable partial transcriptions (bool)
- `vad_threshold` - Voice activity detection threshold (0.0-1.0)
- `sample_rate` - Audio sample rate in Hz
- `channels` - Audio channels (1=mono, 2=stereo)

Configuration can be edited via:
1. **Config Manager UI** (recommended) - Web interface at `http://localhost:5173` (Config drawer)
2. **Config Manager API** - REST API at `http://localhost:8081/api/config/services/stt-worker`
3. **Environment variables** (legacy fallback)

### Legacy Environment Variables

All configuration is also available via environment variables. See `.env.example` for complete list.

**Note**: Environment variables take precedence over database configuration during the migration period.

### Core Settings
- `MQTT_URL` - MQTT broker URL (default: `mqtt://localhost:1883`)
- `WHISPER_MODEL` - Whisper model size (default: `base.en`)
- `STT_BACKEND` - Backend type: `whisper` or `ws` (default: `whisper`)
- `WS_URL` - WebSocket backend URL (when `STT_BACKEND=ws`)

### Audio Settings
- `SAMPLE_RATE` - Audio sample rate (default: `16000`)
- `CHUNK_SIZE` - Audio chunk size (default: `512`)
- `VAD_AGGRESSIVENESS` - VAD sensitivity 0-3 (default: `3`)
- `SILENCE_DURATION` - Silence threshold in seconds (default: `1.0`)

### Streaming & Partials
- `STREAMING_PARTIALS` - Enable partial transcriptions (default: `0`)
- `PARTIAL_INTERVAL` - Interval for partials in seconds (default: `0.5`)

### Suppression Heuristics
- `SUPPRESS_ECHO` - Enable echo suppression (default: `1`)
- `SUPPRESS_REPEATS` - Enable repeat detection (default: `1`)
- `SUPPRESS_NOISE` - Enable noise filtering (default: `1`)

### FFT Telemetry
- `FFT_PUBLISH` - Publish FFT to MQTT (default: `1`)
- `FFT_WS_ENABLE` - Enable WebSocket FFT server (default: `0`)
- `FFT_WS_HOST` - WebSocket host (default: `0.0.0.0`)
- `FFT_WS_PORT` - WebSocket port (default: `8765`)
- `FFT_WS_PATH` - WebSocket path (default: `/fft`)

## Development

### Running tests
```bash
make test
```

### Formatting and linting
```bash
make check
```

### Available Make targets
- `make fmt` - Format code
- `make lint` - Lint and type-check
- `make test` - Run tests with coverage
- `make check` - Run all checks (CI gate)
- `make build` - Build package
- `make clean` - Remove artifacts

## Architecture

The STT worker follows an event-driven architecture:

1. **Audio Capture** (`audio_capture.py`) - Captures microphone input via PyAudio
2. **VAD** (`vad.py`) - Voice activity detection to segment speech
3. **Transcription** (`transcriber.py`) - Whisper-based transcription (local or WebSocket)
4. **Suppression** (`suppression.py`) - Heuristics to filter noise, echoes, repeats
5. **MQTT Publishing** - Publishes final/partial transcriptions to MQTT

### FFT Telemetry

The worker can surface a down-sampled FFT feed for UI spectrum renders. By default it still publishes frames over MQTT (`stt/audio_fft`); set `FFT_PUBLISH=0` to disable that channel. For lightweight consumers, enable the built-in WebSocket fan-out by setting `FFT_WS_ENABLE=1` (and optionally adjust `FFT_WS_HOST`, `FFT_WS_PORT`, or `FFT_WS_PATH`). Clients can then connect to `ws://<host>:<port><path>` and receive JSON payloads shaped as `{"fft": [...], "ts": <epoch_seconds>}`.

## MQTT Topics

### Published
- `stt/final` - Final transcriptions with confidence scores
  ```json
  {
    "text": "transcribed text",
    "lang": "en",
    "confidence": 0.95,
    "timestamp": 1234567890.123,
    "is_final": true
  }
  ```
- `stt/partial` - Partial transcriptions (when `STREAMING_PARTIALS=1`)
  ```json
  {
    "text": "partial transcription",
    "confidence": 0.80,
    "is_final": false
  }
  ```
- `stt/audio_fft` - FFT spectrum data (when `FFT_PUBLISH=1`)
  ```json
  {
    "fft": [0.1, 0.2, ...],
    "ts": 1234567890.123
  }
  ```
- `system/health/stt` - Health status (retained)
  ```json
  {
    "ok": true,
    "event": "started"
  }
  ```

### Subscribed
- `wake/event` - Wake word detection events to trigger transcription
