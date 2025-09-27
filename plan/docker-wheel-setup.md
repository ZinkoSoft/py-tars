# Docker Wheel-based Build Migration Plan

## Goal
Migrate all services to the shared `docker/app.Dockerfile` pattern and install project code as wheels, eliminating per-app Dockerfiles and manual `PYTHONPATH` tweaks.

## Prerequisites
- Current tests (`./run.tests.sh`) are green.
- Local virtual environment can install editable packages.
- Docker 24+ and Compose v2 available.

## Phase 1 – Package Restructuring
1. **Create shared core package**
   - Move `src/tars` into `packages/tars-core/src/tars`.
   - Add `packages/tars-core/pyproject.toml` with dependencies (e.g., `pydantic`, `orjson`).
   - Update imports so services reference `tars` from the new package.
2. **Define optional contracts package (if splitting)**
   - If contracts deserve isolation, create `packages/tars-contracts` mirroring current `tars.contracts` tree.
   - Adjust shared package dependencies accordingly.
3. **Convert each app to a package**
   - For every worker (router, stt, tts, llm, memory, ui-web, wake-activation):
     - Move sources into `apps/<name>/src/<package_name>/`.
     - Write `pyproject.toml` listing dependencies and `[project.scripts]` entry, e.g., `tars-router = "tars_router.app_main:main"`.
     - Update tests/imports if paths change.
4. **Update local dev tooling**
   - Replace manual `pip install -r requirements.txt` with `pip install -e packages/tars-core apps/router ...`.
   - Remove legacy `requirements.txt` files once dependencies live in `pyproject.toml`.

## Phase 2 – Docker Build Alignment
1. **Adopt reusable Dockerfile**
   - Keep `docker/app.Dockerfile` as the single build file.
   - Ensure it installs wheels for both shared packages and the targeted app.
2. **Refine build args**
   - For each service, capture required `apt` packages (e.g., ALSA/Pulse for STT/TTS) via build args or a thin service-specific stage.
   - Document any service needing extra runtime hooks (voice models, GPU libraries).
3. **Configure Compose**
   - Replace `docker-compose.yml` entries with services in `ops/compose.yaml` using the shared Dockerfile.
   - Mirror existing environment variables, devices, and volume mounts (Pulse audio sockets, model caches, etc.).
   - Add profiles or overrides as needed (e.g., keep `ui` under a `pygame` profile).
4. **Bake console scripts**
   - If `[project.scripts]` entries exist, update Compose `command:` to the script name (reduces `sh -c python -m ...`).

## Phase 3 – Validation & Cleanup
1. **Local smoke tests**
   - Rebuild stack: `docker compose -f ops/compose.yaml up --build`.
   - Verify services connect to MQTT and no module import errors occur.
2. **Functional checks**
   - Run core flows (wake phrase, LLM query, TTS playback) to confirm runtime parity.
   - Ensure model/voice mounts resolve as before.
3. **CI adjustments**
   - Update pipelines to build packages and wheels prior to tests if applicable.
   - Point CI compose usage to `ops/compose.yaml`.
4. **Doc updates**
   - Refresh README/DEV docs with new dev setup commands.
   - Note removal of per-app Dockerfiles and `requirements.txt`.
5. **Cleanup**
   - Delete deprecated Dockerfiles and compose configs after successful validation.
   - Remove old instructions referencing `PYTHONPATH` adjustments.

## Open Questions / Follow-ups
- Do we split shared code into multiple packages (`tars-core`, `tars-contracts`, `tars-runtime`)?
- Should ALSA/Pulse dependencies live in a shared base image instead of per-service installs?
- Any services needing GPU acceleration or platform-specific wheels (e.g., Piper voices)?

## Success Criteria
- All services build via `docker/app.Dockerfile` without ad-hoc COPY of `src`.
- Runtime logs show no missing module errors; MQTT loop is functional.
- `docker compose -f ops/compose.yaml up --build` matches old stack behavior.
- Local and CI documentation reflect the new workflow.
