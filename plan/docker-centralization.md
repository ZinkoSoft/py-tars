# Dockerfile Centralization Plan

## Why centralize
- Reduce duplicated base-layer maintenance across services.
- Standardize build args, Python versions, and security patch cadence.
- Simplify Compose configuration and CI linting for container builds.

## Current state snapshot (Sept 2025)
- Per-service Dockerfiles previously lived under each `apps/*/Dockerfile`; they are being consolidated under `docker/specialized/*.Dockerfile` with stubs left in place to point to the new paths.
- A reusable template already exists at `docker/app.Dockerfile` with `docker/start-app.sh` for wheel-based apps.
- Compose targets each local Dockerfile directly; build contexts are the repo root.

## Target structure
```
docker/
  images/
    base-python.Dockerfile      # shared Python + OS deps
    app.Dockerfile              # general template (existing)
  specialized/
    stt-worker.Dockerfile       # audio capture + VAD stack
    tts-worker.Dockerfile       # Piper voices, aggregation assets
    ui-web.Dockerfile           # static web build pipeline
  start-app.sh                  # shared launcher (existing)
```
- All Docker-related artifacts move under `docker/` for discoverability.
- Specialized images extend either `images/base-python` or an optimized distro base.

## Implementation phases & todos
### Phase 1 — Inventory & prerequisites
- [x] Confirm each service's system dependencies and runtime assets.
- [x] Identify which services can be built as wheels (eligible for `images/app.Dockerfile`).
- [x] Document required build args/environment for every service.

#### Phase 1 findings (Sept 2025)

| Service | System deps (apt) | Key extras & assets | Wheel-ready? | Build args | Build-time env / entrypoint notes |
| --- | --- | --- | --- | --- | --- |
| router | ca-certificates | `pip install .[all]` (requires `pyproject.toml`); copies shared `src/` tree | Yes (`pyproject.toml`) | None | Sets `PYTHONPATH=/app/src`; simple `CMD python main.py` |
| llm-worker | ca-certificates, curl | Installs `packages/tars-core`; pure Python deps via `requirements.txt` | No (missing packaging scaffolding) | None | Default `LOG_LEVEL=INFO`; `CMD python -m llm_worker` |
| memory-worker | build-essential | Needs volume-backed HF cache (`/data/model_cache`); adds `/app/src` to path | No | None | Sets `HF_HOME`, `SENTENCE_TRANSFORMERS_HOME`, `TRANSFORMERS_CACHE`, `TORCH_HOME` |
| stt-worker | alsa-utils, pulseaudio-utils, portaudio19-dev, python3-dev, gcc, ca-certificates, ffmpeg | Installs `packages/tars-core`; entrypoint copies `/host-models` into container cache | Yes (`pyproject.toml`) | None | Entry script copies models before running `python /app/main.py`; HuggingFace caches under `/app/models` |
| tts-worker | alsa-utils, sox, psmisc, ca-certificates, pulseaudio-utils | Installs `piper-tts`, `packages/tars-core`; copies `/voice-models` → `/voices` at runtime | No | `PIPER_ARCH`, `PIPER_VERSION` | ENTRYPOINT handles voice copy + warning if `TARS.onnx` missing |
| ui | libasound2, libx11-6, libxext6, libxrender1, libxrandr2, libxcursor1, libxi6, libsdl2-2.0-0, libsdl2-ttf-2.0-0, fonts-dejavu-core, ca-certificates | Ships configuration defaults (`ui.toml`, `layout.json`) | No | None | Exposes `UI_CONFIG=/config/ui.toml`; runs `python -u main.py` |
| ui-web | *(none beyond pip)* | Supports alternate build contexts via `ARG SERVICE_PATH`; static assets served by Uvicorn | No | `SERVICE_PATH` | Defaults `MQTT_URL`, `HOST`, `PORT`; `CMD uvicorn server:app` |
| camera-service | python3-dev, gcc, ca-certificates, libcamera-dev, libjpeg-dev, libpng-dev, libcap-dev, python3-libcamera, libgl1, libegl1, libglib2.0-0, libsm6, libxext6, libxrender-dev, libgomp1 | Heavy camera stack; pure source copy | No | None | No special build env; `CMD python /app/main.py` |
| wake-activation | libspeexdsp-dev | Copies `models/openwakeword`; downloads wake models during build; editable install via `pyproject.toml` | Yes (`pyproject.toml`) | `BASE_IMAGE` | Runtime `python -m wake_activation`; no extra env |

**Notes**
- `packages/tars-core` is baked into `llm-worker`, `stt-worker`, and `tts-worker`; centralization should ensure the package is available from the build context or published index.
- Services flagged "No" under wheel-ready will need minimal `pyproject.toml` scaffolding (or conversion to a package) before they can drop into `images/app.Dockerfile`.
- Assets copied at runtime (`/host-models`, `/voice-models`) imply these images expect read-only volumes; the centralized template should preserve hooks for those copy steps.

### Phase 2 — Directory migration
- [x] Mirror existing Dockerfiles into the new `docker/images` or `docker/specialized` locations without altering instructions.
- [x] Update `docker-compose.yml` (and any overrides) to point to the relocated Dockerfiles.
- [x] Build all services locally to verify paths and COPY instructions remain valid.

### Phase 3 — Template adoption
- [x] Introduce `pyproject.toml` packaging for `llm-worker`, `memory-worker`, and `tts-worker` (wheel-ready for the shared template).
- [x] Harmonize worker dependency pins (e.g., `orjson>=3.11`) with `tars-core` to avoid wheel install conflicts.
- [x] Verify packaged workers export all runtime modules (e.g., add `llm_worker/providers/__init__.py`).
- [ ] Refactor common base layers into `docker/images/base-python.Dockerfile`.
- [ ] Update `docker/images/app.Dockerfile` to `FROM` the new base and expose documented build args.
- [ ] Migrate eligible services to use the template by packaging via `pyproject.toml` and passing build args from Compose.

### Phase 4 — Specialized hardening
- [ ] For services needing custom layers, ensure Dockerfiles extend the shared base where possible.
- [ ] Externalize large assets (voices, models) to volumes or build args to keep images lean.
- [ ] Add service-specific README notes under `docker/specialized/` describing quirks and testing commands.

### Phase 5 — Tooling & validation
- [ ] Add a Make target (e.g. `make docker-build-all`) that builds every image via the centralized paths.
- [ ] Integrate lint/scanning (Hadolint/Trivy) pointing at `docker/` in CI.
- [ ] Update contributor docs (`README`/`REFACTOR_NOTES`) with new build instructions and template usage.

## Risks & mitigations
- **COPY path breakage**: keep build context at repo root; add smoke builds per service after relocation.
- **Divergent dependencies**: maintain `specialized/` Dockerfiles with clear ownership; avoid forcing everything through one template.
- **Packaging blockers**: if a service lacks a `pyproject.toml`, prioritize adding minimal packaging scaffolding before switching to the shared template.

## Definition of done
- All Dockerfiles reside under `docker/` with clearly documented usage.
- Compose builds succeed using the centralized paths.
- At least two services run on the shared template; specialized ones inherit from the base image where feasible.
- CI/Make targets cover the new build layout and pass.
