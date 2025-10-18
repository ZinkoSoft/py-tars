/**
 * UI State Types
 *
 * TypeScript interfaces for UI state management (drawers, modals, etc.)
 *
 * @module types/ui
 */

/**
 * Drawer types available in the application
 */
export type DrawerType = 'mic' | 'memory' | 'stream' | 'camera' | 'health' | 'config'

/**
 * Drawer visibility state
 */
export interface DrawerState {
  /** Currently open drawer (null if none) */
  activeDrawer: DrawerType | null

  /** Backdrop is visible */
  backdropVisible: boolean
}

/**
 * Application state
 */
export interface AppState {
  /** STT is actively listening */
  listening: boolean

  /** STT is processing audio */
  processing: boolean

  /** LLM is writing response */
  llmWriting: boolean

  /** Current status text */
  statusText: string
}

/**
 * Chat bubble role
 */
export type ChatRole = 'tars' | 'user'

/**
 * Chat message
 */
export interface ChatMessage {
  /** Message ID (correlation ID or generated) */
  id: string

  /** Message role */
  role: ChatRole

  /** Message text */
  text: string

  /** Message metadata (e.g., "TARS", "You") */
  meta?: string

  /** Message timestamp */
  timestamp: number

  /** True if message is being streamed */
  streaming?: boolean

  /** Last sequence number (for LLM streaming) */
  lastSeq?: number

  /** Number of TTS chunks received (for wake acknowledgments) */
  ttsChunks?: number
}
