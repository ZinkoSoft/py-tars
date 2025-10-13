# Quickstart: Standardizing App Structures

**Feature**: Standardize App Folder Structures  
**Date**: 2025-10-13

## Overview

This guide provides step-by-step instructions for standardizing each app in `/apps/` to follow Python best practices and consistent structure.

## Prerequisites

- Python 3.11+
- Git
- Basic understanding of Python packaging
- Familiarity with Make and Makefiles

## Quick Reference

### Standard App Structure

```
apps/<app-name>/
├── Makefile                    # Build automation
├── README.md                   # Documentation
├── pyproject.toml             # Package configuration
├── .env.example               # Configuration template
├── src/
│   └── <package_name>/        # Source code
│       ├── __init__.py
│       ├── __main__.py
│       ├── config.py
│       └── service.py
└── tests/
    ├── conftest.py
    ├── unit/
    ├── integration/
    └── contract/
```

### Standard Makefile Targets

```bash
make fmt         # Format code
make lint        # Lint and type-check
make test        # Run tests
make check       # Run all checks (CI gate)
make build       # Build package
make clean       # Remove artifacts
make install     # Install in editable mode
make install-dev # Install with dev dependencies
```

## Migration Process

Follow these steps for each app:

### Phase 1: Analysis

1. **Document current structure**
   ```bash
   cd apps/<app-name>
   tree -L 2 > structure-before.txt
   ```

2. **Identify source files**
   - Main entry point (`main.py` or `__main__.py`)
   - Package directory (e.g., `llm_worker/`, `stt_worker/`)
   - Test directory (e.g., `tests/`)
   - Configuration files

3. **Review existing packaging**
   - Check if `pyproject.toml` exists
   - Review `requirements.txt` if present
   - Note any setup.py or setup.cfg files

### Phase 2: Create New Structure

1. **Create src/ directory**
   ```bash
   mkdir -p src/<package_name>
   ```

2. **Move source files**
   ```bash
   # If package directory exists at root
   mv <package_name>/* src/<package_name>/
   rmdir <package_name>
   
   # If main.py exists at root
   mkdir -p src/<package_name>
   mv main.py src/<package_name>/__main__.py
   ```

3. **Organize tests**
   ```bash
   # Create test structure
   mkdir -p tests/unit tests/integration tests/contract
   
   # Move existing tests
   # If tests are flat, categorize them:
   # - Fast, isolated tests → tests/unit/
   # - Tests requiring MQTT → tests/integration/
   # - Schema validation → tests/contract/
   ```

4. **Create conftest.py**
   ```bash
   touch tests/conftest.py
   ```

### Phase 3: Configuration Files

1. **Create/Update pyproject.toml**
   - Copy template from `contracts/pyproject.toml.template.md`
   - Update `name`, `description`, `packages`, `dependencies`
   - Example:
     ```toml
     [project]
     name = "tars-llm-worker"
     description = "LLM worker for TARS voice assistant"
     
     [tool.setuptools]
     package-dir = {"" = "src"}
     packages = ["llm_worker", "llm_worker.providers"]
     
     [project.scripts]
     tars-llm-worker = "llm_worker.__main__:main"
     ```

2. **Create Makefile**
   - Copy template from `contracts/Makefile.template.md`
   - Update `PACKAGE_NAME` variable
   - Example:
     ```makefile
     PACKAGE_NAME := llm_worker
     SRC_DIR := src/$(PACKAGE_NAME)
     TEST_DIR := tests
     ```

3. **Create/Update README.md**
   - Copy template from `contracts/README.template.md`
   - Fill in app-specific details
   - Document all MQTT topics
   - Document all environment variables

4. **Create .env.example**
   - List all environment variables
   - Provide example values
   - Add comments explaining each variable
   - Example:
     ```bash
     # MQTT Configuration
     MQTT_URL=mqtt://user:pass@localhost:1883
     
     # LLM Configuration
     LLM_PROVIDER=openai
     OPENAI_API_KEY=sk-...
     ```

