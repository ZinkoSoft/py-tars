# Feature Specification: Unified Configuration Management System

**Feature Branch**: `005-unified-configuration-management`  
**Created**: 2025-10-17  
**Status**: Draft  
**Input**: User description: "Unified configuration management system with web UI for managing application settings"

## Clarifications

### Session 2025-10-17

- Q: How should services retrieve their configuration values at startup and runtime? → A: Combined approach - Services read from database at startup, then subscribe to MQTT for runtime updates
- Q: Should secrets be stored in the database at all, or kept exclusively in .env files? → A: Hybrid storage - Common secrets (API keys) in .env; user-created secrets (custom tokens) encrypted in database
- Q: What is the priority order when a configuration value exists in multiple sources? → A: .env secrets override, database for others - Secrets always from .env (immutable); all other configs from database
- Q: How should the encryption key for database secrets be generated and managed? → A: Auto-generate on first run - System generates secure key, writes to .env automatically if missing, logs warning
- Q: When the configuration database is corrupted or inaccessible, how should the system recover? → A: Hybrid recovery - Default read-only fallback mode (C) with opt-in auto-rebuild (B) via ALLOW_AUTO_REBUILD=1 flag or admin endpoint with token
- Q: What database technology and backup strategy should be used? → A: SQLite in WAL mode with app-level AES-GCM encryption (or SQLCipher), Litestream for continuous backups to S3/MinIO, HMAC-signed LKG cache (config.lkg.json) for instant read-only fallback
- Q: How should configurations be organized in the web UI? → A: Utilize existing app tabs (Health, Microphone, Memory, MQTT Stream, Camera) with configuration placeholders; create new tabs for services without existing UI presence; add global settings accessible via settings cog icon in top right for cross-service configurations
- Q: Where should configuration database access logic be implemented? → A: Centralized in tars-core package as global configuration library; each service config uses Pydantic models; services only call library to get/receive configs, never access database directly
- Q: Should encryption and HMAC signing use the same key or separate keys? → A: Split keys - CONFIG_MASTER_KEY_BASE64 (32 bytes) for AES-256-GCM encryption of DB secrets; LKG_HMAC_KEY_BASE64 (32 bytes) for HMAC-SHA256 signing of config.lkg.json. Auto-generate both on first run; if .env unwritable, print to stdout once and fail fast. Track rotation via CONFIG_MASTER_KEY_ID and LKG_HMAC_KEY_ID with re-encrypt job when master key changes
- Q: Should the database use a single JSON blob table or normalized per-key tables for configurations? → A: Dual structure - Canonical service_configs table stores complete service snapshots as JSON for atomic consistency; derived config_items table stores per-key records (service, key, value_json, type, complexity, description, updated_at) for fast search and change history without JSON parsing overhead
- Q: How should MQTT configuration update messages be secured against tampering or spoofing? → A: Ed25519 signatures - Messages include {version, checksum, issued_at, signature} envelope signed with CONFIG_SIGNATURE_PRIVATE_KEY; services verify with CONFIG_SIGNATURE_PUBLIC_KEY from .env before applying updates; published to system/config/<service> with QoS 1 + retained flag
- Q: How should database schema compatibility be tracked and validated as Pydantic models evolve? → A: Schema version tracking - schema_version table (id=1, version, model_hash, updated_at) stores current version and SHA256 hash of all Pydantic model schemas; on startup, compute hash and compare with stored model_hash; if mismatch, log warning and enter read-only fallback mode, require ALLOW_AUTO_REBUILD=1 to recreate; increment version for structural changes; store in health+epoch metadata for cluster alignment
- Q: What level of access control should be implemented for configuration management operations? → A: Minimal two-role system - config.read (default role, view non-secret configs) and config.write (required to save changes, reveal secrets, trigger rebuild); add CSRF protection for web UI and API token authentication for REST endpoints to prevent unauthorized modifications

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View and Update Basic Service Settings (Priority: P1)

A system administrator needs to adjust basic service configurations (like audio volume, wake word sensitivity, or TTS voice) through an intuitive web interface without editing files or restarting services.

**Why this priority**: Core functionality that delivers immediate value by replacing manual .env file editing with a user-friendly interface. Most common administrative task.

**Independent Test**: Can be fully tested by loading the web UI configuration page, changing a simple setting (e.g., TTS voice), saving it, and verifying the change persists across service restarts. Delivers immediate administrative value.

**Acceptance Scenarios**:

1. **Given** the web UI is loaded, **When** the user navigates to an existing service tab (e.g., Microphone, Memory), **Then** all current configuration values for that service are displayed with their current settings loaded from the database
2. **Given** a new service tab is created (e.g., Router, LLM Worker), **When** the user navigates to it, **Then** all configurations specific to that service are displayed in a dedicated section
3. **Given** the user clicks the settings cog icon in the top right, **When** the global settings panel opens, **Then** cross-service configurations (MQTT broker, logging, system defaults) are displayed
4. **Given** a configuration field is displayed, **When** the user hovers over a help icon or field label, **Then** a tooltip appears explaining what the configuration does and its valid values
5. **Given** a basic configuration field (text, number, boolean), **When** the user changes the value and clicks save, **Then** the new value is persisted to the database and becomes active for the service
6. **Given** a configuration has been changed and saved to the database, **When** the change is published via MQTT, **Then** the affected service picks up the new value without requiring a manual restart
7. **Given** a service starts up, **When** it initializes, **Then** it reads all its configuration values directly from the database (not dependent on MQTT)
8. **Given** a .env-based secret and a database config exist for the same service, **When** the service loads configuration, **Then** the .env secret takes precedence and the database provides all other configs
9. **Given** a service-specific tab is displayed, **When** the page loads, **Then** a health status indicator shows whether the service is healthy/unhealthy/offline

