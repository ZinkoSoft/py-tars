/**
 * MQTT Message Type Contracts
 * 
 * TypeScript interfaces for all MQTT message payloads consumed by the ui-web frontend.
 * These types match the backend message schemas defined in .github/copilot-instructions.md
 * 
 * @module contracts/mqtt-messages
 */

// ============================================================================
// STT (Speech-to-Text) Messages
// ============================================================================

/**
 * Partial speech transcript (real-time, may change)
 * Topic: stt/partial
 * QoS: 0, Not retained
 */
export interface STTPartialMessage {
  text: string;
  lang?: string;
  confidence?: number;
  timestamp?: number;
  is_final: false;
}

/**
 * Final speech transcript (stable, won't change)
 * Topic: stt/final
 * QoS: 1, Not retained
 */
export interface STTFinalMessage {
  text: string;
  lang?: string;
  confidence?: number;
  timestamp?: number;
  is_final: true;
}

/**
 * Audio frequency spectrum data (FFT bins)
 * Topic: stt/audio_fft
 * QoS: 0, Not retained
 */
export interface AudioFFTMessage {
  /** FFT bins (normalized 0.0-1.0), typically 64 values */
  fft: number[];
  sample_rate?: number;
  timestamp?: number;
}

// ============================================================================
// LLM Messages
// ============================================================================

/**
 * Streaming LLM response chunk
 * Topic: llm/stream
 * QoS: 1, Not retained
 */
export interface LLMStreamMessage {
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

/**
 * Complete LLM response (after streaming or for non-streaming)
 * Topic: llm/response
 * QoS: 1, Not retained
 */
export interface LLMResponseMessage {
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
    /** Token usage statistics */
    tokens?: {
      prompt: number;
      completion: number;
      total: number;
    };
  };
}

// ============================================================================
// TTS Messages
// ============================================================================

/**
 * Text-to-speech synthesis request
 * Topic: tts/say
 * QoS: 1, Not retained
 * 
 * Note: Frontend receives this but doesn't publish (monitoring only)
 */
export interface TTSSayMessage {
  text: string;
  voice?: string;
  lang?: string;
  /** Utterance ID for aggregation */
  utt_id?: string;
  style?: string;
  /** Original STT timestamp for latency tracking */
  stt_ts?: number;
  /** True if this is a wake word acknowledgment */
  wake_ack?: boolean;
}

/**
 * TTS playback status notification
 * Topic: tts/status
 * QoS: 0, Not retained
 */
export interface TTSStatusMessage {
  event: 'speaking_start' | 'speaking_end';
  text: string;
  timestamp?: number;
  utt_id?: string;
}

// ============================================================================
// Memory Messages
// ============================================================================

/**
 * Memory retrieval query request
 * Topic: memory/query
 * QoS: 1, Not retained
 * 
 * Note: Published by frontend via /api/memory endpoint
 */
export interface MemoryQueryRequest {
  /** Query text (use "*" for most recent) */
  text: string;
  /** Number of results to return (default 25) */
  top_k?: number;
  /** Correlation ID */
  id?: string;
}

/**
 * Memory retrieval results response
 * Topic: memory/results
 * QoS: 1, Not retained
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
 * Single memory entry from retrieval
 */
export interface MemoryEntry {
  /** Similarity score (0.0-1.0, higher is better) */
  score: number;
  /** Document content */
  document: {
    text: string;
    topic?: string;
    timestamp?: number;
    [key: string]: unknown;
  };
}

// ============================================================================
// Health Messages
// ============================================================================

/**
 * Service health status
 * Topic: system/health/{service}
 * QoS: 1, Retained
 * 
 * Services: movement-esp32, stt, llm, tts, memory, camera, router, mcp-bridge
 */
export interface HealthMessage {
  /** Backend may wrap in data field or send directly */
  data?: HealthStatus;
  
  // Support unwrapped format
  ok?: boolean;
  event?: string;
  err?: string;
  timestamp?: number;
}

/**
 * Health status data structure
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

// ============================================================================
// Type Guards for Runtime Validation
// ============================================================================

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
 * Type guard for STT partial message
 */
export function isSTTPartialMessage(payload: unknown): payload is STTPartialMessage {
  return (
    typeof payload === 'object' &&
    payload !== null &&
    'text' in payload &&
    typeof (payload as any).text === 'string' &&
    (payload as any).is_final === false
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
    'delta' in (payload as any).data &&
    'id' in (payload as any).data
  );
}

/**
 * Type guard for LLM response message
 */
export function isLLMResponseMessage(payload: unknown): payload is LLMResponseMessage {
  return (
    typeof payload === 'object' &&
    payload !== null &&
    'data' in payload &&
    typeof (payload as any).data === 'object' &&
    'id' in (payload as any).data &&
    ('reply' in (payload as any).data || 'error' in (payload as any).data)
  );
}

/**
 * Type guard for TTS say message
 */
export function isTTSSayMessage(payload: unknown): payload is TTSSayMessage {
  return (
    typeof payload === 'object' &&
    payload !== null &&
    'text' in payload &&
    typeof (payload as any).text === 'string'
  );
}

/**
 * Type guard for TTS status message
 */
export function isTTSStatusMessage(payload: unknown): payload is TTSStatusMessage {
  return (
    typeof payload === 'object' &&
    payload !== null &&
    'event' in payload &&
    typeof (payload as any).event === 'string' &&
    ['speaking_start', 'speaking_end'].includes((payload as any).event)
  );
}

/**
 * Type guard for memory results message
 */
export function isMemoryResultsMessage(payload: unknown): payload is MemoryResultsMessage {
  return (
    typeof payload === 'object' &&
    payload !== null &&
    'results' in payload &&
    Array.isArray((payload as any).results)
  );
}

/**
 * Type guard for audio FFT message
 */
export function isAudioFFTMessage(payload: unknown): payload is AudioFFTMessage {
  return (
    typeof payload === 'object' &&
    payload !== null &&
    'fft' in payload &&
    Array.isArray((payload as any).fft)
  );
}

/**
 * Type guard for health message
 */
export function isHealthMessage(payload: unknown): payload is HealthMessage {
  if (typeof payload !== 'object' || payload === null) return false;
  
  // Check for wrapped format
  if ('data' in payload && typeof (payload as any).data === 'object') {
    return 'ok' in (payload as any).data && typeof (payload as any).data.ok === 'boolean';
  }
  
  // Check for unwrapped format
  return 'ok' in payload && typeof (payload as any).ok === 'boolean';
}

// ============================================================================
// Topic Patterns
// ============================================================================

/**
 * MQTT topic patterns for routing
 */
export const MQTT_TOPICS = {
  STT_PARTIAL: 'stt/partial',
  STT_FINAL: 'stt/final',
  STT_AUDIO_FFT: 'stt/audio_fft',
  LLM_STREAM: 'llm/stream',
  LLM_RESPONSE: 'llm/response',
  TTS_SAY: 'tts/say',
  TTS_STATUS: 'tts/status',
  MEMORY_QUERY: 'memory/query',
  MEMORY_RESULTS: 'memory/results',
  HEALTH_PREFIX: 'system/health/',
} as const;

/**
 * Check if topic matches pattern
 */
export function matchesTopic(topic: string, pattern: string): boolean {
  if (pattern.endsWith('#')) {
    return topic.startsWith(pattern.slice(0, -1));
  }
  if (pattern.endsWith('+')) {
    const base = pattern.slice(0, -1);
    return topic.startsWith(base) && !topic.slice(base.length).includes('/');
  }
  return topic === pattern;
}
