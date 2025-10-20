<template>
  <button
    :class="['btn', `btn--${variant}`, { 'btn--icon': icon }]"
    :type="type"
    @click="$emit('click', $event)"
  >
    <slot />
  </button>
</template>

<script setup lang="ts">
export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost'

interface Props {
  variant?: ButtonVariant
  type?: 'button' | 'submit' | 'reset'
  icon?: boolean
}

withDefaults(defineProps<Props>(), {
  variant: 'primary',
  type: 'button',
  icon: false
})

defineEmits<{
  click: [event: MouseEvent]
}>()
</script>

<style scoped>
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
  font-weight: 500;
  border: 1px solid transparent;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn--icon {
  padding: 0.5rem;
  aspect-ratio: 1;
}

/* Primary variant */
.btn--primary {
  background: var(--color-primary);
  color: var(--color-bg);
  border-color: var(--color-primary);
}

.btn--primary:hover:not(:disabled) {
  background: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
}

.btn--primary:active:not(:disabled) {
  transform: translateY(1px);
}

/* Secondary variant */
.btn--secondary {
  background: transparent;
  color: var(--color-text);
  border-color: var(--color-border);
}

.btn--secondary:hover:not(:disabled) {
  background: var(--color-surface);
  border-color: var(--color-primary);
}

/* Danger variant */
.btn--danger {
  background: var(--color-error);
  color: var(--color-bg);
  border-color: var(--color-error);
}

.btn--danger:hover:not(:disabled) {
  background: #c82333;
  border-color: #bd2130;
}

/* Ghost variant */
.btn--ghost {
  background: transparent;
  color: var(--color-text);
  border-color: transparent;
}

.btn--ghost:hover:not(:disabled) {
  background: var(--color-surface);
}
</style>
