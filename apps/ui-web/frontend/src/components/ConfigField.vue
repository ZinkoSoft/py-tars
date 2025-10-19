<template>
  <div class="config-field" :class="{ 'has-error': hasError, 'env-override': field.envOverride }">
    <div class="field-header">
      <div class="field-label-group">
        <label :for="field.key" class="field-label">
          {{ formatKey(field.key) }}
          <span v-if="field.required" class="required-indicator">*</span>
        </label>
        <button 
          v-if="field.examples || field.helpText"
          @click="showHelpModal = true" 
          class="help-button"
          type="button"
          title="View detailed help and examples"
        >
          ?
        </button>
      </div>
      <div class="field-badges">
        <span v-if="field.envOverride" class="badge env-badge" title="Overridden by environment variable">
          ENV
        </span>
        <span class="badge complexity-badge" :class="`complexity-${field.complexity}`">
          {{ field.complexity }}
        </span>
      </div>
    </div>

    <div class="field-description" v-if="field.description">
      {{ field.description }}
    </div>

    <div class="field-input">
      <!-- String input -->
      <input
        v-if="field.type === 'string'"
        :id="field.key"
        type="text"
        :value="modelValue"
        @input="handleInput"
        :disabled="field.envOverride"
        class="input-text"
      />

      <!-- Secret input (password) -->
      <input
        v-else-if="field.type === 'secret'"
        :id="field.key"
        type="password"
        :value="modelValue"
        @input="handleInput"
        :disabled="field.envOverride"
        class="input-text"
        placeholder="••••••••"
      />

      <!-- Integer/Float input -->
      <input
        v-else-if="field.type === 'integer' || field.type === 'float'"
        :id="field.key"
        type="number"
        :value="modelValue"
        @input="handleInput"
        :disabled="field.envOverride"
        :min="field.validation?.min"
        :max="field.validation?.max"
        :step="field.type === 'float' ? '0.01' : '1'"
        class="input-number"
      />

      <!-- Boolean checkbox -->
      <label v-else-if="field.type === 'boolean'" class="checkbox-label">
        <input
          :id="field.key"
          type="checkbox"
          :checked="modelValue"
          @change="handleCheckboxChange"
          :disabled="field.envOverride"
          class="input-checkbox"
        />
        <span>{{ modelValue ? 'Enabled' : 'Disabled' }}</span>
      </label>

      <!-- Enum select -->
      <select
        v-else-if="field.type === 'enum'"
        :id="field.key"
        :value="modelValue"
        @change="handleSelectChange"
        :disabled="field.envOverride"
        class="input-select"
      >
        <option v-for="option in field.validation?.allowed" :key="option" :value="option">
          {{ option }}
        </option>
      </select>

      <!-- Path input (file/directory) -->
      <input
        v-else-if="field.type === 'path'"
        :id="field.key"
        type="text"
        :value="modelValue"
        @input="handleInput"
        :disabled="field.envOverride"
        class="input-text"
        placeholder="/path/to/file"
      />

      <!-- Fallback for unknown types -->
      <input
        v-else
        :id="field.key"
        type="text"
        :value="modelValue"
        @input="handleInput"
        :disabled="field.envOverride"
        class="input-text"
      />
    </div>

    <div v-if="field.helpText" class="field-help">
      {{ field.helpText }}
    </div>

    <div v-if="hasError" class="field-error">
      {{ displayError }}
    </div>

    <div v-if="field.envOverride" class="field-warning">
      This value is overridden by an environment variable and cannot be changed here.
    </div>

    <!-- Help Modal -->
    <div v-if="showHelpModal" class="help-modal-overlay" @click.self="showHelpModal = false">
      <div class="help-modal">
        <div class="help-modal-header">
          <h3>{{ formatKey(field.key) }}</h3>
          <button @click="showHelpModal = false" class="close-button" type="button">×</button>
        </div>
        <div class="help-modal-body">
          <div class="help-section">
            <h4>Description</h4>
            <p>{{ field.description || 'No description available.' }}</p>
          </div>

          <div v-if="field.helpText" class="help-section">
            <h4>Additional Information</h4>
            <p>{{ field.helpText }}</p>
          </div>

          <div v-if="field.examples && field.examples.length > 0" class="help-section">
            <h4>Examples</h4>
            <ul class="examples-list">
              <li v-for="(example, idx) in field.examples" :key="idx">
                <code>{{ example }}</code>
              </li>
            </ul>
          </div>

          <div class="help-section">
            <h4>Technical Details</h4>
            <ul class="details-list">
              <li><strong>Type:</strong> {{ field.type }}</li>
              <li><strong>Default:</strong> <code>{{ field.default !== undefined ? field.default : 'None' }}</code></li>
              <li v-if="field.required"><strong>Required:</strong> Yes</li>
              <li v-if="field.validation?.min !== undefined"><strong>Minimum:</strong> {{ field.validation.min }}</li>
              <li v-if="field.validation?.max !== undefined"><strong>Maximum:</strong> {{ field.validation.max }}</li>
              <li v-if="field.validation?.allowed"><strong>Allowed values:</strong> {{ field.validation.allowed.join(', ') }}</li>
              <li v-if="field.envOverride"><strong>Environment Override:</strong> {{ field.envVar }}</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import type { ConfigFieldMetadata } from '../types/config';

