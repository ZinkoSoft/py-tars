/**
 * MQTT Store
 *
 * Stores and manages MQTT message log with FIFO buffer (max 200 messages).
 * Provides pretty-printed payload display and clear history action.
 *
 * @module stores/mqtt
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * MQTT log entry
 */
export interface MQTTLogEntry {
  /** Message topic */
  topic: string

  /** Message timestamp */
  timestamp: number

  /** Original payload (deep cloned) */
  payload: unknown

  /** Pretty-printed payload text */
  payloadText: string
}

const MAX_LOG_ENTRIES = 200

export const useMqttStore = defineStore('mqtt', () => {
  // State
  const log = ref<MQTTLogEntry[]>([])

  // Computed
  const messageCount = computed(() => log.value.length)

  const summary = computed(() => {
    const count = messageCount.value
    return `${count} message${count === 1 ? '' : 's'}`
  })

  // Actions
  function recordMessage(topic: string, payload: unknown): void {
    const entry: MQTTLogEntry = {
      topic: topic || '(unknown)',
      timestamp: Date.now(),
      payload: cloneDeep(payload),
      payloadText: prettify(payload)
    }

    log.value.push(entry)

    // Maintain FIFO buffer
    if (log.value.length > MAX_LOG_ENTRIES) {
      log.value.splice(0, log.value.length - MAX_LOG_ENTRIES)
    }
  }

  function clearLog(): void {
    log.value = []
  }

  // Helper functions
  function cloneDeep(value: unknown): unknown {
    if (value === undefined || value === null) return value

    try {
      // Use structuredClone if available (modern browsers)
      if (typeof structuredClone === 'function') {
        return structuredClone(value)
      }
    } catch {
      // Fall through to JSON method
    }

    try {
      return JSON.parse(JSON.stringify(value))
    } catch {
      return value
    }
  }

  function prettify(value: unknown): string {
    if (value === undefined) return 'undefined'
    if (value === null) return 'null'

    if (typeof value === 'string') {
      return value.length > 4000 ? value.slice(0, 4000) + '\n… (truncated)' : value
    }

    try {
      const text = JSON.stringify(value, null, 2)
      return text.length > 4000 ? text.slice(0, 4000) + '\n… (truncated)' : text
    } catch {
      return String(value)
    }
  }

  return {
    // State
    log,
    messageCount,
    summary,

    // Actions
    recordMessage,
    clearLog
  }
})
