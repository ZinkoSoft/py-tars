<template>
  <div class="config-editor">
    <!-- Loading State -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <p>Loading configuration...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="error-state">
      <div class="error-icon">⚠️</div>
      <h3>Failed to Load Configuration</h3>
      <p>{{ error }}</p>
      <button @click="reload" class="btn-retry">Retry</button>
    </div>

    <!-- Empty State -->
    <div v-else-if="!config" class="empty-state">
      <p>Select a service to view and edit its configuration.</p>
    </div>

    <!-- Configuration Editor -->
    <div v-else class="editor-content">
      <!-- Header -->
      <div class="editor-header">
        <div class="header-left">
          <h2>{{ config.service }} Configuration</h2>
          <div class="meta-info">
            <span class="version-badge">Version {{ config.version }}</span>
            <span class="updated-time">Updated {{ formatTimestamp(config.updatedAt) }}</span>
          </div>
        </div>
        <div class="header-right">
          <button
            @click="handleSave"
            :disabled="!hasChanges || saving || !isValid || !canWrite"
            class="btn-save"
            :class="{ 'btn-disabled': !hasChanges || saving || !isValid || !canWrite }"
            :title="!canWrite ? 'You do not have permission to save configuration' : ''"
          >
            <span v-if="saving">Saving...</span>
            <span v-else-if="!canWrite">Read Only</span>
            <span v-else>{{ hasChanges ? 'Save Changes' : 'No Changes' }}</span>
          </button>
          <button
            v-if="hasChanges"
            @click="handleReset"
            :disabled="saving"
            class="btn-reset"
          >
            Reset
          </button>
        </div>
      </div>

      <!-- Validation Errors Summary -->
      <div v-if="validationErrors.length > 0" class="validation-errors">
        <div class="errors-header">
          <span class="error-icon">⚠️</span>
          <strong>{{ validationErrors.length }} Validation Error(s)</strong>
        </div>
        <ul class="errors-list">
          <li v-for="error in validationErrors" :key="error.field">
            <strong>{{ formatFieldKey(error.field) }}:</strong> {{ error.message }}
          </li>
        </ul>
      </div>

      <!-- Permission Warning -->
      <div v-if="!canWrite" class="permission-warning">
        <span class="warning-icon">🔒</span>
        <strong>Read-Only Mode:</strong> You do not have permission to modify configuration.
        Contact an administrator to request write access.
      </div>

      <!-- Success Message -->
      <div v-if="successMessage" class="success-message">
        <span class="success-icon">✓</span>
        {{ successMessage }}
      </div>

      <!-- Configuration Fields -->
      <div class="fields-container">
        <div
          v-for="(field, key) in filteredFields"
          :key="key"
          class="field-wrapper"
        >
          <ConfigField
            :field="field"
            :model-value="pendingChanges[key] !== undefined ? pendingChanges[key] : config.config[key]"
            @update:model-value="(value) => handleFieldChange(key, value)"
            @validation-error="(error) => handleValidationError(key, error)"
            :error-message="getFieldError(key)"
          />
        </div>
      </div>

      <!-- No Fields Message (if filtered out) -->
      <div v-if="Object.keys(filteredFields).length === 0" class="no-fields">
        <p>No configuration fields match the current filter.</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import ConfigField from './ConfigField.vue';
import { useNotifications } from '../composables/useNotifications';
import type { ServiceConfig, ConfigFieldMetadata, ValidationError } from '../types/config';

const { notify } = useNotifications();
import { useConfig } from '../composables/useConfig';

const { canWrite } = useConfig();

interface Props {
  config: ServiceConfig | null;
  loading: boolean;
  error: string | null;
  complexityFilter?: 'simple' | 'advanced' | 'all';
  searchQuery?: string;
}

interface Emits {
  (e: 'save', data: { config: Record<string, any>; version: number }): void;
  (e: 'reload'): void;
}

const props = withDefaults(defineProps<Props>(), {
  complexityFilter: 'all',
  searchQuery: '',
});

const emit = defineEmits<Emits>();

// State
const pendingChanges = ref<Record<string, any>>({});
const validationErrors = ref<ValidationError[]>([]);
const saving = ref(false);
const successMessage = ref<string | null>(null);

// Computed
const hasChanges = computed(() => Object.keys(pendingChanges.value).length > 0);

const isValid = computed(() => validationErrors.value.length === 0);

const filteredFields = computed(() => {
  if (!props.config?.fields) {
    // If no field metadata, create basic fields from config keys
    return createBasicFields();
  }

  const fields: Record<string, ConfigFieldMetadata> = {};
  for (const field of props.config.fields) {
    if (props.complexityFilter === 'all' || field.complexity === props.complexityFilter) {
      fields[field.key] = field;
    }
  }
  return fields;
});

// Methods
function createBasicFields(): Record<string, ConfigFieldMetadata> {
  if (!props.config) return {};

  const fields: Record<string, ConfigFieldMetadata> = {};
  for (const [key, value] of Object.entries(props.config.config)) {
    fields[key] = {
      key,
      value,
      type: inferType(value),
      complexity: 'simple',
      description: `Configuration for ${key}`,
      required: false,
      source: 'database',
      envOverride: false,
    };
  }
  return fields;
}