interface Props {
  field: ConfigFieldMetadata;
  modelValue: any;
  errorMessage?: string;
}

const showHelpModal = ref(false);

interface Emits {
  (e: 'update:modelValue', value: any): void;
  (e: 'validation-error', error: string | null): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const localError = ref<string | null>(null);

const hasError = computed(() => !!props.errorMessage || !!localError.value);
const displayError = computed(() => props.errorMessage || localError.value);

function validateValue(value: any): string | null {
  const validation = props.field.validation;
  
  if (!validation) {
    return null;
  }

  // Required field validation
  if (props.field.required && (value === null || value === undefined || value === '')) {
    return 'This field is required';
  }

  // Type-specific validations
  if (props.field.type === 'integer' || props.field.type === 'float') {
    const numValue = typeof value === 'number' ? value : parseFloat(value);
    
    if (isNaN(numValue)) {
      return `Must be a valid ${props.field.type}`;
    }
    
    if (validation.min !== undefined && numValue < validation.min) {
      return `Must be at least ${validation.min}`;
    }
    
    if (validation.max !== undefined && numValue > validation.max) {
      return `Must be at most ${validation.max}`;
    }
  }

  // String validations
  if (props.field.type === 'string' || props.field.type === 'secret' || props.field.type === 'path') {
    const strValue = String(value);
    
    // Regex pattern validation
    if (validation.pattern) {
      const regex = new RegExp(validation.pattern);
      if (!regex.test(strValue)) {
        return validation.patternDescription || 'Invalid format';
      }
    }
    
    // Min/max length validation
    if (validation.minLength !== undefined && strValue.length < validation.minLength) {
      return `Must be at least ${validation.minLength} characters`;
    }
    
    if (validation.maxLength !== undefined && strValue.length > validation.maxLength) {
      return `Must be at most ${validation.maxLength} characters`;
    }
  }

  // Enum validation
  if (props.field.type === 'enum') {
    if (validation.allowed && !validation.allowed.includes(value)) {
      return `Must be one of: ${validation.allowed.join(', ')}`;
    }
  }

  // Path validation
  if (props.field.type === 'path') {
    const strValue = String(value);
    
    // Basic path validation (Unix/Windows)
    if (strValue && !strValue.match(/^[a-zA-Z]:|^\//)) {
      return 'Must be an absolute path';
    }
  }

  return null;
}

function handleInput(event: Event): void {
  const target = event.target as HTMLInputElement;
  let value: any = target.value;

  // Type conversion
  if (props.field.type === 'integer') {
    value = parseInt(value, 10);
  } else if (props.field.type === 'float') {
    value = parseFloat(value);
  }

  // Validate
  const error = validateValue(value);
  localError.value = error;
  emit('validation-error', error);

  // Emit value even if invalid (parent decides what to do)
  emit('update:modelValue', value);
}

function handleCheckboxChange(event: Event): void {
  const target = event.target as HTMLInputElement;
  const value = target.checked;
  
  const error = validateValue(value);
  localError.value = error;
  emit('validation-error', error);
  
  emit('update:modelValue', value);
}

function handleSelectChange(event: Event): void {
  const target = event.target as HTMLSelectElement;
  const value = target.value;
  
  const error = validateValue(value);
  localError.value = error;
  emit('validation-error', error);
  
  emit('update:modelValue', value);
}

function formatKey(key: string): string {
  // Convert snake_case to Title Case
  return key
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}
</script>

<style scoped>
.config-field {
  margin-bottom: 1.5rem;
  padding: 1rem;
  border: 1px solid var(--vscode-input-border);
  border-radius: 4px;
  background: var(--vscode-input-background);
}

.config-field.has-error {
  border-color: var(--vscode-errorForeground);
}

.config-field.env-override {
  background: var(--vscode-button-secondaryBackground);
  border-color: var(--vscode-focusBorder);
}

.field-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.field-label-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.field-label {
  font-weight: 600;
  font-size: 0.95rem;
  color: var(--vscode-input-foreground);
}

.help-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.25rem;
  height: 1.25rem;
  border-radius: 50%;
  border: 1px solid var(--vscode-input-border);
  background: var(--vscode-button-secondaryBackground);
  color: var(--vscode-button-secondaryForeground);
  font-size: 0.75rem;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.2s;
}

.help-button:hover {
  background: var(--vscode-button-secondaryHoverBackground);
  border-color: var(--vscode-focusBorder);
  transform: scale(1.1);
}

.required-indicator {
  color: var(--vscode-errorForeground);
  margin-left: 0.25rem;
}

.field-badges {
  display: flex;
  gap: 0.5rem;
}

.badge {
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.env-badge {
  background: #ff9800;
  color: #fff;
}

.complexity-badge {
  color: #fff;
}

.complexity-simple {
  background: #4caf50;
}

.complexity-advanced {
  background: #2196f3;
}

.field-description {
  color: var(--vscode-descriptionForeground);
  font-size: 0.875rem;
  margin-bottom: 0.5rem;
}

.field-input {
  margin-bottom: 0.5rem;
}

.input-text,
.input-number,
.input-select {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid var(--vscode-input-border);
  border-radius: 4px;
  font-size: 0.95rem;
  background: var(--vscode-input-background);
  color: var(--vscode-input-foreground);
}

.input-text:focus,
.input-number:focus,
.input-select:focus {
  outline: none;
  border-color: var(--vscode-focusBorder);
}

.input-text:disabled,
.input-number:disabled,
.input-select:disabled {
  background: var(--vscode-input-background);
  opacity: 0.5;
  cursor: not-allowed;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.input-checkbox {
  width: 1.25rem;
  height: 1.25rem;
  cursor: pointer;
}

.input-checkbox:disabled {
  cursor: not-allowed;
}

.field-help {
  color: var(--vscode-descriptionForeground);
  font-size: 0.8125rem;
  font-style: italic;
}

.field-error {
  color: var(--vscode-errorForeground);
  font-size: 0.875rem;
  margin-top: 0.25rem;
}

.field-warning {
  color: #ff9800;
  font-size: 0.875rem;
  margin-top: 0.25rem;
  font-weight: 500;
}

/* Help Modal */
.help-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  padding: 2rem;
}

.help-modal {
  background: var(--vscode-editorWidget-background);
  border: 1px solid var(--vscode-input-border);
  border-radius: 6px;
  max-width: 600px;
  max-height: 80vh;
  width: 100%;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
}

.help-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid var(--vscode-input-border);
}

.help-modal-header h3 {
  margin: 0;
  font-size: 1.25rem;
  color: var(--vscode-editor-foreground);
}

.close-button {
  background: transparent;
  border: none;
  color: var(--vscode-editor-foreground);
  font-size: 2rem;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  width: 2rem;
  height: 2rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: background 0.2s;
}

.close-button:hover {
  background: var(--vscode-toolbar-hoverBackground);
}

.help-modal-body {
  padding: 1.5rem;
  overflow-y: auto;
}

.help-section {
  margin-bottom: 1.5rem;
}

.help-section:last-child {
  margin-bottom: 0;
}

.help-section h4 {
  margin: 0 0 0.75rem 0;
  font-size: 1rem;
  color: var(--vscode-editor-foreground);
  font-weight: 600;
}

.help-section p {
  margin: 0;
  color: var(--vscode-descriptionForeground);
  line-height: 1.6;
}

.examples-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.examples-list li {
  margin-bottom: 0.5rem;
  padding: 0.75rem;
  background: var(--vscode-input-background);
  border: 1px solid var(--vscode-input-border);
  border-radius: 4px;
}

.examples-list code {
  color: var(--vscode-editor-foreground);
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
}

.details-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.details-list li {
  padding: 0.5rem 0;
  color: var(--vscode-descriptionForeground);
  border-bottom: 1px solid var(--vscode-input-border);
}

.details-list li:last-child {
  border-bottom: none;
}

.details-list strong {
  color: var(--vscode-editor-foreground);
  margin-right: 0.5rem;
}

.details-list code {
  background: var(--vscode-input-background);
  padding: 0.125rem 0.375rem;
  border-radius: 3px;
  font-size: 0.875rem;
  color: var(--vscode-editor-foreground);
}

</style>
