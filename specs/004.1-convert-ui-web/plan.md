# Implementation Plan: Convert ui-web to Vue.js TypeScript Application

**Branch**: `004-convert-ui-web` | **Date**: 2025-10-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-convert-ui-web/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Convert the existing plain HTML ui-web application into a modern Vue.js 3 TypeScript single-page application with component-based architecture. This migration enables modular UI development, reusable components, and easier addition of new monitoring panels while preserving the existing visual design and backend architecture. The solution will use Vite for building, Pinia for state management, and maintain the current WebSocket/MQTT communication protocol.

## Technical Context

**Language/Version**: 
- Backend: Python 3.11+ (existing FastAPI server - unchanged)
- Frontend: TypeScript 5.0+ with Vue.js 3 (Composition API)

**Primary Dependencies**: 
- Backend (unchanged): FastAPI 0.111+, asyncio-mqtt 0.16+, uvicorn, orjson
- Frontend (new): Vue 3.4+, Vite 5+, Pinia 2.1+ (state management), TypeScript 5+

**Storage**: 
- None for frontend (ephemeral WebSocket state only)
- Backend maintains in-memory cache of last memory results

**Testing**: 
- Frontend: Vitest (unit tests), Vue Test Utils (component tests)
- Backend: pytest + pytest-asyncio (existing, unchanged)

**Target Platform**: Modern browsers (Chrome 90+, Firefox 88+, Safari 14+, Edge 90+)

**Project Type**: Web application (frontend + backend split)

**Performance Goals**: 
- 60fps rendering for real-time MQTT message display (100+ messages/second)
- <100ms UI responsiveness for user interactions
- <3s bundle load time on first page view
- <30s production build time

**Constraints**: 
- Backend WebSocket/MQTT bridge must remain unchanged (existing protocol contract)
- Visual design must be preserved (colors, layout, drawer behavior)
- Bundle size <500KB gzipped for initial load
- Must support hot-module-replacement for rapid development iteration

**Scale/Scope**: 
- Single-user debug UI (no multi-user requirements)
- ~10-15 reusable components
- 5-6 drawer modules
- ~2000-3000 lines of TypeScript code
- Real-time handling of 100+ MQTT messages/second

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Initial Check (Pre-Research) ✅

### I. Event-Driven Architecture
✅ **PASS** - Frontend consumes WebSocket messages (MQTT events bridged by backend). No direct service-to-service calls. Backend MQTT bridge unchanged.

### II. Typed Contracts
✅ **PASS** - Will define TypeScript interfaces for all MQTT message payloads matching existing backend contracts. Frontend validates at WebSocket boundary.

### III. Async-First Concurrency
⚠️ **N/A for Frontend** - Browser JavaScript event loop handles async naturally. Backend async patterns unchanged.

### IV. Test-First Development
✅ **COMMITTED** - Will write component tests for each Vue component and integration tests for state management before implementation.

### V. Configuration via Environment
✅ **PASS** - Frontend config via build-time env vars (Vite). Backend env-based config unchanged.

### VI. Observability & Health Monitoring
⚠️ **PARTIAL** - Frontend has no health publishing (browser app). Backend health monitoring unchanged. Frontend will log errors to console.

### VII. Simplicity & YAGNI
✅ **PASS** - Using industry-standard tools (Vue 3, Vite, Pinia) with minimal additional abstractions. Starting with simplest component structure.

### MQTT Contract Standards
✅ **PASS** - Frontend consumes existing MQTT topics via WebSocket bridge. No new topics introduced. Existing payload schemas preserved.

### Docker Build System
✅ **PASS** - Will update existing `ui-web.Dockerfile` to add multi-stage frontend build. Backend stage unchanged.

### Development Workflow & Quality Gates
✅ **COMMITTED** - Will add frontend-specific Makefile targets (fmt, lint, test, build) following existing patterns. TypeScript strict mode enabled.

