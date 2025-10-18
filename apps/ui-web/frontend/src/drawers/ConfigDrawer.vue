<template>
  <div class="config-drawer">
    <ApiTokenPrompt @token-set="handleTokenSet" />
    <Panel title="Service Configuration">
      <div class="config-container">
        <ConfigTabs :key="configKey" />
      </div>
    </Panel>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import Panel from '../components/Panel.vue';
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
}

.config-container {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* Override Panel styles to make it fill space and scroll */
:deep(.panel) {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

:deep(.panel__content) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 0;
}
</style>
