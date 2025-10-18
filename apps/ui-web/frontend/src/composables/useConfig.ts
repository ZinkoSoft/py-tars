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
  SearchRequest,
  SearchResponse,
} from "../types/config";

// API base URL - adjust for your deployment
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/config";

// API Token management
const API_TOKEN_KEY = "api_token";
const CSRF_TOKEN_KEY = "csrf_token";

interface UserRole {
  name: string;
  role: string;
  permissions: string[];
}

/**
 * Get API token from localStorage or environment.
 */
function getApiToken(): string | null {
  // Try localStorage first
  const stored = localStorage.getItem(API_TOKEN_KEY);
  if (stored) {
    return stored;
  }
  
  // Try environment variable
  const envToken = import.meta.env.VITE_API_TOKEN;
  if (envToken) {
    return envToken;
  }
  
  return null;
}

/**
 * Set API token in localStorage.
 */
function setApiToken(token: string): void {
  localStorage.setItem(API_TOKEN_KEY, token);
}

/**
 * Get CSRF token from localStorage.
 */
function getCsrfToken(): string | null {
  return localStorage.getItem(CSRF_TOKEN_KEY);
}

/**
 * Set CSRF token in localStorage.
 */
function setCsrfToken(token: string): void {
  localStorage.setItem(CSRF_TOKEN_KEY, token);
}

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
  const userRole: Ref<UserRole | null> = ref(null);
  const csrfToken = ref<string | null>(getCsrfToken());

  // Computed
  const hasServices = computed(() => services.value.length > 0);
  const hasConfig = computed(() => currentConfig.value !== null);
  const canWrite = computed(() => {
    if (!userRole.value) return false;
    return (
      userRole.value.permissions.includes("config.write") ||
      userRole.value.role === "admin"
    );
  });
  const canRead = computed(() => {
    if (!userRole.value) return false;
    return (
      userRole.value.permissions.includes("config.read") ||
      userRole.value.role === "admin"
    );
  });

  /**
   * Build headers for API requests with authentication.
   */
  function buildHeaders(includeCSRF = false): HeadersInit {
    const headers: HeadersInit = {
      "Content-Type": "application/json",
    };

    const apiToken = getApiToken();
    if (apiToken) {
      headers["X-API-Token"] = apiToken;
    }

    if (includeCSRF && csrfToken.value) {
      headers["X-CSRF-Token"] = csrfToken.value;
    }

    return headers;
  }

  /**
   * Fetch CSRF token from the API.
   */
  async function fetchCsrfToken(): Promise<void> {
    try {
      const response = await fetch(`${API_BASE_URL}/csrf-token`, {
        headers: buildHeaders(),
      });

      if (response.ok) {
        const data = await response.json();
        csrfToken.value = data.csrf_token;
        setCsrfToken(data.csrf_token);
      }
    } catch (err) {
      console.error("Failed to fetch CSRF token:", err);
    }
  }

  /**
   * Detect user role from API response headers or a dedicated endpoint.
   * For now, we infer role from successful API calls.
   */
  async function detectUserRole(): Promise<void> {
    // Try to fetch services to determine if user has read access
    try {
      const response = await fetch(`${API_BASE_URL}/services`, {
        headers: buildHeaders(),
      });

      if (response.ok) {
        // User has at least read access
        // In a real implementation, the API would return role info
        // For now, we assume write access if token is present
        const apiToken = getApiToken();
        userRole.value = {
          name: "User",
          role: apiToken ? "config.write" : "config.read",
          permissions: apiToken
            ? ["config.read", "config.write"]
            : ["config.read"],
        };
      } else if (response.status === 401) {
        userRole.value = null;
        error.value = "Authentication required. Please provide an API token.";
      } else if (response.status === 403) {
        userRole.value = {
          name: "User",
          role: "config.read",
          permissions: ["config.read"],
        };
      }
    } catch (err) {
      console.error("Failed to detect user role:", err);
    }
  }

  /**
   * Load list of available services.
   */
  async function loadServices(): Promise<void> {
    loading.value = true;
    error.value = null;

    // Ensure we have role info
    // Note: CSRF token is only needed for mutations (PUT/POST/DELETE), not GET requests
    if (!userRole.value) {
      await detectUserRole();
    }

    try {
      const response = await fetch(`${API_BASE_URL}/services`, {
        headers: buildHeaders(),
      });
      
      if (response.status === 401) {
        throw new Error("Authentication required. Please provide an API token.");
      }
      if (response.status === 403) {
        throw new Error("Insufficient permissions to view services.");
      }
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
      const response = await fetch(`${API_BASE_URL}/services/${serviceName}`, {
        headers: buildHeaders(),
      });
      
      if (response.status === 401) {
        throw new Error("Authentication required. Please provide an API token.");
      }
      if (response.status === 403) {
        throw new Error("Insufficient permissions to view configuration.");
      }
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

    // Ensure we have CSRF token
    if (!csrfToken.value) {
      await fetchCsrfToken();
    }

    try {
      const request: ConfigUpdateRequest = {
        service: serviceName,
        config,
        version,
      };

      const response = await fetch(`${API_BASE_URL}/services/${serviceName}`, {
        method: "PUT",
        headers: buildHeaders(true), // Include CSRF token
        body: JSON.stringify(request),
      });

      if (response.status === 401) {
        throw new Error("Authentication required. Please provide an API token.");
      }
      if (response.status === 403) {
        throw new Error("Insufficient permissions to update configuration.");
      }
      if (!response.ok) {
        if (response.status === 409) {
          throw new Error(
            "Configuration was modified by another user. Please reload and try again."
          );
        }
        if (response.status === 422) {
          const data = await response.json();
          const errors = data.detail?.errors || [];
          const errorMessages = errors.map((e: any) => `${e.field}: ${e.message}`).join(", ");
          throw new Error(`Validation failed: ${errorMessages || "Invalid configuration"}`);
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
   * Search configurations across all services.
   *
   * @param query - Search query string
   * @param serviceFilter - Optional service name filter
   * @param complexityFilter - Optional complexity filter (simple/advanced)
   * @param maxResults - Maximum number of results (default: 50)
   * @returns Search results or null on error
   */
  async function searchConfigurations(
    query: string,
    serviceFilter?: string | null,
    complexityFilter?: string | null,
    maxResults: number = 50
  ): Promise<SearchResponse | null> {
    loading.value = true;
    error.value = null;

    try {
      const request: SearchRequest = {
        query,
        service_filter: serviceFilter || undefined,
        complexity_filter: complexityFilter || undefined,
        max_results: maxResults,
      };

      const response = await fetch(`${API_BASE_URL}/search`, {
        method: "POST",
        headers: buildHeaders(),
        body: JSON.stringify(request),
      });

      if (response.status === 401) {
        throw new Error("Authentication required. Please provide an API token.");
      }
      if (response.status === 403) {
        throw new Error("Insufficient permissions to search configurations.");
      }
      if (!response.ok) {
        throw new Error(`Search failed: ${response.statusText}`);
      }

      const data: SearchResponse = await response.json();
      return data;
    } catch (err) {
      error.value = err instanceof Error ? err.message : "Unknown error";
      console.error("Search failed:", err);
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
    userRole,

    // Computed
    hasServices,
    hasConfig,
    canWrite,
    canRead,

    // Methods
    loadServices,
    loadConfig,
    updateConfig,
    searchConfigurations,
    reset,
    detectUserRole,
    setApiToken: (token: string) => {
      setApiToken(token);
      // Reset role on token change
      userRole.value = null;
      detectUserRole();
    },
  };
}
