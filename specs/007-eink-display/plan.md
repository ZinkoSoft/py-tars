# Implementation Plan: Remote E-Ink Display for TARS Communication

**Branch**: `007-eink-display` | **Date**: 2025-11-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-eink-display/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Create a visual communication interface for the remote TARS microphone system using a Waveshare 2.13" V4 e-ink display. The display will show system states (standby, listening, processing) and visualize conversation flow with message bubbles for user speech transcripts (right-aligned) and TARS responses (left-aligned). The service subscribes to MQTT topics (`stt/final`, `llm/response`, `wake/event`) and updates the display accordingly, with intelligent screen space management that prioritizes LLM responses when content exceeds display capacity.

## Technical Context

**Language/Version**: Python 3.11  
**Primary Dependencies**: asyncio-mqtt/paho-mqtt (MQTT client), Pillow (image rendering), waveshare-epd (display driver), pydantic (contract validation)  
**Storage**: N/A (ephemeral display state only)  
**Testing**: pytest with pytest-asyncio for async MQTT message handling  
**Target Platform**: Linux ARM64 (Radxa Zero 3W with GPIO access for e-ink display)  
**Project Type**: Single application service (follows standard apps/ structure)  
**Performance Goals**: Display updates within 500ms of MQTT message receipt; e-ink refresh <2 seconds per update  
**Constraints**: E-ink display refresh rate (1-2 seconds full refresh), 250x122 pixel monochrome display, limited screen real estate for text  
**Scale/Scope**: Single remote device deployment, ~5-10 MQTT messages per conversation, 200-character message capacity

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### ✅ I. Event-Driven Architecture
- Service WILL communicate exclusively through MQTT (subscribes to `stt/final`, `llm/response`, `wake/event`)
- No direct service-to-service calls required
- WILL use Pydantic v2 models from tars-core (FinalTranscript, LLMResponse, WakeEvent)
- WILL validate messages at boundaries using existing contracts
- WILL use orjson via tars-core serialization

### ✅ II. Typed Contracts
- WILL use existing Pydantic v2 models with `extra="forbid"` from packages/tars-core/src/tars/contracts/v1/
- No new message contracts required (consuming existing: FinalTranscript, LLMResponse, WakeEvent)
- WILL fail fast on invalid payloads

### ✅ III. Async-First Concurrency
- WILL use asyncio with asyncio-mqtt for MQTT subscriptions
- Display rendering (PIL image generation) WILL use `asyncio.to_thread()` to avoid blocking event loop
- WILL use `asyncio.TaskGroup` for task supervision
- WILL implement graceful cancellation and timeout handling
- No polling loops required (event-driven MQTT subscriptions)

### ✅ IV. Test-First Development
- WILL write contract tests for MQTT message handling
- WILL write integration tests for display state transitions
- WILL use pytest-asyncio for async test cases
- Tests WILL be written before implementation

### ✅ V. Configuration via Environment
- WILL parse configuration from environment variables at startup:
  - `MQTT_HOST`, `MQTT_PORT`, `MQTT_URL` (connection to main TARS system)
  - `LOG_LEVEL` (logging configuration)
  - `DISPLAY_TIMEOUT_SEC` (timeout to return to standby)
  - `PYTHONPATH` (module discovery)
- WILL provide `.env.example` with all variables
- No secrets required for this service

### ✅ VI. Observability & Health Monitoring
- WILL publish retained health status to `system/health/ui-eink-display`
- WILL emit structured JSON logs with service identifier
- WILL log display state transitions at INFO level
- WILL log MQTT message handling at DEBUG level
- WILL log errors with context (display failures, MQTT disconnection)

### ✅ VII. Simplicity & YAGNI
- Simplest solution: Subscribe to topics, update display based on message type
- No abstractions required beyond standard service structure
- Using stdlib (asyncio, PIL) and waveshare-epd library (hardware requirement)
- Single-purpose service with clear responsibility

### ✅ Docker Build System
- WILL require specialized Dockerfile due to:
  - GPIO hardware access for e-ink display control
  - waveshare-epd library with hardware-specific dependencies
  - PIL/Pillow with system image libraries
- WILL follow specialized Dockerfile pattern similar to other hardware services (camera-service, wake-activation)

**GATE STATUS**: ✅ **PASS** - All constitution principles satisfied. No violations require justification.

## Project Structure

### Documentation (this feature)

```text
specs/007-eink-display/
├── spec.md              # Feature specification
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command - will be empty, using existing)
├── checklists/          # Quality assurance
│   └── requirements.md  # Spec validation checklist
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
apps/ui-eink-display/               # New service application
├── src/
│   └── ui_eink_display/            # Python package
│       ├── __init__.py             # Entry point (python -m ui_eink_display)
│       ├── config.py               # Environment variable configuration
│       ├── display_manager.py      # E-ink display control & rendering
│       ├── display_state.py        # State machine for display modes
│       ├── message_formatter.py    # Text formatting & layout logic
│       └── mqtt_handler.py         # MQTT subscription & message routing
├── tests/
│   ├── unit/
│   │   ├── test_display_state.py   # State transition logic
│   │   ├── test_message_formatter.py  # Text wrapping & layout
│   │   └── test_config.py          # Configuration parsing
│   ├── integration/
│   │   ├── test_mqtt_display.py    # MQTT message handling → display update
│   │   └── test_display_manager.py # Display hardware interaction (mocked)
│   └── contract/
│       └── test_mqtt_contracts.py  # Validate consumption of existing contracts
├── pyproject.toml                   # Package metadata & dependencies
├── .env.example                     # Environment variable template
├── README.md                        # Service documentation
└── Dockerfile                       # Specialized build (GPIO + waveshare-epd)

docker/specialized/
└── ui-eink-display.Dockerfile       # New specialized Dockerfile

ops/
├── compose.remote-mic.yml           # Updated to include ui-eink-display service
└── compose.yml                      # Optional: add for standalone testing

packages/tars-core/                  # Existing shared contracts (no changes)
└── src/tars/contracts/v1/
    ├── stt.py                       # FinalTranscript (existing)
    ├── llm.py                       # LLMResponse (existing)
    └── wake.py                      # WakeEvent (existing)
```

**Structure Decision**: Single application service following the established py-tars pattern. The service lives in `apps/ui-eink-display/` with standard Python package structure (`src/ui_eink_display/`). Uses a specialized Dockerfile due to hardware dependencies (GPIO, waveshare-epd library). Integrates with existing MQTT infrastructure and consumes contracts from `tars-core` package. Deployed via `ops/compose.remote-mic.yml` alongside stt-worker and wake-activation on the remote device.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

N/A - No constitution violations. All principles are satisfied.