**Overall Assessment**: ✅ **APPROVED TO PROCEED** - No constitutional violations. Feature is purely additive (frontend modernization) without backend contract changes.

---

### Post-Design Check (After Phase 1) ✅

**Re-evaluated**: 2025-10-17 after completing Phase 1 (Design & Contracts)

### I. Event-Driven Architecture
✅ **PASS** - Design confirms WebSocket store pattern with message routing to domain-specific stores. No direct coupling between components.

**Evidence**: 
- `stores/websocket.ts` centralizes WebSocket connection
- `routeMessage()` function distributes to domain stores (chat, health, mqtt)
- Topic-based routing matches MQTT contract standards

### II. Typed Contracts
✅ **PASS** - Complete TypeScript interfaces defined in `contracts/mqtt-messages.ts` matching backend schemas exactly.

**Evidence**:
- 25+ TypeScript interfaces covering all MQTT messages
- Type guards for runtime validation at WebSocket boundary
- No `any` types - all payloads explicitly typed
- Round-trip validation patterns defined

### III. Async-First Concurrency
✅ **N/A** - Browser event loop handles async natively. No blocking operations introduced.

**Evidence**:
- Vue 3 reactivity system is inherently async
- WebSocket message handling uses event-driven callbacks
- Canvas rendering uses `requestAnimationFrame` (non-blocking)

### IV. Test-First Development
✅ **COMMITTED** - Testing strategy documented with Vitest + Vue Test Utils. Test examples provided in quickstart.

**Evidence**:
- Unit test examples for components
- Integration test examples for stores
- Type guard validation tests
- Quickstart guide includes test-first workflow

### V. Configuration via Environment
✅ **PASS** - Vite environment variables for build-time config. No hard-coded constants.

**Evidence**:
- WebSocket URL computed from `window.location`
- Backend config unchanged (env-based)
- No API keys or secrets in frontend code

### VI. Observability & Health Monitoring
✅ **ENHANCED** - Frontend implements comprehensive client-side health tracking beyond initial plan.

**Evidence**:
- Health store tracks 8 components with timeout detection (30s)
- Computed health status aggregation
- Console logging for debugging
- Health drawer provides operational visibility

### VII. Simplicity & YAGNI
✅ **PASS** - Design follows minimal patterns without over-abstraction.

**Evidence**:
- Standard Vue 3 Composition API (no custom framework)
- Pinia stores use simple reactive state (no complex middleware)
- Composables for shared logic (standard pattern)
- No premature optimization (virtual scrolling only for MQTT log)

### MQTT Contract Standards
✅ **VALIDATED** - All MQTT message types documented in contracts exactly match backend schemas from copilot-instructions.md.

**Evidence**:
- Topic patterns defined in `MQTT_TOPICS` constant
- QoS and retention documented in contract comments
- Type guards enforce schema compliance at runtime
- No new topics introduced (consumption only)

### Docker Build System
✅ **DESIGNED** - Multi-stage Dockerfile pattern defined in research.md.

**Evidence**:
- Stage 1: Node.js builder for frontend
- Stage 2: Python runtime with built assets
- No node_modules in production image
- Build optimization documented

### Development Workflow & Quality Gates
✅ **COMPLETE** - Full CI/CD workflow defined with quality gates.

**Evidence**:
- npm scripts: `format`, `lint`, `type-check`, `test`, `check`
- Prettier + ESLint + TypeScript strict mode
- Vitest for testing with coverage
- Quickstart guide documents all workflows

---

**Final Assessment**: ✅ **DESIGN APPROVED** - All constitution principles satisfied. Ready to proceed to Phase 2 (Task breakdown).

**Notable Enhancements**:
1. Health tracking more comprehensive than spec required (timeout detection, computed aggregations)
2. Type system more rigorous than typical Vue apps (strict mode, no `any`, runtime guards)
3. Testing strategy more thorough (unit, integration, type validation)

**Zero Violations**: No complexity justifications required. All patterns align with constitution and industry best practices.

