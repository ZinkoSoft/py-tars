<!--
SYNC IMPACT REPORT
==================
Version Change: 1.0.0 → 1.1.0
Rationale: Added Docker Build System documentation section

Modified Principles: N/A
Added Sections:
  - Docker Build System (new section between MQTT Contract Standards and Development Workflow)
    - Dockerfile Architecture (app.Dockerfile vs specialized)
    - Build System Guidelines (when to use which)
    - Docker Compose Integration
    - Complete mapping of all 13 specialized Dockerfiles with purposes

Removed Sections: N/A

Templates Requiring Updates:
  ✅ No template changes required - documentation addition only

Follow-up TODOs: 
  - Update specialized Dockerfiles as services are migrated to src/ layout (per 001-standardize-app-structures)
  - Consider consolidating services that no longer need specialized builds

Previous Versions:
  - 1.0.0 (2025-10-13): Initial constitution ratification
-->

# py-tars Constitution

## Core Principles

### I. Event-Driven Architecture (NON-NEGOTIABLE)

All services MUST communicate exclusively through MQTT using structured JSON envelopes. Direct service-to-service calls are FORBIDDEN. Each service MUST:
- Subscribe only to topics it needs to consume
- Publish events with complete, self-contained payloads
- Define typed Pydantic v2 models for all message payloads
- Validate messages at boundaries (on publish and receipt)
- Use `orjson` for all JSON serialization/deserialization

**Rationale**: Event-driven architecture ensures loose coupling, enables independent service deployment, supports graceful degradation, and allows system observation through topic monitoring. Pydantic models enforce contract adherence at compile and runtime.

### II. Typed Contracts (NON-NEGOTIABLE)

All MQTT message payloads MUST have explicit Pydantic v2 models with:
- `ConfigDict(extra="forbid")` to reject unknown fields
- Complete type annotations (no `Any` types without justification)
- Field validation constraints where applicable
- Round-trip serialization tests (`loads(dumps(model.model_dump()))`)

Services MUST fail fast on invalid payloads rather than silently ignoring fields or using defaults.

**Rationale**: Strong typing prevents runtime errors from schema drift, makes contracts self-documenting, enables tooling support, and catches integration bugs at development time rather than production.

### III. Async-First Concurrency (NON-NEGOTIABLE)

All services MUST use `asyncio` with strict event loop hygiene:
- CPU-bound work (VAD, transcription, embeddings, synthesis) MUST use `asyncio.to_thread()`
- No synchronous blocking calls in async contexts (I/O, sleep, CPU work)
- Task supervision via `asyncio.TaskGroup` (Python 3.11+)
- Graceful cancellation with `CancelledError` propagation
- Timeout handling with `asyncio.wait_for()` for all external operations
- Futures for request-response patterns (no polling loops)

Correlation IDs MUST be used for request-response flows with persistent subscriptions.

**Rationale**: Async-first design maximizes throughput on limited hardware (Orange Pi 5 Max), prevents event loop blocking that would delay MQTT message processing, and enables graceful shutdown. Futures eliminate CPU-wasting polling.

### IV. Test-First Development (NON-NEGOTIABLE)

For new features or contract changes:
1. Write tests defining expected behavior
2. Get user/stakeholder approval on test scenarios
3. Verify tests FAIL (red state)
4. Implement feature until tests PASS (green state)
5. Refactor while keeping tests green

Tests MUST include:
- **Contract tests**: Validate MQTT message schemas and topic patterns
- **Integration tests**: Verify cross-service workflows work end-to-end
- **Async tests**: Use `pytest-asyncio` to test concurrent behavior

Run `make check` (fmt + lint + test) before every commit.

**Rationale**: Test-first prevents scope creep, ensures features meet actual requirements, catches regressions early, and provides executable documentation of system behavior.

### V. Configuration via Environment (12-Factor)

All configuration MUST come from environment variables. Services MUST:
- Parse environment once at startup into typed config objects
- Never access `os.environ` deep in call stacks
- Provide `.env.example` with all required and optional variables
- Redact secrets (API keys, passwords) in logs and error messages
- Fail fast with clear error messages for missing required configuration

**Rationale**: Environment-based config enables deployment flexibility (dev/staging/prod), keeps secrets out of source control, supports containerization, and makes configuration changes transparent.

### VI. Observability & Health Monitoring

Every service MUST:
- Publish retained health status to `system/health/<service>` with `{ ok: bool, event?: string, err?: string }`
- Emit structured JSON logs with correlation fields: `request_id`, `utt_id`, `topic`, `service`
- Log at appropriate levels: DEBUG (dev detail), INFO (state transitions), WARNING (retries), ERROR (failures)
- Provide metrics for key operations: latency, throughput, error rates
- Never log secrets or sensitive user data

