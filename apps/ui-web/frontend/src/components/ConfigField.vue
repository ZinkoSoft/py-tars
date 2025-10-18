<template>
  <div class="config-field" :class="{ 'has-error': hasError, 'env-override': field.envOverride }">
    <div class="field-header">
      <label :for="field.key" class="field-label">
        {{ formatKey(field.key) }}
        <span v-if="field.required" class="required-indicator">*</span>
      </label>
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
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background: #fff;
}

.config-field.has-error {
  border-color: #d32f2f;
}

.config-field.env-override {
  background: #f5f5f5;
}

.field-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.field-label {
  font-weight: 600;
  font-size: 0.95rem;
  color: #333;
}

.required-indicator {
  color: #d32f2f;
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
  color: #666;
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
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 0.95rem;
}

.input-text:focus,
.input-number:focus,
.input-select:focus {
  outline: none;
  border-color: #2196f3;
}

.input-text:disabled,
.input-number:disabled,
.input-select:disabled {
  background: #f5f5f5;
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
  color: #757575;
  font-size: 0.8125rem;
  font-style: italic;
}

.field-error {
  color: #d32f2f;
  font-size: 0.875rem;
  margin-top: 0.25rem;
}

.field-warning {
  color: #ff9800;
  font-size: 0.875rem;
  margin-top: 0.25rem;
  font-weight: 500;
}
</style>
