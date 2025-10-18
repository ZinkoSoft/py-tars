/**
 * Composable for monitoring configuration manager health.
 *
 * Polls the health endpoint at regular intervals to track service status.
 */

import { ref, onMounted, onUnmounted, Ref } from 'vue';

export interface HealthStatus {
  ok: boolean;
  service: string;
  version?: string;
  timestamp?: string;
}

const HEALTH_URL = import.meta.env.VITE_API_BASE_URL
  ? `${import.meta.env.VITE_API_BASE_URL.replace('/api/config', '')}/health`
  : '/health';

/**
 * Composable for health monitoring.
 *
 * Usage:
 * ```ts
 * const { isHealthy, lastUpdate, startPolling, stopPolling } = useHealth();
 * startPolling(5000); // Poll every 5 seconds
 * ```
 */
export function useHealth(pollInterval = 10000) {
  const isHealthy: Ref<boolean> = ref(true);
  const lastUpdate: Ref<Date> = ref(new Date());
  const healthData: Ref<HealthStatus | null> = ref(null);
  let intervalId: number | null = null;

  /**
   * Check health status.
   */
  async function checkHealth(): Promise<void> {
    try {
      const response = await fetch(HEALTH_URL, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        isHealthy.value = false;
        lastUpdate.value = new Date();
        return;
      }

      const data: HealthStatus = await response.json();
      healthData.value = data;
      isHealthy.value = data.ok;
      lastUpdate.value = new Date();
    } catch (err) {
      console.error('Health check failed:', err);
      isHealthy.value = false;
      lastUpdate.value = new Date();
    }
  }

  /**
   * Start polling for health updates.
   */
  function startPolling(interval: number = pollInterval): void {
    // Initial check
    checkHealth();

    // Set up polling
    if (intervalId !== null) {
      stopPolling();
    }

    intervalId = window.setInterval(() => {
      checkHealth();
    }, interval);
  }

  /**
   * Stop polling for health updates.
   */
  function stopPolling(): void {
    if (intervalId !== null) {
      clearInterval(intervalId);
      intervalId = null;
    }
  }

  // Auto-start polling on mount
  onMounted(() => {
    startPolling(pollInterval);
  });

  // Auto-stop polling on unmount
  onUnmounted(() => {
    stopPolling();
  });

  return {
    isHealthy,
    lastUpdate,
    healthData,
    checkHealth,
    startPolling,
    stopPolling,
  };
}
