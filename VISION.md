# 🚀 TARS AI Bot — High-Level Roadmap

## 🧠 Current Focus — The Brain (Orange Pi 5 Max)

- **Core stack**
  - **MQTT (Mosquitto)** → central event bus
  - **STT (Faster-Whisper / CTranslate2)** → speech → text  
    - Small/medium models, INT8/FP16 for speed  
    - VAD for latency + efficiency
  - **Router (Python asyncio)** → intents, rules, smalltalk fallback
  - **TTS (Piper)** → text → speech  
    - Voices stored on NVMe, warmed at boot
  - **Async + modular services** → Dockerized, supervised, swappable

- **Key design rules**
  - Low-latency loop: speech → intent → response < 1–1.5s
  - MQTT for **fast, low-level events**  
  - MCP (Model Context Protocol) for **tool calls + semantic tasks**  
  - Resilient (health checks, backpressure, retries)

---

## 🔋 Hardware Foundations

- **Orange Pi 5 Max**
  - NVMe SSD (Samsung 970 EVO) for models/voices
  - RK3588 SoC: big cores pinned for STT, small cores for MQTT/tools
- **ESP32-S3** (planned)
  - Real-time motion controller for servos
  - Subscribes to `tts/cues` and motion topics
- **Battery setup** (future)
  - 3S LiPo + buck converters
  - Separate rails for compute (5 V) vs motors (6–7.4 V)
  - Telemetry via MQTT (`system/power`)

---

## 🎤 Core AI/Audio Pipeline

1. **Wake word** (future)  
   `openWakeWord` → `audio/wake`
2. **Speech capture**  
   16 kHz mono, VAD gating, publish `stt/partial` & `stt/final`
3. **Router**  
   - Rules → direct replies (time, say, hello)  
   - Unknowns → fallback smalltalk  
   - Future: MCP tool calls
4. **TTS**  
   Piper voices → speak sentence-sized chunks  
   Publish motion cues (`tts/cues`) alongside
5. **Health/metrics**  
   Each service → `system/health/<service>`

---

## 🥽 Live AI — Meta Glasses–Style Setup (Future)

- **Vision pipeline**
  - Camera → RKNN-accelerated detector (YOLOv8-n / MobileSAM-lite)
  - OCR (PaddleOCR mobile)
  - Optional captioner (BLIP-tiny) or rules from objects
  - Publish `vision/frame_meta` and `vision/snapshot`
- **Visual memory**
  - CLIP-tiny embeddings → FAISS / SQLite-IVF index on NVMe
  - Rolling buffer of keyframes + embeddings
  - Queryable via MCP tools: “what was I looking at?”
- **Integration**
  - Router fuses `stt/final` + `vision/frame_meta`
  - Answer “what’s this?”, “read that sign”, “where did I put…”
  - Heavy queries → optional edge offload (Jetson/PC with bigger VLMs)

---

## 🔌 MCP Server (Future)

- **Why:** unify tool layer for LLM access
- **Exposed tools:**
  - `memory.search / memory.upsert`
  - `vision.describe`
  - `web.search`
  - `home.toggle / home.query`
  - `notes.create / notes.list`
- **Router logic:** rules first, fallback → MCP tool calls, fallback → smalltalk

---

## 🎯 Roadmap / TODOs

- [ ] Build **STT client** (mic capture + VAD → Faster-Whisper HTTP → MQTT publish)
- [ ] Add **wakeword** daemon
- [ ] Implement **tts/cues** → ESP32-S3 for gestures
- [ ] Add **MCP server** with memory, vision, web tools
- [ ] Expand **Router** with intent classification + tool orchestration
- [ ] Add **health dashboard** (Prometheus/Grafana from MQTT)
- [ ] Add **battery telemetry** (voltage/current → MQTT)
- [ ] Integrate **motion** (walking gaits, nods, blinks, gaze)

---

## 🌟 End Goal

A **self-contained, mobile AI companion**:
- **Orange Pi 5 Max brain** for STT, TTS, lightweight reasoning
- **ESP32-S3 motion controller** for real-time servo control
- **LiPo-powered**, fully mobile platform
- **Live AI interaction**:  
  - See (vision + memory)  
  - Hear (STT)  
  - Understand (router + MCP)  
  - Speak (Piper TTS)  
  - Move (ESP32-S3, servo gaits)  
- Offline-capable, modular, extendable to cloud or edge servers when needed
