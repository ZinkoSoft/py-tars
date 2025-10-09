# Wake Activation Service

Experimental service responsible for detecting the "Hey Tars" wake phrase using OpenWakeWord and
coordinating microphone mute/unmute plus TTS interruption behavior.

**🚀 Now supports NPU acceleration on RK3588 devices (Orange Pi 5 Max, Rock 5B, etc.) for ultra-fast wake word detection!**

## Current status (M3)

- Streams PCM frames from the STT audio fan-out socket and normalizes for inference.
- Runs the OpenWakeWord-backed `WakeDetector`, publishing `wake/event` payloads with confidence/energy.
- Issues `wake/mic` commands with idle-timeout TTL hints so the STT worker unmutes and then remutes on silence.
- Emits structured JSON logs when the microphone state changes or idle timeouts fire.
- Ships regression fixtures and pytest coverage to verify wake/noise scenarios offline.
- **NEW**: Optional NPU acceleration for RK3588 devices providing sub-millisecond inference times.

## NPU Acceleration Setup (RK3588 devices)

### Prerequisites

- RK3588-based device (Orange Pi 5 Max, Rock 5B, etc.)
- RKNN drivers installed and working
- Docker with device access privileges

### Step 1: Convert TFLite Model to RKNN Format

First, you need to convert the existing OpenWakeWord TFLite model to RKNN format for NPU acceleration:

```bash
# Navigate to repository root
cd /path/to/py-tars

# Run the model conversion script (requires hey_tars.tflite in models directory)
python scripts/convert_tflite_to_rknn.py \
  --input models/openwakeword/hey_tars.tflite \
  --output models/openwakeword/hey_tars.rknn \
  --platform rk3588 \
  --quantize_type w8a8
```

**Expected output:**
- Converted RKNN model: `/models/openwakeword/hey_tars.rknn` (~180KB)
- Validation: Model loaded and tested successfully

### Step 2: Verify NPU Hardware

Test that your NPU is properly detected:

```bash
# Check NPU device nodes exist
ls -la /dev/rknpu /dev/dri/renderD*

# Verify RKNN runtime library
ls -la /usr/lib/librknnrt.so

# Run NPU setup script (from repository root)
bash scripts/setup-rknpu.sh

# Test NPU availability
cd apps/wake-activation
python scripts/test_npu_availability.py
```

**Expected output:**
```
✅ NPU render node found: /dev/dri/renderD129
✅ librknnrt.so runtime library available
✅ rknn-toolkit-lite2 Python API available
✅ User is in render group
🎉 NPU is ready for wake word acceleration!
```

### Step 3: Configure NPU Settings

Set the following environment variables to enable NPU acceleration:

```bash
# Enable NPU acceleration
export WAKE_USE_NPU=1

# Path to RKNN model (created in Step 1)
export WAKE_RKNN_MODEL_PATH=/models/openwakeword/hey_tars.rknn

# NPU core selection (optional)
export WAKE_NPU_CORE_MASK=0  # 0=auto, 1=core0, 2=core1, 4=core2, 7=all cores

# Keep other wake settings
export WAKE_DETECTION_THRESHOLD=0.55
export WAKE_MIN_RETRIGGER_SEC=1.0
```

### Step 4: Build and Run NPU-Enabled Container

Use the NPU override file with the main docker compose:

```bash
# Build and start NPU-accelerated wake activation service
cd ops
docker compose -f compose.yml -f compose.npu.yml build wake-activation
docker compose -f compose.yml -f compose.npu.yml up -d wake-activation

# Test NPU functionality (optional)
docker compose -f compose.yml -f compose.npu.yml run --rm wake-activation python /app/scripts/test_npu_docker.py
```

### Step 5: Verify NPU Performance

Check the logs to confirm NPU acceleration is working:

