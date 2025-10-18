# Phase 0: Research - Convert ui-web to Vue.js TypeScript Application

**Feature**: 004-convert-ui-web  
**Date**: 2025-10-17  
**Status**: Complete

## Research Tasks

This document consolidates research findings for all technical decisions required to convert the plain HTML ui-web into a Vue.js TypeScript application.

---

## 1. Frontend Framework Choice: Vue.js 3

### Decision
Use **Vue.js 3** with **Composition API** and **TypeScript**.

### Rationale
- **User-requested**: User explicitly asked for Vue.js as the framework
- **Composition API**: Provides better TypeScript inference and code reusability via composables
- **Progressive adoption**: Can start simple and add complexity only as needed (aligns with YAGNI principle)
- **Excellent TypeScript support**: Vue 3 + `<script setup>` syntax provides seamless TS integration
- **Single File Components (SFC)**: Natural fit for modular UI components with template, script, and styles co-located
- **Smaller bundle size**: Vue 3 is ~30KB gzipped (smaller than React + dependencies)

### Alternatives Considered
- **React**: More verbose boilerplate, requires additional libraries for state management
- **Svelte**: Smaller community, fewer TypeScript patterns documented
- **Plain TypeScript + Web Components**: More effort to build component system from scratch

---

## 2. Build Tool: Vite 5

### Decision
Use **Vite 5** as the build tool and dev server.

### Rationale
- **Official Vue.js recommendation**: Vue team maintains `create-vue` scaffolding tool using Vite
- **Fast HMR**: Sub-100ms hot module replacement for rapid development iteration
- **ESBuild-powered**: Extremely fast TypeScript transpilation and bundling
- **Production optimization**: Built-in code splitting, tree shaking, CSS minification
- **Simple configuration**: Near-zero config for Vue + TypeScript projects
- **Plugin ecosystem**: Mature plugins for TypeScript, testing, etc.

### Alternatives Considered
- **Webpack**: Slower build times, more complex configuration
- **Rollup**: Lower-level tool, more configuration needed
- **Parcel**: Less mature Vue.js integration

### Best Practices
- Use `vite.config.ts` for TypeScript configuration
- Enable `strict` mode in TypeScript for maximum type safety
- Configure path aliases (`@/` for `src/`) for clean imports
- Use environment variables via `import.meta.env` (Vite convention)

---

## 3. State Management: Pinia 2.1+

### Decision
Use **Pinia** for centralized state management.

### Rationale
- **Official Vue state library**: Recommended by Vue core team (replaces Vuex)
- **TypeScript-first design**: Automatic type inference without manual typing
- **Composition API friendly**: Natural integration with Vue 3 patterns
- **Lightweight**: ~2KB gzipped overhead
- **Modular stores**: Each store is independent (health, chat, mqtt, ui, websocket)
- **DevTools integration**: Vue DevTools provides state inspection and time-travel debugging

### Alternatives Considered
- **Vuex 4**: Legacy library, verbose mutations/actions pattern, worse TypeScript support
- **Plain reactive()**: Insufficient for complex cross-component state (health timeouts, MQTT log buffering)
- **Provide/Inject**: Not suitable for global state with persistence and computed derivations

### Store Architecture
Based on the spec requirements, we need these stores:

1. **websocket.ts**: WebSocket connection state, reconnection logic
2. **mqtt.ts**: MQTT message log (FIFO buffer, 200 max), message distribution
3. **chat.ts**: Chat messages, LLM streaming aggregation (by `id`/`utt_id`)
4. **health.ts**: Service health tracking with timeout detection
5. **ui.ts**: Drawer visibility state, active drawer tracking

Each store is a separate file exporting a `defineStore()` call.

---

## 4. TypeScript Configuration

### Decision
Use **TypeScript 5.0+** with **strict mode** enabled.

