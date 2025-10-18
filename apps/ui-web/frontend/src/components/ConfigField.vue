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
      {{ errorMessage }}
    </div>

    <div v-if="field.envOverride" class="field-warning">
      This value is overridden by an environment variable and cannot be changed here.
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { ConfigFieldMetadata } from '../types/config';

interface Props {
  field: ConfigFieldMetadata;
  modelValue: any;
  errorMessage?: string;
}

interface Emits {
  (e: 'update:modelValue', value: any): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const hasError = computed(() => !!props.errorMessage);

function handleInput(event: Event): void {
  const target = event.target as HTMLInputElement;
  let value: any = target.value;

  // Type conversion
  if (props.field.type === 'integer') {
    value = parseInt(value, 10);
  } else if (props.field.type === 'float') {
    value = parseFloat(value);
  }

  emit('update:modelValue', value);
}

function handleCheckboxChange(event: Event): void {
  const target = event.target as HTMLInputElement;
  emit('update:modelValue', target.checked);
}

function handleSelectChange(event: Event): void {
  const target = event.target as HTMLSelectElement;
  emit('update:modelValue', target.value);
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
