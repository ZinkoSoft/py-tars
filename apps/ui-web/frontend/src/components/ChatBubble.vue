<template>
  <div class="chat-bubble-wrapper" :class="roleClass">
    <div class="bubble" :class="role">
      {{ text }}
    </div>
    <div v-if="meta" class="meta">{{ meta }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ChatRole } from '../types/ui'

interface Props {
  role: ChatRole
  text: string
  meta?: string
}

const props = defineProps<Props>()

const roleClass = computed(() => `role-${props.role}`)
</script>

<style scoped>
.chat-bubble-wrapper {
  display: flex;
  flex-direction: column;
  max-width: 72%;
  margin: 8px 0;
}

.role-user {
  margin-left: auto;
}

.bubble {
  padding: 10px 12px;
  border-radius: 12px;
  line-height: 1.3;
  word-wrap: break-word;
  white-space: pre-wrap;
}

.bubble.tars {
  background: var(--tars);
  border: 1px solid #2e3c78;
  border-top-left-radius: 4px;
}

.bubble.user {
  background: var(--user);
  border: 1px solid #2c7a51;
  border-top-right-radius: 4px;
}

.meta {
  font-size: 12px;
  color: var(--muted);
  margin: 6px 2px 0 2px;
}
</style>
