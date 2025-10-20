# Phase 1: Data Models - Convert ui-web to Vue.js TypeScript Application

**Feature**: 004-convert-ui-web  
**Date**: 2025-10-17  
**Status**: Complete

## Overview

This document defines all TypeScript data models, interfaces, and types for the Vue.js frontend application. Models are organized by domain and match the existing backend MQTT message schemas.

---

## 1. WebSocket Message Envelope

The backend WebSocket bridge wraps all MQTT messages in this envelope.

```typescript
/**
 * WebSocket message envelope from backend bridge
 */
export interface WebSocketMessage {
  /** MQTT topic as string (e.g., "stt/final", "llm/stream") */
  topic: string;
  
  /** Parsed MQTT payload (JSON object) */
  payload: unknown;
}
```

---

## 2. STT (Speech-to-Text) Messages

### STT Partial Transcript

```typescript
/**
 * Partial speech transcript (real-time, may change)
 * Topic: stt/partial
 */
export interface STTPartialMessage {
  /** Partial transcript text */
  text: string;
  
  /** Language code (optional) */
  lang?: string;
  
  /** Confidence score 0.0-1.0 (optional) */
  confidence?: number;
  
  /** Unix timestamp (optional) */
  timestamp?: number;
  
  /** Always false for partials */
  is_final: false;
}
```

### STT Final Transcript

```typescript
/**
 * Final speech transcript (stable, won't change)
 * Topic: stt/final
 */
export interface STTFinalMessage {
  /** Final transcript text */
  text: string;
  
  /** Language code (optional) */
  lang?: string;
  
  /** Confidence score 0.0-1.0 (optional) */
  confidence?: number;
  
  /** Unix timestamp (optional) */
  timestamp?: number;
  
  /** Always true for final */
  is_final: true;
}
```

### Audio Spectrum (FFT)

```typescript
/**
 * Audio frequency spectrum data
 * Topic: stt/audio_fft
 */
export interface AudioFFTMessage {
  /** FFT bins (normalized 0.0-1.0), typically 64 values */
  fft: number[];
  
  /** Sample rate (optional) */
  sample_rate?: number;
  
  /** Timestamp (optional) */
  timestamp?: number;
}
```

---

## 3. LLM Messages

### LLM Stream Delta

```typescript
/**
 * Streaming LLM response chunk
 * Topic: llm/stream
 */
export interface LLMStreamMessage {
  /** Container for stream data */
  data: {
    /** Correlation ID for this LLM request */
    id: string;
    
    /** Sequence number (incremental, starting at 1) */
    seq: number;
    
    /** Text delta to append to response */
    delta: string;
    
    /** True if this is the last chunk */
    done: boolean;
  };
}
```

### LLM Complete Response

```typescript
/**
 * Complete LLM response (after streaming or for non-streaming)
 * Topic: llm/response
 */
export interface LLMResponseMessage {
  /** Container for response data */
  data: {
    /** Correlation ID matching request */
    id: string;
    
    /** Complete reply text */
    reply?: string;
    
    /** Error message if request failed */
    error?: string;
    
    /** Provider name (e.g., "openai") */
    provider?: string;
    
    /** Model name (e.g., "gpt-4") */
    model?: string;
    
    /** Token usage statistics (optional) */
    tokens?: {
      prompt: number;
      completion: number;
      total: number;
    };
  };
}
```

---

## 4. TTS Messages

### TTS Say Request

```typescript
/**
 * Text-to-speech synthesis request
 * Topic: tts/say
 */
export interface TTSSayMessage {
  /** Text to synthesize */
  text: string;
  
  /** Voice ID (optional) */
  voice?: string;
  
  /** Language code (optional) */
  lang?: string;
  
  /** Utterance ID for aggregation (optional) */
  utt_id?: string;
  
  /** Speaking style (optional) */
  style?: string;
  
  /** Original STT timestamp for latency tracking (optional) */
  stt_ts?: number;
  
  /** True if this is a wake word acknowledgment (optional) */
  wake_ack?: boolean;
}
```

### TTS Status Event

```typescript
/**
 * TTS playback status notification
 * Topic: tts/status
 */
export interface TTSStatusMessage {
  /** Event type */
  event: 'speaking_start' | 'speaking_end';
  
  /** Text being spoken */
  text: string;
  
  /** Timestamp of event */
  timestamp?: number;
  
  /** Utterance ID (optional) */
  utt_id?: string;
}
```

---

## 5. Memory Messages

### Memory Query Request

```typescript
/**
 * Memory retrieval query
 * Topic: memory/query
 */
export interface MemoryQueryRequest {
  /** Query text (use "*" for most recent) */
  text: string;
  
  /** Number of results to return (default 25) */
  top_k?: number;
  
  /** Correlation ID (optional) */
  id?: string;
}
```

### Memory Results Response

