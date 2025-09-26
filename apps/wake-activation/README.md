# Wake Activation Service

Experimental service responsible for detecting the "Hey Tars" wake phrase using OpenWakeWord and
coordinating microphone mute/unmute plus TTS interruption behavior.

## Current status (M3)

- Streams PCM frames from the STT audio fan-out socket and normalizes for inference.
- Runs the OpenWakeWord-backed `WakeDetector`, publishing `wake/event` payloads with confidence/energy.
- Issues `wake/mic` commands with idle-timeout TTL hints so the STT worker unmutes and then remutes on silence.
- Emits structured JSON logs when the microphone state changes or idle timeouts fire.
- Ships regression fixtures and pytest coverage to verify wake/noise scenarios offline.

## Running locally

```bash
pip install -e .
python -m wake_activation
```

## Configuration

Environment variables (defaults in parentheses):

| Variable | Description |
| --- | --- |
| `MQTT_URL` (`mqtt://tars:pass@127.0.0.1:1883`) | MQTT broker connection string. |
| `WAKE_AUDIO_FANOUT` (`/tmp/tars/audio-fanout.sock`) | Socket used to receive raw audio frames. |
| `WAKE_MODEL_PATH` (`/models/openwakeword/hey_tars.tflite`) | Path to the OpenWakeWord model file. |
| `WAKE_DETECTION_THRESHOLD` (`0.55`) | Probability threshold to treat a detection as wake. |
| `WAKE_MIN_RETRIGGER_SEC` (`1.0`) | Debounce successive detections within this window. |
| `WAKE_INTERRUPT_WINDOW_SEC` (`2.5`) | Window to listen for cancel/stop after double wake. |
| `WAKE_IDLE_TIMEOUT_SEC` (`3.0`) | Silence duration before the service emits a timeout event and TTL hint to re-mute the mic. |
| `WAKE_HEALTH_INTERVAL_SEC` (`15`) | Period between health heartbeats. |
| `WAKE_EVENT_TOPIC` (`wake/event`) | MQTT topic for wake lifecycle events. |
| `WAKE_MIC_TOPIC` (`wake/mic`) | MQTT topic for microphone control commands. |
| `WAKE_TTS_TOPIC` (`tts/control`) | MQTT topic for TTS pause/resume commands. |

## Testing

```bash
pytest tests
```

> **Note:** Install the optional wake-word inference dependency with `pip install -e .[openwakeword]` when
> you're ready to exercise the detector offline.

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
