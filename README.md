# TARS Brain

A modular **AI “brain” stack** for the Orange Pi 5 Max that handles:
- **STT** (speech → text via Faster-Whisper)
- **Router** (rule-based intent routing, fallback smalltalk)
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

TARS supports **Model Context Protocol (MCP)** for extending LLM capabilities with external tools. The MCP Bridge service connects to MCP-compatible servers and exposes their tools to the LLM worker.

**How It Works:**
1. **MCP Bridge** loads server configurations from `ops/mcp/mcp.server.yml`
2. **Tool Discovery** - Bridge connects to each MCP server and enumerates available tools
3. **Registry Publishing** - Tools are published to `llm/tools/registry` as OpenAI-compatible function specs
4. **LLM Enhancement** - LLM Worker receives tool registry and includes tools in API requests
5. **Tool Execution** - When LLM calls tools, requests go via MQTT to MCP Bridge
6. **Result Integration** - Tool results are returned and LLM generates follow-up responses

**Example Configuration** (`ops/mcp/mcp.server.yml`):
```yaml
servers:
  - name: filesystem
    transport: stdio
    command: "mcp-filesystem"
    args: ["--root","/home/user/work"]
    tools_allowlist: ["read_file","write_file","list_dir"]
```

**Supported Tool Types:**
- **Filesystem Tools** - read/write files, list directories
- **API Tools** - HTTP requests, database queries
- **Custom Tools** - any MCP-compatible server implementation

**Enabling Tool Calling:**
```bash
# In .env file
TOOL_CALLING_ENABLED=1
```

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
- **Wake Activation** — OpenWakeWord-based wake phrase detection
- **Router** — intent routing, wake word handling, live mode control
- **LLM Worker** — OpenAI/Gemini/local LLM text generation with optional RAG and tool calling
- **MCP Bridge** — Model Context Protocol integration enabling LLM tool usage (filesystem, APIs, etc.)
- **Memory Worker** — vector database for conversation memory and character profiles
- **TTS Worker** — text-to-speech using Piper or ElevenLabs  
- **Camera Service** — live video streaming via MQTT for mobile robot vision
- **UI (Web)** — FastAPI web interface with real-time MQTT display and camera viewer
- **UI (PyGame)** — optional desktop GUI with audio visualization

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
# Edit MCP server configuration
nano ops/mcp/mcp.server.yml

# Enable tool calling in environment
echo "TOOL_CALLING_ENABLED=1" >> .env
```

### 6. Build & Deploy
```bash
# Build and start all services
cd ops
docker compose build
docker compose up -d

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
# Monitor tool registry
mosquitto_sub -h 127.0.0.1 -p 1883 -u tars -P change_me -t 'llm/tools/registry' -v

# Monitor tool calls
mosquitto_sub -h 127.0.0.1 -p 1883 -u tars -P change_me -t 'llm/tool.call.+' -v

# Test tool-enabled conversation
mosquitto_pub -h 127.0.0.1 -p 1883 -u tars -P change_me -t llm/request \
  -m '{"type":"llm.request","source":"test","data":{"messages":[{"role":"user","content":"List the files in the current directory"}]}}'
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
- Place character TOML files in `apps/voice/characters/`
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
- **🛠️ MCP Tool Support:** Model Context Protocol integration for filesystem access, APIs, and custom tools
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
- [x] **MCP Tool Integration** for LLM tool calling via Model Context Protocol
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
