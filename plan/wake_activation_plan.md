# Wake Activation Service Plan

Goal: Deliver a dedicated wake-activation package that listens for the "Hey Tars" wake phrase via OpenWakeWord, manages the microphone mute gate, and orchestrates TTS pause/stop behavior when the wake phrase is repeated.

## Progress Snapshot

- ✅ Repository plan authored and living at `plan/wake_activation_plan.md`.
- ✅ Wake activation service scaffolded (`apps/wake-activation/` package, config/models/service/tests, Dockerfile, README).
- ✅ Optional OpenWakeWord dependency handled via extras to avoid default install conflicts.
- ✅ Repo test suite (`./run.tests.sh`) passing with new service included.
- ✅ Dockerfile now bundles Colab-exported wake models into `/models/openwakeword/`.
- ✅ Audio fan-out client streams PCM from the STT socket and normalizes frames for inference (Milestone M2).
- ✅ Wake detector wired in with OpenWakeWord backend; service publishes `wake/event` + `wake/mic` on detection (Milestone M2).
- ✅ STT worker subscribes to `wake/mic` and enforces TTL-based mute control (Milestone M3 validated end-to-end).
- ✅ Regression harness and docs captured for the wake detector; curated sequences now guard M2 behavior.
- ✅ Idle-timeout lifecycle exercised through new wake↔STT integration tests and documented for operators.
- ✅ Piper-based TTS path now exposes a playback observer hook so pause/resume orchestration can supervise player processes.
- ✅ Double-wake TTS controls implemented with pause/resume/stop integration tests guarding the flow (Milestone M4).

## 1) Current State & Pain Points

- Wake detection happens downstream in the router by string matching STT text, so the microphone stays muted until the full phrase is transcribed and runs through the router.
- Muting/unmuting is coordinated within the STT worker and router. There is no standalone component tasked with wake phrase detection or coordinating half-duplex control.
- Double wake interactions (interrupting TTS output or cancelling speech) require ad-hoc logic across router/TTS and are not supported today.
- We are training a bespoke OpenWakeWord model for “Hey Tars” on Colab; we need a runtime that can deploy that lightweight neural detector in real time on the edge.

## 2) Proposed Architecture Overview

| Component | Responsibility |
| --- | --- |
| `apps/wake-activation` | Own audio tap, run OpenWakeWord inference, publish wake events, track speaking state, issue mute/unmute and TTS pause/stop commands. |
| `apps/stt-worker` | Expose audio frames (shared ring buffer or IPC) so wake service can read raw PCM without duplicating capture; obey `wake/mic` commands to unmute.
| `apps/tts-worker` | Support pause/resume/stop commands and report status (`speaking_start`, `speaking_end`, `paused`).
| Router | Consume `wake/event` to open conversational windows and close them after timeout rather than performing inline wake phrase checks.

Key runtime contracts:

1. **Audio fan-out** – STT capture writes frames into a bounded asyncio queue. Wake activation reads from that queue and performs 16kHz inference with OpenWakeWord.
2. **Wake lifecycle** – On a positive detection, wake activation publishes `wake/event` (type `wake`) and instructs STT to unmute via `wake/mic`. Router opens interaction window.
3. **Double wake interruptions** – If wake detection fires while TTS status is `speaking`, wake activation issues `tts/pause` (or `tts/stop` if followed by cancel words) and publishes `wake/event` (type `interrupt`).
4. **Idle timeout** – Wake activation tracks trailing ASR results. If no speech arrives within `WAKE_IDLE_TIMEOUT_SEC`, it tells router/TTS to resume or close session.

## 3) Interaction Flows

### 3.1 Initial Wake

1. Wake activation identifies wake phrase.
2. Publishes `wake/event` `{ "type": "wake", "energy": float, "confidence": float, "ts": float }`.
3. Sends `wake/mic` `{ "action": "unmute", "reason": "wake" }` (QoS1) for STT.
4. Router receives `wake/event`, opens wake window (configurable length) without having to parse STT text; optionally plays acknowledgement via TTS.
5. If user remains silent past timeout, wake activation sends `wake/event` type `timeout`, router closes window, microphone returns to mute.

### 3.2 Double Wake / Interrupt