### Rationale
- **Type safety**: Catches errors at development time (aligns with constitution's no-`Any` policy)
- **Better IDE support**: Autocomplete, refactoring, inline documentation
- **Self-documenting code**: Types serve as inline documentation for component props and state
- **Vue 3 compatibility**: Excellent type inference with `<script setup lang="ts">`

### Configuration Best Practices
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "jsx": "preserve",
    "resolveJsonModule": true,
    "esModuleInterop": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "types": ["vite/client"]
  }
}
```

### Type Definition Strategy
- Define MQTT message types matching backend schemas (from copilot-instructions.md)
- Use TypeScript interfaces for all component props
- Use type-safe Pinia stores (automatic inference)
- Avoid `any` type - use `unknown` and type guards when needed

---

## 5. Component Architecture Patterns

### Decision
Use **feature-based component organization** with **Composition API** and **SFC**.

### Rationale
- **Co-location**: Related components grouped by feature (drawers, chat, shared UI)
- **Composition API**: Better code reuse via composables (e.g., `useWebSocket`, `useDrawer`)
- **`<script setup>` syntax**: Less boilerplate, better TS inference
- **Scoped styles**: Component-specific CSS with `<style scoped>`

### Component Hierarchy
```
App.vue (root)
├── Header.vue
│   └── Toolbar.vue (drawer buttons, health indicator)
├── ChatPanel.vue
│   ├── ChatLog.vue
│   │   └── ChatBubble.vue (reusable)
│   ├── Composer.vue
│   └── StatusLine.vue
├── DrawerContainer.vue (manages backdrop, transitions)
│   ├── MicrophoneDrawer.vue
│   │   └── SpectrumCanvas.vue
│   ├── MemoryDrawer.vue
│   ├── MQTTStreamDrawer.vue
│   ├── CameraDrawer.vue
│   └── HealthDrawer.vue
└── (shared components)
    ├── Button.vue
    ├── Panel.vue
    ├── StatusIndicator.vue
    └── CodeBlock.vue
