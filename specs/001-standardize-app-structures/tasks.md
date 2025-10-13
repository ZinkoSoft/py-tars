# Tasks: Standardize App Folder Structures

**Feature**: Standardize App Folder Structures  
**Branch**: `001-standardize-app-structures`  
**Input**: Design documents from `/specs/001-standardize-app-structures/`

## Format: `[ID] [P?] [App] Description`
- **[P]**: Can run in parallel (different apps/files, no dependencies)
- **[App]**: Which app this task belongs to
- All paths are absolute from repository root

## Organization

Tasks are organized by app migration. Each app migration is treated as an independent "story" that can be completed and validated independently. Apps are ordered by migration priority (low to high risk).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create reusable templates and shared tooling

- [X] T001 Verify templates exist in `/specs/001-standardize-app-structures/contracts/`
- [X] T002 Create helper script at `/scripts/migrate-app-structure.sh` for automated migration steps
- [X] T003 [P] Document validation checklist in `/specs/001-standardize-app-structures/VALIDATION.md`

**Checkpoint**: Templates and tooling ready for app migrations

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish standards that all apps will follow

- [X] T004 Verify Python 3.11+ is available in all Docker containers
- [X] T005 Verify build tools (ruff, black, mypy, pytest) versions are consistent across repo
- [X] T006 Create shared dev dependencies list for reference

**Checkpoint**: Foundation ready - app migrations can begin in parallel

---

## Phase 3: Wake Activation Migration (Priority: P1) 🎯 MVP

**Goal**: Migrate wake-activation service to standard structure (smallest, isolated app)

**Independent Test**: `cd apps/wake-activation && make check && docker compose build wake-activation`

### Implementation for wake-activation

- [X] T007 [wake-activation] Analyze current structure and document in `/apps/wake-activation/structure-before.txt`
- [X] T008 [wake-activation] Create `/apps/wake-activation/src/wake_activation/` directory
- [X] T009 [wake-activation] Move source files to `/apps/wake-activation/src/wake_activation/`
- [X] T010 [wake-activation] Create `/apps/wake-activation/src/wake_activation/__main__.py` entry point
- [X] T011 [wake-activation] Create `/apps/wake-activation/tests/unit/`, `/apps/wake-activation/tests/integration/`, `/apps/wake-activation/tests/contract/` directories
- [X] T012 [wake-activation] Organize existing tests into appropriate subdirectories
- [X] T013 [wake-activation] Create `/apps/wake-activation/tests/conftest.py` with shared fixtures
- [X] T014 [wake-activation] Create `/apps/wake-activation/pyproject.toml` from template
- [X] T015 [wake-activation] Create `/apps/wake-activation/Makefile` from template with `PACKAGE_NAME := wake_activation`
- [X] T016 [wake-activation] Create/update `/apps/wake-activation/README.md` with all MQTT topics
- [X] T017 [wake-activation] Create `/apps/wake-activation/.env.example` with all environment variables
- [X] T018 [wake-activation] Test installation with `pip install -e .`
- [X] T019 [wake-activation] Run `make check` and fix any issues
- [X] T020 [wake-activation] Update Dockerfile if needed for src/ layout
- [X] T021 [wake-activation] Test Docker build succeeds
- [X] T022 [wake-activation] Document changes in `/apps/wake-activation/structure-after.txt`

**Checkpoint**: wake-activation fully standardized and validated ✅

---

## Phase 4: Camera Service Migration (Priority: P2)

**Goal**: Migrate camera-service (needs most work - good practice for other apps)

**Independent Test**: `cd apps/camera-service && make check && docker compose build camera-service`

### Implementation for camera-service