---

### User Story 2 - Organize Settings by Simplicity Level (Priority: P1)

A casual user wants to see only the essential, commonly-used settings while an advanced user needs access to all available configurations including technical parameters.

**Why this priority**: Critical for usability - prevents overwhelming users with hundreds of options while still providing power users with full control. Enables progressive disclosure of complexity.

**Independent Test**: Can be tested by loading the UI in "simple mode" (showing only 10-20 essential settings) and toggling to "advanced mode" (showing all settings). Delivers value by making the system approachable for non-technical users.

**Acceptance Scenarios**:

1. **Given** the configuration UI is in simple mode, **When** the page loads, **Then** only settings marked as "commonly used" are visible (approximately 10-20 settings total)
2. **Given** the configuration UI is displayed, **When** the user toggles to "advanced mode", **Then** all available configuration options become visible, organized by service/category
3. **Given** a setting is categorized as advanced, **When** viewed in simple mode, **Then** it is hidden from view
4. **Given** a setting has a complexity level assigned, **When** displayed in the appropriate mode, **Then** it shows the same help information and validation rules regardless of mode

---

### User Story 3 - Validate Configuration Before Saving (Priority: P2)

A user changes multiple configuration values and wants to ensure they are valid before applying them to prevent service failures or unexpected behavior.

**Why this priority**: Prevents configuration errors that could break services, but can be added after basic read/write functionality is working.

**Independent Test**: Can be tested by entering invalid values (e.g., negative numbers for positive-only fields, invalid file paths, out-of-range values) and verifying that the UI prevents saving and shows clear error messages. Delivers value by preventing configuration mistakes.

**Acceptance Scenarios**:

1. **Given** a numeric configuration field with a valid range, **When** the user enters a value outside that range, **Then** an inline error message appears explaining the valid range
2. **Given** a configuration field with specific format requirements (e.g., URL, file path), **When** the user enters an invalid format, **Then** validation feedback appears before the save button is enabled
3. **Given** multiple configuration changes have validation errors, **When** the user attempts to save, **Then** the save is prevented and all errors are highlighted with clear correction guidance
4. **Given** all configuration values pass validation, **When** the user clicks save, **Then** the changes are applied and a success confirmation is shown
5. **Given** a user with config.read role attempts to save configuration changes, **When** they click save, **Then** the operation is blocked with clear message requiring config.write role
6. **Given** a user with config.write role saves configuration changes, **When** the save completes, **Then** the change is logged with user identity and timestamp

---

### User Story 4 - Search and Filter Configurations (Priority: P2)

An administrator looking for a specific setting needs to quickly find it among hundreds of possible configurations without browsing through all categories.

**Why this priority**: Enhances usability for systems with many services and configurations, but not critical for initial MVP.

**Independent Test**: Can be tested by typing a search term (e.g., "whisper") and verifying that only relevant configurations appear (e.g., WHISPER_MODEL, STT_BACKEND). Delivers value by improving navigation efficiency.

**Acceptance Scenarios**:

1. **Given** the configuration UI is loaded, **When** the user types a search term in the search box, **Then** only configurations matching the search term in name, description, or service are displayed
2. **Given** search results are displayed, **When** the user clears the search, **Then** all configurations return to their normal categorized view
3. **Given** advanced mode is enabled, **When** the user searches, **Then** results include both simple and advanced settings
4. **Given** simple mode is enabled, **When** the user searches, **Then** results include only simple settings unless the search explicitly matches an advanced setting name

---

### User Story 5 - Export and Import Configuration Profiles (Priority: P3)

A user wants to save their current configuration as a named profile and switch between different profiles for different use cases (e.g., "quiet mode" vs "full performance").

**Why this priority**: Nice-to-have feature for power users but not essential for basic configuration management.

**Independent Test**: Can be tested by saving current settings as "Profile A", changing settings, saving as "Profile B", then switching back to "Profile A" and verifying original settings are restored. Delivers value for users with multiple use cases.

**Acceptance Scenarios**:

1. **Given** the user is viewing current configurations, **When** they click "Save as Profile", **Then** they can name and save the current configuration state as a reusable profile
2. **Given** multiple profiles exist, **When** the user selects a different profile from a dropdown, **Then** all configurations are updated to match the selected profile
3. **Given** a profile is loaded, **When** the user makes changes without saving, **Then** the UI indicates unsaved changes and prompts before switching profiles or closing

---

### User Story 6 - View Configuration Change History (Priority: P3)

An administrator wants to see what configuration changes were made, when, and by whom to troubleshoot issues or audit system changes.

