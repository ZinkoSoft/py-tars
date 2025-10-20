<template>
  <div class="config-history">
    <!-- Header with filters -->
    <div class="history-header">
      <h3>Configuration History</h3>
      <button @click="$emit('close')" class="btn-close" aria-label="Close">×</button>
    </div>

    <!-- Filters -->
    <div class="filters">
      <div class="filter-group">
        <label for="filterKey">Filter by Key:</label>
        <input
          id="filterKey"
          v-model="filters.key"
          type="text"
          placeholder="e.g., whisper_model"
          @input="loadHistory"
        />
      </div>
      <div class="filter-group">
        <label for="filterStartDate">Start Date:</label>
        <input
          id="filterStartDate"
          v-model="filters.startDate"
          type="datetime-local"
          @change="loadHistory"
        />
      </div>
      <div class="filter-group">
        <label for="filterEndDate">End Date:</label>
        <input
          id="filterEndDate"
          v-model="filters.endDate"
          type="datetime-local"
          @change="loadHistory"
        />
      </div>
      <div class="filter-group">
        <label for="filterLimit">Limit:</label>
        <select id="filterLimit" v-model.number="filters.limit" @change="loadHistory">
          <option :value="50">50</option>
          <option :value="100">100</option>
          <option :value="200">200</option>
          <option :value="500">500</option>
        </select>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading history...</p>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="error-state">
      <span class="error-icon">⚠️</span>
      <p>{{ error }}</p>
      <button @click="loadHistory" class="btn-retry">Retry</button>
    </div>

    <!-- Empty state -->
    <div v-else-if="history.length === 0" class="empty-state">
      <p>No history entries found.</p>
    </div>

    <!-- History timeline -->
    <div v-else class="history-timeline">
      <!-- Select all checkbox -->
      <div class="select-all">
        <label>
          <input
            type="checkbox"
            :checked="selectedEntries.length === history.length"
            :indeterminate="selectedEntries.length > 0 && selectedEntries.length < history.length"
            @change="toggleSelectAll"
          />
          Select All ({{ selectedEntries.length }} selected)
        </label>
        <button
          v-if="selectedEntries.length > 0"
          @click="restoreSelected"
          class="btn-restore"
        >
          Restore Selected ({{ selectedEntries.length }})
        </button>
      </div>

      <!-- History entries -->
      <div
        v-for="entry in history"
        :key="entry.id"
        class="history-entry"
        :class="{ selected: selectedEntries.includes(entry.id) }"
      >
        <div class="entry-header">
          <input
            type="checkbox"
            :checked="selectedEntries.includes(entry.id)"
            @change="toggleEntry(entry.id)"
          />
          <div class="entry-meta">
            <span class="entry-key">{{ entry.key }}</span>
            <span class="entry-time">{{ formatTimestamp(entry.changed_at) }}</span>
            <span class="entry-user">by {{ entry.changed_by }}</span>
          </div>
          <button @click="toggleDetails(entry.id)" class="btn-toggle">
            {{ expandedEntries.has(entry.id) ? '▼' : '▶' }}
          </button>
        </div>

        <div v-if="expandedEntries.has(entry.id)" class="entry-details">
          <div v-if="entry.change_reason" class="change-reason">
            <strong>Reason:</strong> {{ entry.change_reason }}
          </div>

          <div class="value-comparison">
            <div class="value-old">
              <strong>Old Value:</strong>
              <pre>{{ formatValue(entry.old_value) }}</pre>
            </div>
            <div class="value-arrow">→</div>
            <div class="value-new">
              <strong>New Value:</strong>
              <pre>{{ formatValue(entry.new_value) }}</pre>
            </div>
          </div>

          <button @click="restoreSingle(entry)" class="btn-restore-single">
            Restore to Old Value
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { useConfig } from '../composables/useConfig';
import { useNotifications } from '../composables/useNotifications';

interface HistoryEntry {
  id: number;
  service: string;
  key: string;
  old_value: any;
  new_value: any;
  changed_at: string;
  changed_by: string;
  change_reason: string | null;
}

interface Props {
  service: string;
  key?: string;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  close: [];
  restored: [];
}>();

const { getHistory, restoreHistory } = useConfig();
const { notify } = useNotifications();

const loading = ref(false);
const error = ref<string | null>(null);
const history = ref<HistoryEntry[]>([]);
const selectedEntries = ref<number[]>([]);
const expandedEntries = ref<Set<number>>(new Set());

const filters = reactive({
  key: props.key || '',
  startDate: '',
  endDate: '',
  limit: 100,
});

async function loadHistory() {
  loading.value = true;
  error.value = null;

  try {
    const params: any = {
      service: props.service,
      limit: filters.limit,
    };

    if (filters.key) {
      params.key = filters.key;
    }
    if (filters.startDate) {
      params.start_date = filters.startDate;
    }
    if (filters.endDate) {
      params.end_date = filters.endDate;
    }

    history.value = await getHistory(params);
  } catch (err: any) {
    error.value = err.message || 'Failed to load history';
    notify({ message: error.value, type: 'error' });
  } finally {
    loading.value = false;
  }
}

function toggleEntry(id: number) {
  const index = selectedEntries.value.indexOf(id);
  if (index > -1) {
    selectedEntries.value.splice(index, 1);
  } else {
    selectedEntries.value.push(id);
  }
}

function toggleSelectAll(event: Event) {
  const checked = (event.target as HTMLInputElement).checked;
  if (checked) {
    selectedEntries.value = history.value.map((e) => e.id);
  } else {
    selectedEntries.value = [];
  }
}

function toggleDetails(id: number) {
  if (expandedEntries.value.has(id)) {
    expandedEntries.value.delete(id);
  } else {
    expandedEntries.value.add(id);
  }
}

