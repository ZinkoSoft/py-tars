<template>
  <div class="composer">
    <input
      v-model="inputText"
      type="text"
      placeholder="Type to add a user message (UI-only demo)…"
      @keydown.enter="handleSubmit"
    />
    <button @click="handleSubmit">Send</button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useChatStore } from '../stores/chat'

const chatStore = useChatStore()
const inputText = ref('')

function handleSubmit(): void {
  const text = inputText.value.trim()
  if (text) {
    chatStore.addUserMessage(text)
    inputText.value = ''
  }
}
</script>

<style scoped>
.composer {
  display: flex;
  border-top: 1px solid var(--border);
}

.composer input {
  flex: 1;
  background: #0c1020;
  color: var(--text);
  border: none;
  padding: 12px;
  outline: none;
}

.composer input::placeholder {
  color: var(--muted);
  opacity: 0.7;
}

.composer button {
  background: #0c7bdc;
  color: #fff;
  border: none;
  padding: 12px 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.composer button:hover {
  background: #0965b3;
}
</style>
