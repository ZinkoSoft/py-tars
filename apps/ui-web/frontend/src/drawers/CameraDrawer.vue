<template>
  <div class="camera-drawer">
    <Panel title="Camera Feed">
      <div class="camera-placeholder">
        <div class="placeholder-icon">📷</div>
        <p>Camera feed visualization will be implemented in a future update.</p>
        <p class="placeholder-hint">
          The camera service publishes frames to MQTT topics. Integration with the UI will include
          live feed display and snapshot capture.
        </p>
      </div>
    </Panel>

    <Panel title="Camera Status" class="status-panel">
      <div class="status-info">
        <div class="status-item">
          <span class="status-label">Service Status</span>
          <span class="status-value">
            {{ cameraHealth }}
          </span>
        </div>
      </div>
    </Panel>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import Panel from '../components/Panel.vue'
import { useHealthStore } from '../stores/health'
import { isComponentTimedOut } from '../types/health'

const healthStore = useHealthStore()

const cameraHealth = computed(() => {
  const camera = healthStore.components.camera
  if (!camera) return 'Unknown'
  if (isComponentTimedOut(camera, Date.now())) return 'Timed Out'
  return camera.ok ? 'Ready' : camera.error || 'Error'
})
</script>

<style scoped>
.camera-drawer {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.camera-placeholder {
  padding: 3rem 1rem;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.placeholder-icon {
  font-size: 4rem;
  opacity: 0.5;
}

.camera-placeholder p {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 0.875rem;
  max-width: 300px;
}

.placeholder-hint {
  font-size: 0.8125rem !important;
  line-height: 1.5;
  opacity: 0.8;
}

.status-panel {
  margin-top: 0;
}

.status-info {
  padding: 0.5rem;
}

.status-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.status-label {
  font-size: 0.75rem;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.status-value {
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text);
}
</style>