1. While TTS is speaking, wake activation sees wake word again.
2. Publishes `wake/event` `{ "type": "interrupt", "tts_id": optional }` and issues `tts/control` `{ "action": "pause", "reason": "wake_interrupt" }`.
3. Wake activation continues listening for follow-up commands. If STT yields "cancel" or "stop" within `INTERRUPT_WINDOW_SEC`, it sends `tts/control` `{ "action": "stop", "reason": "cancel" }` plus `wake/event` type `cancelled` and drains queued TTS.
4. If other speech follows, router processes it as a new request; if silence persists, wake activation sends `wake/event` type `resume` and `tts/control` `{ "action": "resume" }`.

### 3.3 False Trigger Handling

- Multiple detections within `MIN_RETRIGGER_SEC` are debounced.
- Wake activation maintains detection confidence scores; sub-threshold hits are logged but do not toggle mute.
- Optional "barge-in" guard: require a minimum RMS level before acknowledging a detection.

## 4) MQTT Topics & Payloads

All JSON encoded with `orjson`, `extra="forbid"` in typed models.

- `wake/event` (QoS1, not retained)
  ```json
  {
    "type": "wake" | "interrupt" | "timeout" | "resume" | "cancelled" | "error",
    "confidence": 0.0-1.0,
    "energy": float,
    "tts_id": "optional",
    "cause": "wake_phrase" | "double_wake" | "silence" | "cancel",
    "ts": float
  }
  ```
- `wake/mic` (QoS1)
  ```json
  { "action": "mute" | "unmute", "reason": "wake" | "timeout" | "tts", "ttl_ms": optional }
  ```
- `tts/control` (QoS1)
  ```json
  { "action": "pause" | "resume" | "stop", "reason": "wake_interrupt", "id": optional }
  ```
- `wake/health` retained health heartbeat.

Router listens to `wake/event` in place of parsing raw STT for wake phrases. STT worker obeys `wake/mic`. TTS worker implements `tts/control` with pause/resume semantics (new functionality).

## 5) Configuration & Assets

| Variable | Purpose | Default |
| --- | --- | --- |
| `WAKE_MODEL_PATH` | Path to OpenWakeWord `.tflite` or `.onnx` model bundle | `/models/openwakeword/hey_tars.tflite` |
| `WAKE_SAMPLE_RATE` | Sample rate consumed by the detector | `16000` |
| `WAKE_DETECTION_THRESHOLD` | Probability needed to count as detection | `0.55` |
| `WAKE_MIN_RETRIGGER_SEC` | Suppress successive triggers | `1.0` |
| `WAKE_INTERRUPT_WINDOW_SEC` | Time to wait for cancel/stop after interrupt | `2.5` |
| `WAKE_IDLE_TIMEOUT_SEC` | Silence duration before resuming TTS / closing window | `3.0` |
| `WAKE_ACK_TOPIC` | Optional TTS text on wake | unset |
| `WAKE_DEBUG_AUDIO` | Opt-in to dump wav clips for analysis | `0` |

Model deployment: store `.json` metadata alongside `.tflite`, mount via Docker volume. Provide script to fetch from Colab artifact bucket.

## 6) Inter-Service Changes

1. **STT worker**
   - Expose a `BroadcastAudio` interface (async generator or local UDP) so wake activation can read frames without double opening ALSA.
   - Listen for `wake/mic` topic to override local mute state (set `UNMUTE_GUARD_MS` on wake, enforce re-mute after TTS if commanded).

2. **TTS worker**
   - Track active utterances by `utt_id` and support `pause`, `resume`, `stop` commands via MQTT.
   - Publish enriched `tts/status` events (`paused`, `resumed`, `stopped`) to allow wake activation to follow state.

3. **Router**
   - Subscribe to `wake/event` and open/close wake window based on `type`.
   - Remove inline regex wake detection once wake activation is authoritative.

4. **UI / UX**
   - Display wake/interrupt state (optional). Show when TTS paused awaiting user input.

## 7) Implementation Milestones

- [ ] **M0 – Prep**
   - [x] Stage OpenWakeWord model artifacts (TFLite + ONNX) under `models/openwakeword/` and wire Docker copy step.
   - [ ] Confirm licensing/attribution requirements for distributing the Colab-trained model bundle.
   - [x] Provide optional `openwakeword` extra in `pyproject.toml` and document install guidance in README.

