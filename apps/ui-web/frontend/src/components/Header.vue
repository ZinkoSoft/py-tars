<template>
  <header class="app-header">
    <h1>TARS Chat</h1>
    <div class="status-group">
      <div class="connection-status">
        <span class="status-indicator" :class="{ connected: isConnected }"></span>
        <span class="status-text">{{ connectionStatus }}</span>
      </div>
      <div class="health-status">
        <span class="status-indicator" :class="{ healthy: healthStore.allHealthy }"></span>
        <span class="status-text">
          {{ healthStore.healthyCount }}/{{ healthStore.totalCount }} Services
        </span>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useWebSocketStore } from '../stores/websocket'
import { useHealthStore } from '../stores/health'

const websocketStore = useWebSocketStore()
const healthStore = useHealthStore()

const isConnected = computed(() => websocketStore.connected)

const connectionStatus = computed(() => (isConnected.value ? 'Connected' : 'Disconnected'))
</script>

<style scoped>
.app-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  background: #0c1020;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.app-header h1 {
  margin: 0;
  font-size: 16px;
  color: var(--muted);
  font-weight: 600;
}

.status-group {
  display: flex;
  align-items: center;
  gap: 16px;
}

.connection-status,
.health-status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--muted);
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--error);
  transition: background var(--transition-fast);
}

.status-indicator.connected,
.status-indicator.healthy {
  background: var(--success);
}

.status-text {
  font-weight: 500;
}
</style>
