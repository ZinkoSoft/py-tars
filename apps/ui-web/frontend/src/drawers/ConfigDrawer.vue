<template>
  <div class="config-drawer">
    <ApiTokenPrompt @token-set="handleTokenSet" />
    <div class="config-container">
      <ConfigTabs :key="configKey" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import ConfigTabs from '../components/ConfigTabs.vue';
import ApiTokenPrompt from '../components/ApiTokenPrompt.vue';

// Force re-render ConfigTabs when token is set
const configKey = ref(0);

function handleTokenSet() {
  // Increment key to force ConfigTabs to reload
  configKey.value++;
}
</script>

<style scoped>
.config-drawer {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--vscode-editor-background);
}

.config-container {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
</style>