```bash
# View service logs
docker compose -f compose.yml -f compose.npu.yml logs -f wake-activation

# Look for these success indicators:
# ✅ NPU available, using NPU acceleration for wake detection
# 🚀 NPU Inference: 1.0ms | Output: (1, 1)
# Processing time: 1.14ms
```

### NPU Configuration Variables

| Variable | Default | Description |
| --- | --- | --- |
| `WAKE_USE_NPU` | `0` | Enable NPU acceleration (`1`, `true`, or `yes` to enable). |
| `WAKE_RKNN_MODEL_PATH` | `/models/openwakeword/hey_tars.rknn` | Path to the converted RKNN model file. |
| `WAKE_NPU_CORE_MASK` | `0` | NPU core selection: `0`=auto, `1`=core0, `2`=core1, `4`=core2, `7`=all cores. |

### Performance Benefits

NPU acceleration provides significant performance improvements:

- **CPU inference**: ~50-100ms per frame
- **NPU inference**: ~1-2ms per frame (50x faster!)
- **Power efficiency**: Much lower power consumption than CPU
- **Responsiveness**: Near-instantaneous wake word detection

### Troubleshooting NPU Issues

**NPU not detected:**
```bash
# Check device permissions
sudo usermod -aG render,video $USER
sudo chmod 666 /dev/dri/renderD*

# Verify RKNN drivers
dmesg | grep -i rknpu
```

**Model conversion fails:**
```bash
# Install RKNN Toolkit2 dependencies
pip install rknn-toolkit2==2.3.2

# Try different quantization types
python scripts/convert_tflite_to_rknn.py --quantize_type w16a16i

# Use the NPU setup script for proper environment
bash scripts/setup-rknpu.sh --venv
```

**Container NPU access issues:**
```bash
# Ensure privileged mode and device mounts
docker compose -f compose.yml -f compose.npu.yml down
docker compose -f compose.yml -f compose.npu.yml build --no-cache wake-activation
docker compose -f compose.yml -f compose.npu.yml up wake-activation
```

## Running locally

### CPU Mode (Default)
```bash
pip install -e ".[openwakeword]"
python -m wake_activation
```

### NPU Mode (RK3588 devices)
```bash
# Install with NPU dependencies
pip install -e ".[openwakeword]"
pip install rknn-toolkit-lite2==2.3.2

# Set up NPU hardware (one-time setup)
bash scripts/setup-rknpu.sh

# Convert model to RKNN format (one-time setup)
python scripts/convert_tflite_to_rknn.py \
  --input models/openwakeword/hey_tars.tflite \
  --output models/openwakeword/hey_tars.rknn

# Run with NPU acceleration
export WAKE_USE_NPU=1
export WAKE_RKNN_MODEL_PATH=models/openwakeword/hey_tars.rknn
python -m wake_activation
```

### Docker (Recommended for NPU)
```bash
# CPU mode (default)
cd ops
docker compose up wake-activation

# NPU mode (RK3588 devices) - use override file
docker compose -f compose.yml -f compose.npu.yml up wake-activation
```

## Configuration

Environment variables (defaults in parentheses):

### Core Settings
| Variable | Description |
| --- | --- |
| `MQTT_URL` (`mqtt://tars:pass@127.0.0.1:1883`) | MQTT broker connection string. |
| `WAKE_AUDIO_FANOUT` (`/tmp/tars/audio-fanout.sock`) | Socket used to receive raw audio frames. |
| `WAKE_MODEL_PATH` (`/models/openwakeword/hey_tars.tflite`) | Path to the OpenWakeWord TFLite model file (CPU mode). |
| `WAKE_DETECTION_THRESHOLD` (`0.55`) | Probability threshold to treat a detection as wake. |
| `WAKE_MIN_RETRIGGER_SEC` (`1.0`) | Debounce successive detections within this window. |
| `WAKE_INTERRUPT_WINDOW_SEC` (`2.5`) | Window to listen for cancel/stop after double wake. |
| `WAKE_IDLE_TIMEOUT_SEC` (`3.0`) | Silence duration before the service emits a timeout event and TTL hint to re-mute the mic. |

