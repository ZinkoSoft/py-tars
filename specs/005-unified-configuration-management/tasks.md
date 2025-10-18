# Tasks: Unified Configuration Management System

**Input**: Design documents from `/specs/005-unified-configuration-management/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Tests NOT explicitly requested in spec - using TDD where validation/correctness is critical

**Organization**: Tasks grouped by user story to enable independent implementation and testing

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3...)
- All paths relative to repository root `/home/james/git/py-tars`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure for config-manager service and tars-core config library

- [X] T001 Create config-manager service directory structure at `apps/config-manager/` with src layout
- [X] T002 Create tars-core config module at `packages/tars-core/src/tars/config/`
- [X] T003 [P] Create pyproject.toml for config-manager service with FastAPI, aiosqlite, cryptography dependencies
- [X] T004 [P] Create Makefile for config-manager with standard targets (fmt, lint, test, check)
- [X] T005 [P] Create .env.example for config-manager with all required environment variables (keys, paths, etc.)
- [X] T006 [P] Create README.md for config-manager documenting MQTT topics, environment variables, development workflow
- [X] T007 [P] Create specialized Dockerfile at `docker/specialized/config-manager.Dockerfile`
- [X] T008 Update `ops/compose.yml` to add config-manager service with volume mounts and environment
- [X] T009 Update `ops/compose.npu.yml` to add config-manager service
- [X] T010 Create Litestream configuration at `ops/litestream.yml` for continuous backups

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core configuration library, database schema, and crypto infrastructure that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Core Models & Types

- [X] T011 [P] Create `packages/tars-core/src/tars/config/types.py` with enums (ConfigComplexity, ConfigType, ConfigSource)
- [X] T012 [P] Create `packages/tars-core/src/tars/config/models.py` with base Pydantic models (ConfigFieldMetadata, ServiceConfig, ConfigItem, SchemaVersion, ConfigEpochMetadata, LKGCache)
- [X] T013 [P] Create `packages/tars-core/src/tars/config/mqtt_models.py` with MQTT message models (ConfigUpdatePayload, ConfigHealthPayload)

### Cryptography Foundation

- [X] T014 Create `packages/tars-core/src/tars/config/crypto.py` with AES-256-GCM encryption functions (encrypt_secret, decrypt_secret)
- [X] T015 Add Ed25519 signature functions to crypto.py (generate_keypair, sign_message, verify_signature)
- [X] T016 Add HMAC-SHA256 functions to crypto.py (sign_cache, verify_cache)
- [X] T017 Add key generation and auto-rotation support to crypto.py (generate_master_key, detect_key_rotation)

### Database Layer

- [X] T018 Create `packages/tars-core/src/tars/config/database.py` with SQLite schema initialization (WAL mode, all tables from data-model.md)
- [X] T019 Add async CRUD operations to database.py (get_service_config, update_service_config, search_config_items)
- [X] T020 Add schema version tracking to database.py (compute_model_hash, validate_schema_version, increment_schema_version)
- [X] T021 Add config epoch management to database.py (create_epoch, validate_epoch, write_epoch_metadata)
- [X] T022 Add encrypted secrets management to database.py (store_encrypted_secret, retrieve_encrypted_secret, list_secrets_by_key_id)

### Cache & Fallback

- [X] T023 Create `packages/tars-core/src/tars/config/cache.py` with LKG cache management (write_lkg_cache, read_lkg_cache, verify_lkg_signature)
- [X] T024 Add atomic cache update to cache.py (ensure cache updates on every successful DB read within 100ms)

### Configuration Precedence & Library API

- [X] T025 Create `packages/tars-core/src/tars/config/precedence.py` with resolution logic (.env → database → defaults)
- [X] T026 Create `packages/tars-core/src/tars/config/library.py` with public API (ConfigLibrary class with get_config, subscribe_updates methods)
- [X] T027 Add MQTT subscription management to library.py (persistent subscription to system/config/<service>, signature verification)
- [X] T028 Add read-only fallback detection to library.py (auto-switch to LKG cache on DB failure)
- [X] T029 Add service initialization helper to library.py (load config at startup, register update callback)

### Service Configuration Models

- [X] T030 [P] Add service-specific Pydantic models to models.py (STTWorkerConfig, TTSWorkerConfig, RouterConfig, LLMWorkerConfig, MemoryWorkerConfig)
- [X] T031 [P] Add field metadata for all service configs (complexity levels, descriptions, help text, validation constraints)

### Testing Foundation

- [X] T032 [P] Create `packages/tars-core/tests/unit/config/test_crypto.py` with tests for encryption, signing, HMAC
- [X] T033 [P] Create `packages/tars-core/tests/unit/config/test_precedence.py` with tests for config resolution order
- [X] T034 [P] Create `packages/tars-core/tests/integration/config/test_database.py` with tests for SQLite operations
- [X] T035 [P] Create `packages/tars-core/tests/contract/config/test_mqtt_schemas.py` with tests validating MQTT message schemas

**Checkpoint**: Configuration library complete - services can now integrate; web UI can be built

---

## Phase 3: User Story 1 - View and Update Basic Service Settings (Priority: P1) 🎯 MVP

**Goal**: Enable administrators to view and update basic service configurations through web UI without editing files or restarting services

**Independent Test**: Load web UI config page, change TTS voice setting, save, restart service, verify new voice persists

### Config Manager Service Core (T036-T042)

- [X] T036 [P] [US1] Create `apps/config-manager/src/config_manager/__init__.py` (empty module)
- [X] T037 [P] [US1] Create `apps/config-manager/src/config_manager/config.py` with ConfigManagerConfig (db_path, mqtt_url, api_port, etc.)
- [X] T038 [P] [US1] Create `apps/config-manager/src/config_manager/service.py` with ConfigManagerService (initialize, health_check, shutdown)
- [X] T039 [P] [US1] Create `apps/config-manager/src/config_manager/__main__.py` with FastAPI entry point and lifespan management
- [ ] T040 [P] [US1] Add health check endpoint to api.py (GET /health → db_available, cache_available)
- [ ] T041 [P] [US1] Add database initialization on startup (create schema if missing, generate keys if absent)
- [ ] T042 [P] [US1] Add LKG cache initialization on startup (create empty cache if missing, load and verify if present)

### MQTT Integration (T043-T046)

- [X] T043 [P] [US1] Create `apps/config-manager/src/config_manager/mqtt.py` with MQTTPublisher class
- [X] T044 [P] [US1] Add publish_config_update method with Ed25519 signing
- [X] T045 [P] [US1] Add publish_health method for retained health status
- [X] T046 [P] [US1] Integrate MQTTPublisher into service.py (connect on startup, disconnect on shutdown)

### REST API Implementation (T047-T053)

- [X] T047 [P] [US1] Create `apps/config-manager/src/config_manager/api.py` with FastAPI router
- [X] T048 [P] [US1] Add GET /api/config/services endpoint (list all services)
- [X] T049 [P] [US1] Add GET /api/config/services/{service} endpoint (get config with version and epoch)
- [X] T050 [P] [US1] Add PUT /api/config/services/{service} endpoint (update config with optimistic locking)
- [X] T051 [P] [US1] Add MQTT notification on config update (publish to config/update after successful PUT)
- [X] T052 [P] [US1] Add LKG cache update on config change (atomic write after database update)
- [ ] T053 [P] [US1] Add error handling and logging to all API endpoints (structured logs with correlation IDs)

### MQTT Integration

- [ ] T043 Create `apps/config-manager/src/config_manager/mqtt_handler.py` with MQTT client setup and connection management
- [ ] T044 Add configuration update publishing to mqtt_handler.py (sign with Ed25519, publish to system/config/<service> with QoS 1 + retained)
- [ ] T045 Add health status publishing to mqtt_handler.py (publish to system/health/config-manager with retained flag)
- [ ] T046 Add signature verification for incoming MQTT messages to mqtt_handler.py (timestamp validation, replay attack prevention)

### REST API (Basic CRUD)

- [ ] T047 [P] [US1] Create `apps/config-manager/src/config_manager/api.py` with FastAPI router setup
- [ ] T048 [P] [US1] Add GET /api/config/services endpoint to list all services
- [ ] T049 [P] [US1] Add GET /api/config/services/{service} endpoint to retrieve service config
- [ ] T050 [US1] Add PUT /api/config/services/{service} endpoint to update service config (depends on T048, T049)
- [ ] T051 [US1] Add optimistic locking to PUT endpoint (version check, conflict detection)
- [ ] T052 [US1] Add config validation to PUT endpoint (Pydantic model validation before persist)
- [ ] T053 [US1] Add MQTT notification to PUT endpoint (publish signed update after successful save)

### Web UI - Service Tabs

- [X] T054 [P] [US1] Create `apps/ui-web/frontend/src/types/config.ts` with TypeScript types for all config models
- [X] T055 [P] [US1] Create `apps/ui-web/frontend/src/composables/useConfig.ts` with REST API client functions
- [X] T056 [P] [US1] Create `apps/ui-web/frontend/src/components/ConfigField.vue` for single field editor (string/int/float/bool/enum/path/secret types)
- [X] T057 [P] [US1] Create `apps/ui-web/frontend/src/components/ConfigEditor.vue` for displaying and editing service config
- [X] T058 [P] [US1] Create `apps/ui-web/frontend/src/components/ConfigTabs.vue` for service navigation tabs
- [X] T059 [P] [US1] Create `apps/ui-web/frontend/src/components/HealthIndicator.vue` for service health status display
- [X] T060 [US1] Create App.vue and main.ts entry point with Vite configuration
- [X] T061 [US1] Create package.json, tsconfig.json, and vite.config.ts for Vue 3 + TypeScript setup
- [X] T062 [US1] Create index.html and style.css for standalone config UI application

### Integration & Validation

- [ ] T063 [US1] Add client-side validation to ConfigField.vue (min/max ranges, regex patterns, enum constraints)
- [ ] T064 [US1] Add save button with validation error display to ConfigEditor.vue
- [ ] T065 [US1] Add success/error notifications to useConfig.ts for save operations
- [ ] T066 [US1] Add real-time health status updates to service tabs (poll or WebSocket)

### Service Integration (Example: STT Worker)

- [ ] T067 [US1] Update `apps/stt-worker/src/stt_worker/service.py` to use tars-core ConfigLibrary
- [ ] T068 [US1] Add config update callback to stt-worker service.py (handle runtime config changes)
- [ ] T069 [US1] Remove hardcoded config reading from stt-worker (rely on library for all config access)

### Testing & Documentation

- [ ] T070 [P] [US1] Create `apps/config-manager/tests/integration/test_crud_flow.py` for end-to-end config read/write
- [ ] T071 [P] [US1] Create `apps/config-manager/tests/contract/test_mqtt_publishing.py` for MQTT message format validation
- [ ] T072 [P] [US1] Add test scenario for quickstart.md validation (change TTS voice, verify persistence)

**Checkpoint**: User Story 1 complete - Basic config viewing and updating works end-to-end, services can read from DB and receive MQTT updates

---

## Phase 4: User Story 2 - Organize Settings by Simplicity Level (Priority: P1)

**Goal**: Provide simple/advanced mode toggle so casual users see only essential settings while power users see everything

**Independent Test**: Load UI in simple mode (10-20 settings visible), toggle to advanced mode (all settings visible), filter works correctly

### UI Enhancement for Complexity Filtering

- [ ] T073 [P] [US2] Add complexity level indicator to ConfigField.vue (badge showing "Simple" or "Advanced")
- [ ] T074 [P] [US2] Create `apps/ui-web/frontend/src/components/ComplexityToggle.vue` for simple/advanced mode switch
- [ ] T075 [US2] Add complexity filtering logic to ConfigEditor.vue (filter fields based on current mode)
- [ ] T076 [US2] Add complexity level to all service config models in tars-core (mark commonly-used settings as SIMPLE)
- [ ] T077 [US2] Update ConfigTabs.vue to show ComplexityToggle component in header
- [ ] T078 [US2] Persist user's mode preference in localStorage (remember simple/advanced choice across sessions)

### Backend Support

- [ ] T079 [US2] Add complexity metadata to config_items table sync in database.py
- [ ] T080 [US2] Update GET /api/config/services/{service} to include complexity metadata for each field

### Testing

- [ ] T081 [P] [US2] Add test for complexity filtering in `apps/ui-web/frontend/tests/unit/ConfigEditor.spec.ts`
- [ ] T082 [P] [US2] Add test for mode persistence in localStorage

**Checkpoint**: User Story 2 complete - Simple/advanced mode toggle works, settings properly categorized

---

## Phase 5: User Story 3 - Validate Configuration Before Saving (Priority: P2)

**Goal**: Prevent invalid configuration values from being saved and breaking services

**Independent Test**: Enter invalid values (negative numbers, invalid URLs, out-of-range), verify UI blocks save and shows clear errors

### Validation Enhancement

- [ ] T083 [P] [US3] Add inline validation to ConfigField.vue (real-time feedback as user types)
- [ ] T084 [P] [US3] Add validation error display to ConfigEditor.vue (highlight all invalid fields, prevent save)
- [ ] T085 [US3] Add server-side validation to PUT /api/config/services/{service} (reject invalid payloads with clear error messages)
- [ ] T086 [US3] Add validation rules to all service config Pydantic models (Field constraints: ge, le, regex, etc.)
- [ ] T087 [US3] Add custom validators for complex rules (file path existence, URL reachability, etc.)

### Access Control

- [ ] T088 Create `apps/config-manager/src/config_manager/auth.py` with role-based access control (config.read, config.write)
- [ ] T089 Add API token authentication to api.py (X-API-Token header validation)
- [ ] T090 Add role enforcement to PUT endpoint (require config.write role)
- [ ] T091 Add CSRF protection to api.py (token generation and validation for web UI requests)
- [ ] T092 Add access control audit logging to api.py (log unauthorized attempts)

### UI Access Control Integration

- [ ] T093 [US3] Add role detection to useConfig.ts (determine current user's role from API)
- [ ] T094 [US3] Disable save button in ConfigEditor.vue for users without config.write role
- [ ] T095 [US3] Show clear message when save is blocked due to insufficient permissions

### Testing

- [ ] T096 [P] [US3] Add validation tests to `packages/tars-core/tests/unit/config/test_models.py`
- [ ] T097 [P] [US3] Add access control tests to `apps/config-manager/tests/unit/test_auth.py`
- [ ] T098 [P] [US3] Add CSRF protection tests to `apps/config-manager/tests/integration/test_csrf.py`

**Checkpoint**: User Story 3 complete - Validation prevents errors, access control enforced

---

## Phase 6: User Story 4 - Search and Filter Configurations (Priority: P2)

**Goal**: Enable quick search across all configurations without browsing through categories

**Independent Test**: Type "whisper" in search box, verify only Whisper-related settings appear across all services

### Search UI

- [ ] T099 [P] [US4] Create `apps/ui-web/frontend/src/components/ConfigSearch.vue` with search input and filter controls
- [ ] T100 [P] [US4] Add search state management to useConfig.ts (query, filters, debouncing)
- [ ] T101 [US4] Integrate ConfigSearch into ConfigTabs.vue (show search bar above tabs)
- [ ] T102 [US4] Update ConfigEditor.vue to display search results (highlight matches, show service context)

### Search API

- [ ] T103 [US4] Add POST /api/config/search endpoint to api.py (query, service_filter, complexity_filter, type_filter)
- [ ] T104 [US4] Implement full-text search in database.py (query config_items table by service, key, description)
- [ ] T105 [US4] Add search result ranking (exact matches first, then partial matches)
- [ ] T106 [US4] Add search performance optimization (ensure indexes on config_items exist, target <300ms)

### Testing

- [ ] T107 [P] [US4] Add search tests to `apps/config-manager/tests/integration/test_search.py`
- [ ] T108 [P] [US4] Add search UI tests to `apps/ui-web/frontend/tests/unit/ConfigSearch.spec.ts`

**Checkpoint**: User Story 4 complete - Search finds configurations quickly across all services

---

## Phase 7: User Story 5 - Export and Import Configuration Profiles (Priority: P3)

**Goal**: Save and restore named configuration profiles for different use cases

**Independent Test**: Save current settings as "Profile A", change settings, save as "Profile B", switch back to "Profile A", verify original settings restored

### Profile Models

- [ ] T109 [P] [US5] Add ConfigProfile model to models.py (profile_name, config_snapshot, created_at, description)
- [ ] T110 [P] [US5] Add profile management to database.py (save_profile, list_profiles, load_profile, delete_profile)

### Profile API

- [ ] T111 [P] [US5] Add GET /api/config/profiles endpoint (list all saved profiles)
- [ ] T112 [P] [US5] Add POST /api/config/profiles endpoint (save current config as new profile)
- [ ] T113 [P] [US5] Add PUT /api/config/profiles/{profile_name}/activate endpoint (load profile and apply to services)
- [ ] T114 [P] [US5] Add DELETE /api/config/profiles/{profile_name} endpoint

### Profile UI

- [ ] T115 [P] [US5] Create `apps/ui-web/frontend/src/components/ProfileManager.vue` for profile CRUD
- [ ] T116 [US5] Add profile dropdown to ConfigTabs.vue (select active profile)
- [ ] T117 [US5] Add unsaved changes detection (warn before switching profiles or closing)
- [ ] T118 [US5] Add profile activation confirmation dialog

### Testing

- [ ] T119 [P] [US5] Add profile tests to `apps/config-manager/tests/integration/test_profiles.py`

**Checkpoint**: User Story 5 complete - Profile management enables quick configuration switching

---

## Phase 8: User Story 6 - View Configuration Change History (Priority: P3)

**Goal**: See audit trail of all configuration changes for troubleshooting and compliance

**Independent Test**: Make several config changes, view history, verify all changes logged with timestamps and previous/new values

### History Tracking

- [ ] T120 [US6] Add history recording to database.py (insert into config_history on every update)
- [ ] T121 [US6] Add history query functions to database.py (get_history_for_service, get_history_for_key, filter by date range)

### History API

- [ ] T122 [P] [US6] Add GET /api/config/history endpoint (query params: service, key, start_date, end_date)
- [ ] T123 [P] [US6] Add POST /api/config/history/restore endpoint (restore configuration to specific point in time)

### History UI

- [ ] T124 [P] [US6] Create `apps/ui-web/frontend/src/components/ConfigHistory.vue` for displaying change log
- [ ] T125 [P] [US6] Add history view to ConfigEditor.vue (show change history per field or for entire service)
- [ ] T126 [US6] Add date range filter to ConfigHistory.vue
- [ ] T127 [US6] Add restore confirmation dialog (warn about overwriting current config)

### Testing

- [ ] T128 [P] [US6] Add history tests to `apps/config-manager/tests/integration/test_history.py`

**Checkpoint**: User Story 6 complete - Full audit trail available for all configuration changes

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Production readiness, documentation, and optimization

### Backup & Recovery

- [ ] T129 [P] Create `apps/config-manager/src/config_manager/backup.py` with Litestream integration (health checks, restore operations)
- [ ] T130 [P] Add backup status to health endpoint (last_backup timestamp, litestream_status)
- [ ] T131 [P] Add manual rebuild endpoint POST /api/config/rebuild (requires REBUILD_TOKEN)
- [ ] T132 [P] Add rebuild tombstone file creation (rebuild.info with timestamp, reason)

### Error Handling & Resilience

- [ ] T133 Add read-only fallback mode detection to service.py (detect DB corruption, switch to LKG cache automatically)
- [ ] T134 Add background health checks to service.py (periodic DB integrity checks, auto-recovery when healthy)
- [ ] T135 Add graceful degradation to library.py (services continue with LKG config if DB unavailable at runtime)
- [ ] T136 Add split-brain prevention to library.py (reject configs with mismatched config_epoch)

### Security Hardening

- [ ] T137 [P] Add secret masking to all logging (ensure CONFIG_MASTER_KEY_BASE64 never logged)
- [ ] T138 [P] Add rate limiting to REST API endpoints (prevent brute-force attacks on tokens)
- [ ] T139 [P] Add secret reveal audit logging to api.py (log every time a secret is revealed in UI)
- [ ] T140 [P] Add encryption key rotation job to service.py (re-encrypt secrets when CONFIG_MASTER_KEY_ID changes)

### Documentation

- [ ] T141 [P] Update main README.md with configuration management overview
- [ ] T142 [P] Create `docs/CONFIGURATION_MANAGEMENT.md` with architecture diagrams and design decisions
- [ ] T143 [P] Update all service READMEs with instructions for using tars-core ConfigLibrary
- [ ] T144 [P] Add API documentation endpoint (Swagger/OpenAPI UI at /api/docs)

### Integration with Other Services

- [ ] T145 [P] Migrate stt-worker to use ConfigLibrary (example for other services)
- [ ] T146 [P] Migrate tts-worker to use ConfigLibrary
- [ ] T147 [P] Migrate router to use ConfigLibrary
- [ ] T148 [P] Migrate llm-worker to use ConfigLibrary
- [ ] T149 [P] Migrate memory-worker to use ConfigLibrary

### Testing & Validation

- [ ] T150 [P] Run full quickstart.md validation (follow setup guide, verify all steps work)
- [ ] T151 [P] Add end-to-end test for read-only fallback mode (simulate DB corruption, verify LKG cache fallback)
- [ ] T152 [P] Add end-to-end test for MQTT signature verification (simulate tampered messages, verify rejection)
- [ ] T153 [P] Add performance test for config reads (<50ms p95 target)
- [ ] T154 [P] Add load test for concurrent config updates (10+ services updating simultaneously)

### Code Quality

- [ ] T155 Run `make check` on config-manager (fmt + lint + test)
- [ ] T156 Run `make check` on tars-core config module
- [ ] T157 Code cleanup and refactoring (remove dead code, improve naming)
- [ ] T158 Add comprehensive docstrings to all public APIs (Google style)

**Checkpoint**: Feature complete, production-ready, fully documented

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational - MVP functionality
- **User Story 2 (Phase 4)**: Depends on Foundational - Can run parallel with US1 (different files)
- **User Story 3 (Phase 5)**: Depends on US1 (builds on REST API) - Sequential after US1
- **User Story 4 (Phase 6)**: Depends on Foundational - Can run parallel with US1/US2 (different files)
- **User Story 5 (Phase 7)**: Depends on US1 (needs core CRUD) - Sequential after US1
- **User Story 6 (Phase 8)**: Depends on US1 (needs core CRUD) - Can run parallel with US5 (different files)
- **Polish (Phase 9)**: Depends on desired user stories being complete

### Within Each Phase

- Tasks marked [P] can run in parallel (different files, no conflicts)
- Tasks without [P] must run sequentially (same file or direct dependencies)
- Foundational phase is CRITICAL PATH - prioritize completion

### Parallel Opportunities

**Setup (Phase 1)**: T003, T004, T005, T006, T007 can all run in parallel

**Foundational (Phase 2)**: T011, T012, T013 (models) can run together; T032, T033, T034, T035 (tests) can run together

**User Story 1 (Phase 3)**: T047, T048, T049 (REST endpoints) can run in parallel; T054, T055, T056, T057, T058, T059 (UI components) can run in parallel; T070, T071 (tests) can run in parallel

**Across Stories**: US2 and US4 can run in parallel with US1 (different files)

---

## Parallel Example: Foundational Phase

```bash
# Launch all model files together:
Task T011: "Create types.py with enums"
Task T012: "Create models.py with Pydantic models"
Task T013: "Create mqtt_models.py with MQTT schemas"

