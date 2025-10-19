/**
 * WebSocket Communication Contracts
 *
 * TypeScript interfaces for WebSocket messages between browser and backend.
 * The backend FastAPI WebSocket bridge wraps MQTT messages in these envelopes.
 *
 * @module types/websocket
 */

/**
 * WebSocket message envelope from backend bridge
 *
 * All MQTT messages received from the backend are wrapped in this structure.
 * The payload contains the original MQTT message content (JSON parsed).
 */
export interface WebSocketMessage {
  /** MQTT topic as string (e.g., "stt/final", "llm/stream") */
  topic: string

  /** Parsed MQTT payload (JSON object) */
  payload: unknown
}

/**
 * WebSocket connection states
 */
export enum WebSocketState {
  /** Connection is being established */
  CONNECTING = 'connecting',
  /** Connection is open and ready */
  CONNECTED = 'connected',
  /** Connection is closing */
  CLOSING = 'closing',
  /** Connection is closed */
  CLOSED = 'closed',
  /** Connection failed or was disconnected */
  DISCONNECTED = 'disconnected'
}

/**
 * WebSocket connection configuration
 */
export interface WebSocketConfig {
  /** WebSocket URL (computed from window.location) */
  url: string

  /** Reconnection enabled */
  reconnect: boolean

  /** Reconnection delay in milliseconds */
  reconnectDelay: number

  /** Maximum reconnection attempts (0 = unlimited) */
  maxReconnectAttempts: number
}

/**
 * WebSocket connection info
 */
export interface WebSocketConnectionInfo {
  /** Current connection state */
  state: WebSocketState

  /** Connection is ready to send/receive */
  connected: boolean

  /** Number of reconnection attempts made */
  reconnectAttempts: number

  /** Last connection error */
  lastError: Error | null

  /** Connection established timestamp */
  connectedAt: number | null

  /** Connection closed timestamp */
  disconnectedAt: number | null
}

/**
 * WebSocket event types
 */
export enum WebSocketEvent {
  /** Connection opened */
  OPEN = 'open',
  /** Message received */
  MESSAGE = 'message',
  /** Connection closed */
  CLOSE = 'close',
  /** Connection error */
  ERROR = 'error',
  /** Reconnection attempt started */
  RECONNECTING = 'reconnecting',
  /** Reconnection successful */
  RECONNECTED = 'reconnected',
  /** Reconnection failed (max attempts reached) */
  RECONNECT_FAILED = 'reconnect_failed'
}

/**
 * Type guard for WebSocket message envelope
 */
export function isWebSocketMessage(msg: unknown): msg is WebSocketMessage {
  return (
    typeof msg === 'object' &&
    msg !== null &&
    'topic' in msg &&
    typeof (msg as WebSocketMessage).topic === 'string' &&
    'payload' in msg
  )
}

/**
 * Parse WebSocket message from raw data
 */
export function parseWebSocketMessage(data: string | ArrayBuffer | Blob): WebSocketMessage | null {
  try {
    let textData: string

    if (data instanceof ArrayBuffer) {
      const decoder = new TextDecoder()
      textData = decoder.decode(data)
    } else if (data instanceof Blob) {
      // Blob needs async parsing - not supported in this sync function
      console.error('Blob WebSocket messages not supported')
      return null
    } else {
      textData = data
    }

    const parsed = JSON.parse(textData)

    if (isWebSocketMessage(parsed)) {
      return parsed
    }

    console.warn('Invalid WebSocket message format:', parsed)
    return null
  } catch (error) {
    console.error('Failed to parse WebSocket message:', error)
    return null
  }
}

/**
 * WebSocket connection builder
 *
 * Constructs WebSocket URL based on current page protocol and host
 */
export function buildWebSocketUrl(path: string = '/ws'): string {
  // In development mode (Vite dev server), use the backend server IP
  const isDev = import.meta.env.DEV
  
  if (isDev) {
    return `ws://192.168.1.205:5010${path}`
  }
  
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'  
  const host = window.location.host
  return `${protocol}//${host}${path}`
}

/**
 * Default WebSocket configuration
 */
export const DEFAULT_WEBSOCKET_CONFIG: WebSocketConfig = {
  url: buildWebSocketUrl('/ws'),
  reconnect: true,
  reconnectDelay: 1000, // 1 second
  maxReconnectAttempts: 0 // Unlimited
}
