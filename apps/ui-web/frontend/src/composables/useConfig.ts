/**
 * Composable for configuration management API.
 *
 * Provides reactive state and methods for fetching and updating
 * service configurations.
 */

import { ref, computed, Ref } from "vue";
import type {
  ServiceListResponse,
  ConfigGetResponse,
  ConfigUpdateRequest,
  ConfigUpdateResponse,
  ServiceConfig,
} from "../types/config";

// API base URL - adjust for your deployment
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/config";

/**
 * Composable for configuration management.
 *
 * Usage:
 * ```ts
 * const { services, loading, error, loadServices, loadConfig, updateConfig } = useConfig();
 * await loadServices();
 * const config = await loadConfig('stt-worker');
 * ```
 */
export function useConfig() {
  // State
  const services: Ref<string[]> = ref([]);
  const currentConfig: Ref<ServiceConfig | null> = ref(null);
  const loading = ref(false);
  const error: Ref<string | null> = ref(null);

  // Computed
  const hasServices = computed(() => services.value.length > 0);
  const hasConfig = computed(() => currentConfig.value !== null);

  /**
   * Load list of available services.
   */
  async function loadServices(): Promise<void> {
    loading.value = true;
    error.value = null;

    try {
      const response = await fetch(`${API_BASE_URL}/services`);
      if (!response.ok) {
        throw new Error(`Failed to load services: ${response.statusText}`);
      }

      const data: ServiceListResponse = await response.json();
      services.value = data.services;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Unknown error";
      console.error("Failed to load services:", err);
    } finally {
      loading.value = false;
    }
  }

  /**
   * Load configuration for a specific service.
   *
   * @param serviceName - Name of the service
   * @returns Service configuration or null on error
   */
  async function loadConfig(serviceName: string): Promise<ServiceConfig | null> {
    loading.value = true;
    error.value = null;

    try {
      const response = await fetch(`${API_BASE_URL}/services/${serviceName}`);
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error(`Service '${serviceName}' not found`);
        }
        throw new Error(`Failed to load config: ${response.statusText}`);
      }

      const data: ConfigGetResponse = await response.json();

      // Convert snake_case to camelCase for TypeScript
      const config: ServiceConfig = {
        service: data.service,
        config: data.config,
        version: data.version,
        updatedAt: data.updated_at,
        configEpoch: data.config_epoch,
      };

      currentConfig.value = config;
      return config;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Unknown error";
      console.error("Failed to load config:", err);
      return null;
    } finally {
      loading.value = false;
    }
  }

  /**
   * Update configuration for a service.
   *
   * Implements optimistic locking - if the version has changed since
   * the config was loaded, the update will fail with 409 Conflict.
   *
   * @param serviceName - Name of the service
   * @param config - Updated configuration dictionary
   * @param version - Expected current version
   * @returns Update response or null on error
   */
  async function updateConfig(
    serviceName: string,
    config: Record<string, any>,
    version: number
  ): Promise<ConfigUpdateResponse | null> {
    loading.value = true;
    error.value = null;

    try {
      const request: ConfigUpdateRequest = {
        service: serviceName,
        config,
        version,
      };

      const response = await fetch(`${API_BASE_URL}/services/${serviceName}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        if (response.status === 409) {
          throw new Error(
            "Configuration was modified by another user. Please reload and try again."
          );
        }
        if (response.status === 400) {
          const data = await response.json();
          throw new Error(data.detail || "Invalid configuration");
        }
        throw new Error(`Failed to update config: ${response.statusText}`);
      }

      const data: ConfigUpdateResponse = await response.json();

      // Reload configuration to get latest version
      await loadConfig(serviceName);

      return data;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Unknown error";
      console.error("Failed to update config:", err);
      return null;
    } finally {
      loading.value = false;
    }
  }

  /**
   * Clear current state.
   */
  function reset(): void {
    services.value = [];
    currentConfig.value = null;
    error.value = null;
  }

  return {
    // State
    services,
    currentConfig,
    loading,
    error,

    // Computed
    hasServices,
    hasConfig,

    // Methods
    loadServices,
    loadConfig,
    updateConfig,
    reset,
  };
}
