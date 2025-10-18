<template>
  <div class="chat-panel panel">
    <ChatLog />
    <Composer />
    <div class="status-container">
      <StatusLine />
    </div>
  </div>
</template>

<script setup lang="ts">
import ChatLog from './ChatLog.vue'
import Composer from './Composer.vue'
import StatusLine from './StatusLine.vue'
</script>

<style scoped>
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.status-container {
  border-top: 1px solid var(--border);
}
</style>