Services MUST flip health to unhealthy on fatal errors and recover health status when resolved.

**Rationale**: Comprehensive observability enables rapid debugging in production, supports monitoring/alerting, provides audit trails, and makes system behavior transparent without code inspection.

### VII. Simplicity & YAGNI

New features and abstractions require justification:
- Start with the simplest solution that meets requirements
- Add complexity only when concrete needs arise (not "might need later")
- Prefer stdlib over third-party libraries unless significant value
- Keep PRs small and focused (one behavior change per PR)
- Document complexity when unavoidable (link to issues/tickets)

Violations of simplicity MUST be justified in design docs with rationale for why simpler alternatives were insufficient.

**Rationale**: Premature abstraction creates maintenance burden, slows development, and often misses actual use cases. Simple code is easier to understand, test, modify, and debug.

## MQTT Contract Standards

### Topic Design

Topics follow hierarchical patterns:
- `<domain>/<action>` for commands: `tts/say`, `llm/request`, `memory/query`
- `<domain>/<event>` for events: `stt/final`, `tts/status`, `wake/event`
- `system/health/<service>` for health monitoring (retained)

Services MUST NOT publish to topics they don't own without architectural review.

### QoS & Retention Policy

- **Health topics**: QoS 1, retained (e.g., `system/health/*`)
- **Commands/requests**: QoS 1, not retained (e.g., `llm/request`, `tts/say`)
- **Responses**: QoS 1, not retained (e.g., `llm/response`, `memory/results`)
- **Streaming/partials**: QoS 0, not retained (e.g., `stt/partial`, `llm/stream`)

### Idempotency

Message consumers MUST tolerate duplicate deliveries by tracking `(topic, id, seq)` tuples. Producers MUST include correlation IDs (`id`, `utt_id`) for tracing.

### Schema Evolution

Breaking changes require:
1. New topic version or parallel topic (e.g., `llm/request/v2`)
2. Migration plan documented in spec
3. Deprecation timeline for old topics
4. Update to all affected services

## Docker Build System

### Dockerfile Architecture

The project uses a two-tier Docker build system:

#### 1. Shared Multi-Stage Dockerfile (`docker/app.Dockerfile`)

The **default builder** for most services. This reusable multi-stage Dockerfile:
- **Purpose**: Build any app in the monorepo with consistent patterns
- **Build Args**:
  - `PY_VERSION`: Python version (default 3.11)
  - `APP_PATH`: Path to the app (e.g., `apps/router`)
  - `CONTRACTS_PATH`: Path to contracts package (default `packages/tars-contracts`)
  - `APP_MODULE`: Python module to run with `python -m` (e.g., `tars_router.app_main`)
  - `APP_CMD`: Optional shell command (overrides APP_MODULE)
- **Stages**:
  - `base`: Sets up Python environment with tini and non-root user
  - `builder`: Builds wheels for contracts + app packages
  - `runtime`: Installs wheels and runs via `start-app.sh` entrypoint
- **Used by**: Services that follow standard Python packaging (src/ layout, pyproject.toml)

#### 2. Specialized Dockerfiles (`docker/specialized/*.Dockerfile`)

Service-specific Dockerfiles for apps with unique dependencies:

| Dockerfile | Service | Special Requirements |
|------------|---------|---------------------|
| `camera-service.Dockerfile` | Camera Service | libcamera, OpenCV system deps, V4L2 |
| `stt-worker.Dockerfile` | STT Worker | Audio libraries, Whisper models |
| `stt-ws.Dockerfile` | STT WebSocket Server | Faster-Whisper, WebSocket server |
| `tts-worker.Dockerfile` | TTS Worker | Piper synthesis, PulseAudio, ONNX runtime |
| `wake-activation.Dockerfile` | Wake Word Detection | OpenWakeWord, audio processing, optional NPU (rknnlite) |
| `memory-worker.Dockerfile` | Memory/RAG Worker | SentenceTransformers, vector DB, embeddings |
| `llm-worker.Dockerfile` | LLM Worker | OpenAI SDK, provider interfaces |
| `router.Dockerfile` | Router | Minimal deps for rules engine |
| `mcp-bridge.Dockerfile` | MCP Bridge | Model Context Protocol SDK |
| `mcp-server.Dockerfile` | MCP Server | MCP server framework |
| `ui.Dockerfile` | Terminal UI | TUI libraries (textual, rich) |
| `ui-web.Dockerfile` | Web UI | Flask/FastAPI, web framework deps |

### Build System Guidelines

When creating or modifying services:

