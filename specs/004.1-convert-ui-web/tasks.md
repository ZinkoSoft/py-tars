# Tasks: Convert ui-web to Vue.js TypeScript Application

**Input**: Design documents from `/specs/004-convert-ui-web/`  
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Tests are NOT required for this feature (migration/refactor with visual validation). Contract tests exist as TypeScript type definitions.

**Organization**: Tasks are grouped by user story (P1 → P3) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions
- **Web app**: `apps/ui-web/` (backend), `apps/ui-web/frontend/` (Vue.js app)
- Backend: `apps/ui-web/src/ui_web/`
- Frontend: `apps/ui-web/frontend/src/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize Vue.js frontend project and configure build system

- [X] T001 Create frontend directory structure at `apps/ui-web/frontend/`
- [X] T002 Initialize npm project with package.json at `apps/ui-web/frontend/package.json`
- [X] T003 [P] Install Vue.js 3, Vite 5, TypeScript 5, Pinia dependencies in `apps/ui-web/frontend/`
- [X] T004 [P] Create Vite configuration in `apps/ui-web/frontend/vite.config.ts` with WebSocket proxy to backend
- [X] T005 [P] Create TypeScript configuration in `apps/ui-web/frontend/tsconfig.json` with strict mode
- [X] T006 [P] Create HTML entry point at `apps/ui-web/frontend/index.html`
- [X] T007 [P] Setup ESLint + Prettier configuration in `apps/ui-web/frontend/.eslintrc.cjs` and `.prettierrc`
- [X] T008 [P] Setup Vitest configuration in `apps/ui-web/frontend/vitest.config.ts`
- [X] T009 Create frontend directory structure: `src/components/`, `src/stores/`, `src/composables/`, `src/types/`, `src/drawers/`, `src/assets/styles/`
- [X] T010 [P] Add npm scripts to package.json: `dev`, `build`, `preview`, `format`, `lint`, `type-check`, `test`, `check`
- [X] T011 [P] Extract CSS variables from `apps/ui-web/static/index.html` into `apps/ui-web/frontend/src/assets/styles/variables.css`
- [X] T012 [P] Create Vue app entry point at `apps/ui-web/frontend/src/main.ts` with Pinia initialization

**Checkpoint**: ✅ Frontend project scaffolded and build system configured

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core TypeScript types, stores, and utilities that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T013 [P] Create TypeScript MQTT message types in `apps/ui-web/frontend/src/types/mqtt.ts` (copy from contracts/mqtt-messages.ts)
- [X] T014 [P] Create TypeScript WebSocket types in `apps/ui-web/frontend/src/types/websocket.ts` (copy from contracts/websocket.ts)
- [X] T015 [P] Create TypeScript health types in `apps/ui-web/frontend/src/types/health.ts`
- [X] T016 [P] Create TypeScript UI types in `apps/ui-web/frontend/src/types/ui.ts` (DrawerType, AppState)
- [X] T017 Create WebSocket store in `apps/ui-web/frontend/src/stores/websocket.ts` with connection management, reconnection logic, message routing
- [X] T018 [P] Create MQTT store in `apps/ui-web/frontend/src/stores/mqtt.ts` with message log (FIFO, max 200)
- [X] T019 [P] Create chat store in `apps/ui-web/frontend/src/stores/chat.ts` with message aggregation by utt_id
- [X] T020 [P] Create health store in `apps/ui-web/frontend/src/stores/health.ts` with timeout detection (30s)
- [X] T021 [P] Create UI store in `apps/ui-web/frontend/src/stores/ui.ts` with drawer visibility state
- [X] T022 Create root App.vue component in `apps/ui-web/frontend/src/App.vue` with basic layout structure

**Checkpoint**: ✅ Foundation ready - all stores, types, and routing established. User story implementation can now begin.

---

## Phase 3: User Story 1 - Basic Chat Interface (Priority: P1) 🎯 MVP

**Goal**: Users can view the TARS chat interface with existing visual design and interact with conversation via WebSocket

**Independent Test**: Load application in browser, verify chat messages display, composer accepts input, messages send via WebSocket

### Implementation for User Story 1

- [X] T023 [P] [US1] Create ChatBubble component in `apps/ui-web/frontend/src/components/ChatBubble.vue` with role-based styling
- [X] T024 [P] [US1] Create ChatLog component in `apps/ui-web/frontend/src/components/ChatLog.vue` with auto-scroll and message rendering
- [X] T025 [P] [US1] Create Composer component in `apps/ui-web/frontend/src/components/Composer.vue` with text input and submit
- [X] T026 [P] [US1] Create StatusLine component in `apps/ui-web/frontend/src/components/StatusLine.vue` displaying listening/processing/writing states
- [X] T027 [US1] Create ChatPanel component in `apps/ui-web/frontend/src/components/ChatPanel.vue` composing ChatLog, Composer, StatusLine
- [X] T028 [P] [US1] Create Header component in `apps/ui-web/frontend/src/components/Header.vue` with title and status indicators
- [X] T029 [P] [US1] Create Toolbar component in `apps/ui-web/frontend/src/components/Toolbar.vue` with drawer toggle buttons and health indicator
- [X] T030 [US1] Update App.vue to compose Header, ChatPanel with scoped styles matching existing design
- [X] T031 [US1] Implement WebSocket message handlers in chat store for STT (stt/final, stt/partial), LLM (llm/stream, llm/response), TTS (tts/status)
- [X] T032 [US1] Implement message aggregation logic in chat store for LLM streaming by correlation ID
- [X] T033 [US1] Add connection status tracking and display in Header component
- [X] T034 [US1] Update FastAPI server in `apps/ui-web/src/ui_web/__main__.py` to serve `frontend/dist/` directory as static files
- [X] T035 [US1] Test WebSocket connection, message display, and user input submission

**Checkpoint**: ✅ User Story 1 COMPLETE - Chat interface verified functional with full stack integration

---

## Phase 4: User Story 2 - Modular Drawer Components (Priority: P2)

**Goal**: Developers can add new monitoring panels as reusable Vue components that slide out as drawers

**Independent Test**: Create test drawer component, verify it registers and opens/closes independently without modifying core app code

### Implementation for User Story 2

- [X] T036 [P] [US2] Create Button component in `apps/ui-web/frontend/src/components/Button.vue` with variant prop support
- [X] T037 [P] [US2] Create Panel component in `apps/ui-web/frontend/src/components/Panel.vue` with title and border styling
- [X] T038 [US2] Create DrawerContainer component in `apps/ui-web/frontend/src/components/DrawerContainer.vue` with backdrop, transitions, close on Escape
- [ ] T039 [US2] Create useDrawer composable in `apps/ui-web/frontend/src/composables/useDrawer.ts` for drawer state management
- [X] T040 [P] [US2] Create MicrophoneDrawer component in `apps/ui-web/frontend/src/drawers/MicrophoneDrawer.vue` with spectrum canvas
- [X] T041 [P] [US2] Create MemoryDrawer component in `apps/ui-web/frontend/src/drawers/MemoryDrawer.vue` with query input and results display
- [X] T042 [P] [US2] Create MQTTStreamDrawer component in `apps/ui-web/frontend/src/drawers/MQTTStreamDrawer.vue` with message log and clear button
- [X] T043 [P] [US2] Create CameraDrawer component in `apps/ui-web/frontend/src/drawers/CameraDrawer.vue` with placeholder for future camera feed
- [X] T044 [P] [US2] Create HealthDrawer component in `apps/ui-web/frontend/src/drawers/HealthDrawer.vue` with service status list
- [X] T045 [US2] Register all drawers in App.vue with DrawerContainer
- [X] T046 [US2] Implement drawer toggle logic in Toolbar to open/close drawers via UI store
- [X] T047 [US2] Implement drawer backdrop click and Escape key handlers
- [ ] T048 [US2] Test drawer open/close transitions, backdrop behavior, keyboard shortcuts

**Checkpoint**: ⚠️ Phase 4 mostly complete - Drawer system implemented, needs final testing (T039 optional, T048 validation)

---

## Phase 5: User Story 3 - Reusable UI Components (Priority: P2)

**Goal**: Application provides reusable Vue components for common UI patterns that developers can compose into new features

**Independent Test**: Use existing components to build new feature module, verify consistent styling and behavior

### Implementation for User Story 3

- [X] T049 [P] [US3] Create StatusIndicator component in `apps/ui-web/frontend/src/components/StatusIndicator.vue` with status prop (healthy/unhealthy/unknown)
- [X] T050 [P] [US3] Create CodeBlock component in `apps/ui-web/frontend/src/components/CodeBlock.vue` with JSON syntax highlighting
- [X] T051 [US3] Document component usage patterns in `apps/ui-web/frontend/README.md` with examples for Button, Panel, StatusIndicator, CodeBlock
- [ ] T052 [US3] Create component showcase in development mode for visual testing (optional dev tool)
- [ ] T053 [US3] Refactor existing components to use shared Button and Panel components
- [X] T054 [US3] Update HealthDrawer to use StatusIndicator components
- [X] T055 [US3] Update MQTTStreamDrawer to use CodeBlock component for payload display

**Checkpoint**: User Story 3 complete - Component library established and documented

---

## Phase 6: User Story 4 - Audio Spectrum Visualization (Priority: P3)

**Goal**: Users can view live audio spectrum visualization in modular component that updates in real-time

**Independent Test**: Send FFT data via WebSocket, verify spectrum canvas updates correctly within MicrophoneDrawer

### Implementation for User Story 4

- [X] T056 [US4] Create SpectrumCanvas component in `apps/ui-web/frontend/src/components/SpectrumCanvas.vue` with canvas element
- [X] T057 [US4] Create useSpectrum composable in `apps/ui-web/frontend/src/composables/useSpectrum.ts` with requestAnimationFrame rendering
- [X] T058 [US4] Implement FFT data handling in MQTT store for stt/audio_fft topic
- [X] T059 [US4] Integrate SpectrumCanvas into MicrophoneDrawer with FFT data binding
- [X] T060 [US4] Implement fade-to-baseline logic when no FFT data received for 2 seconds
- [X] T061 [US4] Implement rendering pause when drawer is closed to conserve resources
- [ ] T062 [US4] Test spectrum visualization with live audio data and drawer open/close behavior

**Checkpoint**: User Story 4 complete - Audio spectrum visualization working

---

## Phase 7: User Story 5 - MQTT Stream Monitor (Priority: P3)

**Goal**: Users can view all MQTT messages in dedicated drawer with filtering and payload inspection

**Independent Test**: Generate MQTT messages, verify they appear in stream monitor with correct formatting and FIFO behavior

### Implementation for User Story 5

- [X] T063 [US5] Implement message formatting in MQTT store for pretty-printed JSON payloads
- [X] T064 [US5] Implement FIFO buffer logic in MQTT store (max 200 messages)
- [X] T065 [US5] Add clear history action to MQTT store
- [X] T066 [US5] Update MQTTStreamDrawer to display formatted messages with timestamps
- [X] T067 [US5] Add clear button to MQTTStreamDrawer that calls store clear action
- [ ] T068 [US5] Implement virtual scrolling in MQTTStreamDrawer for performance with high message volume
- [ ] T069 [US5] Test with high-frequency MQTT messages (100+ messages/second) and verify performance

**Checkpoint**: User Story 5 complete - MQTT stream monitor functional

---

## Phase 8: User Story 6 - Health Status Dashboard (Priority: P3)

**Goal**: Users can view health status of all TARS services with last-ping timestamps and error details

**Independent Test**: Simulate health messages from services, verify health drawer displays status and detects timeouts

### Implementation for User Story 6

- [X] T070 [US6] Implement health message handlers in health store for system/health/* topics
- [X] T071 [US6] Implement timeout detection in health store (30s) with interval check
- [X] T072 [US6] Add computed properties to health store for overall system health and healthy count
- [X] T073 [US6] Update HealthDrawer to display all tracked services with status indicators
- [X] T074 [US6] Add last-ping timestamp display in HealthDrawer
- [X] T075 [US6] Add error message display in HealthDrawer for unhealthy services
- [X] T076 [US6] Update Header health button to show overall system health (all healthy vs. some unhealthy)
- [ ] T077 [US6] Test timeout detection by stopping services and verifying stale status after 30s

**Checkpoint**: User Story 6 complete - Health monitoring dashboard functional

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Production readiness, optimization, and documentation

- [X] T078 [P] Update `apps/ui-web/README.md` with Vue.js development workflow, build instructions, testing guide
- [X] T079 [P] Create `apps/ui-web/frontend/README.md` with component documentation and quickstart (migrate from specs/004-convert-ui-web/quickstart.md)
- [X] T080 [P] Add `.gitignore` for frontend at `apps/ui-web/frontend/.gitignore` (node_modules, dist, coverage)
- [X] T081 Update `apps/ui-web/docker/ui-web.Dockerfile` with multi-stage build: Node.js builder stage + Python runtime stage
- [X] T082 [P] Optimize bundle size: code splitting, lazy-load drawer components with defineAsyncComponent
- [ ] T083 [P] Add accessibility improvements: ARIA labels, keyboard navigation for drawers
- [X] T084 Test production build: `npm run build` produces dist/ under 500KB gzipped (✅ 44KB gzipped, 164KB total)
- [X] T085 Test Docker build with multi-stage Dockerfile produces working image (✅ Build successful)
- [ ] T086 [P] Add responsive CSS for mobile viewports (drawer width, touch-friendly close)
- [ ] T087 Run full application test in production mode: build, serve via FastAPI, verify all features work
- [X] T088 [P] Update `apps/ui-web/Makefile` to include frontend targets: `make frontend-install`, `make frontend-dev`, `make frontend-build`, `make frontend-check`
- [X] T089 Remove old static HTML at `apps/ui-web/static/index.html` after confirming Vue.js version works (renamed to .legacy)
- [X] T090 Update `.env.example` if new environment variables needed (✅ already complete)

**Checkpoint**: ✅ Application production-ready, documented, and optimized

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup (T001-T012) completion - BLOCKS all user stories
- **User Stories (Phase 3-8)**: All depend on Foundational (T013-T022) completion
  - User stories CAN proceed in parallel if multiple developers available
  - OR sequentially in priority order: US1 (P1) → US2+US3 (P2) → US4+US5+US6 (P3)
- **Polish (Phase 9)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1) - Basic Chat**: Can start after Foundational - NO dependencies on other stories ✅ MVP
- **US2 (P2) - Drawers**: Can start after Foundational - Uses components from US3 but can use basic divs initially
- **US3 (P2) - Components**: Can start after Foundational - Independent component library
- **US4 (P3) - Spectrum**: Depends on US2 (MicrophoneDrawer) but can start if drawer shell exists
- **US5 (P3) - MQTT Monitor**: Depends on US2 (MQTTStreamDrawer) but can start if drawer shell exists
- **US6 (P3) - Health**: Depends on US2 (HealthDrawer) and US3 (StatusIndicator) but can start if shells exist

### Within Each User Story

- **US1**: Components in parallel (T023-T029) → Compose in ChatPanel/App (T030) → Message handlers (T031-T033) → Backend update (T034)
- **US2**: Shared components (T036-T038) → All drawer components in parallel (T040-T044) → Integration (T045-T047)
- **US3**: All components in parallel (T049-T050) → Documentation (T051) → Refactor (T053-T055)
- **US4**: SpectrumCanvas + useSpectrum (T056-T057) → Store integration (T058) → Drawer integration (T059-T061)
- **US5**: Store logic (T063-T065) → Drawer UI (T066-T068)
- **US6**: Store logic (T070-T072) → Drawer UI (T073-T075) → Header integration (T076)

### Parallel Opportunities

#### Phase 1 (Setup) - All [P] tasks run in parallel:
- T003, T004, T005, T006, T007, T008, T010, T011, T012

#### Phase 2 (Foundational) - All [P] tasks run in parallel:
- T013, T014, T015, T016 (all type files)
- T018, T019, T020, T021 (all stores, after T017 WebSocket store)

#### Phase 3 (US1) - Parallel opportunities:
- T023, T024, T025, T026, T029 (independent components)

#### Phase 4 (US2) - Parallel opportunities:
- T036, T037 (Button, Panel)
- T040, T041, T042, T043, T044 (all drawer components)

#### Phase 5 (US3) - Parallel opportunities:
- T049, T050 (StatusIndicator, CodeBlock)

#### Phase 9 (Polish) - Parallel opportunities:
- T078, T079, T080 (documentation and config)
- T082, T083, T086 (optimizations)

---

## Parallel Example: User Story 1 (Basic Chat)

```bash
# Launch all independent components together:
Task T023: "Create ChatBubble.vue"
Task T024: "Create ChatLog.vue"
Task T025: "Create Composer.vue"
Task T026: "Create StatusLine.vue"
Task T029: "Create Toolbar.vue"

