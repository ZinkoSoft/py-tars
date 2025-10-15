# README.md Template for py-tars Apps

This template provides standardized documentation structure for all py-tars applications.

## Full Template

```markdown
# <App Name>

<Brief one-sentence description>

## Overview

<2-3 paragraph description of what this service does, its role in the py-tars ecosystem, and key features>

## Installation

### From Source

```bash
cd apps/<app-name>
pip install -e .
```

### For Development

```bash
cd apps/<app-name>
pip install -e ".[dev]"
```

### Docker

This service is designed to run in Docker as part of the py-tars stack:

```bash
docker compose up <service-name>
```

## Usage

### Running the Service

**Standalone:**
```bash
tars-<app-name>
```

**With Python module:**
```bash
python -m <package_name>
```

**In Docker:**
```bash
docker compose up <service-name>
```

### Command-Line Options

[If applicable, list CLI arguments]

```bash
tars-<app-name> --help
```

## Configuration

All configuration is via environment variables (12-factor app):

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `MQTT_URL` | MQTT broker URL | `mqtt://user:pass@localhost:1883` |
| `<APP>_<VAR>` | App-specific config | `value` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `<APP>_<VAR>` | Optional setting | `default_value` |

### Example Configuration

See [`.env.example`](./.env.example) for a complete configuration template.

```bash
# Copy example and customize
cp .env.example .env
# Edit .env with your settings
```

## Architecture

### High-Level Design

<Brief description of the service architecture: main components, data flow, key design decisions>

**Key Components:**
- **`service.py`** - Core business logic
- **`config.py`** - Configuration management
- **`models.py`** - Data models and validation

### MQTT Integration

This service communicates via MQTT following the py-tars event-driven architecture.

#### Subscribed Topics

| Topic | QoS | Payload Schema | Purpose |
|-------|-----|----------------|---------|
| `<topic>/<action>` | 0/1 | `{ field: type }` | Description |

**Example Payload:**
```json
{
  "field": "value",
  "timestamp": 1234567890.123
}
```

#### Published Topics

| Topic | QoS | Retained | Payload Schema | Purpose |
|-------|-----|----------|----------------|---------|
| `<topic>/<event>` | 0/1 | No/Yes | `{ field: type }` | Description |

**Example Payload:**
```json
{
  "field": "value",
  "timestamp": 1234567890.123
}
```

#### Health Monitoring

Publishes health status to `system/health/<service>` (retained, QoS 1):

```json
{
  "ok": true,
  "event": "service_started",
  "timestamp": 1234567890.123
}
```

On error:
```json
{
  "ok": false,
  "err": "Error description",
  "timestamp": 1234567890.123
}
```

### Data Flow

```
[Input Source] 
    ↓
[MQTT Topic] 
    ↓
[This Service] 
    ↓
[Processing/Logic] 
    ↓
[MQTT Topic] 
    ↓
[Output Destination]
```

### Dependencies

**Runtime:**
- Python 3.11+
- MQTT broker (Mosquitto)
- [List app-specific dependencies]

**Python Packages:**
See [`pyproject.toml`](./pyproject.toml) for complete dependency list.

## Development

### Setup Development Environment

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Copy example environment
cp .env.example .env
```

### Running Tests

```bash
# Run all tests
make test

# Run specific test categories
pytest -m unit
pytest -m integration
pytest -m contract

# Run with coverage
pytest --cov=<package_name> --cov-report=html
```

### Code Quality

```bash
# Format code
make fmt

# Lint and type-check
make lint

# Run all checks (fmt + lint + test)
make check
```

### Available Make Targets

| Target | Description |
|--------|-------------|
| `make fmt` | Format code with ruff and black |
| `make lint` | Lint with ruff and type-check with mypy |
| `make test` | Run tests with coverage |
| `make check` | Run all checks (CI gate) |
| `make build` | Build Python package |
| `make clean` | Remove build artifacts |
| `make install` | Install in editable mode |
| `make install-dev` | Install with dev dependencies |

### Project Structure

```
<app-name>/
├── src/
│   └── <package_name>/
│       ├── __init__.py       # Package initialization
│       ├── __main__.py       # CLI entry point
│       ├── config.py         # Configuration parsing
│       ├── service.py        # Core business logic
│       └── models.py         # Pydantic models
├── tests/
│   ├── conftest.py          # Shared fixtures
│   ├── unit/                # Unit tests
│   ├── integration/         # Integration tests
│   └── contract/            # MQTT contract tests
├── Makefile                 # Build automation
├── pyproject.toml          # Package configuration
├── README.md               # This file
└── .env.example            # Configuration template
```

## Troubleshooting

### Common Issues

#### Service won't start

**Check MQTT connection:**
```bash
# Verify MQTT broker is running
docker compose ps mosquitto

# Check MQTT_URL environment variable
echo $MQTT_URL
```

#### Import errors

**Install package in editable mode:**
```bash
pip install -e .
```

#### Tests failing

**Check environment:**
```bash
# Install dev dependencies
pip install -e ".[dev]"