```typescript
/**
 * Memory retrieval results
 * Topic: memory/results
 */
export interface MemoryResultsMessage {
  /** Original query text */
  query: string;
  
  /** Number of results requested */
  k: number;
  
  /** Retrieved memory entries */
  results: MemoryEntry[];
}

/**
 * Single memory entry
 */
export interface MemoryEntry {
  /** Similarity score (0.0-1.0, higher is better) */
  score: number;
  
  /** Document content */
  document: {
    /** Document text */
    text: string;
    
    /** Source topic (optional) */
    topic?: string;
    
    /** Timestamp (optional) */
    timestamp?: number;
    
    /** Additional metadata (optional) */
    [key: string]: unknown;
  };
}
```

---

## 6. Health Messages

### Health Status

```typescript
/**
 * Service health status
 * Topic: system/health/{service}
 * Retained message
 */
export interface HealthMessage {
  /** Container for health data (backend may wrap or send directly) */
  data?: HealthStatus;
  
  // Support unwrapped format as well
  ok?: boolean;
  event?: string;
  err?: string;
  timestamp?: number;
}

/**
 * Health status data
 */
export interface HealthStatus {
  /** Service is healthy */
  ok: boolean;
  
  /** Status event description (e.g., "ready", "processing", "error") */
  event?: string;
  
  /** Error message if unhealthy */
  err?: string;
  
  /** Timestamp of status update */
  timestamp?: number;
}
```

### Health Component State

```typescript
/**
 * Frontend health tracking for a service component
 */
export interface HealthComponent {
  /** Display name */
  name: string;
  
  /** Current health status */
  ok: boolean;
  
  /** Last received ping timestamp (Date.now()) */
  lastPing: number | null;
  
  /** Error message if unhealthy */
  error: string | null;
}

/**
 * Map of all tracked health components
 */
export type HealthComponents = {
  esp32: HealthComponent;
  stt: HealthComponent;
  llm: HealthComponent;
  tts: HealthComponent;
  memory: HealthComponent;
  camera: HealthComponent;
  router: HealthComponent;
  'mcp-bridge': HealthComponent;
};
```

---

## 7. Chat Domain Models

### Chat Message

```typescript
/**
 * Chat message in the conversation log
 */
export interface ChatMessage {
  /** Unique ID for this message */
  id: string;
  
  /** Message role */
  role: 'user' | 'tars';
  
  /** Message text content */
  text: string;
  
  /** Display metadata (e.g., "You", "TARS") */
  meta: string;
  
  /** Creation timestamp */
  timestamp: number;
  
  /** For assistant messages: LLM stream state */
  streamState?: {
    /** Last sequence number received */
    lastSeq: number;
    
    /** Number of TTS chunks received */
    ttsChunks: number;
  };
}
```

### Assistant Message Aggregation

```typescript
/**
 * Tracks ongoing assistant message construction
 * Used to aggregate LLM streams and TTS chunks
 */
export interface AssistantMessageEntry {
  /** Message ID (correlation ID from LLM) */
  id: string;
  
  /** Accumulated text */
  text: string;
  
  /** Last sequence number from LLM stream */
  lastSeq: number;
  
  /** Number of TTS chunks received for this message */
  ttsChunks: number;
  
  /** Reference to DOM node for live updates (legacy pattern) */
  node?: HTMLElement;
}
```

---

## 8. UI State Models

### Drawer State

```typescript
/**
 * Available drawer types
 */
export type DrawerType = 'mic' | 'memory' | 'stream' | 'camera' | 'health';

/**
 * Drawer visibility state
 */
export interface DrawerState {
  /** Currently open drawer (null if all closed) */
  current: DrawerType | null;
  
  /** Backdrop visibility */
  backdropVisible: boolean;
}
```

### Application State

```typescript
/**
 * Overall application status
 */
export interface AppState {
  /** Listening for speech input */
  listening: boolean;
  
  /** Processing audio (STT complete, waiting for LLM) */
  processing: boolean;
  
  /** LLM is actively streaming response */
  llmWriting: boolean;
  
  /** WebSocket connection status */
  connected: boolean;
}
```

---

## 9. MQTT Stream Log Models

### MQTT Log Entry

```typescript
/**
 * MQTT message log entry for the Stream drawer
 */
export interface MQTTLogEntry {
  /** MQTT topic */
  topic: string;
  
  /** Timestamp (Date.now()) */
  ts: number;
  
  /** Parsed payload (original object) */
  payload: unknown;
  
  /** Formatted payload string (JSON pretty-printed) */
  payloadText: string;
  
  /** WebSocket envelope (optional, for debugging) */
  envelope?: WebSocketMessage;
  
  /** Formatted envelope string (optional) */
  envelopeText?: string;
}
```

---

## 10. Component Props & Emits

### Common Component Props

