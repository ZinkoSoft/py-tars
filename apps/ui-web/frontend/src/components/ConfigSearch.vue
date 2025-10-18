<template>
  <div class="config-search">
    <div class="search-container">
      <!-- Search Input -->
      <div class="search-input-wrapper">
        <svg class="search-icon" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          v-model="localQuery"
          type="text"
          class="search-input"
          placeholder="Search configurations (e.g., 'whisper', 'model', 'threshold')..."
          @input="handleSearchInput"
          @keydown.esc="clearSearch"
        />
        <button
          v-if="localQuery"
          class="clear-button"
          @click="clearSearch"
          title="Clear search"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Search Results Count -->
    <div v-if="searchQuery" class="search-results-info">
      <span v-if="resultCount > 0">
        Found {{ resultCount }} result{{ resultCount !== 1 ? 's' : '' }}
      </span>
      <span v-else class="no-results">
        No configurations matching "{{ searchQuery }}"
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

// Props
const props = defineProps<{
  modelValue: string
  complexity?: 'simple' | 'advanced' | null
  resultCount?: number
}>()

// Emits
const emit = defineEmits<{
  'update:modelValue': [value: string]
  'update:complexity': [value: 'simple' | 'advanced' | null]
  'search': [query: string]
}>()

// Local state for immediate input feedback
const localQuery = ref(props.modelValue)

// Debounce timer
let debounceTimer: ReturnType<typeof setTimeout> | null = null

// Computed value for display
const searchQuery = ref(props.modelValue)

// Handle search input with debouncing
const handleSearchInput = () => {
  // Update local state immediately for responsive UI
  if (debounceTimer) {
    clearTimeout(debounceTimer)
  }

  // Debounce the actual search by 300ms
  debounceTimer = setTimeout(() => {
    searchQuery.value = localQuery.value
    emit('update:modelValue', localQuery.value)
    emit('search', localQuery.value)
  }, 300)
}

// Clear search
const clearSearch = () => {
  localQuery.value = ''
  searchQuery.value = ''
  emit('update:modelValue', '')
  emit('search', '')
  
  if (debounceTimer) {
    clearTimeout(debounceTimer)
  }
}

// Watch for external changes to modelValue
watch(() => props.modelValue, (newValue) => {
  localQuery.value = newValue
  searchQuery.value = newValue
})
</script>

<style scoped>
.config-search {
  margin-bottom: 1rem;
}

.search-container {
  background: var(--vscode-input-background);
  border: 1px solid var(--vscode-input-border);
  border-radius: 6px;
  padding: 0.75rem;
}

.search-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 0.75rem;
  width: 1.25rem;
  height: 1.25rem;
  color: var(--vscode-input-placeholderForeground);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: 0.625rem 2.5rem 0.625rem 2.75rem;
  font-size: 0.9375rem;
  background: var(--vscode-input-background);
  color: var(--vscode-input-foreground);
  border: 1px solid var(--vscode-input-border);
  border-radius: 4px;
  outline: none;
  transition: border-color 0.2s;
}

.search-input:focus {
  border-color: var(--vscode-focusBorder);
}

.search-input::placeholder {
  color: var(--vscode-input-placeholderForeground);
}

.clear-button {
  position: absolute;
  right: 0.5rem;
  padding: 0.25rem;
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--vscode-input-placeholderForeground);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 3px;
  transition: all 0.2s;
}

.clear-button:hover {
  background: var(--vscode-toolbar-hoverBackground);
  color: var(--vscode-input-foreground);
}

.clear-button svg {
  width: 1rem;
  height: 1rem;
}

.search-results-info {
  margin-top: 0.75rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  color: var(--vscode-descriptionForeground);
  background: var(--vscode-editorWidget-background);
  border-radius: 4px;
}

.no-results {
  color: var(--vscode-errorForeground);
}
</style>