# Verify test dependencies
pytest --version
```

### Logging

Logs are structured JSON for parsing:

```json
{
  "timestamp": "2025-10-13T12:00:00Z",
  "level": "INFO",
  "service": "<service-name>",
  "message": "Event description",
  "request_id": "abc123",
  "extra_field": "value"
}
```

**Log levels:**
- **DEBUG**: Detailed development information
- **INFO**: State transitions and key events
- **WARNING**: Retries and recoverable errors
- **ERROR**: Failures requiring attention

**Increase logging verbosity:**
```bash
LOG_LEVEL=DEBUG tars-<app-name>
```

## Contributing

See [main repository CONTRIBUTING.md](../../CONTRIBUTING.md) for:
- Code style guidelines
- PR requirements
- Testing standards
- Git workflow

### Before Submitting PR

1. Run `make check` - all checks must pass
2. Add tests for new features
3. Update this README if adding configuration or changing behavior
4. Follow constitution principles (see `.specify/memory/constitution.md`)

## Related Services

- **[Other Service]** (`apps/other-service/`) - How they interact
- **[Another Service]** (`apps/another-service/`) - Relationship

## References

- [py-tars Architecture](../../README.md)
- [Copilot Instructions](../../.github/copilot-instructions.md)
- [Constitution](./.specify/memory/constitution.md)
- [MQTT Contract Standards](../../docs/mqtt-contracts.md) [if exists]

## License

[Same as parent repository]
```

## Customization Guide

### Required Changes

1. **Title and description**
   ```markdown
   # LLM Worker
   
   Language model worker service for the TARS voice assistant stack.
   ```

2. **App name placeholders**
   - Replace `<app-name>` with actual app directory name (e.g., `llm-worker`)
   - Replace `<package_name>` with Python package name (e.g., `llm_worker`)
   - Replace `<service-name>` with Docker Compose service name

3. **Configuration variables**
   - List all environment variables used by the app
   - Specify required vs optional
   - Provide sensible defaults and examples

4. **MQTT topics**
   - Document all subscribed topics with schemas
   - Document all published topics with schemas
   - Include example JSON payloads
   - Specify QoS and retention policies

5. **Architecture section**
   - Describe service's role in py-tars ecosystem
   - Explain key components and their responsibilities
   - Include data flow diagram or description

### Optional Sections

#### Command-Line Arguments

If your app accepts CLI arguments, document them:

```markdown
### Command-Line Options

```bash
tars-<app-name> [OPTIONS]
```

**Options:**
- `--config PATH` - Path to config file
- `--debug` - Enable debug logging
- `--help` - Show help message
```

#### Advanced Configuration

For complex configuration:

```markdown
### Advanced Configuration

#### Performance Tuning

- `<APP>_WORKER_THREADS` - Number of worker threads (default: 4)
- `<APP>_BATCH_SIZE` - Batch size for processing (default: 100)

#### Feature Flags

- `<APP>_ENABLE_FEATURE` - Enable experimental feature (default: false)
```

#### Examples

Provide usage examples:

```markdown
## Examples

### Basic Usage

```bash
# Start service with defaults
tars-<app-name>
```

### Custom Configuration

```bash
# Use custom MQTT broker
MQTT_URL=mqtt://custom:1883 tars-<app-name>
```
```

#### Performance Characteristics

Document performance:

```markdown
### Performance

- **Latency**: <90th percentile response time>
- **Throughput**: <requests per second>
- **Memory**: <typical memory usage>
- **CPU**: <typical CPU usage>
```

## Section-by-Section Guidance

### Overview
Write 2-3 paragraphs explaining:
- What problem this service solves
- How it fits into py-tars architecture
- Key features or capabilities

### Installation
Standard for all apps. Minimal customization needed.

### Usage
Show how to run the service in different contexts:
- Standalone (development)
- Docker (production)
- With custom configuration

### Configuration
**Critical section** - document ALL environment variables:
- Required vs optional
- Data types and validation
- Default values
- Examples

Use table format for readability.

### Architecture
Explain the service internals:
- Major components (files/classes)
- Data flow (input → processing → output)
- MQTT integration points
- Dependencies on other services

### MQTT Integration
**Most important section** - document message contracts:
- All subscribed topics with schemas
- All published topics with schemas
- Example JSON payloads
- QoS and retention policies

This serves as API documentation for the service.

### Development
Standard developer workflow. Minimal customization needed.

### Troubleshooting
Add common issues specific to your app:
- Connection problems
- Configuration errors
- Dependency issues
- Performance problems

## Validation Checklist

Before considering README complete:

- [ ] All placeholders (`<app-name>`, etc.) replaced
- [ ] All environment variables documented
- [ ] All MQTT topics documented with schemas
- [ ] Example payloads provided for key messages
- [ ] Architecture section explains service role
- [ ] Make targets documented
- [ ] Installation instructions tested
- [ ] Common issues listed with solutions
- [ ] Related services documented
- [ ] Code examples are accurate

## Style Guidelines

- **Tone**: Technical but accessible
- **Formatting**: Use tables for structured data
- **Code blocks**: Always specify language (```bash, ```json, ```python)
- **Examples**: Provide concrete examples, not placeholders
- **Links**: Link to related documentation
- **Accuracy**: Test all commands and examples

## Maintenance

Update README when:
- Adding new environment variables
- Changing MQTT topics or schemas
- Adding new features
- Changing CLI interface
- Fixing common issues (add to troubleshooting)
- Updating dependencies

Keep README in sync with code!
