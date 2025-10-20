# TARS UI Web Frontend

Vue.js 3 + TypeScript frontend for the TARS voice assistant UI.

## Quick Start

See [Quickstart Guide](../../../specs/004-convert-ui-web/quickstart.md) for detailed setup instructions.

```bash
# Install dependencies
npm install

# Run dev server
npm run dev

# Build for production
npm run build

# Run tests
npm test

# Run all checks (format, lint, type-check, test)
npm run check
```

## Component Library

### Shared UI Components

#### Button

Styled button component with variant support.

**Props:**

- `label: string` - Button text
- `variant?: 'default' | 'primary' | 'danger'` - Visual style (default: 'default')
- `disabled?: boolean` - Disabled state (default: false)

**Events:**

- `@click` - Emitted when button is clicked

**Example:**

```vue
<Button label="Save" variant="primary" @click="handleSave" />
<Button label="Delete" variant="danger" :disabled="!canDelete" @click="handleDelete" />
```

#### Panel

Container with optional title and consistent border styling.

**Props:**

- `title?: string` - Panel header text
- `className?: string` - Additional CSS classes

**Slots:**

- `default` - Panel content

**Example:**

```vue
<Panel title="Settings">
  <p>Panel content goes here</p>
</Panel>
```

#### StatusIndicator

Status indicator with colored dot and label.

**Props:**

- `label: string` - Status text
- `status: 'healthy' | 'unhealthy' | 'unknown'` - Status type

**Example:**

```vue
<StatusIndicator label="STT Worker" :status="sttHealth ? 'healthy' : 'unhealthy'" />
<StatusIndicator label="Router" status="unknown" />
```

#### CodeBlock

Code display with syntax highlighting and scrolling.

**Props:**

- `code: string` - Code content to display
- `language?: string` - Language for highlighting (default: 'json')
- `maxLines?: number` - Maximum lines before scrolling (optional)

**Example:**

```vue
<CodeBlock :code="JSON.stringify(payload, null, 2)" language="json" :maxLines="20" />
```

### Chat Components

#### ChatBubble

Individual chat message bubble with role-based styling.

**Props:**

- `role: 'user' | 'tars'` - Message sender
- `text: string` - Message content
- `meta?: string` - Metadata label (e.g., "You", "TARS")

**Example:**

```vue
<ChatBubble role="user" text="Hello TARS" meta="You" />
<ChatBubble role="tars" text="Hello! How can I help?" meta="TARS" />
```

#### ChatLog

Scrollable message list with auto-scroll support.

**Props:**

- `messages: ChatMessage[]` - Array of messages to display
- `autoScroll?: boolean` - Auto-scroll to bottom on new messages (default: true)

**Example:**

```vue
<ChatLog :messages="chatStore.messages" :autoScroll="true" />
```

#### Composer

Text input for composing chat messages.

**Events:**

- `@submit: (text: string) => void` - Emitted when user submits message

**Example:**

```vue
<Composer @submit="handleSendMessage" />
```

### Drawer System

#### DrawerContainer

Wrapper for drawer content with backdrop and transitions.

**Props:**

- `type: DrawerType` - Drawer identifier ('mic' | 'memory' | 'stream' | 'camera' | 'health')
- `title: string` - Drawer header text
- `isOpen: boolean` - Visibility state

**Events:**

- `@close` - Emitted when drawer should close (backdrop click, Escape key)

**Slots:**

- `default` - Drawer content

**Example:**

```vue
<DrawerContainer
  :is-open="uiStore.activeDrawer === 'mic'"
  title="Microphone"
  @close="uiStore.closeDrawer"
>
  <MicrophoneDrawer />
</DrawerContainer>
```

## State Management (Pinia Stores)

### WebSocket Store (`useWebSocketStore`)

Manages WebSocket connection and message routing.

**State:**

- `connected: boolean` - Connection status
- `socket: WebSocket | null` - WebSocket instance

**Actions:**

- `connect()` - Establish WebSocket connection
- `disconnect()` - Close connection

**Usage:**

```ts
const wsStore = useWebSocketStore()
wsStore.connect() // Auto-reconnects on disconnect
```

### Chat Store (`useChatStore`)

Manages chat messages and LLM streaming.

**State:**