```typescript
/**
 * Button component props
 */
export interface ButtonProps {
  /** Button label text */
  label: string;
  
  /** Visual variant */
  variant?: 'default' | 'primary' | 'danger';
  
  /** Disabled state */
  disabled?: boolean;
}

/**
 * Panel component props
 */
export interface PanelProps {
  /** Panel title (optional) */
  title?: string;
  
  /** Additional CSS classes */
  className?: string;
}

/**
 * Status indicator props
 */
export interface StatusIndicatorProps {
  /** Status label */
  label: string;
  
  /** Status type */
  status: 'healthy' | 'unhealthy' | 'unknown';
}

/**
 * Code block props
 */
export interface CodeBlockProps {
  /** Code content */
  code: string;
  
  /** Language for syntax highlighting (default: json) */
  language?: string;
  
  /** Max lines before scrolling */
  maxLines?: number;
}
```

### Chat Component Props

```typescript
/**
 * Chat bubble props
 */
export interface ChatBubbleProps {
  /** Message role */
  role: 'user' | 'tars';
  
  /** Message text */
  text: string;
  
  /** Metadata label (optional) */
  meta?: string;
}

/**
 * Chat log props
 */
export interface ChatLogProps {
  /** Array of chat messages */
  messages: ChatMessage[];
  
  /** Auto-scroll to bottom on new messages */
  autoScroll?: boolean;
}

/**
 * Composer emits
 */
export interface ComposerEmits {
  /** User submitted a message */
  (e: 'submit', text: string): void;
}
```

### Drawer Component Props

```typescript
/**
 * Drawer container props
 */
export interface DrawerContainerProps {
  /** Drawer type ID */
  type: DrawerType;
  
  /** Drawer title */
  title: string;
  
  /** Is drawer currently open */
  isOpen: boolean;
}

/**
 * Drawer container emits
 */
export interface DrawerContainerEmits {
  /** User requested drawer close */
  (e: 'close'): void;
}
```

---

## 11. Validation Rules

While TypeScript provides compile-time safety, runtime validation is needed for WebSocket messages:

```typescript
/**
 * Type guard for WebSocket message envelope
 */
export function isWebSocketMessage(msg: unknown): msg is WebSocketMessage {
  return (
    typeof msg === 'object' &&
    msg !== null &&
    'topic' in msg &&
    typeof (msg as any).topic === 'string' &&
    'payload' in msg
  );
}

/**
 * Type guard for STT final message
 */
export function isSTTFinalMessage(payload: unknown): payload is STTFinalMessage {
  return (
    typeof payload === 'object' &&
    payload !== null &&
    'text' in payload &&
    typeof (payload as any).text === 'string' &&
    (payload as any).is_final === true
  );
}

/**
 * Type guard for LLM stream message
 */
export function isLLMStreamMessage(payload: unknown): payload is LLMStreamMessage {
  return (
    typeof payload === 'object' &&
    payload !== null &&
    'data' in payload &&
    typeof (payload as any).data === 'object' &&
    'delta' in (payload as any).data
  );
}

// Additional type guards for other message types...
```

---

## 12. State Transitions

### Chat Message Flow

```
User Input → STT Partial → STT Final → LLM Stream (seq 1..N) → TTS Say → TTS Status
                ↓              ↓               ↓                    ↓
         Update status  Add user msg   Update TARS msg      Update status
```

### Health Status Flow

```
Health Message → Parse Component → Update lastPing → Check Timeout (30s)
                                           ↓
                                   Update health indicator
                                           ↓
                                   Render health drawer
```

### Drawer State Flow

```
User Click → Check Current → Close Other → Open Requested → Show Backdrop
                                  ↓
                          Trigger transition animation
```

---

## 13. Computed Derivations

These computed values are derived from store state:

```typescript
/**
 * Overall system health (all components healthy)
 */
export const isSystemHealthy = computed(() => 
  Object.values(healthComponents).every(comp => comp.ok)
);

/**
 * Number of healthy components
 */
export const healthyCount = computed(() => 
  Object.values(healthComponents).filter(comp => comp.ok).length
);

/**
 * Current status text for display
 */
export const statusText = computed(() => {
  const parts: string[] = [];
  if (state.listening) parts.push('Listening…');
  if (state.processing) parts.push('Processing audio…');
  if (state.llmWriting) parts.push('TARS is writing…');
  return parts.length ? parts.join(' • ') : 'Idle';
});

/**
 * MQTT log message count
 */
export const mqttMessageCount = computed(() => mqttLog.length);
```

---

## Model Summary

This data model provides:

✅ **Type safety**: All MQTT messages have explicit TypeScript interfaces  
✅ **Backend compatibility**: Models match existing backend schemas from copilot-instructions.md  
✅ **Validation**: Type guards enable runtime validation at WebSocket boundary  
✅ **State management**: Clear domain models for Pinia stores  
✅ **Component contracts**: Typed props and emits for all components  
✅ **Computed derivations**: Type-safe derived state  

**Total Entities**: 25+ interfaces covering all MQTT messages, UI state, and component contracts

**Next Step**: Create API contracts (TypeScript type definitions exported as contracts)