**Why this priority**: Useful for debugging and compliance but not required for basic functionality.

**Independent Test**: Can be tested by making several configuration changes over time and verifying that a history view shows each change with timestamp and previous/new values. Delivers value for troubleshooting and accountability.

**Acceptance Scenarios**:

1. **Given** configuration changes have been made, **When** the user views the change history, **Then** each change shows the configuration name, old value, new value, timestamp, and user (if authentication exists)
2. **Given** the change history is displayed, **When** the user filters by date range or configuration name, **Then** only relevant history entries are shown
3. **Given** a historical configuration state is selected, **When** the user clicks "Restore", **Then** the system offers to restore configurations to that point in time

---

### Edge Cases

- What happens when a configuration change is saved but the service cannot be reached to apply it? (Configuration update published to MQTT with retained flag and QoS 1; service receives signed update when it reconnects and verifies signature before applying)
- How does the system handle configuration conflicts when multiple users edit simultaneously? (Optimistic locking with conflict detection on save)
- What happens if the configuration database becomes corrupted? (Enter read-only fallback mode using .env secrets and HMAC-verified LKG cache; display red banner in UI; disable writes; background health checks for auto-recovery)
- What happens if operator enables auto-rebuild during corruption? (Create new database with unique config_epoch, seed non-secret defaults from .env, write rebuild.info tombstone, emit audit logs; tenant secrets remain unavailable until re-entered)
- How are .env-based secret values displayed in the UI? (Masked with read-only indicator showing source as ".env file"; cannot be modified via UI)
- How are user-created encrypted secrets displayed in the UI? (Masked by default with "Reveal" button; audit log on reveal; can be updated/deleted with confirmation)
- What happens when CONFIG_MASTER_KEY_BASE64 or LKG_HMAC_KEY_BASE64 are missing on first run? (Auto-generate both cryptographically secure keys with unique IDs, attempt to write to .env; if .env unwritable, print keys to stdout once with instructions and fail fast until operator manually sets them)
- What happens if CONFIG_MASTER_KEY_BASE64 is changed after secrets are encrypted? (System detects CONFIG_MASTER_KEY_ID mismatch; triggers re-encryption job if grace window active with both old/new keys available; otherwise enters degraded mode and warns user to restore original key or re-enter secrets)
- What happens if LKG_HMAC_KEY_BASE64 is changed? (LKG cache signature verification fails; system regenerates cache with new key on next successful database read; no data loss occurs)
- What happens during encryption key rotation? (Re-encryption job runs in background; both old and new CONFIG_MASTER_KEY_ID supported during grace window; all secrets re-encrypted with new key; old key marked for deprecation after completion)
- What happens when a new service is added that introduces new configuration fields? (Auto-discover and display with defaults; services read from database at startup)
- How does the system handle migration when configuration schema changes? (Dual table structure handles gracefully: service_configs stores JSON snapshots without schema constraints; config_items derived table auto-syncs on write; new fields get defaults; schema_version table tracks compatibility via Pydantic model hash; on mismatch, enter read-only fallback until ALLOW_AUTO_REBUILD=1)
- What happens if Pydantic models change and model_hash no longer matches schema_version? (System detects mismatch on startup, logs schema incompatibility warning, enters read-only fallback mode using LKG cache, disables writes, requires ALLOW_AUTO_REBUILD=1 to trigger database rebuild with new schema)
- What if a user sets an invalid configuration that breaks a service? (Validate before save; if service breaks despite validation, rollback to last known good config via change history)
- How does the system prevent split-brain with multiple database instances? (Each database has unique config_epoch in health+epoch metadata file; services refuse to read from mismatched epoch)
- What happens if MQTT is down when a service starts? (Service reads from database at startup successfully; subscribes to MQTT when available; continues operating with startup config)
- What happens if an MQTT configuration update message has an invalid signature? (Service rejects update, logs security warning with signature validation failure details, retains current configuration, alerts administrator)
- What happens if an MQTT configuration update message timestamp is too old? (Service rejects updates with issued_at older than 5 minutes to prevent replay attacks; logs security warning; re-pulls fresh config from database if needed)
- What happens if CONFIG_SIGNATURE_PUBLIC_KEY is missing or mismatched with private key? (Service startup fails with clear error; cannot verify MQTT updates; requires operator to restore matching key pair or regenerate both keys)
- What happens if a user with config.read role attempts to save configuration changes? (UI displays save button as disabled or operation returns 403 Forbidden with clear message requiring config.write role; action logged as access control violation)
- What happens if a user with config.read role attempts to reveal a secret? (UI displays reveal button as disabled or operation returns 403 Forbidden; action logged as unauthorized secret access attempt)
- What happens if CSRF token is missing or invalid on a configuration save request? (Request rejected with 403 Forbidden; error logged; user prompted to refresh page and retry)
- What happens during read-only fallback if the database becomes healthy again? (Background health checks detect recovery, verify schema, exit fallback mode, resume normal operations automatically)
- What happens if LKG cache HMAC signature is invalid? (Reject tampered cache, log security warning, enter degraded mode using .env secrets only, alert administrator)
- What happens if SQLite database is locked during read? (Fall back to LKG cache immediately without waiting; retry database read in background)
- What happens if Litestream backup fails or S3 is unavailable? (Log error, continue operating normally with local database, alert administrator, retry backup on next interval)
- What happens during Litestream restore if epoch metadata is missing or invalid? (Refuse to restore, log error, require manual epoch validation or force-restore flag with warnings)
- What happens if LKG cache becomes stale (database updated but cache write fails)? (Next successful database read updates cache; read-only fallback uses slightly stale but valid config; system logs staleness duration)
- What happens if WAL checkpoint fails? (SQLite handles automatically; if persistent, log error and alert; consider manual checkpoint or database rebuild)
- What happens if a service bypasses the tars-core library and tries to access the database directly? (Database file permissions and library encapsulation prevent direct access; attempting direct access fails with clear error message directing to library API)
- What happens if a service's Pydantic configuration model changes (new fields, removed fields, type changes)? (Library validates against current model; missing fields use defaults; extra fields ignored; type mismatches raise validation errors with clear upgrade path)
- What happens if tars-core library initialization fails during service startup? (Service fails to start with clear error; logs indicate library initialization failure reason; provides fallback to .env-only mode if configured)
- What happens if configuration update callback in service raises an exception? (Library logs exception, marks update as failed, retains previous valid configuration, service continues with last known good config)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST store all service configurations in SQLite database running in WAL (Write-Ahead Logging) mode for concurrent read performance
- **FR-001a**: System MUST use dual table structure: canonical service_configs table stores complete service configuration snapshots as JSON; derived config_items table stores individual key-value records for fast querying
- **FR-001b**: System MUST automatically sync config_items table from service_configs on every configuration write to maintain search/history index
- **FR-001c**: System MUST use config_items table for search, filter, and change history queries to avoid JSON parsing overhead
- **FR-001d**: System MUST use service_configs table as source of truth for atomic service configuration retrieval
- **FR-001e**: System MUST maintain schema_version table (id=1, version, model_hash, updated_at) to track database schema compatibility with Pydantic models
- **FR-001f**: System MUST compute SHA256 hash of all Pydantic model JSON schemas on startup and compare with stored model_hash in schema_version table
- **FR-001g**: System MUST enter read-only fallback mode if computed model_hash does not match stored schema_version.model_hash, logging schema incompatibility warning
- **FR-001h**: System MUST require ALLOW_AUTO_REBUILD=1 flag to recreate database when schema version mismatch detected
- **FR-001i**: System MUST increment schema_version.version for any structural database changes (new tables, columns, or config_items modifications)
- **FR-001j**: System MUST store current schema version in health+epoch metadata file for cluster schema alignment validation
- **FR-002**: System MUST support hybrid secret storage: core secrets (API keys, passwords) remain in .env files; user-created secrets (custom tokens, credentials) are encrypted and stored in database using AES-256-GCM encryption
- **FR-003**: System MUST auto-generate CONFIG_MASTER_KEY_BASE64 (32 bytes, base64-encoded) and LKG_HMAC_KEY_BASE64 (32 bytes, base64-encoded) on first run if missing; write both to .env with warnings
- **FR-003a**: System MUST use CONFIG_MASTER_KEY_BASE64 exclusively for AES-256-GCM encryption/decryption of user-created secrets in database
- **FR-003b**: System MUST use LKG_HMAC_KEY_BASE64 exclusively for HMAC-SHA256 signing and verification of config.lkg.json cache file
- **FR-003c**: System MUST fail fast on first run if .env file is unwritable: print generated keys to stdout once with clear instructions, then exit with error until operator manually sets keys in .env
- **FR-003d**: System MUST track encryption key rotation via CONFIG_MASTER_KEY_ID (UUID) and LKG_HMAC_KEY_ID (UUID) stored in .env alongside respective keys
- **FR-003e**: System MUST provide a re-encryption job that re-encrypts all database secrets when CONFIG_MASTER_KEY_ID changes, supporting a grace window where both old and new key IDs are readable during rotation
- **FR-004**: System MUST enforce configuration source precedence: .env values for secrets (immutable, always override); database values for all other configurations
- **FR-005**: System MUST enable services to read configurations from database at startup, then subscribe to MQTT topics for runtime configuration updates
- **FR-006**: System MUST maintain an HMAC-signed last-known-good (LKG) cache file (config.lkg.json) that is atomically updated on every successful database read
- **FR-007**: System MUST use LKG cache for instant read-only fallback when SQLite is locked, corrupted, or temporarily unavailable
- **FR-008**: System MUST continuously backup configuration database to S3-compatible storage (S3/MinIO) using Litestream for point-in-time recovery
- **FR-009**: System MUST support Litestream restore to specific timestamp or latest backup before service startup
- **FR-010**: System MUST write health+epoch metadata file so services refuse to use configurations from mismatched post-restore database (prevents split-brain)
- **FR-011**: System MUST provide a web UI that displays all configurations organized by service (stt-worker, tts-worker, llm-worker, router, etc.)
- **FR-012**: System MUST categorize each configuration as either "simple" (commonly used) or "advanced" (technical/rarely changed)
- **FR-013**: System MUST display configuration descriptions, valid value ranges, types, and current values in the web UI
- **FR-014**: System MUST provide contextual help for each configuration via hover tooltips or help icons
- **FR-015**: System MUST validate configuration values client-side (UI) before allowing save
- **FR-016**: System MUST validate configuration values server-side before persisting to database
- **FR-017**: System MUST publish configuration changes to MQTT topics (e.g., `system/config/<service>`) with QoS 1 and retained flag so services can react without restart
- **FR-017a**: System MUST sign all MQTT configuration update messages with Ed25519 signature using CONFIG_SIGNATURE_PRIVATE_KEY
- **FR-017b**: System MUST include message envelope in MQTT updates: {version, config_data, checksum, issued_at, signature}
- **FR-017c**: System MUST verify Ed25519 signature on received MQTT configuration updates using CONFIG_SIGNATURE_PUBLIC_KEY from .env before applying changes
- **FR-017d**: System MUST reject and log MQTT configuration updates with invalid signatures, expired timestamps (>5 minutes old), or checksum mismatches
- **FR-017e**: System MUST auto-generate Ed25519 key pair (CONFIG_SIGNATURE_PRIVATE_KEY and CONFIG_SIGNATURE_PUBLIC_KEY) on first run if missing; distribute public key to all services via .env
- **FR-018**: System MUST allow services to subscribe to their configuration changes and apply them at runtime when safe to do so
- **FR-019**: System MUST persist configuration changes immediately and make them available to services
- **FR-020**: System MUST provide a default configuration for each service that is used when no custom configuration exists
- **FR-021**: System MUST support basic configuration types: string, integer, float, boolean, enum (dropdown), file path, secret
- **FR-022**: System MUST mask secret values in the UI and require explicit user action to reveal them (with audit logging)
- **FR-023**: System MUST prevent .env-based secrets from being modified via the UI (display as read-only with source indicator)
- **FR-024**: System MUST allow user-created secrets to be added, updated, and deleted via the UI (with confirmation prompts)
- **FR-025**: System MUST provide a search/filter capability to find configurations by name, description, or service
- **FR-026**: System MUST allow toggling between "simple mode" (essential settings only) and "advanced mode" (all settings)
- **FR-027**: System MUST log all configuration changes with timestamp and changed values for audit purposes
- **FR-028**: System MUST provide a RESTful API for reading and updating configurations programmatically
- **FR-028a**: System MUST implement minimal two-role access control: config.read (default, view non-secret configs) and config.write (save changes, reveal secrets, trigger rebuild)
- **FR-028b**: System MUST enforce config.write role requirement for all configuration modification operations (save, update, delete)
- **FR-028c**: System MUST enforce config.write role requirement for secret reveal operations with justification text logging
- **FR-028d**: System MUST enforce config.write role requirement for auto-rebuild trigger operations
- **FR-028e**: System MUST implement CSRF protection for all web UI state-changing operations
- **FR-028f**: System MUST support API token authentication for REST endpoints with token-to-role mapping
- **FR-028g**: System MUST log all access control violations (unauthorized operation attempts) with user identity and requested action
- **FR-029**: System MUST support configuration value defaults that are automatically applied for new installations
- **FR-030**: System MUST handle concurrent configuration updates with conflict detection
- **FR-031**: System MUST implement read-only fallback mode when database is corrupted or inaccessible: run using .env secrets and LKG cached configs, display red "Read-Only Fallback" banner in UI, disable all write operations
- **FR-032**: System MUST support opt-in auto-rebuild via ALLOW_AUTO_REBUILD=1 flag or admin endpoint with REBUILD_TOKEN for emergency database recovery
- **FR-033**: System MUST create new database with unique config_epoch on rebuild to prevent split-brain scenarios with stale database instances
- **FR-034**: System MUST perform background health checks in read-only fallback mode and automatically resume normal operations when database is healthy and schema verified
- **FR-035**: System MUST write rebuild tombstone file (rebuild.info) and emit audit logs when auto-rebuild occurs
- **FR-036**: System MUST verify HMAC signature on LKG cache before using it for read-only fallback (reject tampered cache)
- **FR-037**: System MUST support Litestream restore operation that validates epoch metadata before allowing services to connect
- **FR-038**: System MUST organize configurations in web UI using existing app tabs (Health, Microphone, Memory, MQTT Stream, Camera) where configuration placeholders already exist
- **FR-039**: System MUST create new dedicated tabs for services that do not have existing UI presence (e.g., Router, LLM Worker, TTS Worker, STT Worker, Wake Activation)
- **FR-040**: System MUST provide a global settings section accessible via settings cog icon in top right corner for cross-service configurations (MQTT broker, logging, system-wide defaults)
- **FR-041**: System MUST clearly label each configuration with the service(s) it affects when displayed in service-specific tabs
- **FR-042**: System MUST show service health status indicator within each service's configuration tab
- **FR-043**: System MUST implement all configuration database access logic in tars-core package as a centralized configuration library
- **FR-044**: System MUST define Pydantic v2 models for each service's configuration schema in tars-core package
- **FR-045**: System MUST provide library API for services to get configuration (read) and receive configuration updates (MQTT subscription callback)
- **FR-046**: System MUST prevent individual services from directly accessing the configuration database (enforce library-only access pattern)
- **FR-047**: System MUST handle all configuration precedence logic (.env override, database, defaults) within the tars-core configuration library
- **FR-048**: System MUST provide typed configuration objects to services based on their Pydantic models (no raw dict/JSON)
- **FR-049**: System MUST validate all configuration values against Pydantic models before returning to services

