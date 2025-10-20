/**
 * UI Store
 *
 * Manages UI state including drawer visibility and application status.
 *
 * @module stores/ui
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { DrawerType, DrawerState, AppState } from '../types/ui'

export const useUIStore = defineStore('ui', () => {
  // Drawer state
  const activeDrawer = ref<DrawerType | null>(null)
  const backdropVisible = ref(false)

  // App state
  const listening = ref(false)
  const processing = ref(false)
  const llmWriting = ref(false)

  // Computed
  const drawerState = computed<DrawerState>(() => ({
    activeDrawer: activeDrawer.value,
    backdropVisible: backdropVisible.value
  }))

  const appState = computed<AppState>(() => ({
    listening: listening.value,
    processing: processing.value,
    llmWriting: llmWriting.value,
    statusText: getStatusText()
  }))

  const isDrawerOpen = computed(() => activeDrawer.value !== null)

  // Actions
  function openDrawer(drawer: DrawerType): void {
    if (activeDrawer.value === drawer) {
      // Toggle off if same drawer
      closeDrawer()
      return
    }

    activeDrawer.value = drawer
    backdropVisible.value = true
  }

  function closeDrawer(): void {
    activeDrawer.value = null
    backdropVisible.value = false
  }

  function toggleDrawer(drawer: DrawerType): void {
    if (activeDrawer.value === drawer) {
      closeDrawer()
    } else {
      openDrawer(drawer)
    }
  }

  function setListening(value: boolean): void {
    listening.value = value
  }

  function setProcessing(value: boolean): void {
    processing.value = value
  }

  function setLLMWriting(value: boolean): void {
    llmWriting.value = value
  }

  function getStatusText(): string {
    const statuses: string[] = []

    if (listening.value) statuses.push('Listening…')
    if (processing.value) statuses.push('Processing audio…')
    if (llmWriting.value) statuses.push('TARS is writing…')

    return statuses.length ? statuses.join(' • ') : 'Idle'
  }

  return {
    // Drawer state
    activeDrawer,
    backdropVisible,
    drawerState,
    isDrawerOpen,

    // App state
    listening,
    processing,
    llmWriting,
    appState,

    // Actions
    openDrawer,
    closeDrawer,
    toggleDrawer,
    setListening,
    setProcessing,
    setLLMWriting
  }
})