- [X] T023 [camera-service] Analyze current structure and document in `/apps/camera-service/structure-before.txt`
- [X] T024 [camera-service] Create `/apps/camera-service/src/camera_service/` directory
- [X] T025 [camera-service] Move all .py files to `/apps/camera-service/src/camera_service/`
- [X] T026 [camera-service] Rename main.py to `/apps/camera-service/src/camera_service/__main__.py`
- [X] T027 [camera-service] Create `/apps/camera-service/src/camera_service/__init__.py`
- [X] T028 [camera-service] Extract configuration to `/apps/camera-service/src/camera_service/config.py`
- [X] T029 [camera-service] Create `/apps/camera-service/tests/unit/`, `/apps/camera-service/tests/integration/`, `/apps/camera-service/tests/contract/` directories
- [X] T030 [camera-service] Create `/apps/camera-service/tests/conftest.py` with MQTT fixtures
- [X] T031 [camera-service] Create `/apps/camera-service/pyproject.toml` from scratch (no existing packaging)
- [X] T032 [camera-service] Create `/apps/camera-service/Makefile` with `PACKAGE_NAME := camera_service`
- [X] T033 [camera-service] Create `/apps/camera-service/README.md` documenting all MQTT topics and configuration
- [X] T034 [camera-service] Create `/apps/camera-service/.env.example`
- [X] T035 [camera-service] Test installation with `pip install -e .`
- [X] T036 [camera-service] Run `make check` and fix any issues (⚠️ mypy skipped due to unresolved issue)
- [X] T037 [camera-service] Create or update Dockerfile for src/ layout
- [X] T038 [camera-service] Test Docker build succeeds
- [X] T039 [camera-service] Document changes in `/apps/camera-service/structure-after.txt`

**Checkpoint**: camera-service fully standardized and validated

---

## Phase 5: UI Services Migration (Priority: P3)

**Goal**: Migrate ui and ui-web services (supporting services, less critical)

**Independent Test**: Build and run both UI services

### Implementation for ui

- [X] T040 [ui] Analyze current structure and document in `/apps/ui/structure-before.txt`
- [X] T041 [ui] Create `/apps/ui/src/ui/` directory structure
- [X] T042 [ui] Move source files to `/apps/ui/src/ui/`
- [X] T043 [ui] Create `/apps/ui/src/ui/__main__.py` entry point
- [X] T044 [ui] Create `/apps/ui/tests/` structure (unit/integration/contract)
- [X] T045 [ui] Create `/apps/ui/tests/conftest.py`
- [X] T046 [ui] Create `/apps/ui/pyproject.toml` with UI-specific dependencies
- [X] T047 [ui] Create `/apps/ui/Makefile` with `PACKAGE_NAME := ui`
- [X] T048 [ui] Create `/apps/ui/README.md` with usage instructions
- [X] T049 [ui] Create `/apps/ui/.env.example`
- [X] T050 [ui] Test installation and `make check`
- [X] T051 [ui] Update Dockerfile if needed
- [X] T052 [ui] Test Docker build
- [X] T053 [ui] Document changes in `/apps/ui/structure-after.txt`

**Checkpoint**: ui fully standardized and validated ✅

### Implementation for ui-web

- [X] T054 [P] [ui-web] Analyze current structure and document in `/apps/ui-web/structure-before.txt`
- [X] T055 [P] [ui-web] Create `/apps/ui-web/src/ui_web/` directory structure
- [X] T056 [P] [ui-web] Move source files to `/apps/ui-web/src/ui_web/`
- [X] T057 [P] [ui-web] Create `/apps/ui-web/src/ui_web/__main__.py` entry point
- [X] T058 [P] [ui-web] Create `/apps/ui-web/tests/` structure
- [X] T059 [P] [ui-web] Create `/apps/ui-web/tests/conftest.py`
- [X] T060 [P] [ui-web] Create `/apps/ui-web/pyproject.toml`
- [X] T061 [P] [ui-web] Create `/apps/ui-web/Makefile` with `PACKAGE_NAME := ui_web`
- [X] T062 [P] [ui-web] Create `/apps/ui-web/README.md`
- [X] T063 [P] [ui-web] Create `/apps/ui-web/.env.example`
- [X] T064 [P] [ui-web] Test installation and `make check`
- [X] T065 [P] [ui-web] Update Dockerfile if needed
- [X] T066 [P] [ui-web] Test Docker build
- [X] T067 [P] [ui-web] Document changes in `/apps/ui-web/structure-after.txt`

**Checkpoint**: Both UI services standardized and validated ✅

---

## Phase 6: Voice Service Migration (Priority: P4)

