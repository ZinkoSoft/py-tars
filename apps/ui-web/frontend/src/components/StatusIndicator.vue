<template>
  <div class="status-indicator" :class="`status-indicator--${status}`">
    <div class="status-indicator__dot"></div>
    <span class="status-indicator__label">{{ label }}</span>
  </div>
</template>

<script setup lang="ts">
interface Props {
  label: string
  status: 'healthy' | 'unhealthy' | 'unknown'
}

defineProps<Props>()
</script>

<style scoped>
.status-indicator {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  line-height: 1.4;
}

.status-indicator__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-indicator__label {
  color: var(--text);
}

/* Status variants */
.status-indicator--healthy .status-indicator__dot {
  background: #34c759;
  box-shadow: 0 0 8px rgba(52, 199, 89, 0.5);
}

.status-indicator--unhealthy .status-indicator__dot {
  background: #ff3b30;
  box-shadow: 0 0 8px rgba(255, 59, 48, 0.5);
}

.status-indicator--unknown .status-indicator__dot {
  background: #8e8e93;
  box-shadow: 0 0 8px rgba(142, 142, 147, 0.5);
}

.status-indicator--healthy .status-indicator__label {
  color: #34c759;
}

.status-indicator--unhealthy .status-indicator__label {
  color: #ff3b30;
}

.status-indicator--unknown .status-indicator__label {
  color: #8e8e93;
}
</style>