### Key Entities

- **Configuration Entry**: Represents a single configuration setting with attributes:
  - Unique key (e.g., "stt.whisper_model")
  - Current value
  - Default value
  - Data type (string, int, float, bool, enum, path, secret)
  - Validation rules (min/max, regex pattern, allowed values)
  - Description (user-facing explanation)
  - Help text (detailed documentation)
  - Complexity level (simple/advanced)
  - Service/category (which service it belongs to)
  - Is secret (whether value should be masked)
  - Secret source (env-based immutable / user-created encrypted)
  - Encryption status (for user-created secrets: encrypted with AES-GCM)
  - Source precedence (env/database/default)
  - Last modified timestamp
  - Change history (optional for P3)

- **Service Configuration Snapshot**: Canonical atomic configuration state
  - Service name identifier
  - Complete configuration JSON blob
  - Configuration version/hash
  - Last updated timestamp
  - Config epoch reference

- **Configuration Item**: Individual key-value record for search/history
  - Service name
  - Environment (if multi-tenant; else default)
  - Configuration key
  - Value (stored as JSON for type flexibility)
  - Data type
  - Complexity level (simple/advanced)
  - Description
  - Help text
  - Last updated timestamp
  - Updated by (user identifier if available)

- **Service Category**: Logical grouping of related configurations
  - Service name (stt-worker, tts-worker, etc.)
  - Display name (user-friendly)
  - Description
  - List of configuration entries
  - Configuration load status (loaded/fallback/read-only)
  - UI tab mapping (existing tab name or "create new")
  - Health status (healthy/unhealthy/offline)