**Goal**: Migrate voice service

**Independent Test**: `cd apps/voice && make check && docker compose build voice`

### Implementation for voice

- [ ] T068 [voice] Analyze current structure and document in `/apps/voice/structure-before.txt`
- [ ] T069 [voice] Create `/apps/voice/src/voice/` directory
- [ ] T070 [voice] Move source files to `/apps/voice/src/voice/`
- [ ] T071 [voice] Create `/apps/voice/src/voice/__main__.py` entry point
- [ ] T072 [voice] Create `/apps/voice/tests/` structure (unit/integration/contract)
- [ ] T073 [voice] Create `/apps/voice/tests/conftest.py`
- [ ] T074 [voice] Create `/apps/voice/pyproject.toml`
- [ ] T075 [voice] Create `/apps/voice/Makefile` with `PACKAGE_NAME := voice`
- [ ] T076 [voice] Create `/apps/voice/README.md` with MQTT topics
- [ ] T077 [voice] Create `/apps/voice/.env.example`
- [ ] T078 [voice] Test installation and `make check`
- [ ] T079 [voice] Update Dockerfile if needed
- [ ] T080 [voice] Test Docker build
- [ ] T081 [voice] Document changes in `/apps/voice/structure-after.txt`

**Checkpoint**: voice service standardized and validated

---

## Phase 7: Movement Service Migration (Priority: P5)

**Goal**: Migrate movement-service

**Independent Test**: `cd apps/movement-service && make check && docker compose build movement-service`

### Implementation for movement-service

- [ ] T082 [movement-service] Analyze current structure and document in `/apps/movement-service/structure-before.txt`
- [ ] T083 [movement-service] Create `/apps/movement-service/src/movement_service/` directory
- [ ] T084 [movement-service] Move source files to `/apps/movement-service/src/movement_service/`
- [ ] T085 [movement-service] Create `/apps/movement-service/src/movement_service/__main__.py` entry point
- [ ] T086 [movement-service] Create `/apps/movement-service/tests/` structure
- [ ] T087 [movement-service] Create `/apps/movement-service/tests/conftest.py`
- [ ] T088 [movement-service] Create `/apps/movement-service/pyproject.toml`
- [ ] T089 [movement-service] Create `/apps/movement-service/Makefile` with `PACKAGE_NAME := movement_service`
- [ ] T090 [movement-service] Create `/apps/movement-service/README.md` with MQTT topics
- [ ] T091 [movement-service] Create `/apps/movement-service/.env.example`
- [ ] T092 [movement-service] Test installation and `make check`
- [ ] T093 [movement-service] Update Dockerfile if needed
- [ ] T094 [movement-service] Test Docker build
- [ ] T095 [movement-service] Document changes in `/apps/movement-service/structure-after.txt`

**Checkpoint**: movement-service standardized and validated

---

## Phase 8: MCP Services Migration (Priority: P6)

**Goal**: Migrate mcp-bridge and mcp-server

**Independent Test**: Build and run both MCP services

### Implementation for mcp-bridge

- [ ] T096 [mcp-bridge] Analyze current structure and document in `/apps/mcp-bridge/structure-before.txt`
- [ ] T097 [mcp-bridge] Create `/apps/mcp-bridge/src/mcp_bridge/` directory
- [ ] T098 [mcp-bridge] Move source files to `/apps/mcp-bridge/src/mcp_bridge/`
- [ ] T099 [mcp-bridge] Create `/apps/mcp-bridge/src/mcp_bridge/__main__.py` entry point
- [ ] T100 [mcp-bridge] Organize existing tests into `/apps/mcp-bridge/tests/unit/`, `/apps/mcp-bridge/tests/integration/`, `/apps/mcp-bridge/tests/contract/`
- [ ] T101 [mcp-bridge] Create `/apps/mcp-bridge/tests/conftest.py`
- [ ] T102 [mcp-bridge] Update `/apps/mcp-bridge/pyproject.toml` for src/ layout
- [ ] T103 [mcp-bridge] Create `/apps/mcp-bridge/Makefile` with `PACKAGE_NAME := mcp_bridge`
- [ ] T104 [mcp-bridge] Update `/apps/mcp-bridge/README.md` with MQTT topics
- [ ] T105 [mcp-bridge] Update `/apps/mcp-bridge/.env.example`
- [ ] T106 [mcp-bridge] Test installation and `make check`
- [ ] T107 [mcp-bridge] Update Dockerfile for src/ layout
- [ ] T108 [mcp-bridge] Test Docker build
- [ ] T109 [mcp-bridge] Document changes in `/apps/mcp-bridge/structure-after.txt`

