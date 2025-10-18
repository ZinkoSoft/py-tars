# Quickstart Guide - Vue.js TypeScript UI Development

**Feature**: 004-convert-ui-web  
**Date**: 2025-10-17

## Overview

This guide provides step-by-step instructions for developing the Vue.js TypeScript frontend for the ui-web application. Follow this guide whether you're contributing to the migration or starting fresh development on the Vue.js codebase.

---

## Prerequisites

### Required Tools
- **Node.js 20+** (LTS version recommended)
- **npm 10+** (comes with Node.js)
- **Python 3.11+** (for running backend)
- **Git** (for version control)

### Verify Installation
```bash
node --version   # Should be v20.x or higher
npm --version    # Should be 10.x or higher
python --version # Should be 3.11 or higher
```

---

## Initial Setup

### 1. Clone and Navigate to Project

```bash
cd /home/james/git/py-tars
git checkout 004-convert-ui-web  # Feature branch
cd apps/ui-web
```

### 2. Install Backend Dependencies

```bash
# Activate Python virtual environment
source /home/james/git/py-tars/.venv/bin/activate

# Install backend package
pip install -e ".[dev]"
```

### 3. Install Frontend Dependencies

```bash
cd frontend
npm install
```

This will install:
- Vue 3 (framework)
- Vite 5 (build tool)
- TypeScript 5 (type safety)
- Pinia 2 (state management)
- Vitest (testing)
- Vue Test Utils (component testing)

---

## Development Workflow

### Running the Full Stack Locally

You need **two terminal windows**:

#### Terminal 1: Backend Server (MQTT WebSocket Bridge)

```bash
# From apps/ui-web directory
cd /home/james/git/py-tars/apps/ui-web
source /home/james/git/py-tars/.venv/bin/activate

# Set MQTT broker URL if not using defaults
export MQTT_URL="mqtt://tars:pass@localhost:1883"

# Run backend
python -m ui_web
```

Backend will start on **http://localhost:8080**

Expected output:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080
```

#### Terminal 2: Frontend Dev Server (Hot Module Replacement)

```bash
# From apps/ui-web/frontend directory
cd /home/james/git/py-tars/apps/ui-web/frontend

# Run Vite dev server
npm run dev
```

Frontend dev server will start on **http://localhost:5173**

Expected output:
```
  VITE v5.x.x  ready in 342 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
  ➜  press h to show help