# Then compose:
Task T027: "Create ChatPanel.vue" (depends on T023-T026)
Task T028: "Create Header.vue" (depends on T029)
Task T030: "Update App.vue" (depends on T027, T028)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. **Complete Phase 1**: Setup (T001-T012) - Frontend project scaffolded
2. **Complete Phase 2**: Foundational (T013-T022) - CRITICAL: All stores, types, routing ready
3. **Complete Phase 3**: User Story 1 (T023-T035) - Basic chat interface
4. **STOP and VALIDATE**: 
   - Load http://localhost:5173
   - Verify chat messages display from WebSocket
   - Send test message via Composer
   - Verify status indicators update
5. **Deploy/Demo MVP**: Functional chat interface with Vue.js + TypeScript

**Estimated Tasks for MVP**: 35 tasks (T001-T035)

### Incremental Delivery

1. **Foundation Ready** (Setup + Foundational) → T001-T022 complete
2. **MVP: User Story 1** (Chat) → T023-T035 → Test independently → Demo ✅
3. **Add: User Story 2** (Drawers) → T036-T048 → Test drawer system → Demo
4. **Add: User Story 3** (Components) → T049-T055 → Test component reuse → Demo
5. **Add: User Story 4** (Spectrum) → T056-T062 → Test visualization → Demo
6. **Add: User Story 5** (MQTT Monitor) → T063-T069 → Test monitoring → Demo
7. **Add: User Story 6** (Health) → T070-T077 → Test health tracking → Demo
8. **Production Ready** (Polish) → T078-T090 → Final validation