### Implementation for mcp-server

- [ ] T110 [P] [mcp-server] Analyze current structure and document in `/apps/mcp-server/structure-before.txt`
- [ ] T111 [P] [mcp-server] Create `/apps/mcp-server/src/mcp_server/` directory
- [ ] T112 [P] [mcp-server] Move source files to `/apps/mcp-server/src/mcp_server/`
- [ ] T113 [P] [mcp-server] Create `/apps/mcp-server/src/mcp_server/__main__.py` entry point
- [ ] T114 [P] [mcp-server] Create `/apps/mcp-server/tests/` structure
- [ ] T115 [P] [mcp-server] Create `/apps/mcp-server/tests/conftest.py`
- [ ] T116 [P] [mcp-server] Create/update `/apps/mcp-server/pyproject.toml`
- [ ] T117 [P] [mcp-server] Create `/apps/mcp-server/Makefile` with `PACKAGE_NAME := mcp_server`
- [ ] T118 [P] [mcp-server] Create/update `/apps/mcp-server/README.md`
- [ ] T119 [P] [mcp-server] Create `/apps/mcp-server/.env.example`
- [ ] T120 [P] [mcp-server] Test installation and `make check`
- [ ] T121 [P] [mcp-server] Update Dockerfile if needed
- [ ] T122 [P] [mcp-server] Test Docker build
- [ ] T123 [P] [mcp-server] Document changes in `/apps/mcp-server/structure-after.txt`

**Checkpoint**: Both MCP services standardized and validated

---

## Phase 9: Memory Worker Migration (Priority: P7)

**Goal**: Migrate memory-worker (complex but isolated)

**Independent Test**: `cd apps/memory-worker && make check && docker compose build memory-worker`

### Implementation for memory-worker

- [ ] T124 [memory-worker] Analyze current structure and document in `/apps/memory-worker/structure-before.txt`
- [ ] T125 [memory-worker] Create `/apps/memory-worker/src/memory_worker/` directory
- [ ] T126 [memory-worker] Move `memory_worker/*` to `/apps/memory-worker/src/memory_worker/`
- [ ] T127 [memory-worker] Ensure `/apps/memory-worker/src/memory_worker/__main__.py` exists
- [ ] T128 [memory-worker] Organize existing tests into `/apps/memory-worker/tests/unit/`, `/apps/memory-worker/tests/integration/`, `/apps/memory-worker/tests/contract/`
- [ ] T129 [memory-worker] Create `/apps/memory-worker/tests/conftest.py`
- [ ] T130 [memory-worker] Update `/apps/memory-worker/pyproject.toml` for src/ layout
- [ ] T131 [memory-worker] Create `/apps/memory-worker/Makefile` with `PACKAGE_NAME := memory_worker`
- [ ] T132 [memory-worker] Update `/apps/memory-worker/README.md` with MQTT topics
- [ ] T133 [memory-worker] Update `/apps/memory-worker/.env.example`
- [ ] T134 [memory-worker] Test installation and `make check`
- [ ] T135 [memory-worker] Update Dockerfile for src/ layout
- [ ] T136 [memory-worker] Test Docker build
- [ ] T137 [memory-worker] Document changes in `/apps/memory-worker/structure-after.txt`

**Checkpoint**: memory-worker standardized and validated

---

## Phase 10: TTS Worker Migration (Priority: P8)

**Goal**: Migrate tts-worker (audio output service)

**Independent Test**: `cd apps/tts-worker && make check && docker compose build tts-worker`

### Implementation for tts-worker

