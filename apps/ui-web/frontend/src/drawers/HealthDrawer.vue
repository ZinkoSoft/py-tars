<template>
  <div class="health-drawer">
    <Panel title="System Health">
      <div class="health-summary">
        <div class="summary-card">
          <span class="summary-label">Status</span>
          <span :class="['summary-value', healthStore.allHealthy ? 'healthy' : 'unhealthy']">
            {{ healthStore.allHealthy ? 'All Systems Operational' : 'Issues Detected' }}
          </span>
        </div>
        <div class="summary-card">
          <span class="summary-label">Healthy Services</span>
          <span class="summary-value">
            {{ healthStore.healthyCount }} / {{ healthStore.totalCount }}
          </span>
        </div>
      </div>

      <div class="component-list">
        <div v-for="component in componentsList" :key="component.id" class="component-item">
          <div class="component-header">
            <StatusIndicator :label="component.name" :status="getStatusIndicator(component)" />
          </div>
          <div v-if="component.error" class="component-error">
            {{ component.error }}
          </div>
          <div v-if="component.lastPing" class="component-timestamp">
            Last ping: {{ formatTimestamp(component.lastPing) }}
          </div>
        </div>
      </div>
    </Panel>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import Panel from '../components/Panel.vue'
import StatusIndicator from '../components/StatusIndicator.vue'
import { useHealthStore } from '../stores/health'
import { isComponentTimedOut, type ServiceComponent } from '../types/health'

const healthStore = useHealthStore()

const componentsList = computed(() => {
  return Object.values(healthStore.components)
})

const getStatusIndicator = (component: ServiceComponent): 'healthy' | 'unhealthy' | 'unknown' => {
  if (isComponentTimedOut(component, Date.now())) return 'unknown'
  return component.ok ? 'healthy' : 'unhealthy'
}

const formatTimestamp = (timestamp: number): string => {
  const date = new Date(timestamp)
  const now = Date.now()
  const diff = now - timestamp

  if (diff < 60000) return 'just now'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`

  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<style scoped>
.health-drawer {
  display: flex;
  flex-direction: column;
}

.health-summary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.summary-card {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 1rem;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 4px;
}

.summary-label {
  font-size: 0.75rem;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.summary-value {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--color-text);
}

.summary-value.healthy {
  color: var(--color-success);
}

.summary-value.unhealthy {
  color: var(--color-error);
}

.component-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.component-item {
  padding: 0.75rem;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 4px;
}

.component-header {
  display: flex;
  align-items: center;
  margin-bottom: 0.5rem;
}

.component-error {
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: var(--color-error);
  font-style: italic;
}

.component-timestamp {
  margin-top: 0.25rem;
  font-size: 0.75rem;
  color: var(--color-text-secondary);
}
</style>