- `messages: ChatMessage[]` - Conversation history
- `partialText: string` - Current STT partial transcript
- `isProcessing: boolean` - Processing state

**Actions:**

- `addUserMessage(text: string)` - Add user message
- `updatePartialText(text: string)` - Update STT partial
- `handleLLMStream(data: LLMStreamMessage)` - Handle LLM delta
- `handleLLMResponse(data: LLMResponseMessage)` - Handle complete response

**Usage:**

```ts
const chatStore = useChatStore()
chatStore.addUserMessage('Hello')
```

### Health Store (`useHealthStore`)

Tracks service health with timeout detection.

**State:**

- `components: HealthComponents` - Health status for all services
- `isSystemHealthy: Computed<boolean>` - Overall system health

**Actions:**

- `updateHealth(service: string, data: HealthStatus)` - Update service health
- `checkTimeouts()` - Mark stale services as unhealthy (30s timeout)

**Usage:**

```ts
const healthStore = useHealthStore()
const sttStatus = healthStore.components.stt.ok ? 'healthy' : 'unhealthy'
```

### MQTT Store (`useMqttStore`)

MQTT message log with FIFO buffering.

**State:**

- `messages: MQTTLogEntry[]` - Message history (max 200)

**Actions:**

- `addMessage(topic: string, payload: unknown)` - Add message to log
- `clearHistory()` - Clear all messages

**Usage:**

```ts
const mqttStore = useMqttStore()
mqttStore.clearHistory()
```

### UI Store (`useUIStore`)

Application UI state (drawers, status).

**State:**

- `activeDrawer: DrawerType | null` - Currently open drawer
- `listening: boolean` - Listening for speech
- `processing: boolean` - Processing audio
- `llmWriting: boolean` - LLM streaming response

**Actions:**

- `openDrawer(type: DrawerType)` - Open drawer
- `closeDrawer()` - Close active drawer
- `setListening(value: boolean)` - Update listening state
- `setProcessing(value: boolean)` - Update processing state
- `setLLMWriting(value: boolean)` - Update LLM writing state

**Usage:**

```ts
const uiStore = useUIStore()
uiStore.openDrawer('health')
```

## TypeScript Types

All MQTT message types are defined in `src/types/mqtt.ts`:

- `STTPartialMessage` / `STTFinalMessage`
- `LLMStreamMessage` / `LLMResponseMessage`
- `TTSSayMessage` / `TTSStatusMessage`
- `MemoryQueryRequest` / `MemoryResultsMessage`
- `HealthMessage` / `HealthStatus`

WebSocket envelope: `WebSocketMessage` in `src/types/websocket.ts`

UI types: `DrawerType`, `AppState` in `src/types/ui.ts`

## Development Patterns

### Adding a New Component

1. Create `.vue` file in `src/components/`
2. Use `<script setup lang="ts">` for TypeScript support
3. Define props interface with `defineProps<Props>()`
4. Use scoped styles with CSS variables (`var(--text)`, `var(--border)`, etc.)
5. Export and use in other components

### Adding MQTT Message Handler

1. Define TypeScript interface in `src/types/mqtt.ts`
2. Create type guard function (`isXXXMessage`)
3. Add routing logic in `stores/websocket.ts` → `routeMessage()`
4. Handle message in appropriate store

### Adding a New Drawer

1. Create drawer component in `src/drawers/`
2. Register in `App.vue` with `<DrawerContainer>`
3. Add button in `Toolbar.vue`
4. Handle open/close via `useUIStore()`

## Testing

```bash
# Unit tests (components, composables)
npm run test:unit

# Integration tests (stores)
npm run test:integration

# All tests with coverage
npm run test:coverage
```

Test files: `tests/unit/` and `tests/integration/`

## Architecture

- **Framework**: Vue 3 (Composition API)
- **Build Tool**: Vite 5
- **Language**: TypeScript 5 (strict mode)
- **State**: Pinia 2
- **Testing**: Vitest + Vue Test Utils
- **Styling**: Scoped CSS + CSS variables

## Resources

- [Quickstart Guide](../../../specs/004-convert-ui-web/quickstart.md)
- [Data Models](../../../specs/004-convert-ui-web/data-model.md)
- [Research & Decisions](../../../specs/004-convert-ui-web/research.md)
- [MQTT Contracts](../../../specs/004-convert-ui-web/contracts/)
