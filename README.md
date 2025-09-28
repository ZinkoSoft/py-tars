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
                      ↓        ↑                         ↑
               Wake Activation  │                         │
                      ↓        │                         │
                   Memory Worker ← ← ← ← ← ← ← ← ← ← ← ← ← ←
                      ↓
               UI (Web/PyGame)
```

**Event-Driven Pattern:** All services communicate through structured MQTT envelopes using the `tars-core` contracts package. Each service subscribes to specific topics, processes events, and publishes responses.

### Core Topics
- `wake/event` — wakeword detection events
- `stt/partial` — streaming speech transcripts
- `stt/final` — finalized speech transcripts  
- `stt/audio_fft` — audio visualization data
- `llm/request` — LLM generation requests
- `llm/response` — LLM completions
- `llm/stream` — streaming LLM tokens
- `tts/say` — text-to-speech requests
- `tts/status` — TTS playback status
- `memory/query` — RAG memory queries
- `memory/results` — retrieved memory context
- `character/get` — character profile requests
- `system/health/+` — service health monitoring

### Services
- **MQTT Broker** (Mosquitto) — message bus for all services
- **STT Worker** — speech-to-text using Faster-Whisper, OpenAI Whisper API, or WebSocket STT
- **Wake Activation** — OpenWakeWord-based wake phrase detection
- **Router** — intent routing, wake word handling, live mode control
- **LLM Worker** — OpenAI/Gemini/local LLM text generation with optional RAG
- **Memory Worker** — vector database for conversation memory and character profiles
- **TTS Worker** — text-to-speech using Piper or ElevenLabs  
- **UI (Web)** — FastAPI web interface with real-time MQTT display
- **UI (PyGame)** — optional desktop GUI with audio visualization

---

## 📂 Repo Layout

```
py-tars/
├─ README.md
├─ docker-compose.yml           # Multi-service orchestration
├─ apps/                        # Individual microservices
│  ├─ router/                   # Intent routing & wake word handling
│  ├─ stt-worker/               # Speech-to-text processing
│  ├─ tts-worker/               # Text-to-speech synthesis
│  ├─ wake-activation/          # OpenWakeWord detection
│  ├─ llm-worker/               # LLM text generation
│  ├─ memory-worker/            # Vector memory & character profiles
│  ├─ ui-web/                   # FastAPI web interface
│  └─ ui/                       # PyGame desktop interface
├─ packages/
│  └─ tars-core/               # Shared contracts & domain models
│     └─ src/tars/
│        ├─ contracts/         # Pydantic models & event registry
│        ├─ adapters/          # MQTT & external service adapters
│        ├─ domain/            # Core business logic
│        └─ runtime/           # Service composition utilities
├─ ops/                        # Infrastructure configs
│  ├─ mosquitto-config/        # MQTT broker config
│  └─ mosquitto-data/          # Persistent broker data
├─ models/                     # AI model storage
│  ├─ whisper/                 # STT models
│  └─ openwakeword/            # Wake detection models
├─ server/                     # Optional WebSocket STT service
└─ .env.example               # Configuration template
```

**Monorepo Architecture:** Each service in `apps/` is a self-contained package with its own dependencies, while `packages/tars-core` provides shared contracts and utilities. Services communicate through well-defined MQTT events using structured JSON envelopes.

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
# Create MQTT user credentials
mkdir -p ops/mosquitto-config ops/mosquitto-data
echo "listener 1883 0.0.0.0" > ops/mosquitto-config/mosquitto.conf
echo "allow_anonymous false" >> ops/mosquitto-config/mosquitto.conf  
echo "password_file /mosquitto/config/passwd" >> ops/mosquitto-config/mosquitto.conf
docker run --rm -v $(pwd)/ops/mosquitto-config:/config eclipse-mosquitto:2 mosquitto_passwd -c /config/passwd tars
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

### 5. Build & Deploy
```bash
docker compose build
docker compose up -d

# Check service health
docker compose ps
docker compose logs -f
```

### 6. Verify Deployment
```bash
# Check all services are running
docker compose ps

# Monitor logs from all services
docker compose logs -f

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
# Run the full test suite (creates venv, installs deps, runs pytest)
./run.tests.sh

# Or run tests manually with pytest
python -m pytest apps/*/tests/ packages/tars-core/tests/
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

**Text-to-Speech:**
```bash
# Direct TTS test
mosquitto_pub -h 127.0.0.1 -p 1883 -u tars -P change_me -t tts/say \
  -m '{"type":"tts.say","source":"test","data":{"text":"TARS system operational."}}'
```

**LLM Integration:**
```bash
# Test conversation flow
mosquitto_pub -h 127.0.0.1 -p 1883 -u tars -P change_me -t llm/request \
  -m '{"type":"llm.request","source":"test","data":{"messages":[{"role":"user","content":"Hello TARS"}]}}'
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
mkdir apps/my-worker
cd apps/my-worker
# Create pyproject.toml, main.py, and service logic
# Use tars-core contracts for MQTT communication
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
- **🤖 LLM Integration:** OpenAI, Gemini, xAI Grok, or local models
- **🧠 Memory System:** RAG-powered conversation memory with character profiles
- **🔊 Flexible TTS:** Local Piper or cloud ElevenLabs synthesis
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
- [x] **LLM Integration** with multiple providers (OpenAI, Gemini, local models)
- [x] **Memory System** with RAG and character profiles
- [x] **Streaming TTS** with Piper and ElevenLabs support
- [x] **Web & Desktop UIs** with real-time MQTT monitoring
- [x] **Event-driven Architecture** with structured MQTT contracts

### In Progress 🚧
- [ ] **MCP (Model Context Protocol) Server** integration for tool calling
- [ ] **Vision Processing** worker for image/camera input
- [ ] **Enhanced Router** with intent classification beyond simple rules
- [ ] **Health Dashboard** with Prometheus/Grafana monitoring

### Planned 📋
- [ ] **Motion Cues** publishing (`tts/cues`) for gesture synchronization
- [ ] **Multi-language Support** with language detection and switching
- [ ] **Voice Cloning** integration for personalized TTS
- [ ] **Plugin System** for easy third-party extensions
- [ ] **Mobile App** companion with push notifications
- [ ] **Kubernetes Deployment** manifests for cloud/edge deployment