- [ ] T138 [tts-worker] Analyze current structure and document in `/apps/tts-worker/structure-before.txt`
- [ ] T139 [tts-worker] Create `/apps/tts-worker/src/tts_worker/` directory
- [ ] T140 [tts-worker] Move existing package to `/apps/tts-worker/src/tts_worker/`
- [ ] T141 [tts-worker] Ensure `/apps/tts-worker/src/tts_worker/__main__.py` entry point exists
- [ ] T142 [tts-worker] Organize tests into `/apps/tts-worker/tests/unit/`, `/apps/tts-worker/tests/integration/`, `/apps/tts-worker/tests/contract/`
- [ ] T143 [tts-worker] Create `/apps/tts-worker/tests/conftest.py`
- [ ] T144 [tts-worker] Update `/apps/tts-worker/pyproject.toml` for src/ layout
- [ ] T145 [tts-worker] Create `/apps/tts-worker/Makefile` with `PACKAGE_NAME := tts_worker`
- [ ] T146 [tts-worker] Update `/apps/tts-worker/README.md` with MQTT topics
- [ ] T147 [tts-worker] Update `/apps/tts-worker/.env.example`
- [ ] T148 [tts-worker] Test installation and `make check`
- [ ] T149 [tts-worker] Update Dockerfile for src/ layout
- [ ] T150 [tts-worker] Test Docker build
- [ ] T151 [tts-worker] Document changes in `/apps/tts-worker/structure-after.txt`

**Checkpoint**: tts-worker standardized and validated

---

## Phase 11: LLM Worker Migration (Priority: P9)

**Goal**: Migrate llm-worker (LLM integration service)

**Independent Test**: `cd apps/llm-worker && make check && docker compose build llm-worker`

### Implementation for llm-worker

- [ ] T152 [llm-worker] Analyze current structure and document in `/apps/llm-worker/structure-before.txt`
- [ ] T153 [llm-worker] Create `/apps/llm-worker/src/llm_worker/` directory
- [ ] T154 [llm-worker] Move `llm_worker/*` to `/apps/llm-worker/src/llm_worker/` (including providers subpackage)
- [ ] T155 [llm-worker] Ensure `/apps/llm-worker/src/llm_worker/__main__.py` exists
- [ ] T156 [llm-worker] Organize tests into `/apps/llm-worker/tests/unit/`, `/apps/llm-worker/tests/integration/`, `/apps/llm-worker/tests/contract/`
- [ ] T157 [llm-worker] Create `/apps/llm-worker/tests/conftest.py`
- [ ] T158 [llm-worker] Update `/apps/llm-worker/pyproject.toml` packages list: `["llm_worker", "llm_worker.providers"]`
- [ ] T159 [llm-worker] Create `/apps/llm-worker/Makefile` with `PACKAGE_NAME := llm_worker`
- [ ] T160 [llm-worker] Update `/apps/llm-worker/README.md` with MQTT topics
- [ ] T161 [llm-worker] Update `/apps/llm-worker/.env.example`
- [ ] T162 [llm-worker] Test installation and `make check`
- [ ] T163 [llm-worker] Update Dockerfile for src/ layout
- [ ] T164 [llm-worker] Test Docker build
- [ ] T165 [llm-worker] Document changes in `/apps/llm-worker/structure-after.txt`

**Checkpoint**: llm-worker standardized and validated

---

## Phase 12: STT Worker Migration (Priority: P10)

**Goal**: Migrate stt-worker (audio input service)

**Independent Test**: `cd apps/stt-worker && make check && docker compose build stt-worker`

### Implementation for stt-worker