- [x] **M1 – Wake Activation Skeleton**
   - ✅ Scaffolded `apps/wake-activation` with config objects, MQTT wiring, service skeleton, and placeholder inference loop.
   - ✅ Added unit tests for config parsing and model serialization; ensured service installs via `pyproject.toml`.
   - ✅ Dockerfile builds editable install and now copies wake models into `/models/openwakeword/`.

- [x] **M2 – OpenWakeWord Integration**
   - ✅ Audio fan-out transport implemented and unit-tested (`AudioFanoutClient`).
   - ✅ Real-time inference loop integrated: wake detector consumes streamed PCM, emits `wake/event`, and unmutes mic on detection.
   - ✅ Regression tests with captured score sequences replay the detector offline and assert first-threshold detection.
   - ✅ Documentation refreshed with regression harness guidance and backend selection notes.

- [x] **M3 – Mute/Unmute Coordination**
   - ✅ `wake/mic` contract implemented; STT worker now obeys commands and schedules TTL re-mute.
   - ✅ Wake activation emits idle-timeout TTL hints and publishes timeout events after silence.
   - ✅ Structured logs trace wake sessions and mute lifecycle for observability.

- [x] **M4 – Double Wake & TTS Controls**
   - [x] Introduce playback observer scaffolding in the Piper TTS stack to emit player lifecycle callbacks.
   - [x] Extend TTS worker with pause/resume/stop control.
   - [x] Implement double wake detection logic and speech-cancel window behavior in wake activation.
   - [x] Author integration tests simulating TTS playback with double wake + cancel.

- [ ] **M5 – Timeouts & Resumption Logic**
   - [ ] Wire wake activation's idle-timeout branch to publish `tts/control` resume events once pause handling exists.
   - [ ] Update router to consume `wake/event` `timeout/resume/cancelled` types and retire regex wake detection.
   - [ ] Add integration coverage that exercises timeout → resume, timeout → session close, and ensures metrics/logging capture the transitions.

- [ ] **M6 – Hardening & Observability**
   - Structured logging, metrics (detection count, false triggers, pause durations).
   - Health endpoints, watchdog for audio pipeline stalls.
   - Docs (README + operations guide) and add `make wake-check` smoke test.

## 10) Next Milestone (M4) Action Items

1. ✅ Ensure observer callbacks fire for all Piper player spawns to support downstream pause/resume orchestration.
2. ✅ Extend the TTS worker to honor pause/resume/stop commands issued during double wake interactions.
3. ✅ Implement wake activation logic to publish `wake/event` type `interrupt`, coordinate cancel phrases, and resume playback on timeout.
4. ✅ Author integration coverage that simulates double wake scenarios and validates TTS pause/resume behavior end-to-end.
5. Update service docs with interrupt lifecycle diagrams once the flow is implemented.

## 11) Next Milestone (M5) Early Prep

Once M4 control paths are stable, immediately begin validating the timeout/resume orchestration:

- Draft MQTT contract tests that assert `wake/event` type `timeout` drives router window closure when no follow-up speech arrives.
- Prototype a metrics counter for idle timeouts vs. cancels so we can observe regressions while finishing M5.
- Capture any configuration deltas needed for `WAKE_IDLE_TIMEOUT_SEC` tuning ahead of the implementation sprint.

## 8) Risks & Mitigations

- **Audio capture contention** – Need a reliable way to share audio frames between STT worker and wake activation without fighting over ALSA. Mitigation: create a single capture process that fan-outs frames over IPC (Unix domain socket or shared memory ring).
- **False positives** – Tune detection threshold, add RMS gating, maintain moving average to reject background audio.
- **Latency** – Ensure detection loop stays sub-200ms. Use optimized inference (TFLite runtime) and possibly run on dedicated thread.
- **New TTS pause support** – Requires non-trivial changes in TTS worker to buffer audio chunks for resume. Mitigation: implement chunk queue with ability to halt/resume streaming to Piper.
- **State synchronization** – Need robust sequencing between wake activation and router/TTS to avoid stuck states. Use UUIDs and explicit acknowledgements on control topics.

## 9) Follow-Ups & Nice-to-Haves

- Add CLI / dev tool to replay recorded audio through detector for model evaluation.
- Support multiple wake phrases by loading additional OpenWakeWord models.
- Telemetry dashboard (Prometheus/Grafana) with wake counts and interruption stats.
- Mobile push notification when wake is triggered (optional future).
