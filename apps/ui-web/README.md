# TARS UI Web

A modern Vue.js 3 TypeScript web interface for monitoring and interacting with TARS services. The UI provides a real-time chat interface and modular drawer panels for inspecting system state.

## Features

- **Chat Interface** - Interactive conversation with TARS, displaying STT transcripts, LLM responses, and TTS status
- **Audio Spectrum** - Live audio FFT visualization
- **Memory Inspector** - Query memory and view retrieval results
- **MQTT Stream Monitor** - Real-time view of all MQTT messages with JSON payload inspection
- **Health Dashboard** - Service health monitoring with timeout detection
- **Camera Feed** - Placeholder for future camera integration

## Architecture

### Backend (Python)
- **FastAPI** server serving the Vue.js application and providing WebSocket bridge
- **MQTT integration** - Subscribes to all TARS topics and forwards to WebSocket clients
- **REST API** - `/api/memory` endpoint for memory queries

### Frontend (Vue.js 3 + TypeScript)
- **Modern SPA** - Built with Vite for fast development and optimized production builds
- **State Management** - Pinia stores for WebSocket, chat, health, MQTT log, and UI state
- **Type Safety** - Full TypeScript coverage with strict mode
- **Component Architecture** - Reusable components and modular drawer system

## Installation

### Backend
```bash
pip install -e .
```

For development:
```bash
pip install -e ".[dev]"
```

### Frontend
```bash
cd frontend
npm install
```

## Usage

### Development Mode (Recommended)

Run backend and frontend separately for hot module replacement:

```bash
# Terminal 1: Backend server (port 8080)
tars-ui-web

# Terminal 2: Frontend dev server (port 5173)
cd frontend
npm run dev
```

Open <http://localhost:5173> - Vite dev server proxies WebSocket/API to backend.

### Production Mode

Build frontend and serve via backend:

```bash
# Build frontend
cd frontend
npm run build

# Run backend (serves built frontend)
cd ..
tars-ui-web
```

Open <http://localhost:8080>

## Frontend Development

See [frontend/README.md](frontend/README.md) for detailed component documentation and development guide.

### Quick Commands

```bash
cd frontend

# Development
npm run dev          # Start Vite dev server
npm run build        # Build for production
npm run preview      # Preview production build

# Quality
npm run format       # Format code (Prettier)
npm run lint         # Lint code (ESLint)
npm run type-check   # TypeScript validation
npm run test         # Run tests (Vitest)
npm run check        # Run all checks (CI gate)
```

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

## Backend Development

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
- `make frontend-install` - Install frontend dependencies
- `make frontend-dev` - Run frontend dev server
- `make frontend-build` - Build frontend for production
- `make frontend-check` - Run frontend checks

## MQTT Topics

### Subscribed
- `stt/partial` - Partial speech transcripts
- `stt/final` - Final speech transcripts
- `stt/audio_fft` - Audio spectrum data (FFT bins)
- `tts/status` - TTS playback status (speaking_start/speaking_end)
- `tts/say` - TTS synthesis requests
- `llm/stream` - Streaming LLM responses (deltas)
- `llm/response` - Complete LLM responses
- `memory/results` - Memory query results
- `system/health/#` - Health status from all services

### Published
- `memory/query` - Memory query requests (via REST API)

## Tips

- **MQTT Stream** - The drawer retains the most recent 200 messages. Use the **Clear** button to reset.
- **Keyboard Shortcuts** - Press `Esc` to close the currently open drawer.
- **Health Monitoring** - Services are marked unhealthy if no ping received for 30 seconds.
- **Audio Spectrum** - FFT visualization fades to baseline after 2 seconds of no data.
- **Development** - Use Vite dev server for instant hot module replacement.

## Technology Stack

- **Backend**: Python 3.11+, FastAPI 0.111+, asyncio-mqtt 0.16+
- **Frontend**: Vue 3.4+, TypeScript 5.0+, Vite 5.0+, Pinia 2.1+
- **Testing**: pytest (backend), Vitest (frontend)
- **Build**: Multi-stage Docker with Node.js builder + Python runtime

For detailed frontend architecture and component documentation, see [frontend/README.md](frontend/README.md).

For development patterns and best practices, see [Quickstart Guide](../../specs/004-convert-ui-web/quickstart.md).
