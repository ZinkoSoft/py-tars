# Configuration Metadata System

## Overview

The `config-metadata.yml` file provides human-readable documentation for all configuration fields across TARS services. This metadata is used by the config-manager UI to display helpful descriptions, detailed explanations, and example values.

## Architecture

- **Location**: `/ops/config-metadata.yml` (source) → `/etc/tars/config-metadata.yml` (in containers)
- **Format**: YAML
- **Loading**: Loaded once at startup by config-manager, cached in memory
- **Usage**: Merged with Pydantic Field definitions during metadata extraction

## YAML Structure

```yaml
service-name:
  field_name:
    description: "Short one-line description (shown next to field)"
    help_text: "Detailed explanation with usage guidance"
    examples:
      - "example1"
      - "example2"
```

### Field Definitions

- **`description`** (required): Short, user-friendly description displayed next to the field
- **`help_text`** (optional): Detailed explanation shown in the help modal
- **`examples`** (required for enums): List of example values
  - For enum fields, these populate the dropdown options
  - For other fields, shown in the help modal as reference values

## How It Works

1. **Build Time**: `ops/config-metadata.yml` is copied into Docker images at `/etc/tars/config-metadata.yml`
2. **Runtime**: Config-manager loads the YAML file on startup
3. **Metadata Extraction**: When building field metadata, the system:
   - Extracts base metadata from Pydantic `Field()` definitions
   - Loads custom metadata from YAML
   - Merges YAML values (description, help_text, examples) with Pydantic metadata
4. **API Response**: Enriched metadata is returned via `/api/config/services/{service}` endpoint
5. **UI Display**: Frontend shows descriptions, help text, and examples in the configuration UI

## Adding Metadata for New Services

1. Edit `/ops/config-metadata.yml`
2. Add a new service section with field documentation:

```yaml
my-new-service:
  my_field:
    description: "What this field does"
    help_text: "Detailed explanation of usage, best practices, etc."
    examples:
      - "default_value"
      - "alternative_value"
```

3. Rebuild affected containers (config-manager)
4. Metadata will automatically appear in the UI

## Benefits of YAML-Based Metadata

✅ **Centralized**: All service documentation in one file  
✅ **Easy to Edit**: No code changes required  
✅ **Version Controlled**: Changes tracked in git  
✅ **No Rebuilds**: Only config-manager needs rebuilding (not individual services)  
✅ **Readable**: YAML format is human-friendly  
✅ **Extensible**: Easy to add new services and fields

## Example: Enum Field with Dropdown

```yaml
stt-worker:
  stt_backend:
    description: "Speech-to-text backend implementation"
    help_text: "Choose 'whisper' for local Faster-Whisper, 'ws' for WebSocket offload (Jetson/NPU), or 'openai' for cloud API."
    examples:
      - "whisper"
      - "ws"
      - "openai"
```

**Result in UI:**
- Field label shows: "Stt Backend"
- Description below label: "Speech-to-text backend implementation"
- Dropdown populated with: whisper, ws, openai
- Help modal (?) shows detailed help_text

## Technical Details

- **Load Function**: `tars.config.metadata._load_yaml_metadata()`
- **Cache**: Metadata is cached in memory after first load
- **Fallback**: If YAML file missing or field not documented, falls back to Pydantic Field descriptions
- **Type Handling**: For enum types, `examples` list automatically populates `validation.allowed` field

## Files Modified

- `/packages/tars-core/src/tars/config/metadata.py` - Added YAML loading logic
- `/packages/tars-core/pyproject.toml` - Added `pyyaml>=6.0` dependency
- `/docker/specialized/config-manager.Dockerfile` - Copies YAML file into container
- `/.dockerignore` - Whitelisted `ops/config-metadata.yml`

## Troubleshooting

**Metadata not showing in UI:**
- Check config-manager logs: `docker logs tars-config-manager | grep metadata`
- Should see: `Loaded metadata for N services from /etc/tars/config-metadata.yml`
- Verify file exists in container: `docker exec tars-config-manager cat /etc/tars/config-metadata.yml`

**YAML syntax errors:**
- Check logs for: `Failed to parse YAML metadata file`
- Validate YAML syntax with: `yamllint ops/config-metadata.yml`

**Field not documented:**
- Ensure service name matches exactly (e.g., `stt-worker` not `stt_worker`)
- Ensure field name matches Pydantic model field name exactly
- Rebuild config-manager if YAML was updated
