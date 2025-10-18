<template>
  <div class="config-tabs">
    <!-- Tabs Header -->
    <div class="tabs-header">
      <div class="tabs-nav">
        <button
          v-for="service in services"
          :key="service"
          @click="selectService(service)"
          class="tab-button"
          :class="{ 'tab-active': selectedService === service }"
        >
          {{ formatServiceName(service) }}
        </button>
      </div>
      <div class="tabs-controls">
        <!-- Complexity Filter -->
        <div class="complexity-toggle">
          <button
            @click="setComplexity('simple')"
            class="complexity-btn"
            :class="{ active: complexity === 'simple' }"
            title="Show only simple settings"
          >
            Simple
          </button>
          <button
            @click="setComplexity('advanced')"
            class="complexity-btn"
            :class="{ active: complexity === 'advanced' }"
            title="Show only advanced settings"
          >
            Advanced
          </button>
          <button
            @click="setComplexity('all')"
            class="complexity-btn"
            :class="{ active: complexity === 'all' }"
            title="Show all settings"
          >
            All
          </button>
        </div>

        <!-- Health Indicator -->
        <HealthIndicator :is-healthy="isHealthy" :last-update="lastUpdate" />

        <!-- Refresh Button -->
        <button @click="handleRefresh" class="btn-refresh" title="Refresh configuration">
          <span class="refresh-icon">↻</span>
        </button>
      </div>
    </div>

    <!-- Tabs Content -->
    <div class="tabs-content">
      <ConfigEditor
        :config="currentConfig"
        :loading="loading"
        :error="error"
        :complexity-filter="complexity"
        @save="handleSave"
        @reload="handleReload"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useConfig } from '../composables/useConfig';
import { useNotifications } from '../composables/useNotifications';
import { useHealth } from '../composables/useHealth';
import ConfigEditor from './ConfigEditor.vue';
import HealthIndicator from './HealthIndicator.vue';
import type { ServiceConfig } from '../types/config';

// Composables
const { services, currentConfig, loading, error, loadServices, loadConfig, updateConfig } = useConfig();
const { notify } = useNotifications();
const { isHealthy, lastUpdate } = useHealth(10000); // Poll every 10 seconds

// State
const selectedService = ref<string | null>(null);
const complexity = ref<'simple' | 'advanced' | 'all'>('simple');

// Computed
const currentConfigData = computed(() => currentConfig.value);

// Methods
async function selectService(service: string): Promise<void> {
  selectedService.value = service;
  await loadConfig(service);
}

function setComplexity(level: 'simple' | 'advanced' | 'all'): void {
  complexity.value = level;
  // Persist to localStorage
  localStorage.setItem('config-complexity-mode', level);
}

async function handleSave(data: { config: Record<string, any>; version: number }): Promise<void> {
  if (!selectedService.value) return;

  const result = await updateConfig(selectedService.value, data.config, data.version);

  if (result) {
    // Reload configuration to get latest version
    await loadConfig(selectedService.value);
    notify.success('Configuration saved successfully!');
  } else if (error.value) {
    notify.error(error.value);
  }
}

async function handleReload(): Promise<void> {
  if (selectedService.value) {
    await loadConfig(selectedService.value);
  }
}

async function handleRefresh(): Promise<void> {
  await loadServices();
  if (selectedService.value) {
    await loadConfig(selectedService.value);
  }
}

function formatServiceName(service: string): string {
  // Convert "stt-worker" to "STT Worker"
  return service
    .split('-')
    .map(word => word.toUpperCase())
    .join(' ');
}

// Lifecycle
onMounted(async () => {
  // Load services
  await loadServices();

  // Restore complexity preference
  const savedComplexity = localStorage.getItem('config-complexity-mode');
  if (savedComplexity === 'simple' || savedComplexity === 'advanced' || savedComplexity === 'all') {
    complexity.value = savedComplexity;
  }

  // Auto-select first service
  if (services.value.length > 0) {
    await selectService(services.value[0]);
  }
});

// Watch for MQTT health updates (placeholder - integrate with WebSocket)
// This would connect to existing MQTT stream in the ui-web service
watch(() => services.value, (newServices) => {
  // If services list changes, re-select if current service is gone
  if (selectedService.value && !newServices.includes(selectedService.value)) {
    selectedService.value = newServices.length > 0 ? newServices[0] : null;
  }
});
</script>

<style scoped>
.config-tabs {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
}

/* Tabs Header */
.tabs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  border-bottom: 2px solid #e0e0e0;
  background: #fafafa;
  gap: 1rem;
  flex-wrap: wrap;
}

.tabs-nav {
  display: flex;
  gap: 0.5rem;
  overflow-x: auto;
  flex: 1;
  min-width: 0;
}

.tab-button {
  padding: 0.5rem 1rem;
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 4px 4px 0 0;
  cursor: pointer;
  font-weight: 500;
  font-size: 0.875rem;
  white-space: nowrap;
  transition: all 0.2s;
  color: #666;
}

.tab-button:hover {
  background: #f5f5f5;
  border-color: #bbb;
}

.tab-button.tab-active {
  background: #2196f3;
  color: white;
  border-color: #2196f3;
  font-weight: 600;
}

.tabs-controls {
  display: flex;
  align-items: center;
  gap: 1rem;
}

/* Complexity Toggle */
.complexity-toggle {
  display: flex;
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 4px;
  overflow: hidden;
}

.complexity-btn {
  padding: 0.375rem 0.75rem;
  border: none;
  background: #fff;
  cursor: pointer;
  font-size: 0.8125rem;
  font-weight: 500;
  color: #666;
  transition: all 0.2s;
  border-right: 1px solid #ddd;
}

.complexity-btn:last-child {
  border-right: none;
}

.complexity-btn:hover {
  background: #f5f5f5;
}

.complexity-btn.active {
  background: #4caf50;
  color: white;
  font-weight: 600;
}

/* Refresh Button */
.btn-refresh {
  padding: 0.375rem 0.75rem;
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-refresh:hover {
  background: #f5f5f5;
  border-color: #bbb;
}

.refresh-icon {
  font-size: 1.25rem;
  display: inline-block;
  transition: transform 0.3s;
}

.btn-refresh:active .refresh-icon {
  transform: rotate(180deg);
}

/* Tabs Content */
.tabs-content {
  flex: 1;
  overflow: hidden;
  background: #fff;
}

/* Responsive */
@media (max-width: 768px) {
  .tabs-header {
    flex-direction: column;
    align-items: stretch;
  }

  .tabs-nav {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  .tabs-controls {
    justify-content: space-between;
  }
}
</style>
