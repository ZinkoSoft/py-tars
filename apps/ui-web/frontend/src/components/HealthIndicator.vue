<template>
  <div class="health-indicator" :class="healthClass" :title="healthTooltip">
    <span class="health-dot"></span>
    <span class="health-text">{{ healthText }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

interface Props {
  isHealthy: boolean;
  lastUpdate?: Date;
  serviceName?: string;
}

const props = withDefaults(defineProps<Props>(), {
  isHealthy: true,
  serviceName: 'Config Manager',
});

// Computed
const healthClass = computed(() => {
  return props.isHealthy ? 'health-healthy' : 'health-unhealthy';
});

const healthText = computed(() => {
  return props.isHealthy ? 'Healthy' : 'Unhealthy';
});

const healthTooltip = computed(() => {
  const status = props.isHealthy ? 'Healthy' : 'Unhealthy';
  const time = props.lastUpdate ? formatTimestamp(props.lastUpdate) : 'Unknown';
  return `${props.serviceName}: ${status} (Last update: ${time})`;
});

// Methods
function formatTimestamp(date: Date): string {
  try {
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSecs = Math.floor(diffMs / 1000);

    if (diffSecs < 10) return 'just now';
    if (diffSecs < 60) return `${diffSecs}s ago`;

    const diffMins = Math.floor(diffSecs / 60);
    if (diffMins < 60) return `${diffMins}m ago`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;

    return date.toLocaleDateString();
  } catch {
    return 'Unknown';
  }
}
</script>

<style scoped>
.health-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0.75rem;
  border-radius: 4px;
  font-size: 0.8125rem;
  font-weight: 600;
  cursor: help;
  transition: all 0.2s;
}

.health-healthy {
  background: #e8f5e9;
  color: #2e7d32;
}

.health-unhealthy {
  background: #ffebee;
  color: #c62828;
}

.health-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  animation: pulse 2s ease-in-out infinite;
}

.health-healthy .health-dot {
  background: #4caf50;
}

.health-unhealthy .health-dot {
  background: #f44336;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.health-text {
  user-select: none;
}

.health-indicator:hover {
  opacity: 0.9;
}
</style>
