# Developer Onboarding Guide

Welcome to the TARS project! This guide will help you get up and running with the development environment and understand the project's architecture, conventions, and workflows.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Setup](#initial-setup)
3. [Project Architecture](#project-architecture)
4. [Development Workflow](#development-workflow)
5. [Testing](#testing)
6. [Contributing](#contributing)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

### Hardware

- **Development Machine**: Any Linux/macOS system with Docker
- **Target Hardware** (optional): Orange Pi 5 Max with NVMe SSD
- **Microphone**: USB or 3.5mm for STT testing
- **Speaker**: USB or 3.5mm for TTS testing

### Software

- **Python**: 3.11+ (required for all services)
- **Docker**: 24.0+ with Docker Compose
- **Git**: 2.30+
- **Make**: GNU Make (for build automation)
- **MQTT Client** (optional): mosquitto-clients for debugging

### Skills

- **Python**: Async/await, type hints, pytest
- **MQTT**: Pub/sub patterns, QoS levels
- **Docker**: Container basics, Docker Compose
- **Linux**: Command line, bash scripting

## Initial Setup

### 1. Clone the Repository

```bash
git clone https://github.com/ZinkoSoft/py-tars.git
cd py-tars
```

### 2. Set Up Python Virtual Environment

```bash
# Create venv at project root
python3.11 -m venv .venv

# Activate venv
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

**Important**: All development work should use this virtual environment at `/home/james/git/py-tars/.venv/bin`. Never use system Python or global packages.

### 3. Configure Environment

```bash
# Copy example configuration
cp .env.example .env

# Edit .env with your settings
nano .env
```

**Required variables**:
- `MQTT_URL`: MQTT broker URL (default: `mqtt://localhost:1883`)
- `OPENAI_API_KEY`: OpenAI API key (for LLM worker)

See individual service `.env.example` files for service-specific configuration.

### 4. Install Development Tools

```bash
# Install shared dev tools
pip install pytest pytest-asyncio pytest-cov black ruff mypy
```

### 5. Install Pre-Commit Hooks (Optional)

```bash
# Configure git to use .githooks directory
git config core.hooksPath .githooks

# Verify hook is executable
ls -la .githooks/pre-commit
```

The pre-commit hook runs `make check` for any modified services.

### 6. Start Infrastructure

```bash
# Start MQTT broker and config-manager
cd ops
docker compose up -d mosquitto config-manager
cd ops
docker compose up -d mosquitto

# Verify broker is running
docker compose ps
mosquitto_sub -h localhost -t '#' -v  # Subscribe to all topics
```

## Project Architecture

### Event-Driven Design

TARS follows an **event-driven architecture** where all services communicate exclusively through MQTT:

```
[Mic] → STT → MQTT → Router → MQTT → LLM → MQTT → TTS → [Speaker]
             ↑         ↓                ↑         ↑
        Wake Word     Health      Memory/RAG   Status
```

**Key principles**:
- **Loose coupling**: Services never call each other directly
- **Typed contracts**: All messages use Pydantic models
- **Async-first**: All services use `asyncio` for concurrency
- **12-factor config**: All configuration via environment variables

### Service Organization

Services are organized in `/apps/` following a **standardized structure**:

```
apps/<service>/
├── Makefile          # Build automation (fmt, lint, test, check)
├── README.md         # Service documentation
├── pyproject.toml    # Python packaging
├── .env.example      # Configuration template
├── src/              # Source code (src layout)
│   └── <package>/
│       ├── __init__.py
│       ├── __main__.py
│       ├── config.py
│       └── service.py
└── tests/            # Test suite
    ├── conftest.py
    ├── unit/
    ├── integration/
    └── contract/
```

**Core services**:
- **router**: Central message orchestration
- **stt-worker**: Speech-to-text (Whisper)
- **llm-worker**: LLM integration (OpenAI, Anthropic, etc.)
- **tts-worker**: Text-to-speech (Piper)
- **memory-worker**: Vector memory & RAG
- **wake-activation**: Wake word detection

### Shared Packages

- **tars-core** (`packages/tars-core/`): Shared contracts, domain models, adapters

### MQTT Topics

All services communicate via MQTT topics. Key patterns:

- **Commands**: `<service>/<action>` (e.g., `tts/say`, `llm/request`)
- **Events**: `<service>/<event>` (e.g., `stt/final`, `wake/event`)
- **Health**: `system/health/<service>` (retained)

See individual service READMEs for complete topic documentation.

## Development Workflow

### Working on a Service

1. **Navigate to service directory**:
   ```bash
   cd apps/<service>
   ```

2. **Install service in editable mode**:
   ```bash
   pip install -e ".[dev]"
   ```

3. **Make changes** to source files in `src/<package>/`

4. **Run checks**:
   ```bash
   make check  # Runs fmt + lint + test
   ```

5. **Test locally**:
   ```bash
   # Using CLI entry point
   tars-<service>
   
   # Or using Python module
   python -m <package>
   ```

6. **Test with Docker**:
   ```bash
   cd ops
   docker compose build <service>
   docker compose up <service>
   ```

### Makefile Targets

All services have identical Makefile targets:

- `make fmt` - Format code (ruff + black)
- `make lint` - Lint and type-check (ruff + mypy)
- `make test` - Run tests with coverage
- `make check` - Run all checks (CI gate)
- `make build` - Build Python package
- `make clean` - Remove build artifacts
- `make install` - Install in editable mode
- `make install-dev` - Install with dev dependencies

### Git Workflow

1. **Create feature branch**:
   ```bash
   git checkout -b <feature-name>
   ```

2. **Make changes** following conventions

3. **Run checks**:
   ```bash
   cd apps/<service>
   make check
   ```

4. **Commit changes**:
   ```bash
   git add .
   git commit -m "feat(<service>): <description>"
   ```
   
   Use conventional commits: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`

5. **Push and create PR**:
   ```bash
   git push origin <feature-name>
   # Create PR on GitHub
   ```

## Testing

### Test Organization

Tests are organized by type:

- **Unit tests** (`tests/unit/`): Fast, isolated, no external dependencies
- **Integration tests** (`tests/integration/`): Cross-component, may need MQTT
- **Contract tests** (`tests/contract/`): MQTT message schema validation

### Running Tests

```bash
# All tests
pytest tests/

# Unit tests only (fast)
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Specific test file
pytest tests/unit/test_config.py

# With coverage
pytest tests/ --cov=src/<package> --cov-report=html
```

### Writing Tests

Use pytest fixtures from `tests/conftest.py`:

```python
def test_my_feature(mock_mqtt_client):
    # Use mock_mqtt_client fixture
    pass
```

Follow naming conventions:
- Test files: `test_*.py`
- Test functions: `test_*`
- Test classes: `Test*`

### Test Fixtures

Common fixtures (defined in `conftest.py`):
- `mock_mqtt_client`: Mock MQTT client
- `mock_publisher`: Mock MQTT publisher
- `mock_subscriber`: Mock MQTT subscriber
- `event_loop`: Async event loop

## Contributing

### Code Style

- **Line length**: 100 characters (enforced by black/ruff)
- **Type hints**: All public functions must be typed
- **Docstrings**: Google style (Args, Returns, Raises)
- **Imports**: Organized by ruff (stdlib, third-party, local)

### Constitution Compliance

All contributions must follow the **Constitution** (`.specify/memory/constitution.md`):

1. **Event-Driven Architecture**: No direct service-to-service calls
2. **Typed Contracts**: All MQTT messages use Pydantic models
3. **Async-First**: Use `asyncio`, never block event loop
4. **Test-First**: Write tests before implementation
5. **12-Factor Config**: All config via environment variables
6. **Observability**: Structured logging, health monitoring
7. **Simplicity**: Start simple, add complexity only when needed

### PR Checklist

Before submitting a PR:

- [ ] `make check` passes for all modified services
- [ ] Tests added/updated for new functionality
- [ ] README updated if MQTT topics or config changed
- [ ] .env.example updated if new variables added
- [ ] Docker build succeeds
- [ ] Constitution principles followed
- [ ] Commit messages follow conventional commits

### Review Process

1. **Automated checks**: CI runs `make check` for all services
2. **Code review**: Maintainer reviews code and tests
3. **Integration testing**: PR tested with full stack
4. **Merge**: Squash and merge to main

## Troubleshooting

### Virtual Environment Issues

**Problem**: ImportError or module not found

**Solution**:
```bash
# Ensure venv is activated
source /home/james/git/py-tars/.venv/bin/activate

# Reinstall service
cd apps/<service>
pip install -e ".[dev]"
```

### MQTT Connection Issues

**Problem**: Service can't connect to MQTT broker

**Solution**:
```bash
# Check broker is running
docker compose ps mosquitto

# Check broker logs
docker compose logs mosquitto

# Verify MQTT_URL in .env
echo $MQTT_URL

# Test connection manually
mosquitto_sub -h localhost -t '#' -v
```

### Docker Build Failures

**Problem**: Docker build fails

**Solution**:
```bash
# Check build context
cd ops
docker compose build <service> --no-cache

# Check Dockerfile
cat ../docker/app.Dockerfile  # or docker/specialized/<service>.Dockerfile

# Verify pyproject.toml is valid
cd ../apps/<service>
python -m build  # Should succeed locally
```

### Test Failures

**Problem**: Tests fail locally

**Solution**:
```bash
# Ensure dev dependencies installed
pip install -e ".[dev]"

# Run tests with verbose output
pytest tests/ -v

# Run single test for debugging
pytest tests/unit/test_foo.py::test_bar -v

# Check test fixtures
cat tests/conftest.py
```

### Type Checking Errors

**Problem**: mypy reports type errors

**Solution**:
```bash
# Install type stubs
pip install types-orjson types-setuptools

# Check mypy config
cat pyproject.toml  # Look for [tool.mypy]

# Run mypy with verbose output
mypy src/<package> --show-error-codes
```

### Performance Issues

**Problem**: Service is slow or blocking

**Solution**:
- Check for blocking calls in async code
- Use `asyncio.to_thread()` for CPU-bound work
- Monitor event loop with DEBUG logging
- Profile with `cProfile` or `py-spy`

## Resources

### Documentation

- **Constitution**: `.specify/memory/constitution.md` - Core principles
- **Copilot Instructions**: `.github/copilot-instructions.md` - Patterns and conventions
- **Spec 001**: `specs/001-standardize-app-structures/` - App structure standardization
- **Service READMEs**: Each service has comprehensive documentation

### External Links

- [Python 3.11 Docs](https://docs.python.org/3.11/)
- [MQTT Protocol](https://mqtt.org/)
- [Pydantic v2](https://docs.pydantic.dev/)
- [pytest Documentation](https://docs.pytest.org/)
- [Docker Compose](https://docs.docker.com/compose/)

### Community

- **Issues**: Report bugs or request features on GitHub
- **Discussions**: Ask questions on GitHub Discussions
- **PRs**: Submit contributions via pull requests

## Next Steps

1. **Pick a service** to work on (start with simpler ones like wake-activation)
2. **Read service README** to understand architecture
3. **Run service locally** with `tars-<service>`
4. **Make a small change** and run `make check`
5. **Test with full stack** using Docker Compose
6. **Submit PR** when ready

Welcome to the team! 🚀
