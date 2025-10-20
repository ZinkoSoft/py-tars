<template>
  <div :class="['panel', { 'panel--bordered': bordered }]">
    <div v-if="title || $slots.header" class="panel__header">
      <slot name="header">
        <h3 class="panel__title">{{ title }}</h3>
      </slot>
    </div>
    <div class="panel__content">
      <slot />
    </div>
    <div v-if="$slots.footer" class="panel__footer">
      <slot name="footer" />
    </div>
  </div>
</template>

<script setup lang="ts">
interface Props {
  title?: string
  bordered?: boolean
}

withDefaults(defineProps<Props>(), {
  title: undefined,
  bordered: true
})
</script>

<style scoped>
.panel {
  background: var(--color-surface);
  border-radius: 4px;
  overflow: hidden;
}

.panel--bordered {
  border: 1px solid var(--color-border);
}

.panel__header {
  padding: 1rem;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg);
}

.panel__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text);
}

.panel__content {
  padding: 1rem;
}

.panel__footer {
  padding: 1rem;
  border-top: 1px solid var(--color-border);
  background: var(--color-bg);
}
</style>
