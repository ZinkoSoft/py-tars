# Quickstart: Remote Microphone Interface

**Feature**: 006-remote-mic | **Date**: 2025-11-02

## Overview

Deploy wake-activation and stt-worker services on a Radxa Zero 3W device to enable remote voice input for TARS.

**Prerequisites**:
- Radxa Zero 3W with Docker and Docker Compose installed
- USB-C microphone connected to Radxa Zero 3W
- Main TARS system running on another device with MQTT broker accessible on network
- Both devices on same local network

**Time to Complete**: ~10 minutes

---

## Quick Setup

### 1. Clone Repository on Remote Device

```bash
# SSH into Radxa Zero 3W
ssh radxa@radxa-zero-3w.local

# Clone TARS repository
git clone https://github.com/your-org/py-tars.git
cd py-tars
```

### 2. Configure MQTT Connection

```bash
# Copy example environment file
cp ops/.env.remote-mic.example .env

# Edit .env with your main system's IP address
nano .env
```

**Required Configuration**:
```bash
# MQTT Connection (REQUIRED)
MQTT_HOST=192.168.1.100    # Replace with your main TARS system IP
MQTT_PORT=1883              # Default MQTT port

# Audio Device (OPTIONAL - leave empty for auto-detect)
AUDIO_DEVICE_NAME=

# Logging
LOG_LEVEL=INFO
```

**Find your main TARS system IP**:
```bash
# On main TARS system, run:
ip addr show | grep "inet " | grep -v 127.0.0.1
```

### 3. Start Remote Microphone Services

```bash
# Start services
docker compose -f ops/compose.remote-mic.yml up -d

# Verify services are running
docker compose -f ops/compose.remote-mic.yml ps
```

**Expected Output**:
```
NAME                        STATUS
tars-stt-remote             Up (healthy)
tars-wake-activation-remote Up
```

### 4. Verify Connection

```bash
# Check logs for successful MQTT connection
docker compose -f ops/compose.remote-mic.yml logs | grep "Connected to MQTT"
```

**Expected Log Output**:
```
tars-stt-remote             | INFO: Connected to MQTT broker at 192.168.1.100:1883
tars-wake-activation-remote | INFO: Connected to MQTT broker at 192.168.1.100:1883
```

### 5. Test Voice Input

1. Speak the wake word: "Hey TARS"
2. Speak a command: "What time is it?"
3. Check remote device logs:

```bash
docker compose -f ops/compose.remote-mic.yml logs --tail=20
```

**Expected Log Output**:
```
tars-wake-activation-remote | INFO: Wake word detected (score=0.87, word=hey_tars)
tars-stt-remote             | INFO: Transcription complete (text="what time is it", duration=1.8s)
```

4. Verify main TARS system responds (TTS output on main system)

---

## Common Issues

### Issue: Services won't start

**Check Docker is running**:
```bash
sudo systemctl status docker
```

**Start Docker if needed**:
```bash
sudo systemctl start docker
```

### Issue: "Failed to connect to MQTT broker"

**Check network connectivity**:
```bash
ping 192.168.1.100  # Replace with your MQTT_HOST
```

**Check MQTT broker is accessible**:
```bash
# Install mosquitto-clients if needed
sudo apt-get install mosquitto-clients

# Test MQTT connection
mosquitto_sub -h 192.168.1.100 -t 'test' -v
```

**Verify MQTT broker is listening on network**:
```bash
# On main TARS system, check mosquitto.conf:
cat ops/mosquitto.conf | grep listener
# Should show: listener 1883 0.0.0.0
```

### Issue: "Failed to initialize audio device"

**List available audio devices**:
```bash
docker compose -f ops/compose.remote-mic.yml run --rm stt-worker python -c "import pyaudio; p = pyaudio.PyAudio(); [print(f'{i}: {p.get_device_info_by_index(i)[\"name\"]}') for i in range(p.get_device_count())]"
```

**Set specific audio device in .env**:
```bash
AUDIO_DEVICE_NAME=USB Audio Device
```

### Issue: Wake word not detected

**Check microphone is working**:
```bash
# Record 5 seconds of audio
docker compose -f ops/compose.remote-mic.yml run --rm stt-worker arecord -d 5 test.wav

# Play back (if speakers connected)
aplay test.wav
```

**Adjust wake word sensitivity**:
```bash
# Add to .env
WAKE_DETECTION_THRESHOLD=0.25  # Lower = more sensitive (default: 0.35)
```

### Issue: Transcription not working

**Check STT service logs**:
```bash
docker compose -f ops/compose.remote-mic.yml logs stt-worker
```

**Verify Whisper model downloaded**:
```bash
docker compose -f ops/compose.remote-mic.yml logs stt-worker | grep "Loading model"
```

---

## Updating

### Update Code

```bash
cd ~/py-tars
git pull
docker compose -f ops/compose.remote-mic.yml build
docker compose -f ops/compose.remote-mic.yml up -d
```

### View Logs

```bash
# All logs
docker compose -f ops/compose.remote-mic.yml logs -f

# Specific service
docker compose -f ops/compose.remote-mic.yml logs -f wake-activation
docker compose -f ops/compose.remote-mic.yml logs -f stt-worker
```

### Restart Services

```bash
docker compose -f ops/compose.remote-mic.yml restart
```

### Stop Services

```bash
docker compose -f ops/compose.remote-mic.yml down
```

---

## Advanced Configuration

### Custom Audio Settings

Add to `.env`:
```bash
# Audio Processing
SAMPLE_RATE=16000           # Sample rate in Hz
VAD_AGGRESSIVENESS=3        # Voice activity detection (1-3)
SILENCE_THRESHOLD_MS=600    # Silence before ending transcription

# Wake Detection
WAKE_MIN_RETRIGGER_SEC=0.8  # Min time between wake word detections
```

### Whisper Model Selection

Add to `.env`:
```bash
WHISPER_MODEL=small  # Options: tiny, base, small, medium, large
```

**Model Trade-offs**:
- `tiny`: Fastest, least accurate, lowest memory
- `small`: Good balance (recommended)
- `medium/large`: Higher accuracy, slower, more memory

### Debug Logging

```bash
LOG_LEVEL=DEBUG
```

---

## Monitoring

### Service Health

```bash
# Check service status
docker compose -f ops/compose.remote-mic.yml ps

# Check resource usage
docker stats
```

### MQTT Messages

```bash
# Subscribe to wake events
mosquitto_sub -h 192.168.1.100 -t 'wake/event' -v

# Subscribe to transcriptions
mosquitto_sub -h 192.168.1.100 -t 'stt/final' -v

# Subscribe to health status
mosquitto_sub -h 192.168.1.100 -t 'system/health/#' -v
```

---

## Cleanup

```bash
# Stop and remove containers
docker compose -f ops/compose.remote-mic.yml down

# Remove images (optional)
docker compose -f ops/compose.remote-mic.yml down --rmi all

# Remove volumes (optional - will delete audio cache)
docker compose -f ops/compose.remote-mic.yml down -v
```

---

## Next Steps

- **Multiple Microphones**: Deploy on additional Radxa devices (each needs own .env with same MQTT_HOST)
- **Security**: Add MQTT authentication (future enhancement)
- **Monitoring**: Set up Grafana/Prometheus for metrics (future enhancement)

---

## References

- **Full Documentation**: `docs/REMOTE_MICROPHONE_SETUP.md`
- **Feature Spec**: `specs/006-remote-mic/spec.md`
- **Implementation Plan**: `specs/006-remote-mic/plan.md`
- **Troubleshooting**: See "Common Issues" section above or check logs
