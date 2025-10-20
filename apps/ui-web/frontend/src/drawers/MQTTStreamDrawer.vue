<template>
  <div class="mqtt-drawer">
    <Panel>
      <template #header>
        <div class="drawer-header">
          <h3 class="panel__title">MQTT Stream</h3>
          <Button variant="secondary" size="small" @click="mqttStore.clearLog"> Clear </Button>
        </div>
      </template>

      <div v-if="mqttStore.log.length === 0" class="empty-state">
        <p>No MQTT messages yet. Messages will appear here as they arrive.</p>
      </div>

      <div v-else class="message-list">
        <div v-for="entry in mqttStore.log" :key="entry.id" class="message-entry">
          <div class="message-header">
            <span class="message-topic">{{ entry.topic }}</span>
            <span class="message-timestamp">{{ formatTime(entry.timestamp) }}</span>
          </div>
          <CodeBlock :code="entry.payload" language="json" :maxLines="10" />
        </div>
      </div>
    </Panel>
  </div>
</template>

<script setup lang="ts">
import Panel from '../components/Panel.vue'
import Button from '../components/Button.vue'
import CodeBlock from '../components/CodeBlock.vue'
import { useMqttStore } from '../stores/mqtt'

const mqttStore = useMqttStore()

const formatTime = (timestamp: number): string => {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('en-US', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}
</script>

<style scoped>
.mqtt-drawer {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.empty-state {
  padding: 2rem 1rem;
  text-align: center;
}

.empty-state p {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 0.875rem;
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.message-entry {
  padding: 0.75rem;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 4px;
}

.message-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.message-topic {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-primary);
  font-family: 'Courier New', monospace;
}

.message-timestamp {
  font-size: 0.75rem;
  color: var(--color-text-secondary);
}
</style>