```

### Composable Patterns
- **useWebSocket**: Manages WebSocket connection, reconnection, message parsing
- **useDrawer**: Manages drawer open/close state, keyboard shortcuts (Escape)
- **useSpectrum**: Canvas rendering for audio spectrum with requestAnimationFrame
- **useMqttLog**: MQTT message buffering (FIFO, max 200), filtering

---

## 6. CSS Strategy: Scoped Styles + CSS Variables

### Decision
Use **scoped styles** in SFCs with **global CSS variables** for theming.

### Rationale
- **Preserve existing design**: Migrate existing CSS variables to global stylesheet
- **Scoped isolation**: Component styles don't leak globally
- **No CSS framework needed**: Existing design is custom, no need for Tailwind/Bootstrap
- **Performance**: No runtime CSS-in-JS overhead

### Migration Strategy
1. Extract CSS variables from `static/index.html` into `frontend/src/assets/styles/variables.css`
2. Import variables in `main.ts`
3. Use variables in scoped component styles: `color: var(--text);`
4. Preserve existing animations and transitions

### Example
```css
/* variables.css */
:root {
  --bg: #0a0a12;
  --panel: #0f1324;
  --border: #1e2545;
  --text: #e8ecff;
  --tars: #1d2b56;
  --user: #1d5637;
  --muted: #9aa4d6;
  --accent: #5ac8fa;
}
```

---

## 7. WebSocket Communication Pattern

### Decision
Use **Pinia store** to manage WebSocket connection with **reactive message distribution**.

### Rationale
- **Centralized connection**: Single WebSocket instance shared across all components
- **Automatic reconnection**: Store handles reconnection logic on disconnect
- **Message routing**: Store parses topic and distributes to appropriate sub-stores
- **Type safety**: All WebSocket messages have TypeScript interfaces

### Implementation Pattern
```typescript
// stores/websocket.ts
export const useWebSocketStore = defineStore('websocket', () => {
  const socket = ref<WebSocket | null>(null);
  const connected = ref(false);
  
  const connect = () => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    socket.value = new WebSocket(`${proto}://${location.host}/ws`);
    
    socket.value.onopen = () => { connected.value = true; };
    socket.value.onclose = () => { 
      connected.value = false;
      setTimeout(connect, 1000); // Reconnect
    };
    socket.value.onmessage = (ev) => {
      const msg = JSON.parse(ev.data) as WebSocketMessage;
      routeMessage(msg); // Distribute to sub-stores
    };
  };
  
  return { socket, connected, connect };
});
```

### Message Routing Strategy
- WebSocket store receives all messages
- Parses `topic` field and calls appropriate store action:
  - `stt/*` → chat store
  - `llm/*` → chat store
  - `tts/*` → chat store
  - `memory/results` → memory store (drawer)
  - `system/health/*` → health store
  - All messages → mqtt store (for MQTT Stream drawer)

---

## 8. Testing Strategy: Vitest + Vue Test Utils

### Decision
Use **Vitest** for unit testing and **Vue Test Utils** for component testing.

### Rationale
- **Vite integration**: Vitest shares Vite config (same plugins, aliases, transforms)
- **Fast**: Same instant HMR as Vite dev server
- **Jest-compatible API**: Familiar testing patterns
- **Vue Test Utils**: Official Vue component testing library
- **TypeScript support**: Native TS support without configuration

### Test Categories

#### Unit Tests (composables, utilities)
```typescript
// tests/unit/composables/useDrawer.test.ts
import { describe, it, expect } from 'vitest';
import { useDrawer } from '@/composables/useDrawer';

describe('useDrawer', () => {
  it('toggles drawer visibility', () => {
    const { isOpen, toggle } = useDrawer('mic');
    expect(isOpen.value).toBe(false);
    toggle();
    expect(isOpen.value).toBe(true);
  });
});
```

#### Component Tests
```typescript
// tests/unit/components/ChatBubble.test.ts
import { mount } from '@vue/test-utils';
import { describe, it, expect } from 'vitest';
import ChatBubble from '@/components/ChatBubble.vue';

describe('ChatBubble', () => {
  it('renders user message with correct class', () => {
    const wrapper = mount(ChatBubble, {
      props: { role: 'user', text: 'Hello TARS' }
    });
    expect(wrapper.classes()).toContain('user');
    expect(wrapper.text()).toBe('Hello TARS');
  });
});
```

#### Integration Tests (state management)
```typescript
// tests/integration/stores/health.test.ts
import { setActivePinia, createPinia } from 'pinia';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useHealthStore } from '@/stores/health';

describe('Health Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers();
  });

  it('marks service as offline after timeout', () => {
    const store = useHealthStore();
    store.updateHealth('stt', { ok: true, event: 'ready' });
    expect(store.components.stt.ok).toBe(true);
    
    vi.advanceTimersByTime(31000); // 30s timeout + buffer
    expect(store.components.stt.ok).toBe(false);
  });
});
```

---

## 9. Development Workflow

### Decision
Use **dual-server development** with **Vite proxy** for backend API.

### Rationale
- **Hot Module Replacement**: Vite dev server provides instant feedback on code changes
- **Backend integration**: Vite proxy forwards `/ws` and `/api/*` to FastAPI backend
- **No CORS issues**: Proxy makes backend appear on same origin
- **Production parity**: Built assets served by FastAPI in production

### Development Setup
```bash
# Terminal 1: Run backend (serves WebSocket bridge)
cd apps/ui-web
python -m ui_web

# Terminal 2: Run frontend dev server (HMR)
cd apps/ui-web/frontend
npm run dev
```

### Vite Proxy Configuration
```typescript
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/ws': {
        target: 'http://localhost:8080',
        ws: true
      },
      '/api': {
        target: 'http://localhost:8080'
      }
    }
  }
});
```

### Production Build
```bash
cd apps/ui-web/frontend
npm run build  # Outputs to dist/
# Backend serves dist/ as static files
```

---

## 10. Migration Strategy (Backward Compatibility)

### Decision
**Phased migration** with **parallel deployment** during transition.

### Rationale
- **Low risk**: Old HTML remains functional until Vue.js version is complete
- **A/B testing**: Can compare performance and functionality
- **Rollback**: Easy to revert if issues discovered

### Migration Phases

#### Phase 1: Setup (P1 - Basic Chat Interface)
1. Create `frontend/` directory with Vite + Vue + TypeScript
2. Implement core layout (header, chat panel, status)
3. Connect WebSocket and display basic messages
4. Preserve visual design (CSS variables)
5. Update FastAPI to serve `dist/` instead of `static/`

**Deliverable**: Working chat interface with WebSocket connection

#### Phase 2: Component Architecture (P2 - Drawers + Reusable Components)
1. Implement drawer system (DrawerContainer, backdrop, transitions)
2. Create reusable components (Button, Panel, StatusIndicator, CodeBlock)
3. Migrate existing drawers (Microphone, Memory, MQTT Stream, Camera, Health)
4. Implement state management (Pinia stores)

**Deliverable**: Full feature parity with existing HTML version

#### Phase 3: Polish & Optimization (P3)
1. Performance optimization (lazy loading, code splitting)
2. Bundle size optimization (<500KB gzipped)
3. Accessibility improvements (ARIA labels, keyboard navigation)
4. Documentation (component usage, development guide)

**Deliverable**: Production-ready Vue.js application

### Rollback Plan
- Keep `static/index.html` in git history
- Can serve old version by reverting FastAPI static file path
- Feature flag in backend config: `SERVE_VUE_UI=true/false`

---

## 11. Docker Build Integration

### Decision
Use **multi-stage Dockerfile** to build frontend and serve with backend.

### Rationale
- **Single deployable artifact**: Docker image contains both frontend and backend
- **Build-time compilation**: TypeScript compiled and optimized during image build
- **Minimal runtime image**: Only built assets + Python backend in final layer
- **No node_modules in production**: Frontend build dependencies not in final image

### Dockerfile Strategy
```dockerfile
# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /workspace/frontend
COPY apps/ui-web/frontend/package*.json ./
RUN npm ci
COPY apps/ui-web/frontend/ ./
RUN npm run build

# Stage 2: Backend runtime
FROM python:3.11-slim
WORKDIR /app
COPY apps/ui-web/src/ ./src/
COPY --from=frontend-builder /workspace/frontend/dist/ ./dist/
RUN pip install -e .
CMD ["python", "-m", "ui_web"]
```

### Build Optimization
- Use `npm ci` for reproducible builds
- Cache `node_modules` layer for faster rebuilds
- Multi-stage build keeps final image small (~150MB vs 1GB+ with node_modules)

---

## 12. Performance Optimization Patterns

### Decision
Use **throttling** and **virtual scrolling** for high-frequency MQTT messages.

### Rationale
- **60fps target**: Must maintain smooth rendering with 100+ messages/second
- **Memory efficiency**: Virtual scrolling prevents DOM bloat with 1000s of messages
- **CPU efficiency**: Throttle canvas rendering to 60fps max

### Implementation Patterns

#### MQTT Log Throttling
```typescript
// Batch message insertions to reduce reactive updates
const mqttBuffer = ref<MQTTMessage[]>([]);
const flushBuffer = useDebounceFn(() => {
  mqttLog.value.push(...mqttBuffer.value);
  mqttBuffer.value = [];
  // Trim to 200 max (FIFO)
  if (mqttLog.value.length > 200) {
    mqttLog.value = mqttLog.value.slice(-200);
  }
}, 100); // Flush every 100ms
```

#### Spectrum Canvas Throttling
```typescript
// useSpectrum composable
const drawSpectrum = () => {
  // Only draw if drawer is open (avoid wasted rendering)
  if (!isDrawerOpen.value) return;
  
  // Canvas rendering logic...
  
  requestAnimationFrame(drawSpectrum); // 60fps max
};
```

#### Component-Level Optimizations
- Use `v-memo` directive for expensive list items that rarely change
- Use `v-once` for static content
- Lazy load drawer components with `defineAsyncComponent`

---

## Research Summary

All technical unknowns from the plan have been resolved:

✅ **Framework**: Vue.js 3 (Composition API) + TypeScript 5  
✅ **Build Tool**: Vite 5  
✅ **State Management**: Pinia 2.1+  
✅ **Testing**: Vitest + Vue Test Utils  
✅ **CSS Strategy**: Scoped styles + CSS variables  
✅ **Component Patterns**: Feature-based organization, composables  
✅ **WebSocket Pattern**: Centralized Pinia store with message routing  
✅ **Development Workflow**: Dual-server with Vite proxy  
✅ **Docker Build**: Multi-stage with frontend build step  
✅ **Performance**: Throttling + virtual scrolling for high-frequency data  
✅ **Migration Strategy**: Phased approach with rollback capability

**Next Phase**: Phase 1 - Design & Contracts (data models, API contracts, quickstart guide)