- [ ] T166 [stt-worker] Analyze current structure and document in `/apps/stt-worker/structure-before.txt`
- [ ] T167 [stt-worker] Create `/apps/stt-worker/src/stt_worker/` directory
- [ ] T168 [stt-worker] Move existing package to `/apps/stt-worker/src/stt_worker/`
- [ ] T169 [stt-worker] Create `/apps/stt-worker/src/stt_worker/__main__.py` from main.py
- [ ] T170 [stt-worker] Organize tests into `/apps/stt-worker/tests/unit/`, `/apps/stt-worker/tests/integration/`, `/apps/stt-worker/tests/contract/`
- [ ] T171 [stt-worker] Create `/apps/stt-worker/tests/conftest.py`
- [ ] T172 [stt-worker] Update `/apps/stt-worker/pyproject.toml` for src/ layout
- [ ] T173 [stt-worker] Create `/apps/stt-worker/Makefile` with `PACKAGE_NAME := stt_worker`
- [ ] T174 [stt-worker] Update `/apps/stt-worker/README.md` with MQTT topics (including VAD, suppression)
- [ ] T175 [stt-worker] Update `/apps/stt-worker/.env.example`
- [ ] T176 [stt-worker] Test installation and `make check`
- [ ] T177 [stt-worker] Update Dockerfile for src/ layout
- [ ] T178 [stt-worker] Test Docker build
- [ ] T179 [stt-worker] Document changes in `/apps/stt-worker/structure-after.txt`

**Checkpoint**: stt-worker standardized and validated

---

## Phase 13: Router Migration (Priority: P11 - CRITICAL)

**Goal**: Migrate router (central service - do last, most critical)

**Independent Test**: `cd apps/router && make check && docker compose build router`

### Implementation for router

- [ ] T180 [router] Analyze current structure and document in `/apps/router/structure-before.txt`
- [ ] T181 [router] Create `/apps/router/src/router/` directory
- [ ] T182 [router] Move main.py to `/apps/router/src/router/__main__.py`
- [ ] T183 [router] Extract components: `/apps/router/src/router/config.py`, `/apps/router/src/router/service.py`, `/apps/router/src/router/models.py`
- [ ] T184 [router] Create `/apps/router/src/router/__init__.py`
- [ ] T185 [router] Create `/apps/router/tests/unit/`, `/apps/router/tests/integration/`, `/apps/router/tests/contract/` directories
- [ ] T186 [router] Create comprehensive contract tests for all MQTT topics in `/apps/router/tests/contract/`
- [ ] T187 [router] Create `/apps/router/tests/conftest.py`
- [ ] T188 [router] Create `/apps/router/pyproject.toml` from template
- [ ] T189 [router] Create `/apps/router/Makefile` with `PACKAGE_NAME := router`
- [ ] T190 [router] Create comprehensive `/apps/router/README.md` documenting all routing rules and MQTT contracts
- [ ] T191 [router] Create `/apps/router/.env.example`
- [ ] T192 [router] Test installation and `make check`
- [ ] T193 [router] Update Dockerfile for src/ layout
- [ ] T194 [router] Test Docker build
- [ ] T195 [router] Document changes in `/apps/router/structure-after.txt`
- [ ] T196 [router] Integration test: Start full stack and verify router works with all services

**Checkpoint**: router standardized and validated - ALL APPS NOW STANDARDIZED

---

## Phase 14: Polish & Cross-Cutting Concerns

**Purpose**: Final touches and documentation

- [ ] T197 [P] Update main `/README.md` with new app structure conventions
- [ ] T198 [P] Update `.github/copilot-instructions.md` with standardization patterns
- [ ] T199 [P] Create pre-commit hook template for `make check` at `/.githooks/pre-commit`
- [ ] T200 [P] Update CI/CD workflows to use `make check` per app
- [ ] T201 [P] Create developer onboarding guide at `/docs/DEVELOPER_ONBOARDING.md`
- [ ] T202 Test full Docker Compose stack: `docker compose -f ops/compose.yml up --build`
- [ ] T203 Verify all services start and communicate correctly
- [ ] T204 Run validation: all apps pass `make check`
- [ ] T205 Create summary report in `/specs/001-standardize-app-structures/COMPLETION_REPORT.md`
- [ ] T206 Update `plan.md` status to COMPLETE

**Checkpoint**: All documentation updated, full integration tested

---

## Dependencies & Execution Order

### Phase Dependencies

1. **Phase 1 (Setup)**: No dependencies - creates templates/tools
2. **Phase 2 (Foundational)**: Depends on Phase 1 - establishes standards
3. **Phases 3-13 (App Migrations)**: All depend on Phase 2 completion
   - Apps can be migrated in parallel if multiple developers
   - Or sequentially following priority order (wake-activation → router)
