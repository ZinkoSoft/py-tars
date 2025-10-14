# TTS Worker

Text-to-speech worker for the TARS voice assistant. Uses Piper by default for local TTS. Subscribes to `tts/say`, aggregates adjacent utterances when desired, and plays audio via PulseAudio/ALSA using the domain orchestration layer.

## Installation

```bash
pip install -e .
```

For development:
```bash
pip install -e ".[dev]"
```

## Usage

Run the TTS worker:
```bash
tars-tts-worker
```

Or via Python module:
```bash
python -m tts_worker
```

## Configuration

Set these environment variables on the `tts` service (most have sane defaults):

| Variable | Default | Description |
| --- | --- | --- |
| `PIPER_VOICE` | `/voices/TARS.onnx` | Voice model path when using Piper locally. |
| `TTS_STREAMING` | `0` | When `1`, stream audio chunks as soon as they are synthesized to minimize latency. |
| `TTS_PIPELINE` | `1` | When `1`, split long text into sentences and pipeline them for faster time-to-first-audio. |
| `TTS_CONCURRENCY` | `1` | Number of concurrent synthesis workers when pipelining non-streamed playback. |
| `TTS_SIMPLEAUDIO` | `0` | Use in-process `simpleaudio` playback instead of spawning `paplay`/`aplay`. Requires the dependency to be installed. |
| `TTS_AGGREGATE` | `1` | Merge consecutive `tts/say` messages that share an `utt_id` before speaking to reduce inter-sentence gaps. |
| `TTS_AGGREGATE_DEBOUNCE_MS` | `150` | Debounce window (milliseconds) before flushing an aggregated utterance. |
| `TTS_AGGREGATE_SINGLE_WAV` | `1` | When `1`, aggregated text is synthesized as a single WAV (streaming disabled for that flush). When `0`, each chunk is spoken sequentially. |
| `TTS_WAKE_CACHE_ENABLE` | `1` | Enable caching of wake acknowledgements so repeated wake phrases reuse the synthesized audio clip. |
| `TTS_WAKE_CACHE_DIR` | `/tmp/tars/wake-ack` | Directory inside the container where cached wake acknowledgement WAV files are stored. |
| `TTS_WAKE_CACHE_MAX` | `16` | Maximum number of cached wake acknowledgement clips to retain before pruning the oldest entries. |
| `TTS_WAKE_ACK_TEXTS` | *(derived from `ROUTER_WAKE_ACK_CHOICES`)* | Pipe or comma separated wake acknowledgement phrases to pre-synthesize into the cache during startup. |
| `TTS_PROVIDER` | `piper` | Selects the synthesizer backend. See below for ElevenLabs options. |
| `ELEVEN_API_BASE` | `https://api.elevenlabs.io/v1` | ElevenLabs API base URL. |
| `ELEVEN_API_KEY` | *(none)* | ElevenLabs API key (required when `TTS_PROVIDER=elevenlabs`). |
| `ELEVEN_VOICE_ID` | *(none)* | ElevenLabs voice identifier (required when `TTS_PROVIDER=elevenlabs`). |
| `ELEVEN_MODEL_ID` | `eleven_multilingual_v2` | ElevenLabs model name to request. |
| `ELEVEN_OPTIMIZE_STREAMING` | `0` | ElevenLabs streaming optimization level (`0`-`3`). |

When you select a hosted provider (for example, ElevenLabs), the worker still keeps a Piper instance warm for wake acknowledgements so the “Yes?” response remains quick and local. If Piper fails to initialize, those acknowledgements fall back to the primary provider.

All phrases listed in `TTS_WAKE_ACK_TEXTS` (defaulting to the router's wake acknowledgement choices) are synthesized into the cache as soon as the worker starts, so the very first wake word reuses the pre-rendered audio.

## External providers

You can switch to ElevenLabs by setting the following environment variables for the `tts` service:

- TTS_PROVIDER=elevenlabs
- ELEVEN_API_KEY=... (required)
- ELEVEN_VOICE_ID=... (required)
- ELEVEN_API_BASE (optional, default https://api.elevenlabs.io/v1)
- ELEVEN_MODEL_ID (optional, default eleven_multilingual_v2)
- ELEVEN_OPTIMIZE_STREAMING (optional 0-3)

When using ElevenLabs, the worker will stream audio to the system player for low latency; if streaming fails, it will fall back to synthesizing a WAV then playing it.

## Aggregation behavior

When `TTS_AGGREGATE=1`, the domain service buffers updates that share an `utt_id` and flushes them after `TTS_AGGREGATE_DEBOUNCE_MS` elapses. Setting `TTS_AGGREGATE_SINGLE_WAV=1` produces a seamless single clip, while `0` keeps per-sentence playback but still coalesces scheduling.

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
- `make fmt` - Format code with ruff and black
- `make lint` - Lint with ruff and type-check with mypy
- `make test` - Run tests with coverage
- `make check` - Run all checks (CI gate)
- `make build` - Build Python package
- `make clean` - Remove build artifacts

## Architecture

The TTS worker follows a domain-driven architecture:

- **TTSDomainService** - Main service that handles TTS requests and orchestrates playback
- **PiperSynth** - Local Piper TTS synthesizer
- **ElevenLabsTTS** - Cloud-based ElevenLabs synthesizer (optional)
- **PlaybackSession** - Manages individual playback sessions with pause/resume/stop controls
- **Wake Cache** - Pre-synthesizes and caches wake acknowledgement phrases for low-latency responses

Key components:
- `src/tts_worker/__main__.py` - Entry point and service initialization
- `src/tts_worker/service.py` - MQTT message handling and service orchestration
- `src/tts_worker/piper_synth.py` - Piper TTS implementation
- `src/tts_worker/config.py` - Configuration from environment variables
- `src/tts_worker/models.py` - Pydantic models for MQTT messages
- `src/external_services/eleven_labs.py` - ElevenLabs TTS implementation

## MQTT Topics

### Subscribed
- `tts/say` - Receives text to synthesize and play (TtsSay message)
- `tts/control` - Receives playback control commands (pause/resume/stop)

### Published
- `tts/status` - Publishes playback status updates (TtsStatus message)
  - Events: `speaking_start`, `speaking_end`, `paused`, `resumed`, `stopped`
- `system/health/tts` - Publishes health status (retained)
