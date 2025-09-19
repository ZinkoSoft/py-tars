# TARS Brain

A modular **AI “brain” stack** for the Orange Pi 5 Max that handles:
- **STT** (speech → text via Faster-Whisper)
- **Router** (rule-based intent routing, fallback smalltalk)
- **TTS** (text → voice via Piper)
- **MQTT backbone** to glue everything together  

Motion and battery subsystems (ESP32-S3, LiPo pack, etc.) can connect later through MQTT topics.

---

## 🧩 Architecture

```
[Mic] → STT → MQTT → Router → MQTT → TTS → [Speaker]
```

### Topics
- `audio/wake` — wakeword events (future)
- `stt/partial` — partial transcripts
- `stt/final` — final transcripts
- `tts/say` — text to speak
- `tts/cues` — motion/gesture cues (future)
- `system/health/+` — health pings from services

### Services
- **Mosquitto** — broker
- **STT** — Faster-Whisper HTTP service + publisher
- **Router** — Python asyncio service (rule-first)
- **TTS Worker** — Piper CLI subscriber

---

## 📂 Repo Layout

```
tars-brain/
├─ README.md
├─ docker-compose.yml
├─ apps/
│  ├─ router/           # Asyncio MQTT router
│  └─ tts-worker/       # Piper CLI wrapper
├─ ops/
│  └─ mosquitto.conf    # Broker config
├─ models/              # Whisper models (NVMe mount)
└─ voices/              # Piper voices (NVMe mount)
```

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

### 1. Clone repo
```bash
git clone https://github.com/yourname/tars-brain.git
cd tars-brain
```

### 2. Configure Mosquitto
Edit `ops/mosquitto.conf`:
```conf
listener 1883 0.0.0.0
allow_anonymous false
password_file /mosquitto/config/passwd
```

Create broker user:
```bash
sudo mosquitto_passwd -c ./ops/passwd tars
```

### 3. Place models & voices
- Whisper models → `/mnt/nvme/models/`
- Piper voices → `/mnt/nvme/voices/`  
  Example: `en_US-amy-medium.onnx`

### 4. Build & run
```bash
docker compose build
docker compose up -d
```

---

## 🔊 Audio Setup

The TTS service requires proper audio configuration to output speech. The setup varies depending on your audio hardware:

### Audio Output Options
- **HDMI Audio** (monitors/TVs with speakers)
- **3.5mm Headphone Jack** (headphones/speakers)
- **USB Audio Devices** (USB speakers/DACs)

### Configure Audio Output

1. **Check available audio devices:**
   ```bash
   aplay -l  # List ALSA devices
   pactl list short sinks  # List PulseAudio sinks
   ```

2. **Set default audio output:**
   ```bash
   # For HDMI0 output
   pactl set-default-sink alsa_output.platform-hdmi0-sound.stereo-fallback
   
   # For HDMI1 output  
   pactl set-default-sink alsa_output.platform-hdmi1-sound.stereo-fallback
   
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

1. **MQTT sanity**
   ```bash
   mosquitto_sub -h $MQTT_HOST -p $MQTT_PORT -u $MQTT_USER -P $MQTT_PASS -t 'system/#' -v
   ```

2. **Audio setup test**
   ```bash
   # Test host audio first
   speaker-test -t wav -c 2 -l 1
   
   # Set correct audio output (adjust device as needed)
   pactl set-default-sink alsa_output.platform-es8388-sound.stereo-fallback
   ```

3. **TTS test**
   ```bash
   mosquitto_pub -h $MQTT_HOST -p $MQTT_PORT -u $MQTT_USER -P $MQTT_PASS -t tts/say -m '{"text":"TARS voice initialized."}'
   ```
   ✅ You should hear Piper speak through your configured audio device.

4. **STT → Router → TTS loop**
   - Run your STT publisher (captures mic, sends `stt/final`).  
   - Router will publish `tts/say` with a reply.  
   - TTS worker speaks it.

---

## 🔧 Extending

- **Wakeword:** add `openWakeWord` → `audio/wake`.
- **Cues:** router publishes `tts/cues` for gestures → ESP32-S3.
- **MCP server:** add tool calls (`memory`, `vision`, `web`) behind router.
- **Battery/motion:** add later, isolated on their own rails.

---

## 📈 Performance (Orange Pi 5 Max)

- **STT (Faster-Whisper small INT8/FP16):** ~0.7–1.2 s finalization after speech ends
- **TTS (Piper):** <400 ms first phrase, <200 ms steady state
- **Router:** negligible latency (<5 ms)

---

## 📌 Roadmap / TODOs
- [ ] **Add STT client** (mic capture, VAD, call Faster-Whisper HTTP, publish `stt/partial` + `stt/final`)
- [ ] Add **wakeword** daemon (`openWakeWord` → `audio/wake`)
- [ ] Publish **tts/cues** for motion sync (blink, nod, gaze)
- [ ] Add **MCP server** with tools (`memory`, `vision.describe`, `web.search`, `home.toggle`)
- [ ] Expand **Router** with intent classifier + tool calling
- [ ] Add **health dashboard** (system/health MQTT → Prometheus/Grafana)
