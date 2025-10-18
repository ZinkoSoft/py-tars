<template>
  <div class="app">
    <div class="app__top-bar">
      <Header />
      <Toolbar @open-drawer="handleOpenDrawer" />
    </div>

    <main class="app__main">
      <ChatPanel />
    </main>

    <!-- Drawers -->
    <DrawerContainer
      :is-open="uiStore.activeDrawer === 'mic'"
      title="Microphone"
      @close="uiStore.closeDrawer"
    >
      <MicrophoneDrawer />
    </DrawerContainer>

    <DrawerContainer
      :is-open="uiStore.activeDrawer === 'memory'"
      title="Memory"
      @close="uiStore.closeDrawer"
    >
      <MemoryDrawer />
    </DrawerContainer>

    <DrawerContainer
      :is-open="uiStore.activeDrawer === 'stream'"
      title="MQTT Stream"
      @close="uiStore.closeDrawer"
    >
      <MQTTStreamDrawer />
    </DrawerContainer>

    <DrawerContainer
      :is-open="uiStore.activeDrawer === 'camera'"
      title="Camera"
      @close="uiStore.closeDrawer"
    >
      <CameraDrawer />
    </DrawerContainer>

    <DrawerContainer
      :is-open="uiStore.activeDrawer === 'health'"
      title="System Health"
      @close="uiStore.closeDrawer"
    >
      <HealthDrawer />
    </DrawerContainer>
  </div>
</template>

<script setup lang="ts">
import { watch, computed, defineAsyncComponent } from 'vue';
import Header from './components/Header.vue';
import Toolbar from './components/Toolbar.vue';
import ChatPanel from './components/ChatPanel.vue';
import DrawerContainer from './components/DrawerContainer.vue';
// Lazy load drawer components for better code splitting
const MicrophoneDrawer = defineAsyncComponent(() => import('./drawers/MicrophoneDrawer.vue'));
const MemoryDrawer = defineAsyncComponent(() => import('./drawers/MemoryDrawer.vue'));
const MQTTStreamDrawer = defineAsyncComponent(() => import('./drawers/MQTTStreamDrawer.vue'));
const CameraDrawer = defineAsyncComponent(() => import('./drawers/CameraDrawer.vue'));
const HealthDrawer = defineAsyncComponent(() => import('./drawers/HealthDrawer.vue'));
import { useWebSocketStore } from './stores/websocket';
import { useChatStore } from './stores/chat';
import { useUIStore } from './stores/ui';
import type { DrawerType } from './types/ui';

const wsStore = useWebSocketStore()
const chatStore = useChatStore()
const uiStore = useUIStore()

// Connect WebSocket on mount
wsStore.connect()

// Update listening state based on partial text
watch(
  () => chatStore.partialText,
  (partial: string) => {
    uiStore.setListening(!!partial)
  }
)

// Check if any messages are streaming
const isStreaming = computed(() => {
  return chatStore.messages.some(msg => msg.streaming)
})

// Update LLM writing state based on streaming messages
watch(isStreaming, (streaming: boolean) => {
  uiStore.setLLMWriting(streaming)
})

const handleOpenDrawer = (drawer: DrawerType) => {
  uiStore.openDrawer(drawer)
}
</script>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.app__top-bar {
  flex-shrink: 0;
}

.app__main {
  flex: 1;
  overflow: hidden;
  display: flex;
}
</style>
