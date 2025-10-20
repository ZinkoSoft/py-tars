<template>
  <div class="toast-container">
    <transition-group name="toast">
      <div
        v-for="notification in notifications"
        :key="notification.id"
        :class="['toast', `toast-${notification.type}`]"
        @click="remove(notification.id)"
      >
        <div class="toast-icon">
          <span v-if="notification.type === 'success'">✓</span>
          <span v-else-if="notification.type === 'error'">✕</span>
          <span v-else-if="notification.type === 'warning'">⚠</span>
          <span v-else>ℹ</span>
        </div>
        <div class="toast-message">{{ notification.message }}</div>
        <button class="toast-close" @click.stop="remove(notification.id)">
          ×
        </button>
      </div>
    </transition-group>
  </div>
</template>

<script setup lang="ts">
import { useNotifications } from '../composables/useNotifications';

const { notifications, remove } = useNotifications();
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 1rem;
  right: 1rem;
  z-index: 10000;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-width: 400px;
}

.toast {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  cursor: pointer;
  transition: all 0.3s ease;
  min-width: 300px;
}

.toast:hover {
  transform: translateX(-4px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
}

.toast-success {
  background: #4caf50;
  color: white;
}

.toast-error {
  background: #f44336;
  color: white;
}

.toast-warning {
  background: #ff9800;
  color: white;
}

.toast-info {
  background: #2196f3;
  color: white;
}

.toast-icon {
  font-size: 1.5rem;
  font-weight: bold;
  flex-shrink: 0;
}

.toast-message {
  flex: 1;
  font-size: 0.95rem;
  line-height: 1.4;
}

.toast-close {
  background: none;
  border: none;
  color: inherit;
  font-size: 1.5rem;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  margin: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  flex-shrink: 0;
  transition: background 0.2s;
}

.toast-close:hover {
  background: rgba(0, 0, 0, 0.1);
}

/* Transitions */
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(100%) scale(0.8);
}
</style>
