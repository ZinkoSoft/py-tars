<template>
  <div class="toolbar">
    <button class="btn health" :title="healthTitle" @click="$emit('open-drawer', 'health')">
      Health
      <span class="health-indicator" :style="{ background: healthColor }"></span>
    </button>
    <button class="btn" @click="$emit('open-drawer', 'mic')">Microphone</button>
    <button class="btn" @click="$emit('open-drawer', 'memory')">Memory</button>
    <button class="btn" @click="$emit('open-drawer', 'stream')">
      MQTT Stream
      <span v-if="mqttCount > 0" class="badge">{{ mqttCount }}</span>
    </button>
    <button class="btn" @click="$emit('open-drawer', 'camera')">Camera</button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useHealthStore } from '../stores/health'
import { useMqttStore } from '../stores/mqtt'
import type { DrawerType } from '../types/ui'

defineEmits<{
  'open-drawer': [drawer: DrawerType]
}>()

const healthStore = useHealthStore()
const mqttStore = useMqttStore()

const healthColor = computed(() => (healthStore.allHealthy ? '#4caf50' : '#f44336'))

const healthTitle = computed(() => {
  const ok = healthStore.healthyCount
  const total = healthStore.totalCount
  return `System Health: ${ok}/${total} components online`
})

const mqttCount = computed(() => mqttStore.messageCount)
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 8px;
}

.btn {
  background: transparent;
  color: var(--muted);
  border: 1px solid var(--border);
  padding: 6px 10px;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  font-size: 13px;
  transition: all var(--transition-fast);
  display: flex;
  align-items: center;
  gap: 6px;
}

.btn:hover {
  color: #fff;
  border-color: #2a3469;
  background: #0b132e;
}

.health-indicator {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  transition: background var(--transition-fast);
}

.badge {
  background: var(--accent);
  color: var(--bg);
  font-size: 11px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 10px;
  line-height: 1;
}
</style>