# Launch all test files together:
Task T032: "Create test_crypto.py"
Task T033: "Create test_precedence.py"
Task T034: "Create test_database.py"
Task T035: "Create test_mqtt_schemas.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 & 2 Only)

1. Complete Phase 1: Setup (10 tasks)
2. Complete Phase 2: Foundational (25 tasks) - CRITICAL
3. Complete Phase 3: User Story 1 (37 tasks) - Basic config management
4. Complete Phase 4: User Story 2 (10 tasks) - Simple/advanced toggle
5. **STOP and VALIDATE**: Test config viewing, editing, simplicity filtering
6. Deploy MVP - Administrators can manage configs without editing .env files

### Full Feature Delivery

Continue with:
- Phase 5: User Story 3 (validation + access control) - 15 tasks
- Phase 6: User Story 4 (search) - 10 tasks
- Phase 7: User Story 5 (profiles) - 11 tasks (optional)
- Phase 8: User Story 6 (history) - 9 tasks (optional)
- Phase 9: Polish (production hardening) - 30 tasks

### Parallel Team Strategy

With 3 developers after Foundational phase completes:

- **Developer A**: User Story 1 (core config management)
- **Developer B**: User Story 2 (simplicity levels) + User Story 4 (search)
- **Developer C**: Integration tests + service migrations

---

## Summary

**Total Tasks**: 158 tasks across 9 phases

**Task Breakdown by Phase**:
- Setup: 10 tasks
- Foundational: 25 tasks (CRITICAL PATH)
- User Story 1 (P1 - MVP): 37 tasks
- User Story 2 (P1 - MVP): 10 tasks
- User Story 3 (P2): 15 tasks
- User Story 4 (P2): 10 tasks
- User Story 5 (P3): 11 tasks
- User Story 6 (P3): 9 tasks
- Polish: 30 tasks

**Parallel Opportunities**: 65+ tasks marked [P] can run in parallel (different files)

**MVP Scope**: Phases 1-4 (82 tasks) deliver core configuration management with web UI and simplicity filtering

**Independent Testing**: Each user story has clear test criteria for independent validation

**Constitution Compliance**: 
- ✅ Event-driven (MQTT for config updates)
- ✅ Typed contracts (Pydantic v2 models for all payloads)
- ✅ Async-first (aiosqlite, asyncio.to_thread for crypto)
- ✅ Configuration via environment (all keys from .env)
- ✅ Observability (structured logs, health status, audit trail)
- ✅ Simplicity justified (complexity documented in plan.md)
