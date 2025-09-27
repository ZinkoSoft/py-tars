# Refactor Plan: SOLID & Observer Compliance

## Goals
- Align services with SOLID principles using clear domain ports and adapters.
- Ensure MQTT usage follows a consistent Observer pattern with idempotent, QoS-aware messaging.
- Improve reliability, observability, and developer ergonomics without changing core product behavior.

## Guiding Blueprint
This plan operationalizes the outcomes captured in `py-tars_SOLID-review.md`.

---

## Progress Snapshot *(27 Sep 2025)*
- ✅ Router dispatcher now runs behind a bounded `asyncio.Queue` with configurable overflow strategies, structured logging, and handler timeouts. Tests cover the new backpressure rules and are wired into `apps/router/tests`.
- ✅ Router composition root passes `RouterStreamSettings` into the dispatcher so queue size and timeout knobs are driven by environment config.
- ✅ Structured logging groundwork in router/runtime is in place (JSON logs with correlation metadata) from earlier phases.
- ✅ Router policy publishes only typed contracts, and the wake-mode regressions now assert against `TtsSay`/`LLMRequest` models instead of raw dict payloads.
- ✅ Shared MQTT adapters (`src/tars/adapters/mqtt_asyncio.py`) expose configurable dedupe options, and router tests exercise the subscriber behavior to guard regressions.
- ✅ STT worker publishes `FinalTranscript`/`PartialTranscript` events via the shared MQTT publisher, introducing envelopes and message IDs for downstream consumers.

## Phase 1 – Stabilize Contracts (Week 1)
**Objectives**
- Define typed message schemas and enforce runtime validation.
- Normalize messaging semantics across services.
- Lock in formatting and type-checking tooling.

**Tasks**
1. Add Pydantic models for all MQTT payloads in `apps/shared/models.py` with `extra="forbid"`.
2. Introduce `message_id` and QoS=1 for critical topics (`tts/say`, `stt/final`, `llm/request`, etc.).
3. Implement dedupe handling on consumers to ignore repeated `message_id`s.
4. Centralize publish helpers to apply structured logging, QoS, and retry policy.
5. Add `ruff`, `black`, and `mypy` configs; update `make check` to run them and ensure CI parity.

**Deliverables**
- New/updated message model module with tests.
- Publish helper module with logging instrumentation.
- Configured lint/type-check workflow and documentation updates.

---

## Phase 2 – Extract Ports & Adapters (Weeks 2–3)
**Objectives**
- Separate domain policy from infrastructure concerns.
- Create swappable abstractions for STT, TTS, and the message bus.

**Tasks**
1. Create `src/tars/domain/{models,ports,policy}.py` to house pure domain logic.
2. Move MQTT/audio specifics into adapters, e.g. `tars/adapters/{mqtt_asyncio,tts_piper,stt_fasterwhisper}.py`.
3. Refactor `apps/router/main.py`, `apps/stt-worker/main.py`, and `apps/tts-worker/main.py` into composition roots
   that wire domain services with adapters.
4. Introduce provider registries/factories to make new STT/TTS engines pluggable without modifying domain code.
5. Add unit tests for domain policies and adapter boundaries.

**Deliverables**
- Domain layer package with protocols and policy logic fully typed.
- Adapter modules with concrete implementations.
- Updated app entrypoints demonstrating Dependency Inversion and improved testability.

---

## Phase 3 – Observer Hygiene & Resilience (Weeks 3–4)
**Objectives**
- Ensure MQTT flows behave predictably under load and failures.
- Harden wake/mic state machine using new abstractions.

**Tasks**
1. ✅ Add bounded queues/backpressure controls inside adapters; guarantee `await` on publishes. *(Router dispatcher updated with bounded queue + overflow strategies and tests in `apps/router/tests/test_runtime_dispatcher.py`.)*
2. Debounce `stt/partial` messages; treat `stt/final` as the routing trigger.
3. Revisit wake/mic logic with `message_id` semantics, TTL tasks, and idempotent handling.
4. Standardize `system/health/+` payload schema and emit periodic heartbeats.
5. Add graceful shutdown hooks responding to SIGINT/SIGTERM to stop subscribers, audio streams, and MQTT cleanly.

**Deliverables**
- Updated adapters and services with resilience features.
- Revised wake control tests ensuring state recovery.
- Health telemetry spec documented and adopted across services.

---

## Phase 4 – Observability & Metrics (Week 4)
**Objectives**
- Provide actionable insight into service health and latency.
- Make logs machine-friendly while preserving human readability.

**Tasks**
1. Configure `structlog` (or similar) for JSON logging with correlation fields (`message_id`, `topic`, `latency_ms`).
2. Add Prometheus metrics (or MQTT-based counters) tracking STT/TTS latency, queue depth, retry counts.
3. Document logging/metrics configuration and consumption (CLI, dashboards).

**Deliverables**
- Logging configuration module shared across services.
- Metrics endpoint or publisher plus documentation.
- Sample dashboards or Grafana JSON (optional stretch).

---

## Phase 5 – Integration & Regression Testing (Weeks 4–5)
**Objectives**
- Guarantee the refactor preserves behavior end-to-end.
- Catch regressions in wake, transcription, and speech synthesis flows.

**Tasks**
1. Add `tests/integration/` powered by `testcontainers` (Mosquitto) to validate STT→Router→TTS flow.
2. Create golden WAV fixtures verifying TTS adapter output characteristics.
3. Ensure `make check` runs lint, type-check, unit, and integration checks in CI and locally.

