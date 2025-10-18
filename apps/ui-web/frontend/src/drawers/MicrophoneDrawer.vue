<template>
  <div class="microphone-drawer">
    <Panel title="Audio Spectrum">
      <SpectrumCanvas :fftData="spectrumStore.currentFFT" :width="400" :height="120" />
    </Panel>

    <Panel title="Microphone Status" class="status-panel">
      <div class="status-grid">
        <div class="status-item">
          <span class="status-label">Listening</span>
          <span :class="['status-value', { active: uiStore.listening }]">
            {{ uiStore.listening ? 'Yes' : 'No' }}
          </span>
        </div>
        <div class="status-item">
          <span class="status-label">Processing</span>
          <span :class="['status-value', { active: uiStore.processing }]">
            {{ uiStore.processing ? 'Yes' : 'No' }}
          </span>
        </div>
      </div>
    </Panel>

    <Panel title="VAD Settings" class="settings-panel">
      <div class="settings-info">
        <p class="info-text">
          Voice Activity Detection (VAD) settings are configured on the STT service. Stream partials
          and threshold adjustments will be available in future updates.
        </p>
      </div>
    </Panel>
  </div>
</template>

<script setup lang="ts">
import Panel from '../components/Panel.vue'
import SpectrumCanvas from '../components/SpectrumCanvas.vue'
import { useUIStore } from '../stores/ui'
import { useSpectrumStore } from '../stores/spectrum'

const uiStore = useUIStore()
const spectrumStore = useSpectrumStore()
</script>

<style scoped>
.microphone-drawer {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.status-panel,
.settings-panel {
  margin-top: 0;
}

.status-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
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

.status-value.active {
  color: var(--color-primary);
}

.settings-info {
  padding: 0.5rem;
}

.info-text {
  margin: 0;
  font-size: 0.875rem;
  color: var(--color-text-secondary);
  line-height: 1.5;
}
</style>
