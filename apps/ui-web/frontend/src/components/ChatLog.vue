<template>
  <div ref="logRef" class="chat-log">
    <ChatBubble
      v-for="message in messages"
      :key="message.id"
      :role="message.role"
      :text="message.text"
      :meta="message.meta"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useChatStore } from '../stores/chat'
import ChatBubble from './ChatBubble.vue'

const chatStore = useChatStore()
const logRef = ref<HTMLElement | null>(null)

const messages = chatStore.messages

// Auto-scroll to bottom when new messages arrive
watch(
  () => chatStore.messages.length,
  async () => {
    await nextTick()
    if (logRef.value) {
      logRef.value.scrollTop = logRef.value.scrollHeight
    }
  }
)
</script>

<style scoped>
.chat-log {
  flex: 1;
  padding: 12px;
  overflow-y: auto;
  scroll-behavior: smooth;
}
</style>