- **Global Settings Category**: Cross-service configurations
  - Setting name (MQTT broker, logging level, etc.)
  - Affects multiple services indicator
  - List of affected services
  - Configuration entries
  - Accessible via settings cog icon

- **Configuration Profile** (P3): Named snapshot of configuration state
  - Profile name
  - Configuration values snapshot
  - Created timestamp
  - Description

- **Database Health State**: Tracks configuration database status
  - Config epoch (unique identifier for database instance)
  - Schema version (integer tracking structural changes)
  - Model hash (SHA256 of Pydantic model schemas for compatibility validation)
  - Health status (healthy/corrupted/inaccessible/locked/schema-mismatch)
  - Operational mode (normal/read-only-fallback/rebuilding)
  - Last health check timestamp
  - Rebuild tombstone (rebuild.info file reference if rebuilt)
  - Litestream backup status (last backup timestamp, S3 location)

- **LKG Cache**: Last-known-good configuration cache
  - File path (config.lkg.json)
  - HMAC signature for tamper detection
  - Cached configuration values
  - Cache generation timestamp
  - Config epoch at cache generation

- **Encryption Metadata**: Manages secret encryption
  - Encryption key source (.env CONFIG_MASTER_KEY_BASE64)
  - Encryption key ID (CONFIG_MASTER_KEY_ID for rotation tracking)
  - Key generation timestamp
  - Encryption algorithm (AES-256-GCM)
  - Encrypted secrets count
  - HMAC key source (.env LKG_HMAC_KEY_BASE64)
  - HMAC key ID (LKG_HMAC_KEY_ID for rotation tracking)
  - Re-encryption job status (idle/in-progress/completed)
  - Grace window configuration (supports both old and new key IDs during rotation)