### Phase 4: Testing

1. **Install in editable mode**
   ```bash
   pip install -e .
   ```

2. **Run tests**
   ```bash
   make test
   ```

3. **Verify CLI entry point**
   ```bash
   tars-<app-name> --help
   ```

4. **Run all checks**
   ```bash
   make check
   ```

5. **Test Docker build** (if applicable)
   ```bash
   docker compose build <service-name>
   ```

### Phase 5: Documentation

1. **Update README.md**
   - Verify all sections complete
   - Test all code examples
   - Document MQTT contracts

2. **Verify .env.example**
   - All variables documented
   - Example values provided

3. **Add inline documentation**
   - Docstrings for public functions
   - Comments explaining complex logic

### Phase 6: Cleanup

1. **Remove old files**
   ```bash
   # Remove old requirements.txt if dependencies moved to pyproject.toml
   # (Keep if still needed for Docker)
   
   # Remove old setup.py/setup.cfg if present
   rm setup.py setup.cfg
   
   # Remove old dist/ if present
   rm -rf dist/ *.egg-info/
   ```

2. **Run clean**
   ```bash
   make clean
   ```

3. **Document changes**
   ```bash
   tree -L 2 > structure-after.txt
   git diff structure-before.txt structure-after.txt
   ```

### Phase 7: Verification

1. **Functional testing**
   - Run app locally
   - Verify MQTT connectivity
   - Test with other services

2. **Integration testing**
   - Start full Docker stack
   - Verify app works in context

3. **Git check**
   ```bash
   git status
   git diff
   # Review changes before committing
   ```

## App-Specific Guides

### LLM Worker

**Current structure**: Has `llm_worker/` directory with providers subpackage

**Steps**:
1. Create `src/` directory
2. Move `llm_worker/` to `src/llm_worker/`
3. Update `pyproject.toml` packages:
   ```toml
   packages = ["llm_worker", "llm_worker.providers"]
   ```
4. Create Makefile with `PACKAGE_NAME := llm_worker`
5. Organize tests into unit/, integration/, contract/

### STT Worker

**Current structure**: Has `main.py` at root and `stt_worker/` directory

**Steps**:
1. Create `src/stt_worker/` directory
2. Move `stt_worker/*` to `src/stt_worker/`
3. Move `main.py` to `src/stt_worker/__main__.py`
4. Update `pyproject.toml` entry point
5. Create Makefile
6. Update README.md with MQTT topics

### Router

**Current structure**: Has `main.py` at root, no package directory

**Steps**:
1. Create `src/router/` directory
2. Move `main.py` to `src/router/__main__.py`
3. Extract components to separate modules:
   - `config.py` for configuration
   - `service.py` for routing logic
   - `models.py` for Pydantic models
4. Create `pyproject.toml`
5. Create Makefile
6. Create comprehensive README.md (Router is critical service)

### Camera Service

**Current structure**: Flat structure with multiple .py files, no packaging

**Steps**:
1. Create `src/camera_service/` directory
2. Move all .py files to `src/camera_service/`
3. Rename `main.py` to `__main__.py`
4. Create `__init__.py`
5. Create `pyproject.toml` from scratch
6. Create `requirements.txt` → move deps to pyproject.toml
7. Create Makefile
8. Create README.md
9. Create tests/ structure

## Common Issues and Solutions

### Issue: Import errors after moving to src/

**Solution**: Install package in editable mode
```bash
pip install -e .
```

### Issue: Tests can't find modules

**Solution**: Ensure `pyproject.toml` has correct package configuration:
```toml
[tool.setuptools]
package-dir = {"" = "src"}
packages = ["<package_name>"]
```

### Issue: Entry point doesn't work

**Solution**: Check `[project.scripts]` in `pyproject.toml`:
```toml
[project.scripts]
tars-<app-name> = "<package_name>.__main__:main"
```

Verify `__main__.py` has `main()` function.