async function restoreSelected() {
  if (selectedEntries.value.length === 0) {
    notify({ message: 'No entries selected', type: 'warning' });
    return;
  }

  if (!confirm(`Restore ${selectedEntries.value.length} configuration changes? This will revert the selected keys to their previous values.`)) {
    return;
  }

  loading.value = true;
  error.value = null;

  try {
    await restoreHistory(props.service, selectedEntries.value);
    notify({ 
      message: `Successfully restored ${selectedEntries.value.length} configuration changes`, 
      type: 'success' 
    });
    emit('restored');
    selectedEntries.value = [];
    await loadHistory();  // Reload to show new history entry
  } catch (err: any) {
    error.value = err.message || 'Failed to restore configuration';
    notify({ message: error.value, type: 'error' });
  } finally {
    loading.value = false;
  }
}

async function restoreSingle(entry: HistoryEntry) {
  if (!confirm(`Restore "${entry.key}" to its previous value?\n\nThis will change it from:\n${formatValue(entry.new_value)}\n\nTo:\n${formatValue(entry.old_value)}`)) {
    return;
  }

  loading.value = true;
  error.value = null;

  try {
    await restoreHistory(props.service, [entry.id]);
    notify({ 
      message: `Successfully restored "${entry.key}"`, 
      type: 'success' 
    });
    emit('restored');
    selectedEntries.value = [];
    await loadHistory();  // Reload to show new history entry
  } catch (err: any) {
    error.value = err.message || 'Failed to restore configuration';
    notify({ message: error.value, type: 'error' });
  } finally {
    loading.value = false;
  }
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;

  return date.toLocaleString();
}

function formatValue(value: any): string {
  if (value === null || value === undefined) {
    return '(empty)';
  }
  if (typeof value === 'string') {
    return value;
  }
  return JSON.stringify(value, null, 2);
}

onMounted(() => {
  loadHistory();
});
</script>

<style scoped>
.config-history {
  display: flex;
  flex-direction: column;
  height: 100%;
  max-height: 80vh;
  background: var(--vscode-editor-background);
  color: var(--vscode-editor-foreground);
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--vscode-panel-border);
}

.history-header h3 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
}

.btn-close {
  background: none;
  border: none;
  color: var(--vscode-editor-foreground);
  font-size: 1.5rem;
  cursor: pointer;
  padding: 0;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-close:hover {
  background: var(--vscode-toolbar-hoverBackground);
  border-radius: 4px;
}

.filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  padding: 1rem 1.5rem;
  background: var(--vscode-input-background);
  border-bottom: 1px solid var(--vscode-panel-border);
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.filter-group label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--vscode-foreground);
}

.filter-group input,
.filter-group select {
  padding: 0.5rem;
  background: var(--vscode-input-background);
  color: var(--vscode-input-foreground);
  border: 1px solid var(--vscode-input-border);
  border-radius: 4px;
  font-family: inherit;
}

.filter-group input:focus,
.filter-group select:focus {
  outline: 1px solid var(--vscode-focusBorder);
}

.loading-state,
.error-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  text-align: center;
}

.spinner {
  width: 2rem;
  height: 2rem;
  border: 3px solid var(--vscode-button-background);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-icon {
  font-size: 2rem;
  margin-bottom: 0.5rem;
}

.btn-retry {
  margin-top: 1rem;
  padding: 0.5rem 1rem;
  background: var(--vscode-button-background);
  color: var(--vscode-button-foreground);
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn-retry:hover {
  background: var(--vscode-button-hoverBackground);
}

.history-timeline {
  flex: 1;
  overflow-y: auto;
  padding: 1rem 1.5rem;
}

.select-all {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background: var(--vscode-input-background);
  border-radius: 4px;
  margin-bottom: 1rem;
}

.select-all label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.btn-restore,
.btn-restore-single {
  padding: 0.5rem 1rem;
  background: var(--vscode-button-background);
  color: var(--vscode-button-foreground);
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
}

.btn-restore:hover,
.btn-restore-single:hover {
  background: var(--vscode-button-hoverBackground);
}

.history-entry {
  border: 1px solid var(--vscode-panel-border);
  border-radius: 4px;
  margin-bottom: 0.75rem;
  background: var(--vscode-input-background);
  transition: all 0.2s;
}

.history-entry.selected {
  border-color: var(--vscode-focusBorder);
  background: rgba(14, 99, 156, 0.15);
}

.entry-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  cursor: pointer;
}

.entry-header input[type="checkbox"] {
  cursor: pointer;
}

.entry-meta {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.entry-key {
  font-weight: 600;
  color: var(--vscode-textLink-foreground);
}

.entry-time,
.entry-user {
  font-size: 0.875rem;
  color: var(--vscode-descriptionForeground);
}

.btn-toggle {
  background: none;
  border: none;
  color: var(--vscode-foreground);
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  font-size: 0.875rem;
}

.entry-details {
  padding: 1rem;
  border-top: 1px solid var(--vscode-panel-border);
  background: var(--vscode-editor-background);
}

.change-reason {
  margin-bottom: 1rem;
  padding: 0.5rem;
  background: var(--vscode-input-background);
  border-left: 3px solid var(--vscode-textLink-foreground);
}

.value-comparison {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 1rem;
  align-items: center;
  margin-bottom: 1rem;
}

.value-old,
.value-new {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.value-old strong,
.value-new strong {
  font-size: 0.875rem;
}

.value-old pre,
.value-new pre {
  margin: 0;
  padding: 0.75rem;
  background: var(--vscode-textCodeBlock-background);
  border: 1px solid var(--vscode-panel-border);
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.value-arrow {
  font-size: 1.5rem;
  color: var(--vscode-descriptionForeground);
}
</style>