- **MQTT Signature Metadata**: Manages configuration update message signing
  - Ed25519 private key source (.env CONFIG_SIGNATURE_PRIVATE_KEY)
  - Ed25519 public key source (.env CONFIG_SIGNATURE_PUBLIC_KEY)
  - Key pair generation timestamp
  - Message envelope version
  - Signature verification failures count
  - Timestamp tolerance (default 5 minutes for replay attack prevention)

- **Access Control Metadata**: Manages minimal role-based permissions
  - Role definitions (config.read, config.write)
  - Default role (config.read for all authenticated users)
  - Role assignment storage (user ID to role mapping)
  - API token to role mapping
  - CSRF token generation and validation
  - Access violation log (user, action, timestamp, reason)

- **Backup Metadata**: Litestream backup configuration
  - S3/MinIO endpoint URL
  - Backup bucket and path
  - Restore point (timestamp or "latest")
  - Epoch validation file (health+epoch metadata)

- **Configuration Library (tars-core)**: Centralized configuration access layer
  - Database connection management (SQLite WAL)
  - Configuration retrieval API (`get_config(service_name)`)
  - MQTT subscription management for config updates
  - Precedence resolution (.env → database → defaults)
  - Pydantic model validation
  - LKG cache management
  - Encryption/decryption for user-created secrets

- **Service Configuration Model**: Pydantic v2 model for each service
  - Service name identifier (e.g., "stt-worker", "tts-worker")
  - Typed configuration fields with validation
  - Default values
  - Field metadata (description, help text, complexity level, is_secret)
  - Validation constraints (min/max, regex, allowed values)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Administrators can update any configuration value through the web UI in under 30 seconds (including finding the setting, changing it, and saving)