### Issue: Docker build fails

**Solution**: Update Dockerfile to handle src/ layout:
```dockerfile
# Copy source code
COPY src/ /app/src/
COPY pyproject.toml /app/

# Install package
WORKDIR /app
RUN pip install -e .
```

### Issue: make commands fail

**Solution**: Install dev dependencies:
```bash
pip install -e ".[dev]"
```

### Issue: Mypy type errors

**Solution**: Add type stubs for third-party libraries:
```toml
[project.optional-dependencies]
dev = [
  "mypy>=1.10",
  "types-orjson>=3.6",
  "types-setuptools>=68",
]
```

## Validation Checklist

For each app, verify:

- [ ] Directory structure matches standard layout
- [ ] `src/<package_name>/` exists with source code
- [ ] `tests/` has unit/, integration/, contract/ subdirectories
- [ ] `Makefile` exists with all required targets
- [ ] `pyproject.toml` exists with complete configuration
- [ ] `README.md` exists with all required sections
- [ ] `.env.example` exists with all variables
- [ ] `pip install -e .` succeeds
- [ ] `make check` passes
- [ ] CLI entry point works (`tars-<app-name>`)
- [ ] Docker build succeeds (if applicable)
- [ ] Tests pass
- [ ] MQTT topics documented in README
- [ ] Environment variables documented

## Timeline

Estimated time per app:

- **Simple apps** (router, wake-activation): 30-60 minutes
- **Medium apps** (stt-worker, tts-worker, llm-worker): 1-2 hours
- **Complex apps** (memory-worker, camera-service): 2-3 hours

Total estimated time: 15-25 hours for all 13 apps

## Order of Migration

Recommended order (lowest to highest risk):

1. **wake-activation** - Small, isolated
2. **camera-service** - Needs most work, good practice
3. **ui** / **ui-web** - UI services, less critical
4. **movement-service** - Supporting service
5. **mcp-bridge** / **mcp-server** - MCP services
6. **memory-worker** - Complex but isolated
7. **tts-worker** - Audio output
8. **llm-worker** - LLM integration
9. **stt-worker** - Audio input
10. **router** - Central service (do last, most critical)

## Git Workflow

For each app:

```bash
# Create feature branch if not exists
git checkout 001-standardize-app-structures

# Make changes for one app
cd apps/<app-name>
# ... follow migration steps ...

# Stage changes
git add apps/<app-name>

# Commit with descriptive message
git commit -m "refactor(<app-name>): standardize app structure

- Add src/ layout
- Create Makefile with standard targets
- Update pyproject.toml with full configuration
- Organize tests into unit/integration/contract
- Document MQTT topics in README
- Add .env.example with all variables

Resolves #<issue-number>"

# Test in isolation
make check
docker compose build <service-name>

# Test with full stack
docker compose up
```

## Success Criteria

Migration complete when:

1. All 13 apps follow standard structure
2. All apps have Makefile with working targets
3. All apps have comprehensive README.md
4. All apps pass `make check`
5. All apps build successfully in Docker
6. Full stack runs without errors
7. Documentation updated

## Next Steps

After standardization:

1. **Update main README.md** with new structure conventions
2. **Update Copilot instructions** with templates
3. **Create pre-commit hooks** for quality checks
4. **Update CI/CD** to use `make check`
5. **Document patterns** for future apps

## Getting Help

If issues arise:

1. Review templates in `contracts/` directory
2. Check existing standardized apps for reference
3. Consult constitution (`.specify/memory/constitution.md`)
4. Review Copilot instructions (`.github/copilot-instructions.md`)
5. Ask for help with specific errors

## References

- [Python Packaging Guide](https://packaging.python.org/)
- [PEP 517](https://peps.python.org/pep-0517/) - Build System
- [PEP 518](https://peps.python.org/pep-0518/) - pyproject.toml
- [Setuptools Documentation](https://setuptools.pypa.io/)
- [pytest Documentation](https://docs.pytest.org/)
