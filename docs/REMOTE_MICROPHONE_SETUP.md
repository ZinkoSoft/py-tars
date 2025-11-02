# Remote Microphone Setup Guide

**Version**: 1.0  
**Date**: 2025-11-02  
**Feature**: 006-remote-mic

## Overview

This guide walks you through deploying wake-activation and stt-worker services on a remote device (Radxa Zero 3W) that connects to your main TARS system via MQTT. This enables physical separation of voice input from the main processing system.

**What You'll Need**:
- Radxa Zero 3W (or similar ARM64 Linux device) with Docker installed
- USB-C microphone
- Main TARS system running on a separate device
- Both devices on the same local network
- Approximately 10 minutes for setup

**What This Enables**:
- Remote voice input from any location in your network
- Lower latency for audio capture (microphone closer to user)
- Reduced load on main TARS system (offload audio processing)
- Multiple remote microphones (deploy on multiple devices)

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Setup (10 Minutes)](#quick-setup)
3. [Network Configuration](#network-configuration)
4. [Audio Device Configuration](#audio-device-configuration)
5. [Service Management](#service-management)
6. [Verification](#verification)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Configuration](#advanced-configuration)
9. [Updating](#updating)
10. [Architecture](#architecture)

---

## Prerequisites

### Hardware

- **Remote Device**: Radxa Zero 3W with:
  - ARM64 CPU (RK3588S SoC)
  - Minimum 2GB RAM (4GB+ recommended)
  - 16GB+ storage
  - Network connectivity (WiFi or Ethernet)
  
- **Microphone**: USB-C microphone compatible with Linux ALSA

- **Main TARS System**: Separate device running full TARS stack with MQTT broker

### Software

**On Remote Device**:
```bash
# Docker 20.10+ and Docker Compose 2.0+
docker --version
docker compose version

# Git
git --version
```

**Installation (if needed)**:
```bash
# Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in for group changes to take effect

# Docker Compose (if not included with Docker)
sudo apt-get install docker-compose-plugin

# Git
sudo apt-get install git
```

**On Main TARS System**:
- Full TARS stack running (`docker compose -f ops/compose.yml up`)
- MQTT broker accessible on network (see [Network Configuration](#network-configuration))

### Network

- Both devices on same local network (LAN)
- Firewall allows MQTT port 1883 between devices
- Ability to ping between devices

---

## Quick Setup

### Step 1: Clone Repository

SSH into your remote device and clone the TARS repository:

```bash
# SSH into remote device
ssh radxa@radxa-zero-3w.local
# Or use IP address: ssh radxa@192.168.1.150

# Clone repository
git clone https://github.com/your-org/py-tars.git
cd py-tars
```

### Step 2: Configure MQTT Connection

Create and edit the configuration file:

```bash
# Copy example configuration
cp ops/.env.remote-mic.example .env

# Edit configuration
nano .env
```

**Required Configuration** (edit these values):
```bash
# Set to your main TARS system's IP address
MQTT_HOST=192.168.1.100    # ← CHANGE THIS
MQTT_PORT=1883

# Optional: Leave empty for auto-detection
AUDIO_DEVICE_NAME=

# Logging
LOG_LEVEL=INFO
```

**Find your main TARS system IP**:
```bash
# On main TARS system, run:
ip addr show | grep "inet " | grep -v 127.0.0.1

# Example output:
#   inet 192.168.1.100/24 ...
# Use the IP address (192.168.1.100 in this example)
```

### Step 3: Start Services

```bash
# Start services in detached mode
docker compose -f ops/compose.remote-mic.yml up --build -d

# Check service status
docker compose -f ops/compose.remote-mic.yml ps
```

**Expected Output**:
```
NAME                        STATUS
tars-stt-remote             Up (healthy)
tars-wake-activation-remote Up
```

### Step 4: Verify Connection

```bash
# Check logs for successful MQTT connection
docker compose -f ops/compose.remote-mic.yml logs | grep "Connected to MQTT"
```

**Expected Log Output**:
```
tars-stt-remote             | INFO: Connected to MQTT broker at 192.168.1.100:1883
tars-wake-activation-remote | INFO: Connected to MQTT broker at 192.168.1.100:1883
```

### Step 5: Test Voice Input

1. **Speak the wake word**: "Hey TARS"
2. **Wait for confirmation** (check logs or main system response)
3. **Speak a command**: "What time is it?"
4. **Verify main TARS system responds**

**Check remote device logs**:
```bash
docker compose -f ops/compose.remote-mic.yml logs --tail=50
```

**Expected Log Output**:
```
tars-wake-activation-remote | INFO: Wake word detected (score=0.87, word=hey_tars)
tars-stt-remote             | INFO: Transcription complete (text="what time is it", duration=1.8s)
```

**Check main TARS system** for LLM response and TTS output.

---

## Network Configuration

### Main TARS System MQTT Broker

The MQTT broker on your main TARS system **must** be accessible from the network.

**Verify Mosquitto Configuration** (`ops/mosquitto.conf` on main system):
```conf
# REQUIRED: Bind to all network interfaces (not just localhost)
listener 1883 0.0.0.0

# REQUIRED: Allow anonymous connections (no authentication)
allow_anonymous true
```

**Restart MQTT broker after configuration changes**:
```bash
# On main TARS system
docker compose -f ops/compose.yml restart mqtt
```

### Firewall Configuration

**On Main TARS System**:
```bash
# Allow MQTT port 1883 (if using firewalld)
sudo firewall-cmd --permanent --add-port=1883/tcp
sudo firewall-cmd --reload

# Or using ufw
sudo ufw allow 1883/tcp
```

### Network Connectivity Test

**From remote device, test connection to main system**:

```bash
# Ping test
ping -c 4 192.168.1.100    # Replace with your MQTT_HOST

# MQTT connection test (requires mosquitto-clients)
sudo apt-get install mosquitto-clients
mosquitto_sub -h 192.168.1.100 -t 'test' -v

# If successful, you'll see no errors and connection will hang (listening for messages)
# Press Ctrl+C to exit
```

### Security Considerations

⚠️ **Important**: This configuration uses **anonymous authentication** (no username/password).

**Current Security Posture**:
- Any device on your local network can connect to the MQTT broker
- Suitable for home/lab environments with trusted network
- **Not recommended for production or untrusted networks**

**Future Enhancement**: Add MQTT authentication and TLS encryption (see "Out of Scope" in feature spec).

---

## Audio Device Configuration

### Automatic Detection (Default)

By default, the system auto-detects your USB-C microphone:

```bash
# In .env file:
AUDIO_DEVICE_NAME=
```

This works for most single-microphone setups.

### Manual Device Selection

If you have multiple audio devices or want to specify a particular microphone:

**Step 1: List available audio devices**:

```bash
# Method 1: Using arecord
arecord -l

# Example output:
# **** List of CAPTURE Hardware Devices ****
# card 0: Device [USB Audio Device], device 0: USB Audio [USB Audio]
#   Subdevices: 1/1
#   Subdevice #0: subdevice #0
# card 1: Microphone [Internal Microphone], device 0: ...

# Method 2: Inside Docker container
docker compose -f ops/compose.remote-mic.yml run --rm stt python -c "import pyaudio; p = pyaudio.PyAudio(); [print(f'{i}: {p.get_device_info_by_index(i)[\"name\"]}') for i in range(p.get_device_count())]"
```

**Step 2: Set device name in .env**:

```bash
# Edit .env
nano .env

# Set AUDIO_DEVICE_NAME to exact device name from list above
AUDIO_DEVICE_NAME=USB Audio Device
```

**Step 3: Restart services**:

```bash
docker compose -f ops/compose.remote-mic.yml restart
```

### Audio Device Testing

**Record a test audio sample**:

```bash
# Record 5 seconds of audio
arecord -d 5 -f cd test.wav

# Play back (if speakers connected to remote device)
aplay test.wav

# Or copy to main system and play there
scp test.wav user@main-tars-system:~/
```

**Expected Result**: Clear audio with minimal background noise.

---

## Service Management

### Starting Services

```bash
# Start all services
docker compose -f ops/compose.remote-mic.yml up -d

# Start with build (after code changes)
docker compose -f ops/compose.remote-mic.yml up --build -d

# Start in foreground (see logs in real-time)
docker compose -f ops/compose.remote-mic.yml up
```

### Stopping Services

```bash
# Stop services (containers remain)
docker compose -f ops/compose.remote-mic.yml stop

# Stop and remove containers
docker compose -f ops/compose.remote-mic.yml down

# Stop, remove containers, and clean volumes
docker compose -f ops/compose.remote-mic.yml down -v
```

### Restarting Services

```bash
# Restart all services
docker compose -f ops/compose.remote-mic.yml restart

# Restart specific service
docker compose -f ops/compose.remote-mic.yml restart stt
docker compose -f ops/compose.remote-mic.yml restart wake-activation
```

### Viewing Logs

```bash
# All services, follow mode
docker compose -f ops/compose.remote-mic.yml logs -f

# Specific service
docker compose -f ops/compose.remote-mic.yml logs -f stt
docker compose -f ops/compose.remote-mic.yml logs -f wake-activation

# Last 50 lines
docker compose -f ops/compose.remote-mic.yml logs --tail=50

# Since specific time
docker compose -f ops/compose.remote-mic.yml logs --since 10m
```

### Checking Service Status

```bash
# Service status
docker compose -f ops/compose.remote-mic.yml ps

# Detailed status
docker compose -f ops/compose.remote-mic.yml ps -a

# Resource usage
docker stats
```

---

## Verification

### 1. Service Health Check

```bash
docker compose -f ops/compose.remote-mic.yml ps
```

**Expected Output**:
```
NAME                        STATUS
tars-stt-remote             Up (healthy)
tars-wake-activation-remote Up
```

- `stt` should show `Up (healthy)` - healthcheck validates audio fanout socket
- `wake-activation` should show `Up` - no healthcheck, relies on stt dependency

### 2. MQTT Connection Verification

```bash
docker compose -f ops/compose.remote-mic.yml logs | grep -i "connect"
```

**Expected Log Lines**:
```
tars-stt-remote             | INFO: Connecting to MQTT broker at 192.168.1.100:1883
tars-stt-remote             | INFO: Connected to MQTT broker at 192.168.1.100:1883
tars-wake-activation-remote | INFO: Connecting to MQTT broker at 192.168.1.100:1883
tars-wake-activation-remote | INFO: Connected to MQTT broker at 192.168.1.100:1883
```

### 3. Audio Device Initialization

```bash
docker compose -f ops/compose.remote-mic.yml logs stt | grep -i "audio"
```

**Expected Log Lines**:
```
tars-stt-remote | INFO: Audio device initialized: USB Audio Device (16kHz, mono)
tars-stt-remote | INFO: Audio fanout socket created: /tmp/tars/audio-fanout.sock
```

### 4. Wake Word Detection Test

**Speak "Hey TARS" and check logs**:

```bash
docker compose -f ops/compose.remote-mic.yml logs --tail=20 wake-activation
```

**Expected Log Output**:
```
tars-wake-activation-remote | INFO: Wake word detected (score=0.87, word=hey_tars)
```

### 5. Transcription Test

**After wake word, speak a command and check logs**:

```bash
docker compose -f ops/compose.remote-mic.yml logs --tail=20 stt
```

**Expected Log Output**:
```
tars-stt-remote | INFO: Starting transcription (utt_id=abc123)
tars-stt-remote | INFO: Transcription complete (utt_id=abc123, text="turn on the lights", duration=2.3s)
```

### 6. End-to-End Test

1. **Speak wake word**: "Hey TARS"
2. **Verify wake detection** in remote logs
3. **Speak command**: "What time is it?"
4. **Verify transcription** in remote logs
5. **Verify LLM response** on main TARS system
6. **Verify TTS output** from main TARS system speakers

### 7. MQTT Message Monitoring (Optional)

**From main TARS system or remote device**:

```bash
# Install mosquitto-clients if needed
sudo apt-get install mosquitto-clients

# Subscribe to wake events
mosquitto_sub -h 192.168.1.100 -t 'wake/event' -v

# Subscribe to transcriptions
mosquitto_sub -h 192.168.1.100 -t 'stt/final' -v

# Subscribe to all system health
mosquitto_sub -h 192.168.1.100 -t 'system/health/#' -v
```

---

## Troubleshooting

### Issue: Services Won't Start

**Symptoms**:
- `docker compose ps` shows services as "Exited" or "Restarting"
- Services crash immediately after starting

**Check Docker is running**:
```bash
sudo systemctl status docker

# Start if needed
sudo systemctl start docker
sudo systemctl enable docker
```

**Check logs for error messages**:
```bash
docker compose -f ops/compose.remote-mic.yml logs
```

**Common Errors**:
- `Cannot connect to Docker daemon`: Docker not running or user not in docker group
- `no such file or directory`: Compose file path incorrect
- `yaml: invalid`: Syntax error in compose file or .env file

### Issue: "Failed to connect to MQTT broker"

**Symptoms**:
```
ERROR: Failed to connect to MQTT broker: Connection refused
WARNING: Disconnected from MQTT broker, attempting reconnect...
```

**Step 1: Verify MQTT_HOST in .env**:
```bash
cat .env | grep MQTT_HOST
# Should show your main TARS system IP, e.g., MQTT_HOST=192.168.1.100
```

**Step 2: Test network connectivity**:
```bash
ping -c 4 192.168.1.100    # Replace with your MQTT_HOST

# Should show successful ping responses
# If "Destination Host Unreachable" or timeout, check network connection
```

**Step 3: Verify MQTT broker is listening**:
```bash
# From remote device
nc -zv 192.168.1.100 1883

# Expected: "Connection to 192.168.1.100 1883 port [tcp/*] succeeded!"
# If "Connection refused", MQTT broker isn't running or not accessible
```

**Step 4: Check main TARS system MQTT broker**:
```bash
# On main TARS system
docker ps | grep mqtt

# Should show tars-mqtt container running

# Check mosquitto.conf
cat ops/mosquitto.conf | grep listener
# Should show: listener 1883 0.0.0.0

# Restart MQTT broker if needed
docker compose -f ops/compose.yml restart mqtt
```

**Step 5: Check firewall**:
```bash
# On main TARS system
sudo ufw status
sudo firewall-cmd --list-ports

# Ensure port 1883/tcp is allowed
```

### Issue: "Failed to initialize audio device"

**Symptoms**:
```
ERROR: Failed to initialize audio device: [Errno -9996] Invalid input device
```

**Step 1: Verify microphone is connected**:
```bash
# List audio devices
arecord -l

# Should show your USB-C microphone in the list
# If not listed, check USB connection
lsusb | grep -i audio
```

**Step 2: Test microphone outside Docker**:
```bash
# Record test audio
arecord -d 3 test.wav

# If error, microphone not properly recognized by ALSA
# Check dmesg for USB device errors
dmesg | grep -i audio
```

**Step 3: Specify audio device explicitly**:
```bash
# List devices with indices
arecord -L

# Edit .env
nano .env

# Set device name
AUDIO_DEVICE_NAME=hw:0,0    # Or device name from arecord -l

# Restart services
docker compose -f ops/compose.remote-mic.yml restart
```

**Step 4: Check Docker device access**:
```bash
# Verify /dev/snd is mounted in container
docker compose -f ops/compose.remote-mic.yml exec stt ls -la /dev/snd

# Should show sound devices (controlC0, pcmC0D0c, etc.)
```

### Issue: Wake Word Not Detected

**Symptoms**:
- Speak "Hey TARS" but no detection log message
- No wake events published

**Step 1: Check wake-activation is running**:
```bash
docker compose -f ops/compose.remote-mic.yml ps wake-activation

# Should show "Up"
# If "Exited" or not listed, check logs
docker compose -f ops/compose.remote-mic.yml logs wake-activation
```

**Step 2: Verify audio fanout socket exists**:
```bash
# Check stt service health
docker compose -f ops/compose.remote-mic.yml ps stt
# Should show "Up (healthy)"

# Verify socket in container
docker compose -f ops/compose.remote-mic.yml exec stt ls -la /tmp/tars/
# Should show audio-fanout.sock
```

**Step 3: Adjust wake word sensitivity**:
```bash
# Edit .env
nano .env

# Lower threshold for more sensitivity (default: 0.35)
WAKE_DETECTION_THRESHOLD=0.25

# Restart services
docker compose -f ops/compose.remote-mic.yml restart
```

**Step 4: Check microphone volume**:
```bash
# Test microphone input level
arecord -vvv -d 3 test.wav

# Should show VU meter with activity when speaking
# If flat/silent, microphone gain too low or muted
```

**Step 5: Verify wake word model loaded**:
```bash
docker compose -f ops/compose.remote-mic.yml logs wake-activation | grep -i model

# Should show: "Loading model from /models/openwakeword/hey_tars.tflite"
```

### Issue: Transcription Not Working

**Symptoms**:
- Wake word detected but no transcription
- No stt/final messages

**Step 1: Check STT worker logs**:
```bash
docker compose -f ops/compose.remote-mic.yml logs stt | grep -i transcr
```

**Step 2: Verify Whisper model downloaded**:
```bash
docker compose -f ops/compose.remote-mic.yml logs stt | grep -i "Loading model"

# Should show: "Loading Whisper model: small"
# First run downloads model (may take several minutes)
```

**Step 3: Check VAD settings**:
```bash
# Edit .env
nano .env

# Adjust VAD aggressiveness (1-3, higher = stricter)
VAD_AGGRESSIVENESS=2

# Adjust silence threshold (ms before ending transcription)
SILENCE_THRESHOLD_MS=800

# Restart services
docker compose -f ops/compose.remote-mic.yml restart
```

**Step 4: Test transcription manually**:
```bash
# Enable debug logging
nano .env
LOG_LEVEL=DEBUG

# Restart and check detailed logs
docker compose -f ops/compose.remote-mic.yml restart
docker compose -f ops/compose.remote-mic.yml logs -f stt
```

### Issue: Network Disconnection During Operation

**Symptoms**:
```
WARNING: Disconnected from MQTT broker
INFO: Attempting to reconnect in 5 seconds...
```

**Expected Behavior**: Services automatically reconnect with exponential backoff (5s, 10s, 30s).

**Check reconnection**:
```bash
docker compose -f ops/compose.remote-mic.yml logs | grep -i reconnect

# Should eventually show:
# INFO: Reconnected to MQTT broker after 5.2s
```

**If reconnection fails repeatedly**:
1. Check network stability (ping main system continuously)
2. Verify MQTT broker still running on main system
3. Check firewall hasn't blocked connections
4. Restart services if needed

### Issue: High CPU Usage

**Symptoms**:
- Remote device running hot
- CPU usage consistently above 80%

**Check resource usage**:
```bash
docker stats

# Note CPU% for each container
```

**Common Causes**:
1. **Whisper model too large**: Use smaller model (tiny or base)
2. **Continuous audio processing**: Expected during active listening
3. **FFT visualization enabled**: Disable if not needed
4. **NPU not being used**: Enable NPU acceleration if available

**Solutions**:
```bash
# Edit .env
nano .env

# Use smaller Whisper model
WHISPER_MODEL=tiny    # Or base

# Disable FFT
FFT_PUBLISH=0
FFT_WS_ENABLE=0

# Enable NPU (if RK3588 device)
WAKE_USE_NPU=1

# Restart
docker compose -f ops/compose.remote-mic.yml restart
```

### Issue: High Memory Usage

**Symptoms**:
- Container OOM (out of memory) errors
- System becomes unresponsive

**Check memory usage**:
```bash
docker stats

# Note MEM USAGE / LIMIT for each container
free -h
```

**Solutions**:
```bash
# Use smaller Whisper model
WHISPER_MODEL=tiny

# Disable model caching if enabled
# (Check service-specific settings)

# Add memory limits to compose file (advanced)
# Edit ops/compose.remote-mic.yml, add under each service:
# deploy:
#   resources:
#     limits:
#       memory: 768M
```

---

## Advanced Configuration

### Whisper Model Selection

Trade-offs between accuracy, speed, and resource usage:

| Model | Size | Speed | Accuracy | Memory | Recommended For |
|-------|------|-------|----------|--------|-----------------|
| tiny | 39MB | Fastest | Low | ~200MB | Very constrained devices |
| base | 74MB | Fast | Medium | ~400MB | Constrained devices |
| small | 244MB | Moderate | Good | ~1GB | **Default - balanced** |
| medium | 769MB | Slow | High | ~2.5GB | High accuracy needed |
| large | 1550MB | Slowest | Highest | ~5GB | Not recommended for Radxa |

**Change model**:
```bash
nano .env
WHISPER_MODEL=base    # Or tiny, small, medium, large
docker compose -f ops/compose.remote-mic.yml restart
```

### Wake Word Sensitivity Tuning

**Default**: `WAKE_DETECTION_THRESHOLD=0.35`

| Threshold | Behavior | Use Case |
|-----------|----------|----------|
| 0.20-0.25 | Very sensitive | Quiet environments, far from mic |
| 0.30-0.35 | **Balanced (default)** | Normal usage |
| 0.40-0.50 | Less sensitive | Noisy environments, reduce false positives |

**Tune sensitivity**:
```bash
nano .env
WAKE_DETECTION_THRESHOLD=0.28
docker compose -f ops/compose.remote-mic.yml restart
```

### NPU Acceleration (RK3588 Devices)

If your Radxa Zero 3W has RK3588 NPU support, enable hardware acceleration:

**Prerequisites**:
```bash
# Install RKNN toolkit (on remote device)
bash scripts/setup-rknpu.sh

# Convert model to RKNN format
python scripts/convert_tflite_to_rknn.py \
  --input models/openwakeword/hey_tars.tflite \
  --output models/openwakeword/hey_tars.rknn
```

**Enable NPU in .env**:
```bash
nano .env
WAKE_USE_NPU=1
WAKE_RKNN_MODEL_PATH=/models/openwakeword/hey_tars.rknn
docker compose -f ops/compose.remote-mic.yml restart
```

**Verify NPU usage**:
```bash
docker compose -f ops/compose.remote-mic.yml logs wake-activation | grep -i npu
# Should show: "NPU acceleration enabled"
```

### Multiple Remote Microphones

Deploy additional remote microphones:

1. **Set up additional Radxa devices** with same setup process
2. **Configure each with same MQTT_HOST** (same main TARS system)
3. **Give each device unique hostname** for identification:
   ```bash
   sudo hostnamectl set-hostname radxa-bedroom
   ```
4. **Start services on each device**

All remote microphones will publish to same MQTT topics. Main TARS router handles all events.

---

## Updating

### Update Code

```bash
cd ~/py-tars
git pull
docker compose -f ops/compose.remote-mic.yml build
docker compose -f ops/compose.remote-mic.yml up -d
```

### Update Configuration

```bash
nano .env
# Make changes
docker compose -f ops/compose.remote-mic.yml restart
```

### Update Docker Images

```bash
docker compose -f ops/compose.remote-mic.yml pull
docker compose -f ops/compose.remote-mic.yml up -d
```

---

## Architecture

### System Diagram

```
┌─────────────────────────────────────┐
│  Radxa Zero 3W (Remote Device)     │
│                                     │
│  ┌────────────┐   ┌──────────────┐ │
│  │ USB-C Mic  │──→│  stt-worker  │ │
│  └────────────┘   │  (Docker)    │ │
│                   └──────┬───────┘ │
│                          │         │
│                          │ MQTT    │
│                          ↓ (network)
│                   ┌──────────────┐ │
│                   │audio-fanout  │ │
│                   │    socket    │ │
│                   └──────┬───────┘ │
│                          │         │
│                          ↓         │
│                   ┌──────────────┐ │
│                   │wake-activation│ │
│                   │  (Docker)    │ │
│                   └──────┬───────┘ │
│                          │         │
│                          │ MQTT    │
│                          ↓ (network)
└──────────────────────────┼─────────┘
                           │
        ┌──────────────────┘
        │ LAN
        ↓
┌─────────────────────────────────────┐
│  Main TARS System                   │
│                                     │
│  ┌──────────────┐                  │
│  │ MQTT Broker  │←──(wake/event)   │
│  │  (port 1883) │←──(stt/final)    │
│  └──────┬───────┘                  │
│         │                           │
│         ↓                           │
│  ┌──────────────┐                  │
│  │   Router     │                  │
│  └──────┬───────┘                  │
│         │                           │
│    ┌────┴────┐                     │
│    ↓         ↓                     │
│  ┌────┐   ┌─────┐   ┌─────┐       │
│  │LLM │   │ TTS │   │ UI  │ ...   │
│  └────┘   └─────┘   └─────┘       │
└─────────────────────────────────────┘
```

### Data Flow

1. **Audio Capture**: USB-C microphone → PyAudio → stt-worker
2. **Audio Sharing**: stt-worker → Unix socket → wake-activation
3. **Wake Detection**: wake-activation → MQTT (wake/event) → router on main system
4. **Transcription**: stt-worker → MQTT (stt/final) → router on main system
5. **Processing**: Router → LLM → TTS → Output

### MQTT Topics

| Topic | Publisher | Subscriber | Purpose |
|-------|-----------|------------|---------|
| `wake/event` | wake-activation (remote) | router (main) | Wake word detection events |
| `stt/final` | stt-worker (remote) | router (main) | Final transcriptions |
| `system/health/wake-activation` | wake-activation (remote) | monitoring | Service health status |
| `system/health/stt` | stt-worker (remote) | monitoring | Service health status |
| `wake/mic` | router (main) | wake-activation (remote) | Mic control (pause/resume) |
| `tts/status` | tts-worker (main) | wake-activation (remote) | TTS coordination |

### Service Dependencies

```
stt-worker (producer)
    ↓
audio-fanout socket
    ↓
wake-activation (consumer)
    ↓
MQTT broker (main system)
    ↓
router (main system)
```

**Startup Order**:
1. stt-worker starts, initializes audio, creates fanout socket
2. healthcheck validates socket is ready
3. wake-activation starts, connects to socket
4. Both services connect to MQTT broker on main system

**Dependency Guarantees** (via Docker Compose):
- wake-activation waits for stt to be `healthy` before starting
- Healthcheck ensures audio fanout socket exists and is connectable
- Both services retry MQTT connection with exponential backoff

---

## Performance Expectations

### Resource Usage

| Metric | Idle | Active (listening) | Transcribing |
|--------|------|--------------------|--------------|
| CPU | <10% | 20-40% | 60-90% |
| RAM | 400MB | 600MB | 800MB-1GB |
| Network | <1 KB/s | <5 KB/s | 10-50 KB/s |

### Latency

| Operation | Target | Notes |
|-----------|--------|-------|
| Wake detection | <200ms | From word end to event |
| Transcription start | <100ms | After wake word |
| Transcription complete | <2s | For 5-word command |
| Network latency | <10ms | LAN only |

### Audio Quality Requirements

| Parameter | Value | Notes |
|-----------|-------|-------|
| Sample rate | 16kHz | Fixed for Whisper |
| Bit depth | 16-bit | Standard PCM |
| Channels | 1 (mono) | Single microphone |
| Noise floor | <-40dB | For reliable detection |

---

## Security Considerations

⚠️ **Current Security Posture**: Anonymous MQTT authentication (no credentials required).

**Risks**:
- Any device on local network can connect to MQTT broker
- No encryption of MQTT traffic (plaintext)
- No authentication of remote devices

**Mitigations**:
- **Physical security**: Trusted local network only
- **Network isolation**: Separate IoT VLAN (recommended)
- **Firewall rules**: Limit MQTT access to known IP ranges

**Future Enhancements** (out of scope for this feature):
- MQTT username/password authentication
- TLS encryption for MQTT traffic (port 8883)
- Mutual TLS (mTLS) for device authentication

---

## Getting Help

### Log Files

All logs are accessible via Docker Compose:

```bash
# All logs
docker compose -f ops/compose.remote-mic.yml logs

# Specific service with timestamp
docker compose -f ops/compose.remote-mic.yml logs --timestamps stt

# Follow mode (real-time)
docker compose -f ops/compose.remote-mic.yml logs -f
```

### Debug Mode

Enable detailed logging:

```bash
nano .env
LOG_LEVEL=DEBUG
docker compose -f ops/compose.remote-mic.yml restart
docker compose -f ops/compose.remote-mic.yml logs -f
```

### System Information

```bash
# Docker version
docker --version
docker compose version

# System resources
free -h
df -h
uptime

# Network connectivity
ip addr show
ping -c 4 <MQTT_HOST>
nc -zv <MQTT_HOST> 1883

# Audio devices
arecord -l
arecord -L
```

### Documentation References

- **Feature Specification**: `specs/006-remote-mic/spec.md`
- **Implementation Plan**: `specs/006-remote-mic/plan.md`
- **Quickstart Guide**: `specs/006-remote-mic/quickstart.md`
- **MQTT Contracts**: `docs/mqtt-contracts.md`
- **Main README**: `README.md`

---

## Appendix

### Example .env File

See `ops/.env.remote-mic.example` for complete configuration template.

### Useful Commands Cheat Sheet

```bash
# Start
docker compose -f ops/compose.remote-mic.yml up -d

# Stop
docker compose -f ops/compose.remote-mic.yml down

# Restart
docker compose -f ops/compose.remote-mic.yml restart

# Logs (all)
docker compose -f ops/compose.remote-mic.yml logs -f

# Logs (specific)
docker compose -f ops/compose.remote-mic.yml logs -f stt

# Status
docker compose -f ops/compose.remote-mic.yml ps

# Resources
docker stats

# Rebuild
docker compose -f ops/compose.remote-mic.yml build
docker compose -f ops/compose.remote-mic.yml up -d

# Update
git pull
docker compose -f ops/compose.remote-mic.yml build
docker compose -f ops/compose.remote-mic.yml up -d
```

---

**Version History**:
- 1.0 (2025-11-02): Initial release for feature 006-remote-mic
