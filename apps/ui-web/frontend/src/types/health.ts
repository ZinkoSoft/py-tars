/**
 * Health Status Types
 *
 * TypeScript interfaces for tracking service health status in the frontend.
 *
 * @module types/health
 */

import type { HealthStatus } from './mqtt'

/**
 * Service component identifiers
 */
export type ServiceComponentId =
  | 'esp32'
  | 'stt'
  | 'llm'
  | 'tts'
  | 'memory'
  | 'camera'
  | 'router'

/**
 * Service component health information
 */
export interface ServiceComponent {
  /** Component identifier */
  id: ServiceComponentId

  /** Display name */
  name: string

  /** Current health status */
  ok: boolean

  /** Last ping timestamp (null if never received) */
  lastPing: number | null

  /** Error message or event description */
  error: string | null
}

/**
 * Overall system health status
 */
export interface SystemHealth {
  /** All components are healthy */
  allHealthy: boolean

  /** Number of healthy components */
  healthyCount: number

  /** Total number of components */
  totalCount: number

  /** Component health details */
  components: Record<ServiceComponentId, ServiceComponent>
}

/**
 * Health timeout configuration
 * Services publish retained health messages at startup, not periodic heartbeats.
 * This timeout is conservative to handle service restarts gracefully.
 */
export const HEALTH_TIMEOUT_MS = 300000 // 5 minutes

/**
 * Default service components
 */
export const DEFAULT_SERVICE_COMPONENTS: Record<ServiceComponentId, ServiceComponent> = {
  esp32: {
    id: 'esp32',
    name: 'ESP32 Movement',
    ok: false,
    lastPing: null,
    error: null
  },
  stt: {
    id: 'stt',
    name: 'Speech-to-Text',
    ok: false,
    lastPing: null,
    error: null
  },
  llm: {
    id: 'llm',
    name: 'Language Model',
    ok: false,
    lastPing: null,
    error: null
  },
  tts: {
    id: 'tts',
    name: 'Text-to-Speech',
    ok: false,
    lastPing: null,
    error: null
  },
  memory: {
    id: 'memory',
    name: 'Memory Service',
    ok: false,
    lastPing: null,
    error: null
  },
  camera: {
    id: 'camera',
    name: 'Camera Service',
    ok: false,
    lastPing: null,
    error: null
  },
  router: {
    id: 'router',
    name: 'Message Router',
    ok: false,
    lastPing: null,
    error: null
  }
}

/**
 * Map MQTT health topic component names to ServiceComponentId
 */
export const HEALTH_TOPIC_MAP: Record<string, ServiceComponentId> = {
  'movement-esp32': 'esp32',
  esp32: 'esp32',
  stt: 'stt',
  'tars-stt': 'stt',
  llm: 'llm',
  'tars-llm': 'llm',
  'llm-worker': 'llm',
  tts: 'tts',
  'tars-tts': 'tts',
  memory: 'memory',
  'tars-memory': 'memory',
  'memory-worker': 'memory',
  camera: 'camera',
  router: 'router',
  'tars-router': 'router',
  movement: 'esp32',
  'tars-movement': 'esp32',
  'wake-activation': 'esp32'
}

/**
 * Extract component ID from health topic
 *
 * @param topic - Health topic (e.g., "system/health/stt")
 * @returns Component ID or null if not recognized
 */
export function extractComponentFromTopic(topic: string): ServiceComponentId | null {
  const parts = topic.split('/')
  const component = parts[parts.length - 1]

  if (!component) return null

  return HEALTH_TOPIC_MAP[component] ?? null
}

/**
 * Check if a component has timed out
 *
 * @param component - Service component
 * @param now - Current timestamp
 * @returns True if component has timed out
 */
export function isComponentTimedOut(component: ServiceComponent, now: number): boolean {
  if (!component.lastPing) return false
  return now - component.lastPing > HEALTH_TIMEOUT_MS
}

/**
 * Update component health from MQTT message
 *
 * @param component - Service component to update
 * @param healthStatus - Health status from MQTT
 */
export function updateComponentHealth(
  component: ServiceComponent,
  healthStatus: HealthStatus
): void {
  component.ok = healthStatus.ok
  component.lastPing = Date.now()
  component.error = healthStatus.err ?? (healthStatus.ok ? null : (healthStatus.event ?? 'unknown'))
}