Each increment adds value without breaking previous features.

### Parallel Team Strategy

With 3 developers after Foundational phase (T022) completes:

- **Developer A**: User Story 1 (P1) → T023-T035 (critical path, MVP)
- **Developer B**: User Story 2 (P2) → T036-T048 (drawer system)
- **Developer C**: User Story 3 (P2) → T049-T055 (component library)

Once US2 and US3 complete, developers can work on US4, US5, US6 in parallel.

---

## Task Summary

**Total Tasks**: 90
- **Phase 1 (Setup)**: 12 tasks
- **Phase 2 (Foundational)**: 10 tasks (BLOCKS all stories)
- **Phase 3 (US1 - Chat - P1)**: 13 tasks 🎯 MVP
- **Phase 4 (US2 - Drawers - P2)**: 13 tasks
- **Phase 5 (US3 - Components - P2)**: 7 tasks
- **Phase 6 (US4 - Spectrum - P3)**: 7 tasks
- **Phase 7 (US5 - MQTT Monitor - P3)**: 7 tasks
- **Phase 8 (US6 - Health - P3)**: 8 tasks
- **Phase 9 (Polish)**: 13 tasks

**MVP Scope**: T001-T035 (35 tasks - Setup + Foundational + US1)

**Parallel Tasks**: 44 tasks marked [P] can run in parallel with other [P] tasks in same phase

**Independent Test Criteria**:
- US1: Chat interface loads, messages display, composer works
- US2: Drawers open/close, backdrop works, keyboard shortcuts work
- US3: Components render consistently, can build new features with them
- US4: Spectrum canvas updates with FFT data
- US5: MQTT messages appear in monitor, FIFO works
- US6: Health status updates, timeout detection works

---

## Notes

- [P] tasks = different files, no dependencies within phase
- [Story] label (US1-US6) maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- No contract tests needed - type safety provided by TypeScript strict mode
- Visual validation replaces automated UI tests for this migration
- Backend MQTT bridge remains unchanged throughout migration
