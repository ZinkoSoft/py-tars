<template>
  <div class="status-line">
    <span class="dot" :style="{ background: dotColor }"></span>
    {{ statusText }}
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useUIStore } from '../stores/ui'
import { useHealthStore } from '../stores/health'

const uiStore = useUIStore()
const healthStore = useHealthStore()

const statusText = computed(() => {
  const statuses: string[] = []

  if (uiStore.listening) statuses.push('Listening…')
  if (uiStore.processing) statuses.push('Processing audio…')
  if (uiStore.llmWriting) statuses.push('TARS is writing…')

  // Add system health status
  const healthyCount = healthStore.healthyCount
  const totalCount = healthStore.totalCount
  const healthStatus = healthStore.allHealthy
    ? 'All systems online'
    : `${healthyCount}/${totalCount} systems online`

  statuses.push(healthStatus)

  return statuses.length ? statuses.join(' • ') : 'Idle'
})

const dotColor = computed(() => {
  if (uiStore.listening) return '#5ac8fa' // Accent blue
  if (uiStore.processing || uiStore.llmWriting) return '#ff9800' // Orange
  return healthStore.allHealthy ? '#4caf50' : '#f44336' // Green or red
})
</script>

<style scoped>
.status-line {
  padding: 10px 12px;
  font-size: 13px;
  color: var(--muted);
  display: flex;
  align-items: center;
  gap: 8px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  transition: background var(--transition-fast);
}
</style>
