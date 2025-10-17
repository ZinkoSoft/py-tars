# TARS Brain

A modular **AI “brain” stack** for the Orange Pi 5 Max that handles:
- **STT** (speech → text via Faster-Whisper)
- **Router** (rule-  ├─ wake-activation/         # OpenWakeWord detection
  ├─ llm-worker/              # LLM text generation with tool calling
  ├─ mcp-bridge/              # Build-time MCP server discovery & configuration
  ├─ memory-worker/           # Vector memory & character profilesd intent routing, fallback smalltalk)
- **TTS** (text → voice via Piper)
- **MQTT backbone** to glue everything together  

Motion and battery subsystems (ESP32-S3, LiPo pack, etc.) can connect later through MQTT topics.

**🆕 Current Capabilities:** This system now includes complete wake word detection, LLM integration with multiple providers, memory & RAG systems, real-time web UI, and support for both local and cloud-based STT/TTS services.

---

## 🧩 Architecture

```
[Mic] → STT Worker → MQTT → Router → MQTT → LLM Worker → MQTT → TTS Worker → [Speaker]
                      ↓         ↑                          ↑         ↑
               Wake Activation  │                          │         │
                      ↓         │                          │         │
                   Memory Worker ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ← ←
                      ↓         ↑                          ↑
               UI (Web/PyGame)  │                          │
                      ↓         │                          │
               Camera Service   │                          │
                                │                          │
                   MCP Bridge ← ← ← ← ← ← ← ← ← ← ← ← ← ← ←
```

**Event-Driven Pattern:** All services communicate through structured MQTT envelopes using the `tars-core` contracts package. Each service subscribes to specific topics, processes events, and publishes responses.

### MCP Tool Integration

TARS supports **Model Context Protocol (MCP)** for extending LLM capabilities with external tools. MCP servers are discovered and configured at **Docker build time**, then used by llm-worker at runtime.

**How It Works:**
1. **Build-Time Discovery** - MCP Bridge runs during `docker compose build llm`:
   - Scans `packages/tars-mcp-*/` for local MCP server packages
   - Scans `extensions/mcp-servers/` for extension packages
   - Loads external server configs from `ops/mcp/mcp.server.yml`
2. **Package Installation** - Python MCP packages are installed via pip (parallel)
3. **Config Generation** - Bridge generates `mcp-servers.json` configuration file
4. **Image Embedding** - Config is baked into the llm-worker Docker image at `/app/config/mcp-servers.json`
5. **Runtime Connection** - LLM Worker reads config at startup and connects to MCP servers
6. **Tool Execution** - When LLM calls tools, llm-worker executes them via MCP protocol

**Architecture:**
```
BUILD TIME (Docker Build):
  MCP Bridge → Discover Servers → Install Packages → Generate Config → Bake into Image

RUNTIME (llm-worker):
  Read Config → Connect to MCP Servers → Register Tools → Execute Tool Calls
```

**Adding MCP Servers:**

1. **Local Package** (recommended for Python tools):
   ```bash
   # Create package following naming convention
   packages/tars-mcp-mytools/
   ├── pyproject.toml
   └── src/tars_mcp_mytools/
       └── server.py
   ```

2. **External Config** (for npm packages or custom commands):
   ```yaml
   # ops/mcp/mcp.server.yml
   servers:
     - name: filesystem
       transport: stdio
       command: "npx"
       args: ["--yes", "@modelcontextprotocol/server-filesystem", "/workspace"]
       allowed_tools: ["read_file", "write_file", "list_dir"]
   ```

3. **Extension Directory** (for third-party packages):
   ```bash
   # Place external MCP servers here
   extensions/mcp-servers/custom-server/
   ```

**Rebuild After Changes:**
```bash
cd ops
docker compose build llm --no-cache  # MCP Bridge runs during build
docker compose up -d llm
```

**Supported Tool Types:**
- **Character Traits** - Adjust TARS personality dynamically (`tars-mcp-character`)
- **Filesystem Tools** - Read/write files, list directories
- **API Tools** - HTTP requests, database queries
- **Custom Tools** - Any MCP-compatible server implementation

**Note:** MCP Bridge is **not a runtime service** - it only runs during Docker builds to prepare the configuration. All runtime tool execution is handled by llm-worker.

---

## 📂 Repo Layout

### Core Topics
- `wake/event` — wakeword detection events
- `stt/partial` — streaming speech transcripts
- `stt/final` — finalized speech transcripts  
- `stt/audio_fft` — audio visualization data
- `llm/request` — LLM generation requests
- `llm/response` — LLM completions
- `llm/stream` — streaming LLM tokens
- `llm/tools/registry` — available MCP tools registry
- `llm/tool.call.request/#` — tool execution requests
- `llm/tool.call.result` — tool execution results
- `tts/say` — text-to-speech requests
- `tts/status` — TTS playback status
- `memory/query` — RAG memory queries
- `memory/results` — retrieved memory context
- `character/get` — character profile requests
- `camera/frame` — occasional camera frames for monitoring (MQTT)
- `system/health/+` — service health monitoring

### Services
- **MQTT Broker** (Mosquitto) — message bus for all services
- **STT Worker** — speech-to-text using Faster-Whisper, OpenAI Whisper API, or WebSocket STT
- **Wake Activation** — OpenWakeWord-based wake phrase detection with optional NPU acceleration (RK3588)
- **Router** — intent routing, wake word handling, live mode control
- **LLM Worker** — OpenAI/Gemini/local LLM text generation with optional RAG and tool calling
- **MCP Bridge** (build-time) — Discovers and configures MCP servers during Docker image builds
- **Memory Worker** — vector database for conversation memory and character profiles
- **TTS Worker** — text-to-speech using Piper or ElevenLabs  
- **Camera Service** — live video streaming via MQTT for mobile robot vision
- **UI (Web)** — FastAPI web interface with real-time MQTT display and camera viewer
- **UI (PyGame)** — optional desktop GUI with audio visualization

#### NPU Acceleration (RK3588 Devices)

TARS supports **hardware-accelerated wake word detection** on RK3588-based devices (Orange Pi 5 Max, Rock 5B, etc.) using the Neural Processing Unit (NPU). This provides **50x performance improvement** over CPU-based detection.

**Benefits:**
- **Ultra-fast inference**: ~1-2ms vs 50-100ms on CPU
- **Low power consumption**: Much more efficient than CPU processing  
- **Real-time responsiveness**: Near-instantaneous wake word detection

**Supported Devices:**
- Orange Pi 5 Max
- Rock 5B/5B+
- Other RK3588/RK3588S devices with NPU support

**Setup Requirements:**
1. RKNN drivers installed (`/dev/rknpu` device available)
2. Converted RKNN model (`hey_tars.rknn` from `hey_tars.tflite`)
3. NPU runtime libraries (`librknnrt.so`)

**Quick NPU Setup:**
```bash
# Automated NPU setup (one-time)
bash scripts/setup-rknpu.sh

# Convert wake word model
python scripts/convert_tflite_to_rknn.py \
  --input models/openwakeword/hey_tars.tflite \
  --output models/openwakeword/hey_tars.rknn

# Run with NPU acceleration
cd ops
docker compose --profile npu up wake-activation-npu
```

See `apps/wake-activation/README.md` for complete setup instructions.

---

## 📂 Repo Layout

```
py-tars/
├─ README.md
├─ .env.example                # Configuration template
├─ apps/                       # Individual microservices (each with pyproject.toml)
│  ├─ router/                  # Intent routing & wake word handling
│  ├─ stt-worker/              # Speech-to-text processing
│  ├─ tts-worker/              # Text-to-speech synthesis
│  ├─ wake-activation/         # OpenWakeWord detection
│  ├─ llm-worker/              # LLM text generation with tool calling
│  ├─ mcp-bridge/              # MCP tool integration for LLM
│  ├─ memory-worker/           # Vector memory & character profiles
│  ├─ camera-service/          # Live video streaming
│  ├─ ui-web/                  # FastAPI web interface
│  ├─ ui/                      # PyGame desktop interface
│  └─ voice/                   # Character profiles & voice configs
├─ packages/
│  └─ tars-core/              # Shared contracts & domain models
│     └─ src/tars/
│        ├─ contracts/        # Pydantic models & event registry
│        ├─ adapters/         # MQTT & external service adapters
│        ├─ domain/           # Core business logic
│        └─ runtime/          # Service composition utilities
├─ docker/                    # Centralized Docker build files
│  ├─ specialized/            # Service-specific Dockerfiles
│  ├─ images/                 # Shared base images (planned)
│  ├─ app.Dockerfile          # Generic wheel-based app template
│  └─ start-app.sh            # Generic app entrypoint
├─ ops/                       # Infrastructure & orchestration
│  ├─ compose.yml             # Main Docker Compose orchestration
│  ├─ mosquitto-config/       # MQTT broker config
│  ├─ mosquitto-data/         # Persistent broker data
│  └─ mcp/                    # MCP server configurations
│     └─ mcp.server.yml       # Tool server definitions
├─ scripts/                   # Development & testing scripts
│  ├─ run.tests.sh            # Test runner (creates venv, runs pytest)
│  └─ test-camera.sh          # Camera service test helper
├─ models/                    # AI model storage (gitignored)
│  ├─ whisper/                # STT models
│  └─ openwakeword/           # Wake detection models
├─ data/                      # Runtime data & caches (gitignored)
│  ├─ memory/                 # Memory worker storage
│  └─ model_cache/            # Sentence-transformer embeddings
└─ server/                    # Optional WebSocket STT service
   └─ stt-ws/                 # Faster-Whisper WebSocket backend
```

**Monorepo Architecture:** Each service in `apps/` is a self-contained Python package with its own `pyproject.toml` and dependencies. Services are built as wheels for efficient Docker image builds. The `packages/tars-core` package provides shared contracts, domain models, and utilities. All services communicate through well-defined MQTT events using structured JSON envelopes (via `orjson`).

**Build System:** Services use modern Python packaging (`pyproject.toml` + `setuptools`) and are installed as wheels in Docker images. Dockerfiles are centralized in `docker/specialized/` for easier maintenance. The generic `docker/app.Dockerfile` template supports wheel-based builds for any service.

### Standard App Structure

All services follow a consistent directory structure (src layout, Python best practices):

```
apps/<service-name>/
├── Makefile                    # Standard targets: fmt, lint, test, check
├── README.md                   # Service-specific documentation
├── pyproject.toml             # Python packaging (PEP 517/518)
├── .env.example               # Configuration template
├── src/                       # Source code (src layout)
│   └── <package_name>/
│       ├── __init__.py
│       ├── __main__.py        # Entry point for CLI
│       ├── config.py          # Configuration from env
│       └── service.py         # Core business logic
└── tests/                     # Test suite
    ├── conftest.py            # Shared pytest fixtures
    ├── unit/                  # Fast, isolated tests
    ├── integration/           # Cross-component tests
    └── contract/              # MQTT message validation
```

**Makefile Targets** (consistent across all services):
- `make fmt` - Format code (ruff + black)
- `make lint` - Lint and type-check (ruff + mypy)
- `make test` - Run tests with coverage
- `make check` - Run all checks (CI gate)
- `make install` - Install in editable mode
- `make install-dev` - Install with dev dependencies

**Development Workflow:**
```bash
cd apps/<service>
pip install -e ".[dev]"    # Install service + dev tools
make check                 # Format, lint, test
tars-<service>             # Run CLI entry point
```

---

## 🔌 Centralized MQTT Client

All services communicate through MQTT using a **centralized, production-ready MQTT client** from the `tars-core` package. This eliminates per-service MQTT boilerplate and ensures consistent behavior across the system.

**Key Features:**
- ✅ **Automatic reconnection** with exponential backoff (2-60s)
- ✅ **Message deduplication** to prevent duplicate processing
- ✅ **Health monitoring** with retained health topics
- ✅ **Heartbeat publishing** for liveness detection
- ✅ **Type-safe** event publishing/subscribing via Pydantic models
- ✅ **Context manager** support for clean resource management
- ✅ **Correlation IDs** for request-response patterns
- ✅ **Async-first** design with full asyncio integration

**Quick Example:**
```python
from tars.adapters.mqtt_client import MQTTClient

async def main():
    # Create client (auto-connects on first publish/subscribe)
    async with MQTTClient("mqtt://user:pass@localhost:1883", "my-service") as client:
        
        # Subscribe with handler
        async def handle_message(payload: bytes) -> None:
            envelope = Envelope.model_validate_json(payload)
            print(f"Received: {envelope.type} - {envelope.data}")
        
        await client.subscribe("test/topic", handle_message)
        
        # Publish event
        await client.publish_event(
            topic="test/response",
            event_type="test.response",
            data={"result": "success"},
            qos=1,
        )
```

**Code Reduction:** Services migrated to the centralized client see **60-68% reduction** in MQTT-related code while gaining better reliability and monitoring.

**Documentation:**
- **API Reference:** [`packages/tars-core/docs/API.md`](packages/tars-core/docs/API.md) - Complete method signatures and examples
- **Configuration:** [`packages/tars-core/docs/CONFIGURATION.md`](packages/tars-core/docs/CONFIGURATION.md) - Environment variables and setup
- **Migration Guide:** [`specs/004-centralize-mqtt-client/MIGRATION_GUIDE.md`](specs/004-centralize-mqtt-client/MIGRATION_GUIDE.md) - Step-by-step migration examples
- **Quickstart:** [`specs/004-centralize-mqtt-client/quickstart.md`](specs/004-centralize-mqtt-client/quickstart.md) - Patterns and best practices

**Services Using Centralized Client:**
- ✅ `llm-worker` - Request-response pattern with streaming
- ✅ `memory-worker` - RAG queries with correlation IDs  
- ✅ `wake-activation` - Health monitoring and event publishing
- 🔄 `stt-worker`, `router`, `tts-worker` - Migration planned (Phase 7)

---

## ⚙️ Requirements

- **Hardware:** Orange Pi 5 Max + NVMe SSD (Samsung 970 EVO recommended)
- **OS:** Ubuntu 22.04 / Joshua-Riek rockchip build
- **Audio:** USB mic + speakers (16 kHz mono capture recommended)
- **Docker & Compose:**
  ```bash
  sudo apt update && sudo apt install -y docker.io docker-compose
  sudo systemctl enable --now docker
  ```

---

## 🚀 Setup

### 1. Clone & Configure
```bash
git clone https://github.com/ZinkoSoft/py-tars.git
cd py-tars
cp .env.example .env
# Edit .env with your MQTT credentials and API keys
```

### 2. Set up MQTT Broker
```bash
# The ops/ directory already contains mosquitto configuration
# Update credentials if needed:
cd ops
docker run --rm -v $(pwd)/mosquitto-config:/config eclipse-mosquitto:2 mosquitto_passwd -c /config/passwd tars
# Enter your desired password when prompted
cd ..
```

### 3. Prepare Model Storage
```bash
# Create model directories
mkdir -p models/whisper models/openwakeword
# Download your preferred Whisper model to models/whisper/
# Place OpenWakeWord models in models/openwakeword/
```

### 4. Configure Voice Models
```bash
# For Piper TTS (local)
mkdir -p apps/tts-worker/voices
# Download TARS.onnx voice model to apps/tts-worker/voices/

# For ElevenLabs TTS (cloud) - set in .env:
# TTS_PROVIDER=elevenlabs
# ELEVEN_API_KEY=your_key
# ELEVEN_VOICE_ID=your_voice_id
```

### 5. Configure MCP Tools (Optional)
```bash
# MCP servers are auto-discovered from packages/tars-mcp-* at build time
# For external servers (npm, custom commands), edit:
nano ops/mcp/mcp.server.yml

# Example local package (automatically discovered):
# packages/tars-mcp-character/ - TARS personality trait adjustment tools

# Enable tool calling in environment
echo "TOOL_CALLING_ENABLED=1" >> .env
```

### 6. Build & Deploy
```bash
# Build and start all services (MCP Bridge runs during llm build)
cd ops
docker compose build
docker compose up -d

# Verify MCP configuration was generated (if tool calling enabled)
docker run --rm tars/llm:dev cat /app/config/mcp-servers.json | jq .

# Check service health
docker compose ps
docker compose logs -f

# Or from repo root:
docker compose -f ops/compose.yml up -d --build
```

### 7. Verify Deployment
```bash
# Check all services are running
cd ops
docker compose ps

# Monitor logs from all services
docker compose logs -f

# Monitor specific services
docker compose logs -f stt router llm tts

# Test the pipeline end-to-end
echo "Say 'Hey TARS' followed by a question..."
```

**First Time Setup:** The system will download required models on first startup. Check logs for download progress.

---

## 🔊 Audio Setup

The TTS service requires proper audio configuration to output speech. The setup varies depending on your audio hardware:

### Audio Output Options
- **HDMI Audio** (monitors/TVs with speakers)
- **3.5mm Headphone Jack** (headphones/speakers)
- **USB Audio Devices** (USB speakers/DACs)


1. **Check available audio devices:**
   ```bash
   aplay -l  # List ALSA devices
   pactl list short sinks  # List PulseAudio sinks
   ```

2. **Set default audio output:**
   ```bash
   # For HDMI0 output
   
   # For 3.5mm headphone jack (ES8388)
   pactl set-default-sink alsa_output.platform-es8388-sound.stereo-fallback
   ```

3. **Test audio output:**
   ```bash
   speaker-test -t wav -c 2 -l 1
   # or
   paplay /usr/share/sounds/alsa/Front_Left.wav
   ```

### Troubleshooting Audio

**No audio output:**
- Check if your audio device is connected and powered on
- Verify volume levels: `amixer sget Master`
- Ensure correct default sink is set (see commands above)
- For headphones: make sure they're plugged into the 3.5mm jack properly

**Wrong audio device:**
- Use `pactl list short sinks` to see available outputs
- Use `pactl set-default-sink <device-name>` to switch
- Restart TTS container after changing: `docker compose restart tts`

**Audio format issues:**
- The TTS container uses PulseAudio which handles format conversion automatically
- If direct ALSA fails, PulseAudio routing usually resolves compatibility issues

---

## 🧪 Testing

### 1. MQTT Health Check
```bash
# Monitor system health across all services
mosquitto_sub -h 127.0.0.1 -p 1883 -u tars -P change_me -t 'system/health/+' -v
```

### 2. Service Integration Tests
```bash
# Run the full test suite (creates venv at repo root, installs deps, runs pytest)
./scripts/run.tests.sh

# Or activate the venv and run tests manually
source .venv/bin/activate
pytest -v

# Run tests for specific services
pytest apps/stt-worker/tests/
pytest packages/tars-core/tests/
```

### 3. Individual Service Tests

**Wake Word Detection:**
```bash
# Check wake activation status
mosquitto_sub -h 127.0.0.1 -p 1883 -u tars -P change_me -t 'wake/+' -v
# Speak "Hey TARS" near your microphone
```

**Speech-to-Text Pipeline:**
```bash
# Monitor STT output
mosquitto_sub -h 127.0.0.1 -p 1883 -u tars -P change_me -t 'stt/+' -v
# Speak after wake word or in live mode
```

**Camera Streaming:**
```bash
# Monitor camera frames
mosquitto_sub -h 127.0.0.1 -p 1883 -u tars -P change_me -t 'camera/frame' -C 5
# Check camera health
mosquitto_sub -h 127.0.0.1 -p 1883 -u tars -P change_me -t 'system/health/camera' -v
```

**LLM Integration:**
```bash
# Test conversation flow
mosquitto_pub -h 127.0.0.1 -p 1883 -u tars -P change_me -t llm/request \
  -m '{"type":"llm.request","source":"test","data":{"messages":[{"role":"user","content":"Hello TARS"}]}}'
```

**MCP Tool Calling:**
```bash
# Verify MCP config was generated at build time
docker run --rm tars/llm:dev cat /app/config/mcp-servers.json | jq .

# Monitor tool registry (published by llm-worker at startup)
mosquitto_sub -h 127.0.0.1 -p 1883 -u tars -P change_me -t 'llm/tools/registry' -v

# Monitor tool calls (handled by llm-worker at runtime)
mosquitto_sub -h 127.0.0.1 -p 1883 -u tars -P change_me -t 'llm/tool.call.+' -v

# Test tool-enabled conversation (example: adjust TARS personality traits)
mosquitto_pub -h 127.0.0.1 -p 1883 -u tars -P change_me -t llm/request \
  -m '{"type":"llm.request","source":"test","data":{"messages":[{"role":"user","content":"Make yourself more confident"}]}}'
```

### 4. End-to-End Conversation Test
1. **Wake:** Say "Hey TARS" (should hear acknowledgment)
2. **Speak:** Ask a question within 8 seconds  
3. **Process:** Watch logs for STT → Router → LLM → TTS pipeline
4. **Response:** Hear TARS speak the generated response

---

## 🔧 Extending

### Adding New Services
Follow the monorepo pattern in `apps/`:
```bash
mkdir -p apps/my-worker/my_worker
cd apps/my-worker

# Create pyproject.toml for packaging
cat > pyproject.toml <<EOF
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "tars-my-worker"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "asyncio-mqtt>=0.16.2",
    "orjson>=3.11.0",
    "tars-core",
]

[tool.setuptools.packages.find]
where = [""]
include = ["my_worker*"]
EOF

# Create service logic using tars-core contracts
touch my_worker/__init__.py
touch my_worker/main.py

# Add Dockerfile in docker/specialized/my-worker.Dockerfile
# Update ops/compose.yml to add your service
```

### Custom LLM Providers
Extend `apps/llm-worker/llm_worker/providers/` with new provider implementations:
- Implement the base `LLMProvider` interface
- Add configuration in `.env` 
- Register in the provider factory

### New Event Types
1. Add Pydantic models to `packages/tars-core/src/tars/contracts/v1/`
2. Register event type → topic mappings in the registry
3. Update services to handle new events

### Memory & Character Customization
- Place character TOML files in `apps/memory-worker/characters/`
- Extend memory worker RAG strategies in `apps/memory-worker/memory_worker/hyperdb.py`
- Customize embedding models via `EMBED_MODEL` environment variable

### UI Extensions
- **Web UI:** Extend FastAPI routes in `apps/ui-web/`
- **Desktop UI:** Modify PyGame components in `apps/ui/`
- Both UIs automatically reflect new MQTT topics

### Integration Examples
- **Home Automation:** Subscribe to `tts/say` for smart home commands
- **Motion Control:** Publish to custom topics from ESP32/Arduino
- **External APIs:** Add new adapters in service `adapters/` directories

---

---

## ✨ Key Features

- **🎤 Multi-Backend STT:** Local Whisper, OpenAI API, or WebSocket server
- **🎯 Wake Word Detection:** "Hey TARS" activation using OpenWakeWord  
- **🤖 LLM Integration:** OpenAI, Gemini, xAI Grok, or local models with tool calling
- **🛠️ MCP Tool Support:** Build-time MCP server discovery with runtime tool execution (character traits, filesystem, APIs)
- **🧠 Memory System:** RAG-powered conversation memory with character profiles
- **🔊 Flexible TTS:** Local Piper or cloud ElevenLabs synthesis
- **📹 Camera Streaming:** Live video feed for mobile robot vision
- **🎛️ Live Monitoring:** Real-time web UI and optional desktop interface
- **📡 Event-Driven:** Loosely coupled services via MQTT with structured contracts
- **🐳 Container Ready:** Full Docker Compose orchestration with health monitoring
- **🔧 Extensible:** Plugin architecture for easy service additions

---

## 📈 Performance (Orange Pi 5 Max)

**Typical Latencies:**
- **Wake Detection:** <100ms from "Hey TARS" to acknowledgment
- **STT Processing:** 0.5-1.5s from speech end to final transcript (Whisper small)
- **LLM Generation:** 1-3s for short responses (depends on provider/model)
- **TTS Synthesis:** <400ms first phrase, <200ms steady state (Piper)
- **End-to-End:** 2-5s from question to audible response

**Resource Usage:**
- **Memory:** ~2-4GB total (varies by loaded models)
- **CPU:** Moderate during inference, idle otherwise
- **Storage:** ~1-2GB for base models (Whisper small + Piper voice)

**Optimization Tips:**
- Use `WHISPER_MODEL=tiny` for faster STT at cost of accuracy
- Enable `TTS_STREAMING=1` to reduce time-to-first-audio
- Use cloud providers (OpenAI STT/LLM, ElevenLabs TTS) for better performance on limited hardware

---

## 📌 Roadmap / TODOs

### Completed ✅
- [x] **STT Worker** with multiple backends (Whisper, OpenAI, WebSocket)
- [x] **Wake Word Detection** using OpenWakeWord 
- [x] **LLM Integration** with multiple providers (OpenAI, Gemini, xAI Grok, local models)
- [x] **MCP Tool Integration** - Build-time discovery and configuration, runtime execution via Model Context Protocol
- [x] **Memory System** with RAG and character profiles
- [x] **Streaming TTS** with Piper and ElevenLabs support
- [x] **Camera Service** with live video streaming via MQTT
- [x] **Web & Desktop UIs** with real-time MQTT monitoring
- [x] **Event-driven Architecture** with structured MQTT contracts
- [x] **Centralized Docker Build** system with wheel-based packaging
- [x] **Monorepo Packaging** with pyproject.toml for all services
- [x] **Automated Testing** with pytest and async test support

### In Progress 🚧
- [ ] **Base Docker Images** - refactor common layers into shared base image
- [ ] **CI/CD Pipeline** - automated builds and tests on push
- [ ] **Vision Processing** worker for image/camera input to LLM
- [ ] **Enhanced Router** with intent classification beyond simple rules
- [ ] **Health Dashboard** with Prometheus/Grafana monitoring

### Planned 📋
- [ ] **Motion Cues** publishing (`tts/cues`) for gesture synchronization
- [ ] **Multi-language Support** with language detection and switching
- [ ] **Voice Cloning** integration for personalized TTS
- [ ] **Plugin System** for easy third-party extensions
- [ ] **Mobile App** companion with push notifications
- [ ] **Kubernetes Deployment** manifests for cloud/edge deployment