function inferType(value: any): any {
  if (typeof value === 'boolean') return 'boolean';
  if (typeof value === 'number') {
    return Number.isInteger(value) ? 'integer' : 'float';
  }
  return 'string';
}

function handleFieldChange(key: string, value: any): void {
  // Track change
  pendingChanges.value[key] = value;

  // Clear success message
  successMessage.value = null;
}

function handleValidationError(key: string, error: string | null): void {
  // Remove existing error for this field
  validationErrors.value = validationErrors.value.filter((e: ValidationError) => e.field !== key);

  // Add new error if present
  if (error) {
    validationErrors.value.push({
      field: key,
      message: error,
    });
  }
}

async function handleSave(): Promise<void> {
  if (!props.config || !hasChanges.value || !isValid.value) return;

  saving.value = true;
  successMessage.value = null;

  try {
    // Merge pending changes with current config
    const updatedConfig = {
      ...props.config.config,
      ...pendingChanges.value,
    };

    emit('save', {
      config: updatedConfig,
      version: props.config.version,
    });

    // Clear pending changes on success
    pendingChanges.value = {};
    successMessage.value = 'Configuration saved successfully!';
    
    // Show success notification
    notify.success('Configuration saved successfully!');

    // Auto-hide success message after 3 seconds
    setTimeout(() => {
      successMessage.value = null;
    }, 3000);
  } catch (err) {
    console.error('Save failed:', err);
    const errorMsg = err instanceof Error ? err.message : 'Failed to save configuration';
    notify.error(errorMsg);
  } finally {
    saving.value = false;
  }
}

function handleReset(): void {
  pendingChanges.value = {};
  validationErrors.value = [];
  successMessage.value = null;
}

function reload(): void {
  emit('reload');
}

function getFieldError(key: string): string | undefined {
  return validationErrors.value.find((e: ValidationError) => e.field === key)?.message;
}

function formatFieldKey(key: string): string {
  return key
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function formatTimestamp(timestamp: string): string {
  try {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;

    return date.toLocaleDateString();
  } catch {
    return timestamp;
  }
}

// Watch for config changes (e.g., from reload)
watch(() => props.config, () => {
  pendingChanges.value = {};
  validationErrors.value = [];
  successMessage.value = null;
});
</script>

<style scoped>
.config-editor {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* Loading State */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #666;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #f3f3f3;
  border-top: 4px solid #2196f3;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 1rem;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* Error State */
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 2rem;
  text-align: center;
}

.error-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.error-state h3 {
  color: #d32f2f;
  margin-bottom: 0.5rem;
}

.error-state p {
  color: #666;
  margin-bottom: 1rem;
}

.btn-retry {
  padding: 0.5rem 1.5rem;
  background: #2196f3;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
}

.btn-retry:hover {
  background: #1976d2;
}

/* Empty State */
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #999;
  font-size: 1.1rem;
}

/* Editor Content */
.editor-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0; /* Allow flex child to shrink below content size */
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 1.5rem;
  border-bottom: 2px solid #e0e0e0;
  background: #fafafa;
}

.header-left h2 {
  margin: 0 0 0.5rem 0;
  font-size: 1.5rem;
  color: #333;
}

.meta-info {
  display: flex;
  gap: 1rem;
  font-size: 0.875rem;
  color: #666;
}

.version-badge {
  padding: 0.25rem 0.75rem;
  background: #e3f2fd;
  color: #1976d2;
  border-radius: 4px;
  font-weight: 600;
}

.header-right {
  display: flex;
  gap: 0.75rem;
}

.btn-save,
.btn-reset {
  padding: 0.625rem 1.25rem;
  border: none;
  border-radius: 4px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-save {
  background: #4caf50;
  color: white;
}

.btn-save:hover:not(.btn-disabled) {
  background: #388e3c;
}

.btn-save.btn-disabled {
  background: #ccc;
  cursor: not-allowed;
}

.btn-reset {
  background: #f5f5f5;
  color: #333;
  border: 1px solid #ddd;
}

.btn-reset:hover {
  background: #e0e0e0;
}

/* Validation Errors */
.validation-errors {
  margin: 1rem 1.5rem;
  padding: 1rem;
  background: #ffebee;
  border: 1px solid #ef5350;
  border-radius: 4px;
}

.errors-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  color: #d32f2f;
}

.errors-list {
  margin: 0;
  padding-left: 1.5rem;
  color: #c62828;
}

/* Permission Warning */
.permission-warning {
  margin: 1rem 1.5rem;
  padding: 1rem;
  background: #fff3e0;
  border: 1px solid #ffb74d;
  border-radius: 4px;
  color: #ef6c00;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.warning-icon {
  font-size: 1.25rem;
}

/* Success Message */
.success-message {
  margin: 1rem 1.5rem;
  padding: 1rem;
  background: #e8f5e9;
  border: 1px solid #66bb6a;
  border-radius: 4px;
  color: #2e7d32;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.success-icon {
  font-weight: bold;
  font-size: 1.25rem;
}

/* Fields Container */
.fields-container {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.field-wrapper {
  margin-bottom: 1rem;
}

.no-fields {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #999;
  font-size: 1.1rem;
}
</style>