```

### Access the Application

Open browser to **http://localhost:5173**

- Vite dev server serves the Vue.js frontend with HMR
- API requests to `/ws` and `/api/*` are proxied to backend on port 8080
- WebSocket connection bridges MQTT messages from broker

---

## Project Structure

```
apps/ui-web/frontend/
├── package.json           # npm dependencies and scripts
├── tsconfig.json          # TypeScript configuration
├── vite.config.ts         # Vite build configuration
├── index.html             # HTML entry point
├── public/                # Static assets (favicon, etc.)
├── src/
│   ├── main.ts            # App entry point
│   ├── App.vue            # Root component
│   ├── assets/
│   │   └── styles/
│   │       └── variables.css  # CSS variables (theme)
│   ├── components/        # Reusable UI components
│   │   ├── Button.vue
│   │   ├── Panel.vue
│   │   ├── ChatBubble.vue
│   │   └── ...
│   ├── drawers/           # Drawer module components
│   │   ├── MicrophoneDrawer.vue
│   │   ├── MemoryDrawer.vue
│   │   └── ...
│   ├── stores/            # Pinia state management
│   │   ├── websocket.ts   # WebSocket connection
│   │   ├── mqtt.ts        # MQTT message log
│   │   ├── chat.ts        # Chat state
│   │   ├── health.ts      # Service health
│   │   └── ui.ts          # UI state (drawers)
│   ├── composables/       # Reusable composition functions
│   │   ├── useWebSocket.ts
│   │   ├── useDrawer.ts
│   │   └── useSpectrum.ts
│   └── types/             # TypeScript type definitions
│       ├── mqtt.ts        # MQTT message types
│       ├── websocket.ts   # WebSocket types
│       └── health.ts      # Health types
└── tests/
    ├── unit/              # Component unit tests
    └── integration/       # State management tests
```

---

## Common Development Tasks

### Add a New Component

1. **Create component file**:
   ```bash
   touch src/components/MyNewComponent.vue
   ```

2. **Define component** (using `<script setup>` syntax):
   ```vue
   <script setup lang="ts">
   interface Props {
     title: string;
     count?: number;
   }
   
   const props = withDefaults(defineProps<Props>(), {
     count: 0
   });
   
   const emit = defineEmits<{
     click: [value: number];
   }>();
   
   function handleClick() {
     emit('click', props.count + 1);
   }
   </script>
   
   <template>
     <div class="my-component">
       <h3>{{ title }}</h3>
       <button @click="handleClick">Count: {{ count }}</button>
     </div>
   </template>
   
   <style scoped>
   .my-component {
     padding: 12px;
     background: var(--panel);
     border: 1px solid var(--border);
     border-radius: 8px;
   }
   </style>
   ```

3. **Import and use**:
   ```vue
   <script setup lang="ts">
   import MyNewComponent from '@/components/MyNewComponent.vue';
   
   function handleComponentClick(value: number) {
     console.log('Clicked:', value);
   }
   </script>
   
   <template>
     <MyNewComponent 
       title="Hello" 
       :count="5" 
       @click="handleComponentClick"
     />
   </template>
   ```

### Add a New Pinia Store

1. **Create store file**:
   ```bash
   touch src/stores/myFeature.ts
   ```

2. **Define store** (using Composition API style):
   ```typescript
   import { ref, computed } from 'vue';
   import { defineStore } from 'pinia';
   
   export const useMyFeatureStore = defineStore('myFeature', () => {
     // State
     const items = ref<string[]>([]);
     const loading = ref(false);
     
     // Getters
     const itemCount = computed(() => items.value.length);
     
     // Actions
     function addItem(item: string) {
       items.value.push(item);
     }
     
     function clear() {
       items.value = [];
     }
     
     return {
       // Expose state, getters, actions
       items,
       loading,
       itemCount,
       addItem,
       clear
     };
   });
   ```

3. **Use in component**:
   ```vue
   <script setup lang="ts">
   import { useMyFeatureStore } from '@/stores/myFeature';
   
   const store = useMyFeatureStore();
   
   function addNew() {
     store.addItem('New item');
   }
   </script>
   
   <template>
     <div>
       <p>Items: {{ store.itemCount }}</p>
       <button @click="addNew">Add Item</button>
     </div>
   </template>
   ```

### Add MQTT Message Handler

1. **Define message type** in `src/types/mqtt.ts`:
   ```typescript
   export interface MyNewMessage {
     action: string;
     data: unknown;
   }
   ```

2. **Add type guard**:
   ```typescript
   export function isMyNewMessage(payload: unknown): payload is MyNewMessage {
     return (
       typeof payload === 'object' &&
       payload !== null &&
       'action' in payload
     );
   }
   ```

3. **Handle in WebSocket store** (`src/stores/websocket.ts`):
   ```typescript
   function routeMessage(msg: WebSocketMessage) {
     const { topic, payload } = msg;
     
     if (topic === 'my/topic') {
       if (isMyNewMessage(payload)) {
         handleMyMessage(payload);
       }
     }
     // ... other routes
   }
   
   function handleMyMessage(msg: MyNewMessage) {
     console.log('Received:', msg.action);
     // Update appropriate store...
   }
   ```

---

## Testing

### Run All Tests

```bash
cd apps/ui-web/frontend
npm test
```

### Run Tests in Watch Mode

```bash
npm run test:watch
```

### Run Tests with Coverage

```bash
npm run test:coverage
```

### Write a Component Test

Create `tests/unit/components/MyComponent.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { mount } from '@vue/test-utils';
import MyComponent from '@/components/MyComponent.vue';

describe('MyComponent', () => {
  it('renders title prop', () => {
    const wrapper = mount(MyComponent, {
      props: { title: 'Test Title' }
    });
    
    expect(wrapper.text()).toContain('Test Title');
  });
  
  it('emits click event', async () => {
    const wrapper = mount(MyComponent, {
      props: { title: 'Test' }
    });
    
    await wrapper.find('button').trigger('click');
    
    expect(wrapper.emitted('click')).toBeTruthy();
    expect(wrapper.emitted('click')![0]).toEqual([1]);
  });
});
```

### Write a Store Test

Create `tests/integration/stores/myStore.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from 'vitest';
import { setActivePinia, createPinia } from 'pinia';
import { useMyStore } from '@/stores/myStore';

describe('My Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });
  
  it('initializes with empty state', () => {
    const store = useMyStore();
    expect(store.items).toEqual([]);
  });
  
  it('adds items', () => {
    const store = useMyStore();
    store.addItem('test');
    expect(store.items).toEqual(['test']);
    expect(store.itemCount).toBe(1);
  });
});
```

---

## Building for Production

### Build Frontend

```bash
cd apps/ui-web/frontend
npm run build
```

This creates optimized static assets in `dist/`:
```
dist/
├── index.html
├── assets/
│   ├── index-[hash].js    # ~150KB gzipped
│   └── index-[hash].css   # ~15KB gzipped
└── ...
```

### Preview Production Build

```bash
npm run preview
```

Opens production build on http://localhost:4173

### Backend Serves Built Assets

Update `apps/ui-web/src/ui_web/__main__.py` to serve `dist/` instead of `static/`:

```python
# Serve built Vue.js app
app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
```

---

## Code Quality Tools

### Format Code

```bash
npm run format
```

Uses Prettier to format all `.vue`, `.ts`, `.json` files

### Lint Code

```bash
npm run lint
```

Uses ESLint to check for code quality issues

### Type Check

```bash
npm run type-check
```

Runs TypeScript compiler in check mode (no emit)

### Run All Checks (CI Gate)

```bash
npm run check
```

Runs format, lint, type-check, and tests

---

## Debugging

### Vue DevTools

Install Vue DevTools browser extension:
- Chrome: [Vue.js devtools](https://chrome.google.com/webstore/detail/vuejs-devtools)
- Firefox: [Vue.js devtools](https://addons.mozilla.org/en-US/firefox/addon/vue-js-devtools/)

Provides:
- Component tree inspection
- State management (Pinia store viewer)
- Event timeline
- Performance profiling

### Browser Console Logs

Add debug logs in components:
```typescript
import { onMounted, watch } from 'vue';

onMounted(() => {
  console.log('Component mounted');
});

watch(() => store.items, (newValue) => {
  console.log('Items changed:', newValue);
});
```

### Vite Dev Server Features

- **HMR (Hot Module Replacement)**: Changes reflect instantly without full reload
- **Fast Refresh**: Component state preserved during updates
- **Source Maps**: Debug TypeScript in browser (maps to original .vue/.ts files)

---

## Common Issues & Solutions

### Port Already in Use

If port 5173 is busy:
```bash
npm run dev -- --port 5174
```

### WebSocket Connection Failed

Check backend is running:
```bash
curl http://localhost:8080/
# Should return HTML
```

Check MQTT broker is accessible:
```bash
docker compose -f ops/compose.yml ps mosquitto
```

### Type Errors in Editor

Reload TypeScript server in VS Code:
- `Cmd+Shift+P` → "TypeScript: Restart TS Server"

### Module Not Found

Clear node_modules and reinstall:
```bash
rm -rf node_modules package-lock.json
npm install
```

---

## Next Steps

1. **Implement P1 features** (Basic Chat Interface):
   - Set up layout components (Header, ChatPanel, StatusLine)
   - Implement WebSocket store and connection
   - Display chat messages from MQTT

2. **Implement P2 features** (Drawers + Components):
   - Create drawer system (DrawerContainer, backdrop)
   - Build reusable components (Button, Panel, etc.)
   - Migrate all existing drawers

3. **Implement P3 features** (Polish):
   - Performance optimization
   - Accessibility improvements
   - Documentation

---

## Resources

- **Vue.js 3 Docs**: https://vuejs.org/guide/introduction.html
- **Pinia Docs**: https://pinia.vuejs.org/
- **Vite Docs**: https://vitejs.dev/guide/
- **TypeScript Handbook**: https://www.typescriptlang.org/docs/
- **Vitest Docs**: https://vitest.dev/guide/
- **Vue Test Utils**: https://test-utils.vuejs.org/

---

## Getting Help

- Review existing components in `src/components/` for patterns
- Check TypeScript types in `src/types/` for message schemas
- Read store implementations in `src/stores/` for state management examples
- Consult `specs/004-convert-ui-web/data-model.md` for entity definitions
- Reference `specs/004-convert-ui-web/research.md` for architectural decisions

**Happy coding! 🚀**
