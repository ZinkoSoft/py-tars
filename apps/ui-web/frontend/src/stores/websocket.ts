/**
 * WebSocket Store
 *
 * Manages WebSocket connection to backend MQTT bridge with automatic reconnection.
 * Routes incoming MQTT messages to domain-specific stores.
 *
 * @module stores/websocket
 */

import { defineStore } from 'pinia'
import { ref, computed, type Ref } from 'vue'
import {
  WebSocketState,
  type WebSocketMessage,
  type WebSocketConnectionInfo,
  parseWebSocketMessage,
  DEFAULT_WEBSOCKET_CONFIG
} from '../types/websocket'
import { useChatStore } from './chat'
import { useMqttStore } from './mqtt'
import { useHealthStore } from './health'
import { useSpectrumStore } from './spectrum'
import { isAudioFFTMessage } from '../types/mqtt'

export const useWebSocketStore = defineStore('websocket', () => {
  // State
  const socket: Ref<WebSocket | null> = ref(null)
  const state = ref<WebSocketState>(WebSocketState.DISCONNECTED)
  const reconnectAttempts = ref(0)
  const lastError: Ref<Error | null> = ref(null)
  const connectedAt: Ref<number | null> = ref(null)
  const disconnectedAt: Ref<number | null> = ref(null)
  const reconnectTimeout: Ref<number | null> = ref(null)

  // Config
  const config = ref(DEFAULT_WEBSOCKET_CONFIG)

  // Computed
  const connected = computed(() => state.value === WebSocketState.CONNECTED)

  const connectionInfo = computed<WebSocketConnectionInfo>(() => ({
    state: state.value,
    connected: connected.value,
    reconnectAttempts: reconnectAttempts.value,
    lastError: lastError.value,
    connectedAt: connectedAt.value,
    disconnectedAt: disconnectedAt.value
  }))

  // Actions
  function connect(): void {
    if (socket.value?.readyState === WebSocket.OPEN) {
      console.warn('[WebSocket] Already connected')
      return
    }

    if (reconnectTimeout.value !== null) {
      clearTimeout(reconnectTimeout.value)
      reconnectTimeout.value = null
    }

    try {
      state.value = WebSocketState.CONNECTING
      const url = config.value.url
      console.log(`[WebSocket] Connecting to ${url}`)

      socket.value = new WebSocket(url)

      socket.value.onopen = handleOpen
      socket.value.onmessage = handleMessage
      socket.value.onclose = handleClose
      socket.value.onerror = handleError
    } catch (error) {
      lastError.value = error as Error
      state.value = WebSocketState.DISCONNECTED
      console.error('[WebSocket] Connection failed:', error)
      scheduleReconnect()
    }
  }

  function disconnect(): void {
    if (reconnectTimeout.value !== null) {
      clearTimeout(reconnectTimeout.value)
      reconnectTimeout.value = null
    }

    if (socket.value) {
      state.value = WebSocketState.CLOSING
      socket.value.close()
      socket.value = null
    }

    state.value = WebSocketState.CLOSED
    connectedAt.value = null
  }

  function handleOpen(): void {
    console.log('[WebSocket] Connected')
    state.value = WebSocketState.CONNECTED
    connectedAt.value = Date.now()
    reconnectAttempts.value = 0
    lastError.value = null
  }

  function handleMessage(event: MessageEvent): void {
    const message = parseWebSocketMessage(event.data)

    if (!message) {
      console.warn('[WebSocket] Failed to parse message:', event.data)
      return
    }

    routeMessage(message)
  }

  function handleClose(event: CloseEvent): void {
    console.log(`[WebSocket] Disconnected (code: ${event.code}, reason: ${event.reason})`)
    state.value = WebSocketState.DISCONNECTED
    disconnectedAt.value = Date.now()
    socket.value = null

    scheduleReconnect()
  }

  function handleError(event: Event): void {
    console.error('[WebSocket] Error:', event)
    lastError.value = new Error('WebSocket error occurred')
  }

  function scheduleReconnect(): void {
    if (!config.value.reconnect) {
      console.log('[WebSocket] Reconnection disabled')
      return
    }

    const maxAttempts = config.value.maxReconnectAttempts
    if (maxAttempts > 0 && reconnectAttempts.value >= maxAttempts) {
      console.error('[WebSocket] Max reconnection attempts reached')
      return
    }

    reconnectAttempts.value++
    const delay = config.value.reconnectDelay

    console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${reconnectAttempts.value})`)

    reconnectTimeout.value = window.setTimeout(() => {
      reconnectTimeout.value = null
      connect()
    }, delay)
  }

  function routeMessage(message: WebSocketMessage): void {
    const { topic, payload } = message

    // Record all messages in MQTT log
    const mqttStore = useMqttStore()
    mqttStore.recordMessage(topic, payload)

    // Route to domain-specific stores
    if (topic.startsWith('stt/')) {
      // Check for FFT data
      if (topic === 'stt/audio_fft' && isAudioFFTMessage(payload)) {
        const spectrumStore = useSpectrumStore()
        spectrumStore.updateFFT(payload)
      } else {
        const chatStore = useChatStore()
        chatStore.handleSTTMessage(topic, payload)
      }
    } else if (topic.startsWith('llm/')) {
      const chatStore = useChatStore()
      chatStore.handleLLMMessage(topic, payload)
    } else if (topic.startsWith('tts/')) {
      const chatStore = useChatStore()
      chatStore.handleTTSMessage(topic, payload)
    } else if (topic.startsWith('memory/')) {
      // Memory results handled by chat store for now
      const chatStore = useChatStore()
      chatStore.handleMemoryMessage(topic, payload)
    } else if (topic.startsWith('system/health/')) {
      const healthStore = useHealthStore()
      healthStore.handleHealthMessage(topic, payload)
    } else {
      console.log(`[WebSocket] Unhandled topic: ${topic}`)
    }
  }

  function updateConfig(newConfig: Partial<typeof config.value>): void {
    config.value = { ...config.value, ...newConfig }
  }

  // Auto-connect on store creation
  connect()

  return {
    // State
    state,
    connected,
    connectionInfo,
    config,

    // Actions
    connect,
    disconnect,
    updateConfig
  }
})