**Deliverables**
- Integration test suite and fixtures.
- Updated CI pipeline.
- Regression documentation for contributors.

---

## Phase 6 – Cleanup & Documentation (Week 5)
**Objectives**
- Publish the final architecture and contributor guidance.
- Identify remaining stretch goals.

**Tasks**
1. Produce architecture diagrams illustrating domain/adapters and MQTT flow.
2. Document provider extension points, message schemas, and wake flow behavior.
3. Add or update `README_dev.md` for environment setup, audio device selection, and Orange Pi notes.
4. Triage remaining tech debt and create follow-up issues (e.g., Grafana dashboards, alternative TTS providers).

**Deliverables**
- Updated docs and diagrams.
- Backlog of optional enhancements.

---

## Quick Wins (Immediate Next Steps)
- ✅ Land the router migration onto `src/tars/runtime.dispatcher` using the new typed contracts for STT, TTS, LLM, wake, and health events. *(Dispatcher now orchestrates subscriptions with typed models and backpressure.)*
- ✅ Replace ad-hoc MQTT payload dicts with `src/tars/contracts/v1/*` models inside router handlers and tests, deleting the legacy `apps/shared/models.py` clones as they fall out of use. *(Router wake-mode tests now validate `TtsSay`/`LLMRequest` models, ensuring typed round-trips.)*
- ✅ Stand up MQTT publisher/subscriber adapters under `src/tars/adapters/mqtt_asyncio.py` (or similar) and point `apps/router/main.py` at them as the first composition root. *(Adapters now ship with a typed options object and dedicated tests under `apps/router/tests/test_mqtt_adapter.py`.)*
- Align the LLM worker with `src/tars/contracts/v1/llm` (including the shared `BaseLLMMessage`) to keep provider responses consistent with the router expectations.
- Turn on strict mypy + ruff checks for the `src/tars` packages so regressions are caught while we migrate callers over module by module.

## Migration Checklist – `src/tars/` Adoption
- **Router**
   - [ ] Replace topic string switches with a subscription table backed by `src/tars/runtime/subscription.py` and `Dispatcher`.
   - ✅ Deserialize inbound MQTT payloads with `src/tars/contracts/v1/{stt,tts,llm,wake,health}` and publish outbound messages through the typed helpers. *(Policy and dispatcher paths now operate purely on typed models.)*
   - [ ] Move rule evaluation and streaming boundary management into `src/tars/domain/policy.py`, leaving `apps/router/main.py` as a thin composition root.
   - ✅ Add regression tests under `apps/router/tests/` that exercise the dispatcher flow with the new contracts. *(Dispatcher queue guardrails + typed wake-mode assertions live under `apps/router/tests/`.)*
- **STT Worker**
   - [x] Emit `FinalTranscript`/`PartialTranscript` from `src/tars/contracts/v1/stt.py` and rely on the shared publisher adapter for MQTT.
   - [ ] Consume wake/health contracts from `src/tars/contracts/v1/` where relevant (e.g., suppressions/ready signals).
   - [ ] Wrap VAD/transcription orchestration in a port-aware service under `src/tars/domain/stt.py`.
   - [ ] Backfill unit tests for suppression heuristics using the shared contracts to guarantee schema parity.
- **TTS Worker**
   - [ ] Accept `TTSSay` models from `src/tars/contracts/v1/tts.py` and funnel speech synthesis through a dispatcher-aware consumer.
   - [ ] Publish `tts/status` as a typed health/event contract and expose aggregation via domain services.
   - [ ] Gradually retire bespoke serialization helpers once the adapter is in place.
- **LLM Worker**
   - [ ] Import `LLMRequest`, `LLMResponse`, and `LLMStreamDelta` from `src/tars/contracts/v1/llm.py` and delete duplicated BaseModel definitions.
   - [ ] Route provider results through domain ports so streaming vs. non-streaming output share the same dispatcher surface.
   - [ ] Add contract round-trip tests (`orjson.loads(dumps(...))`) to lock message shapes.
- **Memory Worker & UI surfaces**
   - [ ] Introduce memory query/result contracts in `src/tars/contracts/v1/memory.py` (mirroring current payloads) and update consumers.
   - [ ] Ensure UI clients subscribe/publish via the shared adapters so the event loop semantics match the backend services.
- **Shared Tooling**
   - [ ] Wire `src/tars/runtime/ctx.py` into each service’s startup path to centralize configuration/env parsing.
   - [ ] Add integration tests that spin up dispatcher + adapters with a Mosquitto container to verify cross-service wiring.
   - [ ] Track progress in this checklist and retire legacy modules as soon as the new sources cover them.

## Risks & Mitigations
- **Risk**: Refactor churn impacting ongoing feature work.  → Mitigation: phase the work; keep PRs small and reviewable.
- **Risk**: MQTT schema changes disrupting deployed robots. → Mitigation: version payloads or deploy adapters gradually; ensure backward compatibility where feasible.
- **Risk**: Integration tests add runtime/complexity. → Mitigation: mark heavy tests separately; provide smoke subset for rapid iteration.

---

## Success Criteria
- All services depend on domain ports, with adapters encapsulating external concerns.
- MQTT messages are validated, idempotent, and use QoS consistently.
- Logs/metrics enable rapid diagnosis of wake/STT/TTS issues.
- `make check` (lint, type, unit, integration) passes inside CI and for contributors.
- Documentation clearly explains architecture, extension points, and operational playbooks.
