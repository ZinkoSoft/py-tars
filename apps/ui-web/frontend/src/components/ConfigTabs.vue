<template>
  <div class="config-tabs">
    <!-- Search Bar -->
    <ConfigSearch
      v-model="searchQuery"
      v-model:complexity="searchComplexity"
      :result-count="searchResultCount"
      @search="handleSearch"
    />

    <!-- Header with Service Selector and Controls -->
    <div class="tabs-header">
      <!-- Service Selector (Hamburger Menu) -->
      <div class="service-selector">
        <button class="hamburger-btn" @click="toggleServiceMenu" title="Select service">
          <span class="hamburger-icon">☰</span>
        </button>
        <h2 class="current-service-title">{{ formatServiceName(selectedService || '') }}</h2>
        
        <!-- Service Dropdown Menu -->
        <div v-if="showServiceMenu" class="service-menu">
          <button
            v-for="service in services"
            :key="service"
            @click="selectServiceFromMenu(service)"
            class="service-menu-item"
            :class="{ 'active': selectedService === service }"
          >
            {{ formatServiceName(service) }}
          </button>
        </div>
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
        :search-query="searchQuery"
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
import ConfigSearch from './ConfigSearch.vue';
import HealthIndicator from './HealthIndicator.vue';
import type { ServiceConfig } from '../types/config';

// Composables
const { services, currentConfig, loading, error, loadServices, loadConfig, updateConfig } = useConfig();
const { notify } = useNotifications();
const { isHealthy, lastUpdate } = useHealth(10000); // Poll every 10 seconds

// State
const selectedService = ref<string | null>(null);
const complexity = ref<'simple' | 'advanced' | 'all'>('simple');
const showServiceMenu = ref(false);

// Search state
const searchQuery = ref('');
const searchComplexity = ref<'simple' | 'advanced' | null>(null);
const searchResultCount = ref(0);

// Methods
function toggleServiceMenu(): void {
  showServiceMenu.value = !showServiceMenu.value;
}

async function selectService(service: string): Promise<void> {
  selectedService.value = service;
  await loadConfig(service);
}

async function selectServiceFromMenu(service: string): Promise<void> {
  await selectService(service);
  showServiceMenu.value = false;
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

async function handleSearch(query: string): Promise<void> {
  searchQuery.value = query;
  
  if (!query.trim()) {
    // Clear search - reset to showing all configs
    searchResultCount.value = 0;
    return;
  }
  
  // Call search API
  const { searchConfigurations } = useConfig();
  const results = await searchConfigurations(
    query,
    selectedService.value, // Filter by current service if selected
    searchComplexity.value
  );
  
  if (results) {
    searchResultCount.value = results.total_count;
  } else {
    searchResultCount.value = 0;
  }
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
  background: var(--vscode-editor-background);
}

/* Tabs Header */
.tabs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--vscode-sideBar-border);
  background: var(--vscode-sideBar-background);
  gap: 1rem;
  flex-wrap: wrap;
}

/* Service Selector with Hamburger Menu */
.service-selector {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
  min-width: 0;
}

.hamburger-btn {
  padding: 0.5rem;
  background: var(--vscode-button-secondaryBackground);
  border: 1px solid var(--vscode-input-border);
  border-radius: 4px;
  cursor: pointer;
  color: var(--vscode-button-secondaryForeground);
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 40px;
  height: 40px;
}

.hamburger-btn:hover {
  background: var(--vscode-button-secondaryHoverBackground);
}

.hamburger-icon {
  font-size: 1.25rem;
  line-height: 1;
}

.current-service-title {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--vscode-editor-foreground);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* Service Dropdown Menu */
.service-menu {
  position: absolute;
  top: 100%;
  left: 0;
  margin-top: 0.5rem;
  background: var(--vscode-editorWidget-background);
  border: 1px solid var(--vscode-input-border);
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
  min-width: 200px;
  max-height: 400px;
  overflow-y: auto;
  z-index: 1000;
}

.service-menu-item {
  display: block;
  width: 100%;
  padding: 0.75rem 1rem;
  background: transparent;
  border: none;
  text-align: left;
  cursor: pointer;
  color: var(--vscode-sideBar-foreground);
  font-size: 0.9375rem;
  transition: all 0.2s;
  border-bottom: 1px solid var(--vscode-input-border);
}

.service-menu-item:last-child {
  border-bottom: none;
}

.service-menu-item:hover {
  background: var(--vscode-list-hoverBackground);
}

.service-menu-item.active {
  background: var(--vscode-list-activeSelectionBackground);
  color: white;
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
  background: var(--vscode-input-background);
  border: 1px solid var(--vscode-input-border);
  border-radius: 4px;
  overflow: hidden;
}

.complexity-btn {
  padding: 0.375rem 0.75rem;
  border: none;
  background: var(--vscode-input-background);
  cursor: pointer;
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--vscode-input-foreground);
  transition: all 0.2s;
  border-right: 1px solid var(--vscode-input-border);
}

.complexity-btn:last-child {
  border-right: none;
}

.complexity-btn:hover {
  background: var(--vscode-button-secondaryHoverBackground);
}

.complexity-btn.active {
  background: var(--vscode-button-background);
  color: var(--vscode-button-foreground);
  font-weight: 600;
}

/* Refresh Button */
.btn-refresh {
  padding: 0.375rem 0.75rem;
  background: var(--vscode-button-secondaryBackground);
  border: 1px solid var(--vscode-input-border);
  border-radius: 4px;
  cursor: pointer;
  color: var(--vscode-button-secondaryForeground);
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-refresh:hover {
  background: var(--vscode-button-secondaryHoverBackground);
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
  min-height: 0;
  overflow-y: auto;
  background: var(--vscode-editor-background);
  display: flex;
  flex-direction: column;
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