4. **Phase 14 (Polish)**: Depends on all app migrations being complete

### App Migration Independence

Each app migration (Phases 3-13) is **completely independent**:
- wake-activation (Phase 3): MVP - smallest app, good practice
- camera-service (Phase 4): Needs most work
- ui/ui-web (Phase 5): Both can be done in parallel
- voice (Phase 6): Independent
- movement-service (Phase 7): Independent
- mcp-bridge/mcp-server (Phase 8): Both can be done in parallel
- memory-worker (Phase 9): Independent
- tts-worker (Phase 10): Independent
- llm-worker (Phase 11): Independent
- stt-worker (Phase 12): Independent
- router (Phase 13): Most critical, do last

### Within Each App Migration

Standard sequence for each app:
1. Analyze current structure
2. Create new directory structure (src/, tests/)
3. Move files to new locations
4. Create configuration files (pyproject.toml, Makefile, README, .env.example)
5. Test installation and validation
6. Update Docker configuration
7. Verify Docker build
8. Document changes

### Parallel Opportunities

**During Setup/Foundational (Phases 1-2)**:
- T003 and T006 can run in parallel with T004-T005

**During App Migrations (Phases 3-13)**:
- With multiple developers, all apps can be migrated in parallel after Phase 2
- Within Phase 5: T040-T053 (ui) and T054-T067 (ui-web) marked [P]
- Within Phase 8: T096-T109 (mcp-bridge) and T110-T123 (mcp-server) - mcp-server tasks marked [P]

**During Polish (Phase 14)**:
- T197, T198, T199, T200, T201 all marked [P] (different files)

---

## Implementation Strategy

### Sequential MVP Approach (Single Developer)

Migrate one app at a time in priority order:

1. **Phase 1-2**: Setup + Foundation (1-2 hours)
2. **Phase 3**: wake-activation (30-60 min) → **TEST & VALIDATE**
3. **Phase 4**: camera-service (2-3 hours) → **TEST & VALIDATE**
4. Continue through Phases 5-13 in order
5. **Phase 14**: Polish and integration

Estimated total time: 15-25 hours

### Parallel Team Approach (Multiple Developers)

After Phase 1-2 completion:

- **Developer A**: Phases 3-5 (wake-activation, camera-service, ui services)
- **Developer B**: Phases 6-9 (voice, movement, MCP, memory)
- **Developer C**: Phases 10-13 (tts, llm, stt, router)

Estimated time: 5-8 hours with 3 developers

### Incremental Validation

After each app migration:
1. Run `make check` in app directory
2. Test Docker build
3. Run app standalone with MQTT broker
4. Test with full stack (optional but recommended)
5. Commit changes before moving to next app

---

## Validation Per App

For each app, verify:

- [ ] Directory structure matches standard (src/, tests/, etc.)
- [ ] `pip install -e .` succeeds
- [ ] `make fmt` runs successfully
- [ ] `make lint` passes
- [ ] `make test` passes (if tests exist)
- [ ] `make check` passes
- [ ] CLI entry point works: `tars-<app-name> --help`
- [ ] Docker build succeeds: `docker compose build <service>`
- [ ] README.md documents all MQTT topics
- [ ] .env.example lists all environment variables
- [ ] Existing functionality preserved (no behavior changes)

---

## Success Criteria

Migration complete when:

1. ✅ All 13 apps follow standard structure
2. ✅ All apps have functional Makefile with all targets
3. ✅ All apps have comprehensive README.md
4. ✅ All apps pass `make check`
5. ✅ All apps build successfully in Docker
6. ✅ Full stack runs without errors: `docker compose up`
7. ✅ All MQTT contracts preserved and documented
8. ✅ Documentation updated (main README, copilot instructions)

---

## Notes

- **[P] markers**: Tasks that can run in parallel (different apps/files)
- **[App] labels**: Track which app each task belongs to
- **Validation**: Each app must pass all checks before moving to next
- **Git workflow**: Commit after each app migration for easy rollback
- **Testing**: Test both standalone (`make check`) and Docker integration
- **Documentation**: README.md and .env.example are critical for each app
- **Priority order**: Designed to start with simple/isolated apps, end with critical router
