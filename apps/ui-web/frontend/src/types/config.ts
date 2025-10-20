/**
 * TypeScript types for configuration management system.
 *
 * Mirrors the Pydantic models in tars.config.models and api responses.
 */

/**
 * Configuration complexity level - determines visibility in UI.
 */
export type ConfigComplexity = "simple" | "advanced";

/**
 * Configuration value types - maps to Pydantic field types.
 */
export type ConfigType =
  | "string"
  | "integer"
  | "float"
  | "boolean"
  | "enum"
  | "path"
  | "secret";

/**
 * Configuration source - where the value comes from.
 */
export type ConfigSource = "env" | "database" | "default";

/**
 * Validation constraints for a configuration field.
 */
export interface ConfigValidation {
  /** Minimum value (for numeric types) */
  min?: number;
  /** Maximum value (for numeric types) */
  max?: number;
  /** Regex pattern (for string types) */
  pattern?: string;
  /** Human-readable description of the pattern (for error messages) */
  patternDescription?: string;
  /** Allowed values (for enum types) */
  allowed?: string[];
  /** Minimum length (for string types) */
  minLength?: number;
  /** Maximum length (for string types) */
  maxLength?: number;
}

/**
 * Metadata for a single configuration field.
 */
export interface ConfigFieldMetadata {
  /** Field key/name */
  key: string;
  /** Current value */
  value: any;
  /** Value type */
  type: ConfigType;
  /** Complexity level (simple or advanced) */
  complexity: ConfigComplexity;
  /** Human-readable description */
  description: string;
  /** Optional help text with usage examples */
  helpText?: string;
  /** Example values */
  examples?: string[];
  /** Validation constraints */
  validation?: ConfigValidation;
  /** Whether field is required */
  required: boolean;
  /** Where the current value came from */
  source: ConfigSource;
  /** Whether value is overridden by environment variable */
  envOverride: boolean;
  /** Environment variable name (if overridden) */
  envVar?: string;
  /** Default value */
  default?: any;
}

/**
 * Service configuration with metadata.
 */
export interface ServiceConfig {
  /** Service name (e.g., "stt-worker") */
  service: string;
  /** Configuration dictionary (raw values) */
  config: Record<string, any>;
  /** Configuration version for optimistic locking */
  version: number;
  /** ISO8601 timestamp of last update */
  updatedAt: string;
  /** Current configuration epoch identifier */
  configEpoch: string;
  /** Optional: field metadata (if requested) */
  fields?: ConfigFieldMetadata[];
}

/**
 * Response from GET /api/config/services.
 */
export interface ServiceListResponse {
  /** List of available service names */
  services: string[];
}

/**
 * Response from GET /api/config/services/{service}.
 */
export interface ConfigGetResponse {
  /** Service name */
  service: string;
  /** Configuration dictionary */
  config: Record<string, any>;
  /** Configuration version */
  version: number;
  /** ISO8601 timestamp of last update */
  updated_at: string;
  /** Current configuration epoch */
  config_epoch: string;
  /** Field metadata with descriptions, help text, examples */
  fields: Array<{
    key: string;
    type: string;
    complexity: string;
    description: string;
    help_text: string | null;
    examples: string[] | null;
    is_secret: boolean;
  }>;
}

/**
 * Request for PUT /api/config/services/{service}.
 */
export interface ConfigUpdateRequest {
  /** Service name */
  service: string;
  /** Updated configuration dictionary */
  config: Record<string, any>;
  /** Expected current version (for optimistic locking) */
  version: number;
}

/**
 * Response from PUT /api/config/services/{service}.
 */
export interface ConfigUpdateResponse {
  /** Whether update succeeded */
  success: boolean;
  /** New configuration version */
  version: number;
  /** Current configuration epoch */
  config_epoch: string;
  /** Optional success/error message */
  message?: string;
}

/**
 * MQTT configuration update payload (config/update topic).
 */
export interface ConfigUpdatePayload {
  /** Service name */
  service: string;
  /** Updated configuration dictionary */
  config: Record<string, any>;
  /** New configuration version */
  version: number;
  /** Configuration epoch */
  config_epoch: string;
  /** Ed25519 signature (hex-encoded) */
  signature?: string;
  /** Timestamp (ISO8601) */
  timestamp?: string;
}

/**
 * Health status payload (system/health/config-manager topic).
 */
export interface ConfigHealthPayload {
  /** Whether service is healthy */
  ok: boolean;
  /** Optional event description */
  event?: string;
  /** Optional error message */
  error?: string;
}

/**
 * Validation error for a specific field.
 */
export interface ValidationError {
  /** Field key */
  field: string;
  /** Error message */
  message: string;
}

/**
 * UI state for configuration editor.
 */
export interface ConfigEditorState {
  /** Currently selected service */
  selectedService: string | null;
  /** Current configuration data */
  config: ServiceConfig | null;
  /** Pending changes (modified but not saved) */
  pendingChanges: Record<string, any>;
  /** Validation errors */
  errors: ValidationError[];
  /** Whether save is in progress */
  saving: boolean;
  /** Whether configuration is loading */
  loading: boolean;
  /** User's complexity mode preference */
  complexityMode: "simple" | "advanced";
}

/**
 * Search request payload.
 */
export interface SearchRequest {
  /** Search query string */
  query: string;
  /** Optional service name filter */
  service_filter?: string;
  /** Optional complexity filter (simple/advanced) */
  complexity_filter?: string;
  /** Maximum number of results (1-200, default 50) */
  max_results?: number;
}

/**
 * Single search result item.
 */
export interface SearchResultItem {
  /** Service name */
  service: string;
  /** Configuration key */
  key: string;
  /** Current value (omitted for secrets) */
  value?: string | null;
  /** Value type */
  type: string;
  /** Complexity level */
  complexity: string;
  /** Description */
  description: string;
  /** Whether value is a secret */
  is_secret: boolean;
  /** Relevance score (0-1) */
  match_score: number;
}

/**
 * Search response payload.
 */
export interface SearchResponse {
  /** Original search query */
  query: string;
  /** Matching configuration items */
  results: SearchResultItem[];
  /** Total number of results */
  total_count: number;
}