1. **Use `app.Dockerfile` by default** if the service:
   - Follows standard Python packaging (src/ layout, pyproject.toml)
   - Has no special system dependencies beyond Python packages
   - Can use pip-installable dependencies

2. **Create specialized Dockerfile** when the service requires:
   - System libraries not available via pip (libcamera, audio libs, NPU drivers)
   - Hardware-specific compilation (ONNX with CPU extensions, rknnlite)
   - Complex multi-stage builds with custom toolchains
   - Non-Python runtimes or frameworks

3. **Migration Path**: As services are standardized (see `specs/001-standardize-app-structures`):
   - Update specialized Dockerfiles to use new src/ layout
   - Change `COPY apps/<service>/ /app/` to `COPY apps/<service>/ /workspace/apps/<service>/`
   - Update `CMD` to use entry point: `["python", "-m", "<package_name>"]`
   - Consider migrating to `app.Dockerfile` if system deps can be removed

### Docker Compose Integration

Service definitions in `ops/compose.yml` and `ops/compose.npu.yml` specify:
- Which Dockerfile to use (`build.dockerfile`)
- Build args for `app.Dockerfile` services
- Volume mounts (source code, models, configs)
- Environment variables
- Network mode (`host` for services needing direct hardware access)

## Development Workflow & Quality Gates

### Python Environment

All development MUST use the project's virtual environment located at `/home/james/git/py-tars/.venv/bin`. When running Python commands or installing packages, always:

1. **Activate the venv**: `source /home/james/git/py-tars/.venv/bin/activate`
2. **Or use direct paths**: `/home/james/git/py-tars/.venv/bin/python` or `/home/james/git/py-tars/.venv/bin/pip`

This ensures:
- Consistent dependency versions across all services
- Isolation from system Python and other projects
- Reproducible builds and test environments
- Proper tooling versions (ruff, black, mypy, pytest)

**Never** install packages globally or use system Python for development work.

### Pre-Commit Requirements

Before every commit, developers MUST:
1. Run `make fmt` (ruff + black) to format code
2. Run `make lint` (ruff + mypy) to catch type errors
3. Run `make test` to verify all tests pass
4. Ensure no secrets or API keys in diff

Consider using pre-commit hooks to automate these checks.

### PR Quality Gates

All pull requests MUST:
- Include typed Pydantic models for any new MQTT payloads
- Add or update tests (unit + async + integration as appropriate)
- Pass CI checks (`make check`)
- Update documentation (README, docstrings, or `.github/copilot-instructions.md`)
- Keep Router rules deterministic (LLM fallback separate)
- Preserve existing suppression heuristics (expose tuning via env)
- Include structured logs with correlation IDs

PRs SHOULD be small and focused: one behavior change per PR, not sweeping refactors.

### Documentation Standards

- **Docstrings**: Google style (summary, Args, Returns, Raises, Examples)
- **Code comments**: Explain *why*, not *what*; link to issues/tickets
- **Architecture changes**: Update `.github/copilot-instructions.md` (authoritative guidance)
- **User-facing features**: Update README.md
- **Internal design decisions**: Document in `docs/` or spec files

### Python Standards

- **Version**: Python 3.11+ (required for `TaskGroup`, performance, better typing)
- **Style**: PEP 8 / PEP 484; snake_case functions, PascalCase classes, UPPER constants
- **Type annotations**: All public APIs fully typed; no `Any` without justification+comment
- **Tooling**: ruff (lint), black (format), mypy (type check), pytest (test)

## Governance

This constitution supersedes all other development practices. When conflicts arise between this document and other guidance, the constitution takes precedence.

### Amendment Process

Changes to this constitution require:
1. Proposal document explaining rationale and impact
2. Review by project maintainers
3. Version bump following semantic versioning:
   - **MAJOR**: Backward-incompatible changes (remove/redefine principles)
   - **MINOR**: New principles or sections added
   - **PATCH**: Clarifications, wording fixes, non-semantic changes
4. Update sync impact report (prepended as HTML comment)
5. Update dependent templates and documentation

### Compliance Verification

All PRs and code reviews MUST verify compliance with constitution principles. Use the checklist in `.github/copilot-instructions.md` section 16 as a starting point.

Complexity violations (e.g., adding architectural patterns, breaking simplicity) MUST be justified in design documents with explanation of why simpler alternatives were insufficient.

### Runtime Development Guidance

For detailed implementation patterns, runtime conventions, and service-specific guidance, refer to `.github/copilot-instructions.md`. That file serves as the authoritative source for:
- Async patterns and anti-patterns
- MQTT payload examples
- Router boundary detection
- Provider interfaces
- Error handling conventions
- Performance guidelines

**Version**: 1.1.0 | **Ratified**: 2025-10-13 | **Last Amended**: 2025-10-13