### NPU Acceleration (RK3588 devices)
| Variable | Description |
| --- | --- |
| `WAKE_USE_NPU` (`0`) | Enable NPU acceleration (`1`, `true`, or `yes` to enable). |
| `WAKE_RKNN_MODEL_PATH` (`/models/openwakeword/hey_tars.rknn`) | Path to the converted RKNN model file. |
| `WAKE_NPU_CORE_MASK` (`0`) | NPU core selection: `0`=auto, `1`=core0, `2`=core1, `4`=core2, `7`=all cores. |

### Audio Processing
| Variable | Description |
| --- | --- |
| `WAKE_SPEEX_NOISE_SUPPRESSION` (`0`) | Enable Speex noise suppression inside OpenWakeWord (`1`, `true`, or `yes` to enable). |
| `WAKE_VAD_THRESHOLD` (`0.0`) | Optional OpenWakeWord VAD gate (0–1); detections require the VAD score to exceed this value. |

### MQTT Topics
| Variable | Description |
| --- | --- |
| `WAKE_HEALTH_INTERVAL_SEC` (`15`) | Period between health heartbeats. |
| `WAKE_EVENT_TOPIC` (`wake/event`) | MQTT topic for wake lifecycle events. |
| `WAKE_MIC_TOPIC` (`wake/mic`) | MQTT topic for microphone control commands. |
| `WAKE_TTS_TOPIC` (`tts/control`) | MQTT topic for TTS pause/resume commands. |

## Testing

```bash
pytest tests
```

> **Note:** The wake detector relies on the OpenWakeWord extra; make sure you install with
> `pip install -e ".[openwakeword]"` before running either locally or in Docker. The package pins
> `numpy<2.0` because the bundled `tflite-runtime` wheels are not yet compatible with NumPy 2.x, and
> the Docker image pre-fetches the OpenWakeWord feature resources (melspectrogram + VAD) at build time.

> To take advantage of Speex suppression, install the Speex development headers and the
> [`speexdsp-ns`](https://github.com/dscripka/openWakeWord/releases) wheel that matches your platform, for example:
>
> ```bash
> sudo apt-get install libspeexdsp-dev
> pip install https://github.com/dscripka/openWakeWord/releases/download/v0.1.1/speexdsp_ns-0.1.1-<platform>.whl
> ```
>
> Then set `WAKE_SPEEX_NOISE_SUPPRESSION=1` in your environment.

The provided Dockerfile for this service installs the x86_64 CPython 3.11 wheel by default. If you
target a different Python version or architecture, override the `SPEEXDSP_NS_WHEEL_URL` build arg
with the matching download from the
[openWakeWord v0.1.1 release](https://github.com/dscripka/openWakeWord/releases/tag/v0.1.1).

## Regression fixtures

The regression harness replays curated score + amplitude traces captured from representative audio scenarios
(`wake`, `near_miss`, `background`). The fixtures live in `tests/data/wake_regression_sequences.json` and drive the
parameterized test `test_regression_sequences_trigger_expected_detection` to guard against detector regressions
without requiring heavyweight audio blobs in the repository.

## Idle timeout lifecycle

When a wake phrase is detected, the service:

1. Publishes a `wake/event` of type `wake` with energy/confidence metadata.
2. Issues a `wake/mic` command with a TTL equal to `WAKE_IDLE_TIMEOUT_SEC * 1000`, allowing the STT worker to unmute immediately and automatically re-mute once the timeout elapses.
3. Schedules an idle timer that, if no follow-up detections occur, emits a `wake/event` of type `timeout` with cause `silence`. Other services can react by closing the interaction window or resuming TTS playback.

The structured logs (`event` field) mirror this lifecycle, making it easy to trace wake sessions across the stack.