## Project Structure

### Documentation (this feature)

```
specs/004-convert-ui-web/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
└── contracts/           # Phase 1 output (/speckit.plan command)
    ├── mqtt-messages.ts # TypeScript interfaces for MQTT payloads
    └── websocket.ts     # WebSocket message envelope types
```

### Source Code (repository root)

```
apps/ui-web/
├── Makefile                    # Backend + frontend targets
├── README.md                   # Updated with Vue.js dev workflow
├── pyproject.toml              # Backend Python package (unchanged)
├── .env.example                # Backend env vars (unchanged)
├── docker/
│   └── ui-web.Dockerfile       # Multi-stage: frontend build + backend runtime
├── src/
│   └── ui_web/                 # Backend Python package (unchanged)
│       ├── __init__.py
│       ├── __main__.py         # FastAPI server (updated to serve dist/)
│       └── config.py
├── static/                     # OLD - will be removed after migration
│   └── index.html              # Plain HTML (to be replaced)
├── frontend/                   # NEW - Vue.js application
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html              # Vite entry point
│   ├── public/                 # Static assets
│   ├── src/
│   │   ├── main.ts             # Vue app entry
│   │   ├── App.vue             # Root component
│   │   ├── components/         # Reusable UI components
│   │   │   ├── ChatBubble.vue
│   │   │   ├── ChatLog.vue
│   │   │   ├── Composer.vue
│   │   │   ├── DrawerContainer.vue
│   │   │   ├── Button.vue
│   │   │   ├── Panel.vue
│   │   │   ├── StatusIndicator.vue
│   │   │   └── CodeBlock.vue
│   │   ├── drawers/            # Drawer modules
│   │   │   ├── MicrophoneDrawer.vue
│   │   │   ├── MemoryDrawer.vue
│   │   │   ├── MQTTStreamDrawer.vue
│   │   │   ├── CameraDrawer.vue
│   │   │   └── HealthDrawer.vue
│   │   ├── stores/             # Pinia state management
│   │   │   ├── websocket.ts    # WebSocket connection
│   │   │   ├── mqtt.ts         # MQTT message aggregation
│   │   │   ├── chat.ts         # Chat state
│   │   │   ├── health.ts       # Service health tracking
│   │   │   └── ui.ts           # UI state (drawer visibility)
│   │   ├── composables/        # Shared composition functions
│   │   │   ├── useWebSocket.ts
│   │   │   ├── useDrawer.ts
│   │   │   └── useSpectrum.ts
│   │   └── types/              # TypeScript type definitions
│   │       ├── mqtt.ts         # MQTT message types
│   │       ├── websocket.ts    # WebSocket envelope types
│   │       └── health.ts       # Health status types
│   └── tests/
│       ├── unit/               # Component unit tests
│       ├── integration/        # State management tests
│       └── setup.ts            # Test configuration
├── dist/                       # Built frontend (gitignored)
│   ├── index.html
│   ├── assets/
│   │   ├── index-[hash].js
│   │   └── index-[hash].css
│   └── ...
└── tests/                      # Backend tests (unchanged)
    ├── unit/
    └── integration/
```

**Structure Decision**: Web application (frontend + backend split). The frontend is a separate Vue.js TypeScript application built with Vite that produces static assets. The backend FastAPI server serves these built assets and provides the WebSocket bridge to MQTT. This structure enables:
- Independent frontend development with HMR via Vite dev server
- Production deployment where FastAPI serves the built frontend
- Clear separation of concerns (UI logic vs. MQTT bridge)
- Standard Vue.js ecosystem tooling and patterns

## Complexity Tracking

*Fill ONLY if Constitution Check has violations that must be justified*

**No violations** - This feature introduces no constitutional violations. The use of Vue.js, Vite, and Pinia are industry-standard, battle-tested tools appropriate for the stated goal of "moving to a more robust and battle tested web framework." These tools are simpler than custom-building a component system.
