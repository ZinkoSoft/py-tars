/**
 * Health Store
 *
 * Tracks service health status with timeout detection (30s).
 * Provides aggregated system health and individual component status.
 *
 * @module stores/health
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  type ServiceComponent,
  type ServiceComponentId,
  type SystemHealth,
  DEFAULT_SERVICE_COMPONENTS,
  extractComponentFromTopic,
  isComponentTimedOut,
  updateComponentHealth
} from '../types/health'
import { isHealthMessage } from '../types/mqtt'

export const useHealthStore = defineStore('health', () => {
  // State
  const components = ref<Record<ServiceComponentId, ServiceComponent>>(
    JSON.parse(JSON.stringify(DEFAULT_SERVICE_COMPONENTS))
  )
  const checkInterval = ref<number | null>(null)

  // Computed
  const allHealthy = computed(() => Object.values(components.value).every(comp => comp.ok))

  const healthyCount = computed(
    () => Object.values(components.value).filter(comp => comp.ok).length
  )

  const totalCount = computed(() => Object.keys(components.value).length)

  const systemHealth = computed<SystemHealth>(() => ({
    allHealthy: allHealthy.value,
    healthyCount: healthyCount.value,
    totalCount: totalCount.value,
    components: components.value
  }))

  const componentsList = computed(() => Object.values(components.value))

  // Actions
  function handleHealthMessage(topic: string, payload: unknown): void {
    if (!isHealthMessage(payload)) {
      console.warn('[Health] Invalid health message:', payload)
      return
    }

    // Try to extract component ID from source field first (new structured format)
    let componentId: string | null = null
    if ('source' in payload && typeof payload.source === 'string') {
      componentId = extractComponentFromTopic(`system/health/${payload.source}`)
    }
    
    // Fallback to extracting from topic (old format or direct subscriptions)
    if (!componentId) {
      componentId = extractComponentFromTopic(topic)
    }
    
    if (!componentId) {
      console.warn('[Health] Unknown component in topic:', topic, 'payload:', payload)
      return
    }

    const component = components.value[componentId]
    if (!component) {
      console.warn('[Health] Component not found:', componentId)
      return
    }

    // Extract health status (handle both wrapped and unwrapped formats)
    const healthStatus = payload.data ?? {
      ok: payload.ok ?? false,
      event: payload.event,
      err: payload.err
    }

    updateComponentHealth(component, healthStatus)

    console.log(
      `[Health] ${componentId}: ok=${component.ok}, event=${healthStatus.event ?? 'none'}`
    )
  }

  function checkTimeouts(): void {
    const now = Date.now()
    let hasChanges = false

    Object.values(components.value).forEach(component => {
      if (component.ok && isComponentTimedOut(component, now)) {
        component.ok = false
        component.error = 'timeout'
        hasChanges = true
        console.warn(`[Health] ${component.id} timed out`)
      }
    })

    if (hasChanges) {
      // Trigger reactivity
      components.value = { ...components.value }
    }
  }

  function startTimeoutMonitoring(): void {
    if (checkInterval.value !== null) {
      console.warn('[Health] Timeout monitoring already running')
      return
    }

    checkInterval.value = window.setInterval(() => {
      checkTimeouts()
    }, 5000) // Check every 5 seconds

    console.log('[Health] Timeout monitoring started')
  }

  function stopTimeoutMonitoring(): void {
    if (checkInterval.value !== null) {
      clearInterval(checkInterval.value)
      checkInterval.value = null
      console.log('[Health] Timeout monitoring stopped')
    }
  }

  function reset(): void {
    components.value = JSON.parse(JSON.stringify(DEFAULT_SERVICE_COMPONENTS))
  }

  // Start monitoring on store creation
  startTimeoutMonitoring()

  return {
    // State
    components,
    componentsList,

    // Computed
    allHealthy,
    healthyCount,
    totalCount,
    systemHealth,

    // Actions
    handleHealthMessage,
    checkTimeouts,
    startTimeoutMonitoring,
    stopTimeoutMonitoring,
    reset
  }
})