- **SC-002**: System supports at least 100 configuration entries across all services without UI performance degradation
- **SC-003**: Configuration changes are persisted to the database and reflected in services within 2 seconds of saving
- **SC-004**: 90% of users can successfully change a basic configuration (marked as "simple") on their first attempt without consulting documentation
- **SC-005**: The web UI loads all configurations and renders the interface in under 2 seconds
- **SC-006**: Validation errors are displayed to users within 500ms of entering an invalid value
- **SC-007**: Services can dynamically apply configuration changes for at least 50% of settings without requiring a restart
- **SC-008**: Search and filter operations return results within 300ms even with 100+ configurations
- **SC-009**: Zero service failures caused by invalid configurations reaching services (validation prevents bad data)
- **SC-010**: Configuration change history is queryable and can retrieve any entry from the past 30 days in under 1 second
- **SC-011**: Services successfully start and load configurations from SQLite database within 1 second even when MQTT is unavailable
- **SC-012**: User-created secrets are encrypted in database with AES-256-GCM using CONFIG_MASTER_KEY_BASE64 and cannot be read without the correct key from .env
- **SC-013**: .env-based secrets are never modifiable via UI and always take precedence over database values
- **SC-014**: System enters read-only fallback mode using LKG cache within 1 second of detecting database corruption or lock
- **SC-015**: Auto-rebuild (when enabled) completes database recreation with defaults within 5 seconds
- **SC-016**: All secret reveal actions and modifications are logged to audit trail with timestamp and user identity
- **SC-017**: LKG cache is updated atomically within 100ms of successful database read
- **SC-018**: HMAC-SHA256 signature verification on LKG cache using LKG_HMAC_KEY_BASE64 completes in under 50ms
- **SC-019**: Litestream continuous backup lag remains under 5 seconds during normal operations
- **SC-020**: Litestream restore to specific timestamp completes within 10 seconds for databases under 10MB
- **SC-021**: SQLite WAL mode supports at least 10 concurrent readers without blocking
- **SC-022**: Config epoch mismatch is detected and rejected within 100ms of service startup
- **SC-023**: Read-only fallback to LKG cache occurs with zero downtime (instant failover)
- **SC-024**: Users can navigate to any service-specific configuration tab within 2 clicks from main UI
- **SC-025**: Global settings panel opens within 500ms of clicking settings cog icon
- **SC-026**: Service health status indicators update within 2 seconds of service state change
- **SC-027**: Existing configuration placeholders in current UI tabs (Health, Microphone, Memory, MQTT Stream, Camera) are successfully replaced with functional configuration controls
- **SC-028**: Tars-core configuration library initialization completes within 500ms during service startup
- **SC-029**: Library API `get_config(service_name)` returns typed, validated configuration object in under 50ms
- **SC-030**: Pydantic model validation catches 100% of type/constraint violations before configurations reach services
- **SC-031**: Services cannot access configuration database directly (library encapsulation enforced)
- **SC-032**: Configuration model schema changes (adding/removing fields) do not break existing services using library
- **SC-033**: Configuration update callbacks in services execute within 100ms of MQTT notification
- **SC-034**: Encryption key rotation job completes re-encryption of all secrets within 30 seconds for databases with up to 1000 encrypted values
- **SC-035**: Grace window during key rotation allows reads using both old and new CONFIG_MASTER_KEY_ID for at least 5 minutes
- **SC-036**: Ed25519 signature verification on MQTT configuration updates completes in under 1ms per message
- **SC-037**: MQTT configuration updates with invalid signatures are rejected with 100% detection rate (zero false accepts)
- **SC-038**: Services reject MQTT updates with timestamps older than 5 minutes to prevent replay attacks
- **SC-039**: Schema version validation (Pydantic model hash comparison) completes within 100ms on service startup
- **SC-040**: Schema version mismatch detection triggers read-only fallback mode within 1 second with clear schema incompatibility warning logged
- **SC-041**: Users with config.read role can view all non-secret configurations without restrictions
- **SC-042**: Users with config.read role cannot save changes, reveal secrets, or trigger rebuilds (100% enforcement of write restrictions)
- **SC-043**: CSRF protection blocks 100% of cross-site configuration modification attempts
- **SC-044**: API token authentication validates tokens within 50ms per request

## Assumptions

