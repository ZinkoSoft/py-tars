<template>
  <div class="config-drawer">
    <Panel title="Service Configuration">
      <div class="config-container">
        <ConfigTabs />
      </div>
    </Panel>
  </div>
</template>

<script setup lang="ts">
import Panel from '../components/Panel.vue';
import ConfigTabs from '../components/ConfigTabs.vue';
</script>

<style scoped>
.config-drawer {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.config-container {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* Override Panel styles to give more space */
:deep(.panel-content) {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 0;
}
</style>
