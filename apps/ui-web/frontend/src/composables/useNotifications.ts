/**
 * Composable for toast notifications.
 *
 * Provides a simple notification system for success/error/info messages.
 */

import { ref, Ref } from 'vue';

export type NotificationType = 'success' | 'error' | 'info' | 'warning';

export interface Notification {
  id: number;
  type: NotificationType;
  message: string;
  duration: number;
}

// Global notifications state (shared across all instances)
const notifications: Ref<Notification[]> = ref([]);
let nextId = 1;

/**
 * Composable for managing notifications.
 *
 * Usage:
 * ```ts
 * const { notify, notifications } = useNotifications();
 * notify.success('Configuration saved!');
 * notify.error('Failed to save configuration');
 * ```
 */
export function useNotifications() {
  /**
   * Add a notification.
   *
   * @param type - Notification type
   * @param message - Message to display
   * @param duration - Duration in milliseconds (0 = no auto-dismiss)
   */
  function add(
    type: NotificationType,
    message: string,
    duration = 5000
  ): void {
    const notification: Notification = {
      id: nextId++,
      type,
      message,
      duration,
    };

    notifications.value.push(notification);

    // Auto-remove after duration
    if (duration > 0) {
      setTimeout(() => {
        remove(notification.id);
      }, duration);
    }
  }

  /**
   * Remove a notification by ID.
   */
  function remove(id: number): void {
    const index = notifications.value.findIndex((n: Notification) => n.id === id);
    if (index !== -1) {
      notifications.value.splice(index, 1);
    }
  }

  /**
   * Clear all notifications.
   */
  function clear(): void {
    notifications.value = [];
  }

  // Convenience methods
  const notify = {
    success: (message: string, duration = 3000) =>
      add('success', message, duration),
    error: (message: string, duration = 5000) =>
      add('error', message, duration),
    info: (message: string, duration = 4000) =>
      add('info', message, duration),
    warning: (message: string, duration = 4000) =>
      add('warning', message, duration),
  };

  return {
    notifications,
    notify,
    remove,
    clear,
  };
}
