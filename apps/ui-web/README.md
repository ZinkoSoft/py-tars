# TARS UI Web

A lightweight WebSocket-powered debug UI for monitoring TARS services. The interface offers pop-out drawers to inspect key data streams:

- **Microphone** – live audio spectrum and partial/final STT transcripts.
- **Memory** – query the memory worker and review the latest retrieval results.
- **MQTT Stream** – real-time view of MQTT events flowing through the system with JSON payload introspection and a clearable history buffer.

## Installation

```bash
pip install -e .
```

For development:
```bash
pip install -e ".[dev]"
```

## Usage

### Running the server

```bash
tars-ui-web
```

Or directly:
```bash
python -m ui_web
```

Then open <http://localhost:8080> in your browser. The UI connects to the same MQTT broker as the backend services via the WebSocket bridge exposed by the server.

## Configuration

Environment variables:

- `MQTT_URL` - MQTT broker URL (default: `mqtt://tars:pass@127.0.0.1:1883`)
- `UI_PARTIAL_TOPIC` - STT partial transcript topic (default: `stt/partial`)
- `UI_FINAL_TOPIC` - STT final transcript topic (default: `stt/final`)
- `UI_AUDIO_TOPIC` - Audio FFT data topic (default: `stt/audio_fft`)
- `UI_TTS_TOPIC` - TTS status topic (default: `tts/status`)
- `UI_TTS_SAY_TOPIC` - TTS say topic (default: `tts/say`)
- `UI_LLM_STREAM_TOPIC` - LLM streaming topic (default: `llm/stream`)
- `UI_LLM_RESPONSE_TOPIC` - LLM response topic (default: `llm/response`)
- `UI_MEMORY_QUERY` - Memory query topic (default: `memory/query`)
- `UI_MEMORY_RESULTS` - Memory results topic (default: `memory/results`)
- `UI_HEALTH_TOPIC` - Health status topic pattern (default: `system/health/#`)
- `LOG_LEVEL` - Logging level (default: `INFO`)

See `.env.example` for complete list.

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

The ui-web service provides a FastAPI-based web server that:

1. **Serves static HTML** - The main UI interface
2. **WebSocket bridge** - Forwards MQTT messages to browser clients
3. **REST API** - `/api/memory` endpoint for memory queries
4. **MQTT integration** - Subscribes to all relevant topics and broadcasts to connected WebSocket clients

### Components

- `config.py` - Configuration management
- `__main__.py` - FastAPI application and MQTT bridge

## MQTT Topics

### Subscribed
- `stt/partial` - Partial speech transcripts
- `stt/final` - Final speech transcripts
- `stt/audio_fft` - Audio spectrum data
- `tts/status` - TTS playback status
- `tts/say` - TTS synthesis requests
- `llm/stream` - Streaming LLM responses
- `llm/response` - Complete LLM responses
- `memory/results` - Memory query results
- `system/health/#` - Health status from all services

### Published
- `memory/query` - Memory query requests (via REST API)

## Tips

- The MQTT stream drawer retains the most recent 200 messages. Use the **Clear** button to reset the log while monitoring.
- Drawer state is keyboard-accessible; press `Esc` to close the currently open drawer.
- The page is designed for debugging and observability. It does not attempt to send messages back over MQTT—use it alongside the core apps in this repo.
