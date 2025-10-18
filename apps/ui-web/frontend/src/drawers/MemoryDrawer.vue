<template>
  <div class="memory-drawer">
    <Panel title="Last RAG Query">
      <div v-if="chatStore.lastMemory" class="memory-content">
        <div class="memory-query">
          <span class="memory-label">Query:</span>
          <code class="memory-text">{{ chatStore.lastMemory.query }}</code>
        </div>
        <div v-if="chatStore.lastMemory.results.length > 0" class="memory-results">
          <span class="memory-label">Results ({{ chatStore.lastMemory.results.length }}):</span>
          <div
            v-for="(result, idx) in chatStore.lastMemory.results"
            :key="idx"
            class="memory-result"
          >
            <div class="result-header">
              <span class="result-score">Score: {{ result.score.toFixed(3) }}</span>
            </div>
            <p class="result-text">{{ result.document.text }}</p>
          </div>
        </div>
        <div v-else class="no-results">
          <p>No results found</p>
        </div>
      </div>
      <div v-else class="no-memory">
        <p>No RAG queries yet. Memory results will appear here when the LLM uses RAG.</p>
      </div>
    </Panel>

    <Panel title="Character Context" class="character-panel">
      <div class="character-info">
        <p class="info-text">
          Character persona and context are configured in the Memory service. Current character
          information is loaded from <code>system/character/current</code> topic.
        </p>
      </div>
    </Panel>
  </div>
</template>

<script setup lang="ts">
import Panel from '../components/Panel.vue'
import { useChatStore } from '../stores/chat'

const chatStore = useChatStore()
</script>

<style scoped>
.memory-drawer {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.memory-content {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.memory-query {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.memory-label {
  font-size: 0.75rem;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
}

.memory-text {
  padding: 0.5rem;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 0.875rem;
  color: var(--color-text);
  font-family: 'Courier New', monospace;
}

.memory-results {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.memory-result {
  padding: 0.75rem;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 4px;
}

.result-header {
  margin-bottom: 0.5rem;
}

.result-score {
  font-size: 0.75rem;
  color: var(--color-primary);
  font-weight: 600;
}

.result-text {
  margin: 0;
  font-size: 0.875rem;
  color: var(--color-text);
  line-height: 1.5;
}

.no-results,
.no-memory {
  padding: 2rem 1rem;
  text-align: center;
}

.no-results p,
.no-memory p {
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 0.875rem;
}

.character-panel {
  margin-top: 0;
}

.character-info {
  padding: 0.5rem;
}

.info-text {
  margin: 0;
  font-size: 0.875rem;
  color: var(--color-text-secondary);
  line-height: 1.5;
}

.info-text code {
  padding: 0.125rem 0.25rem;
  background: var(--color-surface);
  border-radius: 2px;
  font-size: 0.8125rem;
}
</style>