- **Database Technology**: SQLite in WAL (Write-Ahead Logging) mode provides sufficient performance and concurrent read access for configuration storage
- **Database Schema**: Dual table structure balances atomic consistency (service_configs JSON snapshots) with query performance (config_items per-key records for search/history); no traditional schema migrations needed for configuration changes
- **Schema Version Tracking**: schema_version table (CREATE TABLE schema_version (id INTEGER PRIMARY KEY CHECK (id=1), version INTEGER NOT NULL, model_hash TEXT NOT NULL, updated_at TEXT NOT NULL)) tracks compatibility; startup validates Pydantic model hash against stored value; mismatch triggers read-only fallback
- **Encryption Strategy**: App-level AES-256-GCM encryption for user-created secrets stored in database; separate keys for encryption vs HMAC signing to prevent cryptographic cross-protocol attacks
- **Backup Strategy**: Litestream provides continuous replication to S3-compatible storage (S3/MinIO) for point-in-time recovery
- **LKG Cache**: HMAC-SHA256 signed config.lkg.json file provides instant read-only fallback without database dependency
- **Configuration Loading**: Services read configuration from database at startup (not dependent on MQTT being available), then subscribe to MQTT for runtime updates
- **Secret Storage Strategy**: Core secrets (API keys, service passwords) remain in .env files; user-created secrets (custom tokens, user credentials) encrypted in database
- **Encryption Key Management**: CONFIG_MASTER_KEY_BASE64 (32 bytes) and LKG_HMAC_KEY_BASE64 (32 bytes) auto-generated on first run if missing; if .env unwritable, print to stdout and fail fast; track rotation via CONFIG_MASTER_KEY_ID and LKG_HMAC_KEY_ID with re-encryption job support
- **Key Separation**: CONFIG_MASTER_KEY_BASE64 used exclusively for AES-256-GCM encryption/decryption; LKG_HMAC_KEY_BASE64 used exclusively for HMAC-SHA256 signing/verification of LKG cache
- **MQTT Security**: All configuration update messages signed with Ed25519 (CONFIG_SIGNATURE_PRIVATE_KEY); services verify with public key before applying; messages use QoS 1 + retained flag; timestamp validation prevents replay attacks (5 minute tolerance)
- **Access Control**: Minimal two-role system: config.read (default, view non-secret configs) and config.write (save changes, reveal secrets, trigger rebuild); CSRF protection on web UI; API token authentication for REST endpoints
- **Configuration Precedence**: .env secrets always override (immutable); database values used for all other configurations; defaults used only when neither source has the value
- **Database Recovery**: Default behavior is read-only fallback mode using LKG cache on corruption; auto-rebuild requires explicit opt-in via ALLOW_AUTO_REBUILD=1 and REBUILD_TOKEN
- **Split-Brain Prevention**: Each database instance has unique config_epoch stored in health+epoch metadata file; services reject configurations from mismatched epochs
- **Restore Process**: Litestream restore validates epoch metadata before allowing services to connect to restored database
- **LKG Cache Integrity**: HMAC signature verification ensures LKG cache has not been tampered with before use in read-only fallback
- **Authentication**: Configuration UI will use existing authentication mechanisms if present, or operate without authentication in trusted network environments
- **MQTT Integration**: Services already have MQTT clients and can subscribe to topics for configuration updates; MQTT unavailability does not block service startup
- **File System Access**: Services can read configuration database file directly at startup and access LKG cache for fallback
- **UI Framework**: Web UI will be built as an enhancement to existing ui-web service using its current tech stack
- **Existing UI Tabs**: Current ui-web has tabs for Health, Microphone, Memory, MQTT Stream, and Camera with configuration placeholders that will be utilized
- **New Service Tabs**: Services without existing UI presence (Router, LLM Worker, TTS Worker, STT Worker, Wake Activation) will get dedicated configuration tabs
- **Global Settings**: Cross-service configurations (MQTT broker URL, logging levels, system defaults) accessible via settings cog icon in top right corner
- **Tab-Service Mapping**: Each service's configurations displayed in its dedicated tab; shared configurations in global settings panel
- **Migration**: Existing .env values will be imported as initial database values on first run for non-secret configurations
- **Backward Compatibility**: Services will fall back to LKG cache reading if database is unavailable (read-only fallback mode)
- **Performance**: Configuration reads are frequent, writes are infrequent (optimize for read performance with WAL mode and caching)
- **Concurrency**: SQLite WAL mode supports multiple concurrent readers and single writer; optimistic locking for concurrent write detection
- **Data Size**: Configuration database will remain under 10MB even with extensive change history and encrypted secrets
- **Audit Requirements**: All secret reveals and modifications must be logged for security audit trails
- **S3 Compatibility**: Litestream backup target supports S3 API (AWS S3, MinIO, or other S3-compatible storage)
- **Architectural Separation**: All configuration database access logic centralized in tars-core package; services never access database directly
- **Pydantic Models**: Each service's configuration schema defined as Pydantic v2 model in tars-core with full type safety
- **Library API**: Services use tars-core configuration library API to get configs and register for update callbacks; library handles all database, MQTT, precedence, and validation logic
- **Typed Configuration**: Services receive validated, typed configuration objects (not raw dicts) from library based on their Pydantic models
- **Single Responsibility**: Services only consume configurations; tars-core library manages storage, retrieval, encryption, caching, and distribution

## Out of Scope

- Full role-based access control with granular per-service or per-configuration permissions (minimal two-role system config.read/config.write is in scope)
- Configuration versioning with Git-like branching/merging
- Real-time collaborative editing with multiple simultaneous editors
- Configuration templates or wizards for common setups
- Integration with external configuration management systems (Consul, etcd)
- Mobile-optimized UI (web UI targets desktop browsers)
- Configuration validation against live service state (validation is schema-based only)
- Automatic configuration recommendations based on usage patterns
- Configuration backup/restore to external storage
