<template>
  <div class="code-block" :style="{ maxHeight: maxLines ? `${maxLines * 1.5}em` : 'none' }">
    <pre><code :class="`language-${language}`">{{ code }}</code></pre>
  </div>
</template>

<script setup lang="ts">
interface Props {
  code: string
  language?: string
  maxLines?: number
}

withDefaults(defineProps<Props>(), {
  language: 'json',
  maxLines: undefined
})
</script>

<style scoped>
.code-block {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: auto;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Code', 'Consolas', monospace;
}

.code-block pre {
  margin: 0;
  padding: 12px;
}

.code-block code {
  font-size: 13px;
  line-height: 1.5;
  color: var(--text);
  display: block;
}

/* JSON syntax highlighting (basic) */
.language-json {
  color: var(--text);
}

/* Scrollbar styling */
.code-block::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.code-block::-webkit-scrollbar-track {
  background: var(--bg);
}

.code-block::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 4px;
}

.code-block::-webkit-scrollbar-thumb:hover {
  background: var(--muted);
}
</style>
