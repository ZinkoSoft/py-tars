<template>
  <Teleport to="body">
    <!-- Backdrop -->
    <Transition name="fade">
      <div v-if="isOpen" class="drawer-backdrop" @click="handleBackdropClick" />
    </Transition>

    <!-- Drawer -->
    <Transition name="slide">
      <div
        v-if="isOpen"
        :class="['drawer', `drawer--${position}`]"
        role="dialog"
        aria-modal="true"
        :aria-label="ariaLabel"
      >
        <div class="drawer__header">
          <h2 class="drawer__title">{{ title }}</h2>
          <button
            class="drawer__close"
            type="button"
            aria-label="Close drawer"
            @click="handleClose"
          >
            ✕
          </button>
        </div>
        <div class="drawer__content">
          <slot />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, watch } from 'vue'

interface Props {
  isOpen: boolean
  title?: string
  position?: 'left' | 'right'
  ariaLabel?: string
  closeOnBackdrop?: boolean
  closeOnEscape?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  title: 'Drawer',
  position: 'right',
  ariaLabel: undefined,
  closeOnBackdrop: true,
  closeOnEscape: true
})

const emit = defineEmits<{
  close: []
}>()

const handleClose = () => {
  emit('close')
}

const handleBackdropClick = () => {
  if (props.closeOnBackdrop) {
    handleClose()
  }
}

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && props.closeOnEscape && props.isOpen) {
    handleClose()
  }
}

// Lock body scroll when drawer is open
watch(
  () => props.isOpen,
  isOpen => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
  }
)

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
  document.body.style.overflow = ''
})
</script>

<style scoped>
.drawer-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1000;
}

.drawer {
  position: fixed;
  top: 0;
  bottom: 0;
  width: min(400px, 90vw);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  z-index: 1001;
}

.drawer--left {
  left: 0;
  border-left: none;
}

.drawer--right {
  right: 0;
  border-right: none;
}

.drawer__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface);
}

.drawer__title {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--color-text);
}

.drawer__close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: var(--color-text-secondary);
  font-size: 1.5rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.drawer__close:hover {
  background: var(--color-surface);
  color: var(--color-text);
}

.drawer__content {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-enter-active,
.slide-leave-active {
  transition: transform 0.3s ease;
}

.drawer--left.slide-enter-from,
.drawer--left.slide-leave-to {
  transform: translateX(-100%);
}

.drawer--right.slide-enter-from,
.drawer--right.slide-leave-to {
  transform: translateX(100%);
}
</style>
